"""JWT hecho a mano (NO usar PyJWT: bloquearía alg:none y mataría el reto).

Formato estándar:  base64url(header).base64url(payload).base64url(firma)
Firma por defecto: HS256 con un secreto del servidor.

FALLO INTENCIONADO (la vulnerabilidad del reto):
    verify() acepta el token SIN comprobar la firma si el header dice
    {"alg":"none"}. Con "HS256" verifica correctamente. Cualquier otro alg se
    rechaza.
"""

import base64
import hashlib
import hmac
import json


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign_hs256(signing_input: str, secret: str) -> str:
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return _b64url_encode(sig)


def encode(payload: dict, secret: str) -> str:
    """Emite un JWT normal firmado con HS256."""
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}"
    return f"{signing_input}.{_sign_hs256(signing_input, secret)}"


def verify(token: str, secret: str) -> dict | None:
    """Valida un JWT y devuelve el payload, o None si no es válido.

    Aquí vive el bug: con alg:none se acepta el payload sin verificar nada.
    """
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception:
        return None

    alg = header.get("alg")

    # --- Fallo intencionado: alg:none se acepta sin comprobar la firma ---
    if alg == "none":
        return payload

    if alg == "HS256":
        expected = _sign_hs256(f"{header_b64}.{payload_b64}", secret)
        if hmac.compare_digest(expected, signature_b64):
            return payload
        return None

    # Cualquier otro algoritmo se rechaza.
    return None
