"""Three languages. The instance one: one per server, chosen by the admin in Admin space (server_settings).
The response one: from the request's Accept-Language, without it the instance language. The campaign one:
the language of its content, set at creation; everything written into the campaign uses it — log rows,
dispatches, prompts. Texts live in app/locales/<lang>/<section>.json, the key in code is "section.key":
tr("errors.campaign_missing")."""
from __future__ import annotations

import contextvars
import json
import time
from pathlib import Path

LANGS = ("ru", "en")
DEFAULT = "en"

_lang: contextvars.ContextVar[str] = contextvars.ContextVar("lang", default=DEFAULT)
# language of the campaign the request or background work belongs to; empty means the instance language
_content: contextvars.ContextVar[str] = contextvars.ContextVar("content", default="")
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
    """First supported language from Accept-Language, ignoring weights: the frontend sends one.
    Without the header — the instance language."""
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


# the admin changes the language rarely, but it is read on every request: keep a copy for a few seconds
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


_campaign_langs: dict[str, str] = {}


def campaign_lang(campaign_id: str | None) -> str:
    """Language of the campaign's content. It never changes after creation, so it is cached for good;
    campaigns created before languages were chosen use the instance language."""
    if not campaign_id:
        return instance_lang()
    if campaign_id not in _campaign_langs:
        from .db import SessionLocal
        from .models import Campaign
        try:
            with SessionLocal() as db:
                row = db.get(Campaign, campaign_id)
        except Exception:
            row = None
        if row is None:
            return instance_lang()
        _campaign_langs[campaign_id] = row.lang or ""
    lang = _campaign_langs[campaign_id]
    return lang if lang in LANGS else instance_lang()


def use_campaign(campaign_id: str | None) -> contextvars.Token:
    return _content.set(campaign_lang(campaign_id) if campaign_id else "")


def reset_campaign(token: contextvars.Token) -> None:
    _content.reset(token)


def content_lang() -> str:
    return _content.get() or instance_lang()


def twin_lang(module_name: str) -> str:
    """Language of a twin module (see langpack): the English one has "__en" in its name."""
    return "en" if "__en" in module_name else "ru"


def tr(key: str, lang: str | None = None, **kw) -> str:
    """Text by key in the request language; no translation means English, and if that is missing too, the key."""
    lang = lang or _lang.get()
    text = _catalog.get(lang, {}).get(key) or _catalog[DEFAULT].get(key) or key
    return text.format(**kw) if kw else text


def ctr(key: str, **kw) -> str:
    """Text that goes into the database or into generation — in the campaign language, not the reader's."""
    return tr(key, lang=content_lang(), **kw)
