import uuid
from threading import Lock


class ShopStore:
    """Sesiones y carritos de la tienda, en memoria dentro del proceso uvicorn.

    Igual que el historial del chat, es estado efímero: no sobrevive a un
    reinicio y no funcionaría con varios procesos/réplicas. Suficiente para el
    tamaño del evento.

    - sessions: session_id -> datos del usuario logueado ({id, usuario, email}).
    - carts:    session_id -> {product_id(int): cantidad(int)}.
    """

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._carts: dict[str, dict[int, int]] = {}
        self._lock = Lock()

    @staticmethod
    def new_session_id() -> str:
        return uuid.uuid4().hex

    # --- sesión / login ---
    def login(self, session_id: str, user: dict) -> None:
        with self._lock:
            self._sessions[session_id] = user

    def logout(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._carts.pop(session_id, None)

    def get_user(self, session_id: str | None) -> dict | None:
        if not session_id:
            return None
        return self._sessions.get(session_id)

    # --- carrito ---
    def get_cart(self, session_id: str) -> dict[int, int]:
        return dict(self._carts.get(session_id, {}))

    def add_to_cart(self, session_id: str, product_id: int, qty: int) -> None:
        with self._lock:
            cart = self._carts.setdefault(session_id, {})
            cart[product_id] = cart.get(product_id, 0) + qty
            if cart[product_id] <= 0:
                cart.pop(product_id, None)

    def set_cart_item(self, session_id: str, product_id: int, qty: int) -> None:
        with self._lock:
            cart = self._carts.setdefault(session_id, {})
            if qty <= 0:
                cart.pop(product_id, None)
            else:
                cart[product_id] = qty

    def clear_cart(self, session_id: str) -> None:
        with self._lock:
            self._carts.pop(session_id, None)
