"""Тексты правил книги для бланков: в репозитории только структура, сами тексты — у владельца книги.

Файл <PA_BOOK_DIR>/<язык>.json той же формы {"PLAYBOOK_SHEETS": ..., "CHAR_SHEET": ...} заполняет
пустые строки бланков. Нет файла — бланки без текстов правил.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import settings


def _fill(pub, full):
    if pub == "" and isinstance(full, str):
        return full
    if isinstance(pub, dict) and isinstance(full, dict):
        return {k: _fill(v, full.get(k)) for k, v in pub.items()}
    if isinstance(pub, list) and isinstance(full, list):
        return [_fill(v, full[i]) if i < len(full) else v for i, v in enumerate(pub)]
    return pub


def with_text(lang: str, sheets: dict, char_sheet: dict) -> tuple[dict, dict]:
    path = Path(settings.book_dir) / f"{lang}.json"
    if not path.is_file():
        return sheets, char_sheet
    full = json.loads(path.read_text(encoding="utf-8"))
    return _fill(sheets, full.get("PLAYBOOK_SHEETS")), _fill(char_sheet, full.get("CHAR_SHEET"))
