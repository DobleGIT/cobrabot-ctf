import base64
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.db import init_db
from app.llm import LLMClient, LLMError
from app.logger import log_event
from app.security import build_system_prompt, check_login, is_blocked, leaks_secret, load_blocked_phrases
from app.session_store import SessionStore
from app.shop.db import init_shop_db
from app.shop.routes import router as shop_router
from app.tools import BUSCAR_USUARIO_TOOL, execute_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cobrabot")

app = FastAPI(title="CobraBot CTF")
app.mount("/home/static", StaticFiles(directory="static"), name="reto4-static")
app.mount("/admin/static", StaticFiles(directory="static"), name="reto5-static")

store = SessionStore(settings.max_history_turns)
llm_client = LLMClient(settings.llm_base_url, settings.llm_api_key, settings.llm_model)

blocked_phrases = load_blocked_phrases(settings.blocked_phrases_path)
output_secrets = [settings.admin_hash_md5, base64.b64encode(settings.admin_hash_md5.encode()).decode()]
OUTPUT_BLOCKED_REPLY = "No puedo compartir esa información. ¿Tienes alguna pregunta sobre facturación o pagos?"
system_prompt = build_system_prompt(settings.system_prompt_path, settings.admin_user, settings.admin_hash_md5)
init_db(settings.db_path, settings.admin_user, settings.admin_hash_md5)
init_shop_db(settings.shop_db_path)

# Reto de la tienda (ZumoShop): rutas /shop y /shop/api/*
app.include_router(shop_router)


class LoginRequest(BaseModel):
    username: str
    password: str
    turnstile_token: str = ""


class ChatRequest(BaseModel):
    message: str


def get_client_ip(request: Request) -> str:
    # Caddy (reverse proxy) añade X-Forwarded-For con la IP real del cliente.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str) -> bool:
    if not token:
        return False
    try:
        resp = httpx.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": settings.turnstile_secret_key, "response": token},
            timeout=10,
        )
        return resp.json().get("success", False)
    except (httpx.HTTPError, ValueError):
        logger.exception("Error verificando el token de Turnstile")
        return False


@app.get("/admin")
def admin_login_page():
    html = Path("static/index.html").read_text(encoding="utf-8")
    if settings.turnstile_enabled:
        head = '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>'
        widget = f'<div class="cf-turnstile" data-sitekey="{settings.turnstile_site_key}" data-theme="dark"></div>'
    else:
        head = ""
        widget = ""
    html = html.replace("{{TURNSTILE_HEAD}}", head).replace("{{TURNSTILE_WIDGET}}", widget)
    return HTMLResponse(html)


@app.get("/admin/chat")
def admin_chat_page():
    return FileResponse("static/chat.html")


@app.post("/admin/api/login")
def login(req: LoginRequest, request: Request):
    ip = get_client_ip(request)

    if settings.turnstile_enabled and not verify_turnstile(req.turnstile_token):
        log_event(settings.log_path, type="login", ip=ip, username=req.username, success=False, captcha_failed=True)
        raise HTTPException(status_code=400, detail="La verificación anti-bot no se ha superado. Inténtalo de nuevo.")

    success = check_login(req.username, req.password, settings.admin_user, settings.admin_password)
    log_event(settings.log_path, type="login", ip=ip, username=req.username, success=success)

    if success:
        return {"success": True, "flag": settings.flag}
    return {"success": False}


@app.post("/admin/api/chat")
def chat(req: ChatRequest, request: Request, response: Response):
    ip = get_client_ip(request)

    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        session_id = SessionStore.new_session_id()
    response.set_cookie(settings.session_cookie_name, session_id, httponly=True, samesite="lax")

    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")
    if len(message) > settings.max_message_length:
        message = message[: settings.max_message_length]

    if settings.filter_enabled and is_blocked(message, blocked_phrases):
        reply = "Lo siento, no puedo ayudarte con eso. ¿Tienes alguna pregunta sobre facturación o pagos?"
        log_event(settings.log_path, type="chat", ip=ip, session_id=session_id, message=message, response=reply, blocked=True)
        return {"reply": reply}

    history = store.get_messages_for_model(session_id)
    messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": message}]

    try:
        reply, tool_trace = llm_client.chat_with_tools(messages, [BUSCAR_USUARIO_TOOL], execute_tool)
    except LLMError as exc:
        reply = str(exc)
        log_event(
            settings.log_path,
            type="chat",
            ip=ip,
            session_id=session_id,
            message=message,
            response=f"[error] {reply}",
            blocked=False,
        )
        return {"reply": reply}

    output_blocked = settings.output_filter_enabled and leaks_secret(reply, output_secrets)
    if output_blocked:
        reply = OUTPUT_BLOCKED_REPLY

    store.add_turn(session_id, message, reply)
    log_event(
        settings.log_path,
        type="chat",
        ip=ip,
        session_id=session_id,
        message=message,
        response=reply,
        blocked=False,
        output_blocked=output_blocked,
        tool_calls=tool_trace,
    )
    return {"reply": reply}


@app.post("/admin/api/chat/reset")
def reset_chat(request: Request):
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        store.reset(session_id)
    return {"ok": True}
