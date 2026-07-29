from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from tools._shared import ROOT, err

NOTES_DIR = ROOT / "notes"
MAX_CHARS = 50_000


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return (slug or "note")[:60]


def save_note(title: str = "", content: str = "", confirmed: bool = False) -> dict[str, Any]:
    """Write a digest to notes/<slug>.md. Sensitive: writes to disk only after confirmation."""
    if not confirmed:
        return {
            "tool": "save_note",
            "status": "needs_confirmation",
            "message": "Ask the user to confirm before writing the note to disk.",
            "would_write": f"notes/{_slugify(title)}.md",
        }
    try:
        if not title.strip():
            raise ValueError("title must not be empty")
        if not content.strip():
            raise ValueError("content must not be empty")
        if len(content) > MAX_CHARS:
            raise ValueError(f"content exceeds {MAX_CHARS} chars")

        # _slugify strips separators, so the name can never escape NOTES_DIR.
        path = NOTES_DIR / f"{_slugify(title)}.md"
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        saved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path.write_text(f"# {title}\n\n_Saved at {saved_at}_\n\n{content}\n", encoding="utf-8")

        return {
            "tool": "save_note",
            "status": "saved",
            "path": str(path.relative_to(ROOT)),
            "chars_written": len(content),
            "saved_at": saved_at,
        }
    except Exception as exc:
        return err("save_note", exc)
