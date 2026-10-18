import json
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.logger import log_event
from app.shop import db
from app.shop.store import ShopStore

router = APIRouter()
store = ShopStore()

COOKIE = settings.shop_session_cookie_name


# --------------------------------------------------------------------------- #
# Modelos de petición
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    usuario: str
    email: str = ""
    password: str


class LoginRequest(BaseModel):
    usuario: str
    password: str


class CartItemRequest(BaseModel):
    product_id: int
    qty: int = 1


class DiscountRequest(BaseModel):
    code: str


class CheckoutRequest(BaseModel):
    # OJO (reto): el porcentaje de descuento llega desde el cliente y el servidor
    # se fía de él. El carrito y los precios SÍ son de servidor; el único valor
    # que controla el atacante es `discount_percent`. Manipular la petición para
    # ponerlo a 100 (o más) deja el pedido a 0 € y revela la flag.
    discount_code: str = ""
    discount_percent: float = 0.0


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _ensure_session(request: Request, response: Response) -> str:
    session_id = request.cookies.get(COOKIE)
    if not session_id:
        session_id = ShopStore.new_session_id()
    response.set_cookie(COOKIE, session_id, httponly=True, samesite="lax")
    return session_id


def _require_user(request: Request) -> tuple[str, dict]:
    session_id = request.cookies.get(COOKIE)
    user = store.get_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para hacer esto.")
    return session_id, user


def _cart_view(session_id: str) -> dict:
    cart = store.get_cart(session_id)
    productos = db.get_products_by_id(settings.shop_db_path)
    items = []
    subtotal = 0.0
    for pid, qty in cart.items():
        prod = productos.get(pid)
        if not prod:
            continue
        linea = round(prod["precio"] * qty, 2)
        subtotal += linea
        items.append(
            {
                "product_id": pid,
                "nombre": prod["nombre"],
                "emoji": prod["emoji"],
                "precio": prod["precio"],
                "qty": qty,
                "linea": linea,
            }
        )
    items.sort(key=lambda i: i["product_id"])
    return {"items": items, "subtotal": round(subtotal, 2)}


# --------------------------------------------------------------------------- #
# Página
# --------------------------------------------------------------------------- #
@router.get("/home")
def shop_page():
    return FileResponse("static/shop.html")


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@router.post("/home/api/register")
def register(req: RegisterRequest, request: Request, response: Response):
    usuario = req.usuario.strip()
    password = req.password
    if not usuario or not password:
        raise HTTPException(status_code=400, detail="Usuario y contraseña son obligatorios.")
    if len(usuario) > 32 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Usuario o contraseña demasiado largos.")

    ok = db.create_user(settings.shop_db_path, usuario, req.email.strip(), password)
    if not ok:
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya existe.")

    user = db.verify_user(settings.shop_db_path, usuario, password)
    session_id = _ensure_session(request, response)
    store.login(session_id, user)
    log_event(settings.log_path, type="shop_register", ip=_client_ip(request), usuario=usuario)
    return {
        "ok": True,
        "user": {"usuario": user["usuario"], "email": user["email"]},
        "welcome_code": db.WELCOME_CODE,
        "welcome_percent": db.DISCOUNT_CODES.get(db.WELCOME_CODE, 0),
    }


@router.post("/home/api/login")
def login(req: LoginRequest, request: Request, response: Response):
    user = db.verify_user(settings.shop_db_path, req.usuario.strip(), req.password)
    ip = _client_ip(request)
    if not user:
        log_event(settings.log_path, type="shop_login", ip=ip, usuario=req.usuario, success=False)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    session_id = _ensure_session(request, response)
    store.login(session_id, user)
    log_event(settings.log_path, type="shop_login", ip=ip, usuario=user["usuario"], success=True)
    return {"ok": True, "user": {"usuario": user["usuario"], "email": user["email"]}}


@router.post("/home/api/logout")
def logout(request: Request):
    session_id = request.cookies.get(COOKIE)
    if session_id:
        store.logout(session_id)
    return {"ok": True}


@router.get("/home/api/me")
def me(request: Request):
    user = store.get_user(request.cookies.get(COOKIE))
    if not user:
        return {"user": None}
    return {"user": {"usuario": user["usuario"], "email": user["email"]}}


# --------------------------------------------------------------------------- #
# Catálogo y carrito
# --------------------------------------------------------------------------- #
@router.get("/home/api/products")
def products():
    return {"products": db.list_products(settings.shop_db_path)}


