from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = REPO_ROOT / "projects"

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Make a name safe to use as a file/folder name, keeping it readable."""
    cleaned = _UNSAFE_CHARS.sub("-", name).strip().rstrip(".")
    return cleaned or "Untitled"
