"""Cyrillic to Latin: keys from names, and prompts for the drawing model, which can't read Cyrillic."""
from __future__ import annotations

_LOWER = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}
TABLE = str.maketrans({**_LOWER, **{k.upper(): v.capitalize() for k, v in _LOWER.items()}})


def translit(text: str) -> str:
    return (text or "").translate(TABLE)


def slugify(text: str, fallback: str, limit: int = 48) -> str:
    """Latin letters, digits and hyphens: the key reads well both in the snapshot and in edits."""
    out: list[str] = []
    for ch in translit((text or "").strip().lower()):
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:limit].strip("-") or fallback
