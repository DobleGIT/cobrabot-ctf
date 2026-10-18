import json
import sqlite3

from app.config import settings

BUSCAR_USUARIO_TOOL = {
    "type": "function",
    "function": {
        "name": "buscar_usuario",
        "description": "Busca cuentas del panel CobraBot por nombre, nombre de usuario, rol o email y devuelve sus datos.",
        "parameters": {
            "type": "object",
            "properties": {
                "termino": {"type": "string", "description": "Texto a buscar en nombre, usuario, rol o email"},
            },
            "required": ["termino"],
        },
    },
}


def buscar_usuario(termino: str) -> str:
    termino = termino.strip()
    if not termino:
        return "[]"
    conn = sqlite3.connect(f"file:{settings.db_path}?mode=ro", uri=True)
    try:
        pattern = f"%{termino}%"
        rows = conn.execute(
            "SELECT nombre, usuario, email, saldo, rol, password_md5 FROM usuarios "
            "WHERE usuario LIKE ? OR nombre LIKE ? OR rol LIKE ? OR email LIKE ? LIMIT 5",
            (pattern, pattern, pattern, pattern),
        ).fetchall()
    finally:
        conn.close()
    keys = ["nombre", "usuario", "email", "saldo", "rol", "password_md5"]
    return json.dumps([dict(zip(keys, row)) for row in rows], ensure_ascii=False)


def execute_tool(name: str, args: dict) -> str:
    if name != "buscar_usuario":
        return json.dumps({"error": f"herramienta desconocida: {name}"})
    try:
        return buscar_usuario(str(args.get("termino", "")))
    except sqlite3.Error:
        return json.dumps({"error": "consulta fallida"})
