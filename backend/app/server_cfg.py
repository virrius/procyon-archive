"""Общие настройки сервера: хаб, модели, промпты.

Пока значения не перенесены из кампаний, пустое поле сервера берётся у кампании.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session, object_session

from .i18n import tr
from .models import Campaign, ServerSettings
from .langpack import prompting as P

MAIN = "main"
# документы-инструкции: колонка в server_settings и в campaigns
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


def _first_campaign(db: Session, test) -> Campaign | None:
    for camp in db.query(Campaign).order_by(Campaign.created_at).all():
        if test(camp):
            return camp
    return None


def _camp_value(db: Session, camp: Campaign | None, column: str) -> str:
    if camp is None:
        camp = _first_campaign(db, lambda x: bool(getattr(x, column, "") or ""))
    return (getattr(camp, column, "") or "") if camp else ""


def hub_conf(camp: Campaign, purpose: str = "img") -> dict:
    """Адрес, ключ и модель хаба для картинок или новостей."""
    s = server_row(object_session(camp)) or ServerSettings()
    img_model = s.img_model or camp.img_model or ""
    if purpose == "news":
        return {
            "base_url": s.hub_base_url or camp.news_base_url or camp.img_base_url or "",
            "api_key": s.hub_api_key or camp.news_api_key or camp.img_api_key or "",
            "model": s.news_model or camp.news_model or img_model,
        }
    return {
        "base_url": s.hub_base_url or camp.img_base_url or "",
        "api_key": s.hub_api_key or camp.img_api_key or "",
        "model": img_model,
    }


# кто рисует: воркер на этом компьютере или сервис по API. Протокол сервиса (стандартный
# OpenAI-совместимый или асинхронный task-API) определяет hub_draw по ответу — выбирать его не нужно.
# Прежние значения: openai — стандартный протокол, прочие непустые — асинхронный
DRAW_KINDS = ("worker", "api")


def draw_kinds() -> dict[str, str]:
    return {kind: tr(f"admin.draw_kind.{kind}") for kind in DRAW_KINDS}


def draw_kind(s: ServerSettings) -> str:
    return "worker" if s.draw_kind == "worker" or not (s.draw_kind or s.draw_model) else "api"


def draw_protocol(s: ServerSettings) -> str:
    """openai / async, если протокол задан явно; api — определить по ответу."""
    if s.draw_kind in ("openai", "async"):
        return s.draw_kind
    if s.draw_kind and s.draw_kind not in DRAW_KINDS:
        return "async"
    return "api"


def draw_conf(db: Session) -> dict | None:
    """Чем рисуем по API: вид, адрес, ключ, модель. None — рисует локальный воркер."""
    s = server_row(db) or ServerSettings()
    kind = draw_kind(s)
    if kind == "worker" or not s.draw_model:
        return None
    fb = hub_fallback(db)
    return {
        "kind": draw_protocol(s),
        "label": f"{tr(f'admin.draw_kind.{kind}')} · {s.draw_model}",
        "model": s.draw_model,
        "base_url": s.draw_base_url or s.hub_base_url or fb["base_url"],
        "api_key": s.draw_api_key or s.hub_api_key or fb["api_key"],
    }


def hub_fallback(db: Session) -> dict:
    """Чем пишет хаб, пока у сервера пусто: значения первой кампании, где они есть."""
    return {
        "base_url": _camp_value(db, None, "img_base_url"),
        "api_key": _camp_value(db, None, "img_api_key"),
        "img_model": _camp_value(db, None, "img_model"),
        "news_model": _camp_value(db, None, "news_model") or _camp_value(db, None, "img_model"),
    }


def _camp_prompt_kit(camp: Campaign | None) -> dict:
    over = parse_kit(camp.img_prompt_kit) if camp else {}
    over.pop("wardrobe", None)
    return over


def prompt_overrides(db: Session, camp: Campaign | None = None) -> dict:
    """Правки набора промптов без гардероба."""
    over = parse_kit((server_row(db) or ServerSettings()).img_prompt_kit)
    over.pop("wardrobe", None)
    if over:
        return over
    if camp is None:
        camp = _first_campaign(db, lambda x: bool(_camp_prompt_kit(x)))
    return _camp_prompt_kit(camp)


def doc_override(db: Session, key: str, camp: Campaign | None = None) -> str:
    column = DOC_COLUMNS[key]
    value = getattr(server_row(db) or ServerSettings(), column) or ""
    return value or _camp_value(db, camp, column)


def campaign_kit(camp: Campaign) -> dict:
    """Набор кампании: код, поверх общие правки, поверх гардероб кампании."""
    db = object_session(camp)
    kit = P().merge_kit(P().default_kit(), prompt_overrides(db, camp))
    ward = parse_kit(camp.img_prompt_kit).get("wardrobe")
    if ward:
        kit = P().merge_kit(kit, {"wardrobe": ward})
    return kit


def doc_default(kit: dict, key: str) -> str:
    """Текст документа, когда правки нет. У кадра {view} остаётся вставкой."""
    if key == "inpaint":
        return P().DEFAULT_INPAINT_META_PROMPT
    return P().prose.DOCS[key]