@router.get("/home/api/cart")
def get_cart(request: Request, response: Response):
    session_id = _ensure_session(request, response)
    return _cart_view(session_id)


@router.post("/home/api/cart/add")
def cart_add(req: CartItemRequest, request: Request, response: Response):
    session_id = _ensure_session(request, response)
    productos = db.get_products_by_id(settings.shop_db_path)
    if req.product_id not in productos:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")
    qty = max(1, min(req.qty, 99))
    store.add_to_cart(session_id, req.product_id, qty)
    return _cart_view(session_id)


@router.post("/home/api/cart/set")
def cart_set(req: CartItemRequest, request: Request, response: Response):
    session_id = _ensure_session(request, response)
    store.set_cart_item(session_id, req.product_id, max(0, min(req.qty, 99)))
    return _cart_view(session_id)


@router.post("/home/api/cart/clear")
def cart_clear(request: Request, response: Response):
    session_id = _ensure_session(request, response)
    store.clear_cart(session_id)
    return _cart_view(session_id)


# --------------------------------------------------------------------------- #
# Descuentos y checkout (aquí está la vulnerabilidad)
# --------------------------------------------------------------------------- #
@router.post("/home/api/discount")
def apply_discount(req: DiscountRequest):
    code = req.code.strip().upper()
    percent = db.DISCOUNT_CODES.get(code)
    if percent is None:
        return {"valid": False, "percent": 0, "code": code}
    return {"valid": True, "percent": percent, "code": code}


@router.post("/home/api/checkout")
def checkout(req: CheckoutRequest, request: Request, response: Response):
    session_id, user = _require_user(request)
    view = _cart_view(session_id)
    items = view["items"]
    if not items:
        raise HTTPException(status_code=400, detail="Tu carrito está vacío.")

    subtotal = view["subtotal"]

    # --- Punto vulnerable: se confía en el porcentaje que manda el cliente ---
    # En una tienda real el servidor miraría el código en su propia tabla y
    # aplicaría el porcentaje correspondiente. Aquí se usa tal cual lo envía el
    # navegador, sin comprobar que coincida con el código (ni limitarlo a 100).
    discount_percent = float(req.discount_percent or 0)
    total = round(subtotal * (1 - discount_percent / 100.0), 2)
    if total < 0:
        total = 0.0

    free = subtotal > 0 and total <= 0.0

    order_id = db.save_order(
        settings.shop_db_path,
        usuario_id=user["id"],
        items_json=json.dumps(items, ensure_ascii=False),
        subtotal=subtotal,
        descuento_pct=discount_percent,
        total=total,
        creado=time.time(),
    )

    store.clear_cart(session_id)

    log_event(
        settings.log_path,
        type="shop_checkout",
        ip=_client_ip(request),
        usuario=user["usuario"],
        order_id=order_id,
        subtotal=subtotal,
        discount_code=req.discount_code,
        discount_percent=discount_percent,
        total=total,
        free=free,
    )

    result = {
        "ok": True,
        "order_id": order_id,
        "subtotal": subtotal,
        "discount_percent": discount_percent,
        "total": total,
        "free": free,
    }
    if free:
        result["flag"] = settings.shop_flag
        result["message"] = "¡Servicios contratados sin coste! Algo no cuadra en la caja..."
    else:
        result["message"] = "¡Servicios contratados! Gracias por confiar en CobraBot."
    return result


# --------------------------------------------------------------------------- #
# Pedido gratis: permite que la web muestre la celebración aunque el checkout
# se haya hecho desde Burp/curl. Solo devuelve pedidos del propio usuario, así
# que no es un atajo: hay que haber explotado antes el checkout.
# --------------------------------------------------------------------------- #
@router.get("/home/api/orders/free")
def last_free_order(request: Request):
    _, user = _require_user(request)
    order = db.get_last_free_order(settings.shop_db_path, user["id"])
    if not order:
        return {"order": None}
    return {
        "order": {
            "order_id": order["id"],
            "items": json.loads(order["items_json"]),
            "subtotal": order["subtotal"],
            "discount_percent": order["descuento_pct"],
            "total": order["total"],
            "flag": settings.shop_flag,
            "message": "¡Servicios contratados sin coste! Algo no cuadra en la caja...",
        }
    }
