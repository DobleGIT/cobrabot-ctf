import hashlib
import os
import secrets
import sqlite3
import time
from collections import deque
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import jwt_util

# --- Config (desde entorno) ---
PREFIX = "/profile"
COOKIE = "reto6_session"
DB_PATH = os.getenv("DB_PATH", "data/reto6.db")
JWT_SECRET = os.getenv("JWT_SECRET", "cobrabot-super-secreto-hs256-no-lo-necesitan")
FLAG = os.getenv("FLAG", "CTF{placeholder}")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# --- App ---
app = FastAPI(title="CobraBot · Reto 6 (JWT)")
app.mount(f"{PREFIX}/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------------------------------------------------------------------- #
# Base de datos (usuarios). Se recrea al arrancar.
# --------------------------------------------------------------------------- #
def init_db():
    p = Path(DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE usuarios (id INTEGER PRIMARY KEY, usuario TEXT UNIQUE NOT NULL, "
        "email TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user')"
    )
    conn.commit()
    conn.close()


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _hash(pw: str, salt: str) -> str:
    return hashlib.sha256((salt + pw).encode()).hexdigest()


def create_user(usuario: str, email: str, pw: str) -> bool:
    salt = secrets.token_hex(8)
    try:
        c = _conn()
        c.execute(
            "INSERT INTO usuarios (usuario, email, salt, password_hash, role) VALUES (?,?,?,?, 'user')",
            (usuario, email, salt, _hash(pw, salt)),
        )
        c.commit()
        c.close()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(usuario: str, pw: str):
    c = _conn()
    row = c.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
    c.close()
    if row and _hash(pw, row["salt"]) == row["password_hash"]:
        return dict(row)
    return None


def get_user(usuario: str):
    c = _conn()
    row = c.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
    c.close()
    return dict(row) if row else None


def update_user(usuario: str, email=None, new_pw=None):
    c = _conn()
    if email is not None:
        c.execute("UPDATE usuarios SET email=? WHERE usuario=?", (email, usuario))
    if new_pw:
        salt = secrets.token_hex(8)
        c.execute("UPDATE usuarios SET salt=?, password_hash=? WHERE usuario=?", (salt, _hash(new_pw, salt), usuario))
    c.commit()
    c.close()


# --------------------------------------------------------------------------- #
# Rate limit suave por IP (red de seguridad, NO parte del reto).
# --------------------------------------------------------------------------- #
_RL_WINDOW = 5.0        # segundos
_RL_MAX = 500           # peticiones por ventana e IP (subido: toda la sala comparte IP tras Cloudflare)
_rl: dict[str, deque] = {}
_rl_lock = Lock()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    ip = client_ip(request)
    now = time.monotonic()
    with _rl_lock:
        dq = _rl.setdefault(ip, deque())
        while dq and now - dq[0] > _RL_WINDOW:
            dq.popleft()
        if len(dq) >= _RL_MAX:
            return JSONResponse({"error": "Demasiadas peticiones, espera un momento."}, status_code=429)
        dq.append(now)
    return await call_next(request)


# --------------------------------------------------------------------------- #
# Sesión: emite/lee el JWT de la cookie.
# --------------------------------------------------------------------------- #
def issue_token(user: dict) -> str:
    payload = {
        "sub": user["usuario"],
        "email": user["email"],
        "role": user["role"],   # 'user' para todos los registros normales
        "iat": int(time.time()),
    }
    return jwt_util.encode(payload, JWT_SECRET)


def current_payload(request: Request):
    tok = request.cookies.get(COOKIE)
    if not tok:
        return None
    return jwt_util.verify(tok, JWT_SECRET)


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #
class RegisterReq(BaseModel):
    usuario: str
    email: str = ""
    password: str


class LoginReq(BaseModel):
    usuario: str
    password: str


class ProfileReq(BaseModel):
    email: str | None = None
    password: str | None = None


# --------------------------------------------------------------------------- #
# Páginas
# --------------------------------------------------------------------------- #
@app.get(f"{PREFIX}")
@app.get(f"{PREFIX}/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get(f"{PREFIX}/cuenta")
def profile_page(request: Request):
    if not current_payload(request):
        return RedirectResponse(f"{PREFIX}/")
    return FileResponse(str(STATIC_DIR / "profile.html"))


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def _set_cookie(resp: Response, token: str):
    # Cookie SIN HttpOnly a propósito (deben poder leerla/editarla).
    resp.set_cookie(COOKIE, token, httponly=False, samesite="lax", path=PREFIX)


@app.post(f"{PREFIX}/api/register")
def register(req: RegisterReq):
    usuario = req.usuario.strip()
    if not usuario or not req.password:
        raise HTTPException(400, "Usuario y contraseña son obligatorios.")
    if len(usuario) > 32 or len(req.password) > 128:
        raise HTTPException(400, "Usuario o contraseña demasiado largos.")
    if not create_user(usuario, req.email.strip(), req.password):
        raise HTTPException(409, "Ese usuario ya existe.")
    user = get_user(usuario)
    resp = JSONResponse({"ok": True, "usuario": user["usuario"], "email": user["email"]})
    _set_cookie(resp, issue_token(user))
    return resp


@app.post(f"{PREFIX}/api/login")
def login(req: LoginReq):
    user = verify_user(req.usuario.strip(), req.password)
    if not user:
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    resp = JSONResponse({"ok": True, "usuario": user["usuario"], "email": user["email"]})
    _set_cookie(resp, issue_token(user))
    return resp


@app.post(f"{PREFIX}/api/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE, path=PREFIX)
    return resp


@app.get(f"{PREFIX}/api/me")
def me(request: Request):
    payload = current_payload(request)
    if not payload:
        raise HTTPException(401, "No autenticado.")
    # OJO: NO devolvemos el 'role' en claro. Que decodifiquen el JWT ellos.
    return {"usuario": payload.get("sub"), "email": payload.get("email")}


@app.patch(f"{PREFIX}/api/profile")
def edit_profile(req: ProfileReq, request: Request):
    payload = current_payload(request)
    if not payload:
        raise HTTPException(401, "No autenticado.")
    usuario = payload.get("sub")
    if not get_user(usuario):
        raise HTTPException(401, "Sesión no válida.")
    update_user(usuario, email=req.email, new_pw=req.password)
    user = get_user(usuario)
    resp = JSONResponse({"ok": True, "usuario": user["usuario"], "email": user["email"]})
    # Reemitimos el token con el email actualizado (sigue siendo role:user).
    _set_cookie(resp, issue_token(user))
    return resp


# --------------------------------------------------------------------------- #
# Acción SOLO ADMIN: exportar base de clientes (no destructiva) -> flag
# --------------------------------------------------------------------------- #
FAKE_CLIENTS = [
    {"id": 1, "nombre": "Distribuciones Omega S.L.", "deuda_eur": 1240.50, "estado": "moroso"},
    {"id": 2, "nombre": "Talleres Beta", "deuda_eur": 310.00, "estado": "al corriente"},
    {"id": 3, "nombre": "Cafetería La Esquina", "deuda_eur": 87.25, "estado": "moroso"},
    {"id": 4, "nombre": "Gimnasio Pulso", "deuda_eur": 2750.00, "estado": "en litigio"},
]


@app.post(f"{PREFIX}/admin/export")
def admin_export(request: Request):
    payload = current_payload(request)
    if not payload:
        return JSONResponse({"error": "No autenticado. Inicia sesión."}, status_code=401)
    if payload.get("role") != "admin":
        return JSONResponse(
            {"error": "Acceso denegado: se requiere rol 'admin'"}, status_code=403
        )
    return {
        "ok": True,
        "export": FAKE_CLIENTS,
        "generado": int(time.time()),
        "flag": FLAG,
    }


init_db()
