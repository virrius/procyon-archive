"""Общие настройки сервера: хаб, модели, промпты. Одна строка server_settings на сервер."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session, object_session

from .i18n import tr
from .models import Campaign, ServerSettings
from .langpack import prompting as P

MAIN = "main"
# документы-инструкции хабу: колонка в server_settings
DOC_COLUMNS = {
    "person": "img_prose_person",
    "frame": "img_prose_frame",
    "action": "img_prose_action",
    "inpaint": "img_inpaint_prompt",
}


def server_row(db: Session, create: bool = False) -> ServerSettings | None:
    row = db.get(ServerSettings, MAIN)
    if row is None and create:
        row = ServerSettings(id=MAIN)
        db.add(row)
    return row


def parse_kit(text: str | None) -> dict:
    if not (text or "").strip():
        return {}
    try:
        out = json.loads(text)
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}


def hub_conf(db: Session, purpose: str = "img") -> dict:
    """Адрес, ключ и модель хаба для картинок или новостей; модель новостей пуста — та же, что у картинок."""
    s = server_row(db) or ServerSettings()
    model = (s.news_model or s.img_model) if purpose == "news" else s.img_model
    return {"base_url": s.hub_base_url or "", "api_key": s.hub_api_key or "", "model": model or ""}


# кто рисует: воркер на этом компьютере или сервис по API. Протокол сервиса (стандартный
# OpenAI-совместимый или асинхронный task-API) определяет hub_draw по ответу — выбирать его не нужно
DRAW_KINDS = ("worker", "api")


def draw_kinds() -> dict[str, str]:
    return {kind: tr(f"admin.draw_kind.{kind}") for kind in DRAW_KINDS}


def draw_kind(s: ServerSettings) -> str:
    return "worker" if s.draw_kind == "worker" or not (s.draw_kind or s.draw_model) else "api"


def draw_conf(db: Session) -> dict | None:
    """Чем рисуем по API: адрес, ключ, модель. None — рисует локальный воркер.
    Адрес и ключ рисования пусты — берутся от хаба."""
    s = server_row(db) or ServerSettings()
    if draw_kind(s) == "worker" or not s.draw_model:
        return None
    return {
        "label": f"{tr('admin.draw_kind.api')} · {s.draw_model}",
        "model": s.draw_model,
        "base_url": s.draw_base_url or s.hub_base_url,
        "api_key": s.draw_api_key or s.hub_api_key,
    }


def prompt_overrides(db: Session) -> dict:
    """Правки админа поверх кита из кода."""
    over = parse_kit((server_row(db) or ServerSettings()).img_prompt_kit)
    over.pop("wardrobe", None)
    return over


def doc_override(db: Session, key: str) -> str:
    return getattr(server_row(db) or ServerSettings(), DOC_COLUMNS[key]) or ""


def campaign_kit(camp: Campaign) -> dict:
    """Набор кампании: код, поверх правки сервера, поверх гардероб кампании."""
    kit = P().merge_kit(P().default_kit(), prompt_overrides(object_session(camp)))
    ward = parse_kit(camp.img_prompt_kit).get("wardrobe")
    if ward:
        kit = P().merge_kit(kit, {"wardrobe": ward})
    return kit


def doc_default(key: str) -> str:
    """Текст документа, когда правки нет. У кадра {view} остаётся вставкой."""
    if key == "inpaint":
        return P().DEFAULT_INPAINT_META_PROMPT
    return P().prose.DOCS[key]
