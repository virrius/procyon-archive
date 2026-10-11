"""Язык экземпляра — один на сервер, выбирает админ в Admin space; хранится в server_settings.
Язык ответа — из Accept-Language запроса, без него — язык экземпляра.
Тексты — app/locales/<язык>/<раздел>.json, ключ в коде — «раздел.ключ»: tr("errors.campaign_missing")."""
from __future__ import annotations

import contextvars
import json
import time
from pathlib import Path

LANGS = ("ru", "en")
DEFAULT = "ru"

_lang: contextvars.ContextVar[str] = contextvars.ContextVar("lang", default=DEFAULT)
_catalog: dict[str, dict[str, str]] = {}


def _flat(prefix: str, node: dict, out: dict[str, str]) -> None:
    for key, value in node.items():
        full = f"{prefix}.{key}"
        if isinstance(value, dict):
            _flat(full, value, out)
        else:
            out[full] = str(value)


def _load() -> None:
    root = Path(__file__).parent / "locales"
    for lang in LANGS:
        table: dict[str, str] = {}
        for path in sorted((root / lang).glob("*.json")):
            _flat(path.stem, json.loads(path.read_text(encoding="utf-8")), table)
        _catalog[lang] = table


_load()


def pick(header: str | None) -> str:
    """Первый поддерживаемый язык из Accept-Language, без учёта весов: фронт шлёт один.
    Без заголовка — язык экземпляра."""
    for part in (header or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in LANGS:
            return code
    return instance_lang()


def current() -> str:
    return _lang.get()


def use(lang: str) -> contextvars.Token:
    return _lang.set(lang if lang in LANGS else DEFAULT)


def reset(token: contextvars.Token) -> None:
    _lang.reset(token)


# админ меняет язык редко, а читают его на каждый запрос: держим копию несколько секунд
_instance = {"lang": "", "at": 0.0}
_TTL = 5.0


def instance_lang() -> str:
    now = time.monotonic()
    if not _instance["lang"] or now - _instance["at"] > _TTL:
        _instance.update(lang=_read_instance_lang(), at=now)
    return _instance["lang"]


def set_instance_lang(lang: str) -> None:
    _instance.update(lang=lang if lang in LANGS else DEFAULT, at=time.monotonic())


def _read_instance_lang() -> str:
    from .db import SessionLocal
    from .models import ServerSettings
    try:
        with SessionLocal() as db:
            row = db.get(ServerSettings, "main")
            lang = row.lang if row else ""
    except Exception:
        lang = ""
    return lang if lang in LANGS else DEFAULT


def twin_lang(module_name: str) -> str:
    """Язык модуля-двойника (см. langpack): у английского в имени «__en»."""
    return "en" if "__en" in module_name else "ru"


def tr(key: str, lang: str | None = None, **kw) -> str:
    """Текст по ключу на языке запроса; нет перевода — русский, нет и его — сам ключ."""
    lang = lang or _lang.get()
    text = _catalog.get(lang, {}).get(key) or _catalog[DEFAULT].get(key) or key
    return text.format(**kw) if kw else text


def ctr(key: str, **kw) -> str:
    """Текст, который ляжет в базу или в генерацию, — на языке экземпляра, не читателя."""
    return tr(key, lang=instance_lang(), **kw)
