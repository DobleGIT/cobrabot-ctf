import json
import time
from pathlib import Path
from threading import Lock

_lock = Lock()


def log_event(path: str, **fields) -> None:
    event = {"timestamp": time.time(), **fields}
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False)
    with _lock:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
