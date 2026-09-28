"""Versioned prompt files (backend/prompts/*.md) and the document delimiter.

Uploaded text is untrusted data (spec 11.1): it goes inside one <document>
block, and any tag in the text that could close or reopen that block is
neutralised, so injected text cannot step outside it."""

import re
from functools import lru_cache

from etheria.core.settings import BACKEND_DIR

PROMPTS_DIR = BACKEND_DIR / "prompts"
_TAG = re.compile(r"<\s*(/?)\s*document\s*>", re.IGNORECASE)


@lru_cache
def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def wrap_document(text: str) -> str:
    return "<document>\n" + _TAG.sub(r"[\1document]", text) + "\n</document>"
