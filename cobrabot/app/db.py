import hashlib
import secrets
import sqlite3
from pathlib import Path

FAKE_USERS = [
    ("Laura Martínez", "lmartinez", "laura.martinez@example.com", 1240.50),
    ("Carlos Ruiz", "cruiz", "carlos.ruiz@example.com", 310.00),
    ("Ana Gómez", "agomez", "ana.gomez@example.com", 87.25),
    ("Pablo Torres", "ptorres", "pablo.torres@example.com", 2750.00),
    ("María López", "mlopez", "maria.lopez@example.com", 0.00),
    ("Javier Díaz", "jdiaz", "javier.diaz@example.com", 455.75),
    ("Lucía Fernández", "lfernandez", "lucia.fernandez@example.com", 129.99),
    ("Sergio Navarro", "snavarro", "sergio.navarro@example.com", 980.00),
]


def init_db(path: str, admin_user: str, admin_hash: str) -> None:
    db_file = Path(path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_file.unlink(missing_ok=True)

    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            "CREATE TABLE usuarios ("
            "id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, usuario TEXT NOT NULL, "
            "email TEXT NOT NULL, saldo REAL NOT NULL, rol TEXT NOT NULL, password_md5 TEXT NOT NULL)"
        )
        rows = [("Cuenta de sistema", admin_user, "sistema@cobrabot.example", 0.0, "administrador", admin_hash)]
        for nombre, usuario, email, saldo in FAKE_USERS:
            password_md5 = hashlib.md5(secrets.token_urlsafe(16).encode()).hexdigest()
            rows.append((nombre, usuario, email, saldo, "cliente", password_md5))
        conn.executemany(
            "INSERT INTO usuarios (nombre, usuario, email, saldo, rol, password_md5) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
