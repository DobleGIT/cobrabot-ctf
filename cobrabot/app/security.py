import re
import unicodedata
from pathlib import Path


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def load_blocked_phrases(path: str) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    phrases = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        phrases.append(normalize(line))
    return phrases


def is_blocked(message: str, blocked_phrases: list[str]) -> bool:
    normalized = normalize(message)
    return any(phrase in normalized for phrase in blocked_phrases)


def leaks_secret(reply: str, secrets: list[str]) -> bool:
    haystack = re.sub(r"[^0-9a-z]", "", normalize(reply))
    return any(re.sub(r"[^0-9a-z]", "", normalize(s)) in haystack for s in secrets)


def check_login(username: str, password: str, admin_user: str, admin_password: str) -> bool:
    return username == admin_user and password == admin_password


def build_system_prompt(template_path: str, admin_user: str, admin_hash: str) -> str:
    template = Path(template_path).read_text(encoding="utf-8")
    return template.replace("{{ADMIN_USER}}", admin_user).replace("{{ADMIN_HASH}}", admin_hash)
