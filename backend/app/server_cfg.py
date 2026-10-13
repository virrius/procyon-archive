"""Shared server settings: hub, models, prompts. One server_settings row per server."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session, object_session

from .i18n import tr
from .models import Campaign, ServerSettings
from .langpack import prompting as P

MAIN = "main"
# hub instruction documents: column in server_settings
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
    """Hub URL, key and model for images or news; an empty news model means the same one as for images."""
    s = server_row(db) or ServerSettings()
    model = (s.news_model or s.img_model) if purpose == "news" else s.img_model
    return {"base_url": s.hub_base_url or "", "api_key": s.hub_api_key or "", "model": model or ""}


# who draws: a worker on this machine or a service over the API. hub_draw detects the service protocol (standard
# OpenAI-compatible or the async task API) from its response — there is no need to choose it
DRAW_KINDS = ("worker", "api")


def draw_kinds() -> dict[str, str]:
    return {kind: tr(f"admin.draw_kind.{kind}") for kind in DRAW_KINDS}


def draw_kind(s: ServerSettings) -> str:
    return "worker" if s.draw_kind == "worker" or not (s.draw_kind or s.draw_model) else "api"


def draw_conf(db: Session) -> dict | None:
    """What draws over the API: URL, key, model. None means the local worker draws.
    Empty drawing URL and key fall back to the hub ones."""
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
    """Admin overrides on top of the kit from code."""
    over = parse_kit((server_row(db) or ServerSettings()).img_prompt_kit)
    over.pop("wardrobe", None)
    return over


def doc_override(db: Session, key: str) -> str:
    return getattr(server_row(db) or ServerSettings(), DOC_COLUMNS[key]) or ""


def campaign_kit(camp: Campaign) -> dict:
    """Campaign kit: code, then server overrides on top, then the campaign wardrobe on top."""
    kit = P().merge_kit(P().default_kit(), prompt_overrides(object_session(camp)))
    ward = parse_kit(camp.img_prompt_kit).get("wardrobe")
    if ward:
        kit = P().merge_kit(kit, {"wardrobe": ward})
    return kit


def doc_default(key: str) -> str:
    """Document text when there is no override. For the frame, {view} stays a placeholder."""
    if key == "inpaint":
        return P().DEFAULT_INPAINT_META_PROMPT
    return P().prose.DOCS[key]
