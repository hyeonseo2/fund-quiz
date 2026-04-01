from __future__ import annotations

import re


def normalize_name(name: str) -> str:
    text = (name or "").strip().lower()
    text = text.replace(" ", "")
    text = re.sub(r"[()\[\]<>/\\]", "", text)
    text = re.sub(r"[\u3000\t\n\r]", "", text)
    text = text.replace("-", "")
    return text
