"""Кириллица латиницей: ключи из названий и промпт рисующей модели, которая кириллицу не читает."""
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
    """Латиница, цифры и дефисы: ключ читается и в снимке, и в правке."""
    out: list[str] = []
    for ch in translit((text or "").strip().lower()):
        if ch.isascii() and ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:limit].strip("-") or fallback
