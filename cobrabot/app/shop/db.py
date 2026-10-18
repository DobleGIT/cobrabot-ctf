import hashlib
import secrets
import sqlite3
from pathlib import Path

# Catálogo de la tienda (CobraBot): servicios ficticios de "recobro" para el CTF.
# Todo es sátira para el reto, no hay ninguna funcionalidad real detrás. Puedes
# cambiar nombres/precios/categorías sin tocar nada más: la tabla se recrea en cada
# arranque desde esta lista.
# (nombre, descripcion, precio_eur, categoria, emoji)
PRODUCTS = [
    ("WhatsApp al Moroso", "Un mensaje directo y muy persuasivo al que te debe. Entrega inmediata.", 2.99, "Mensajería", "📲"),
    ("Bot Recordatorio WhatsApp", "Recordatorios automáticos cada hora hasta que haga el Bizum.", 9.99, "Automatización", "🤖"),
    ("Solicitud de Bizum Insistente", "Enviamos solicitudes de Bizum en bucle con asuntos creativos.", 4.99, "Pagos", "💸"),
    ("Llamada Automática", "Llamadas robotizadas recordando la deuda a cualquier hora.", 7.50, "Llamadas", "📞"),
    ("Publicación en Redes", "Anunciamos (con mucho estilo) que alguien te debe dinero.", 14.99, "Redes Sociales", "📣"),
    ("SMS Masivo de Cobro", "Tanda de SMS recordatorios imposibles de ignorar.", 3.49, "Mensajería", "📨"),
    ("Email de Cobro Formal", "Plantilla con tono muy legal. Suena a abogado aunque no lo sea.", 1.99, "Mensajería", "📧"),
    ("Reporte a Lista de Morosos", "Añadimos al deudor a 'la lista'. Difícil salir de ella.", 19.99, "Reputación", "📑"),
    ("Panel de Seguimiento", "Rastrea si ha leído tus mensajes y por dónde anda.", 5.99, "Automatización", "📊"),
    ("Visita del Cobrador", "Un cobrador muy educado pasa a dar un 'recordatorio amistoso'.", 49.99, "Premium", "🚪"),
]

# Códigos de descuento válidos (código -> porcentaje). El servidor NO los impone en
# el checkout (ahí está la vulnerabilidad): solo sirven para que el frontend muestre
# un porcentaje "legítimo". Ajusta libremente.
DISCOUNT_CODES = {
    "BIENVENIDA10": 10,
    "VERANO20": 20,
}

# Código que se regala a cada usuario nuevo justo al registrarse (debe existir en
# DISCOUNT_CODES). Es el que el jugador acaba manipulando en el checkout.
WELCOME_CODE = "BIENVENIDA10"


def init_shop_db(path: str) -> None:
    db_file = Path(path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.unlink(missing_ok=True)

    conn = sqlite3.connect(db_file)
    try:
        conn.executescript(
            """
            CREATE TABLE productos (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                precio REAL NOT NULL,
                categoria TEXT NOT NULL,
                emoji TEXT NOT NULL
            );
            CREATE TABLE usuarios (
                id INTEGER PRIMARY KEY,
                usuario TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE pedidos (
                id INTEGER PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                subtotal REAL NOT NULL,
                descuento_pct REAL NOT NULL,
                total REAL NOT NULL,
                creado REAL NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO productos (nombre, descripcion, precio, categoria, emoji) "
            "VALUES (?, ?, ?, ?, ?)",
            PRODUCTS,
        )
        conn.commit()
    finally:
        conn.close()


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def create_user(path: str, usuario: str, email: str, password: str) -> bool:
    """Crea un usuario. Devuelve False si el nombre de usuario ya existe."""
    salt = secrets.token_hex(8)
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO usuarios (usuario, email, salt, password_hash) VALUES (?, ?, ?, ?)",
            (usuario, email, salt, hash_password(password, salt)),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def verify_user(path: str, usuario: str, password: str) -> dict | None:
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    if hash_password(password, row["salt"]) != row["password_hash"]:
        return None
    return {"id": row["id"], "usuario": row["usuario"], "email": row["email"]}


def list_products(path: str) -> list[dict]:
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM productos ORDER BY id").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def get_products_by_id(path: str) -> dict[int, dict]:
    return {p["id"]: p for p in list_products(path)}


def save_order(
    path: str,
    usuario_id: int,
    items_json: str,
    subtotal: float,
    descuento_pct: float,
    total: float,
    creado: float,
) -> int:
    conn = connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO pedidos (usuario_id, items_json, subtotal, descuento_pct, total, creado) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (usuario_id, items_json, subtotal, descuento_pct, total, creado),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_last_free_order(path: str, usuario_id: int) -> dict | None:
    """Último pedido del usuario que salió gratis (subtotal > 0 y total 0)."""
    conn = connect(path)
    try:
        row = conn.execute(
            "SELECT id, items_json, subtotal, descuento_pct, total, creado FROM pedidos "
            "WHERE usuario_id = ? AND subtotal > 0 AND total <= 0 ORDER BY id DESC LIMIT 1",
            (usuario_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None
