import uuid
from collections import defaultdict


class SessionStore:
    """Historial de chat en memoria por sesión, recortado a los últimos N turnos.

    Un turno = un mensaje de usuario + una respuesta del asistente.
    """

    def __init__(self, max_turns: int = 8):
        self.max_turns = max_turns
        self._sessions: dict[str, list[dict]] = defaultdict(list)

    @staticmethod
    def new_session_id() -> str:
        return uuid.uuid4().hex

    def get_messages_for_model(self, session_id: str) -> list[dict]:
        return list(self._sessions[session_id][-(self.max_turns * 2):])

    def add_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        history = self._sessions[session_id]
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_message})
        max_messages = self.max_turns * 2
        if len(history) > max_messages:
            del history[: len(history) - max_messages]

    def reset(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
