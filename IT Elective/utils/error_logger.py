from __future__ import annotations

from datetime import datetime
from pathlib import Path


LOG_FILE = Path(__file__).resolve().parent.parent / "error_log.txt"


def log_error(source: str, message: str) -> None:
    try:
        line = f"[{datetime.utcnow().isoformat()}Z] {source}: {message}\n"
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # Never raise from logger in this prototype.
        return

