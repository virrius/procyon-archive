"""Admin space: настройки сервера и кампании целиком. Только для is_admin."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from urllib.parse import unquote

import httpx

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..api_schema import Role, error_responses
from ..db import get_db
from ..deps import admin_only
from .. import transfer
from ..canon import retranslate
from ..i18n import LANGS, instance_lang, set_instance_lang, tr
from ..models import AuditLog, Campaign, CampaignMember, User
from ..langpack import prompting as P
from ..prompting import KIT_SECTIONS, NEWS_SECTIONS
from ..prompting.kit import prune_nulls, strip_defaults
from ..server_cfg import (
    DOC_COLUMNS,
    DRAW_KINDS,
    doc_default,
    draw_kinds,
    doc_override,
    draw_kind,
    hub_fallback,
    prompt_overrides,
    server_row,
)
from .images import key_out

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_only)],
                   responses=error_responses(401, 403, 404))

PROMPT_SECTIONS = tuple(s for s in KIT_SECTIONS if s != "wardrobe")

DrawKind = Literal["worker", "api"]


class KeyOut(BaseModel):
    api_key_set: bool = Field(description="Whether a key is stored; the key itself is never returned.")
    api_key_tail: str = Field(description="Last four characters of the stored key, for recognition.")


class HubFallbackOut(KeyOut):
    """Values taken from the first campaign that has them, used while the server fields are empty."""

    base_url: str
    img_model: str
    news_model: str


class HubOut(KeyOut):
    base_url: str = Field(description="OpenAI-compatible LLM hub (`/v1`): prompts and dispatches.")
    img_model: str = Field(description="Hub model that drafts image prompts.")
    news_model: str = Field(description="Hub model that writes dispatches and comments.")
    draw_kind: DrawKind = Field(description="`worker` — the local ComfyUI worker draws; `api` — an image API (OpenAI-compatible `images/*` or an asynchronous task API, detected from the response).")
    draw_model: str = Field(description="Image model name when `draw_kind` is `api` (e.g. `gpt-image-2`).")
    draw_base_url: str = Field(description="Image API address; empty → the hub address and key are used.")
    draw_api_key_set: bool
    draw_api_key_tail: str
    draw_kinds: dict[str, str] = Field(description="Allowed `draw_kind` values with labels in the request language.")
    fallback: HubFallbackOut


class LangOut(BaseModel):
    lang: Literal["ru", "en"]


class ModelsOut(BaseModel):
    models: list[str] = Field(description="Model ids the hub lists at `/models`.")


class PromptsOut(BaseModel):
    docs: dict[str, str] = Field(description="Effective instruction documents by key (`person`, `frame`, `action`, `inpaint`): the override or the default.")
    doc_defaults: dict[str, str] = Field(description="Built-in text per document key.")
    kit: dict = Field(description="Effective prompt kit: defaults merged with the stored overrides, by section.")
    defaults: dict = Field(description="Built-in prompt kit.")
    news_sections: list[str] = Field(description="Kit sections that belong to dispatches, not to drawing.")
    news_slots: dict = Field(description="Placeholders the code fills in news templates, with what each one means.")


class CampaignBriefOut(BaseModel):
    id: str
    name: str
    role: Role
    owner: bool = Field(description="This user created the campaign.")


class UserOut(BaseModel):
    id: str
    login: str
    display_name: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    campaigns: list[CampaignBriefOut]


class AdminCampaignOut(BaseModel):
    id: str
    name: str
    slug: str
    created_at: datetime
    gms: list[str] = Field(description="Display names of the GMs.")
    players: int = Field(description="Members other than GMs.")
    member: bool = Field(description="The calling admin is a member of this campaign.")


class TransferStateOut(BaseModel):
    """Progress of an export or import job. Jobs live in memory for a few hours; a restart loses them."""

    id: str
    kind: Literal["export", "import"]
    status: Literal["running", "done", "failed"]
    stage: str = Field(description="`upload`, `read`, `rows`, `files`, `canon`, `done` — what is being processed.")
    done: int = Field(description="Progress inside the stage (rows or bytes).")
    total: int
    error: str
    download: str = Field(description="Export only: suggested file name once `status` is `done`.")
    campaign_id: str = Field(description="Import: id of the created campaign once done; export: the source campaign.")
    name: str = Field(description="Campaign name (export) or upload file name (import).")


def _hub_out(db: Session) -> dict:
    s = server_row(db)
    fb = hub_fallback(db)
    return {
        "base_url": s.hub_base_url if s else "",
        "img_model": s.img_model if s else "",
        "news_model": s.news_model if s else "",
        "draw_kind": draw_kind(s) if s else "worker",
        "draw_model": s.draw_model if s else "",
        "draw_base_url": s.draw_base_url if s else "",
        **{f"draw_{k}": v for k, v in key_out(s.draw_api_key if s else "").items()},
        "draw_kinds": draw_kinds(),
        **key_out(s.hub_api_key if s else ""),
        "fallback": {
            "base_url": fb["base_url"], "img_model": fb["img_model"],
            "news_model": fb["news_model"], **key_out(fb["api_key"]),
        },
    }


@router.get("/hub", summary="Read LLM hub and drawing settings", response_model=HubOut)
def get_hub(db: Session = Depends(get_db)):
    """Admin only. Server-wide hub address, models and who draws. Keys come back only as
    `*_set` / `*_tail`."""
    return _hub_out(db)


class HubIn(BaseModel):
    """Only the keys sent are changed."""

    base_url: str | None = Field(None, description="OpenAI-compatible hub address (`https://host/v1`).", examples=["https://llm.example.com/v1"])
    img_model: str | None = Field(None, description="Hub model for image prompts.")
    news_model: str | None = Field(None, description="Hub model for dispatches and comments.")
    draw_kind: DrawKind | None = Field(None, description="`worker` or `api`.")
    draw_model: str | None = Field(None, description="Image model for `api` drawing.", examples=["gpt-image-2"])
    draw_base_url: str | None = Field(None, description="Image API address; empty string → use the hub address and key (also clears `draw_api_key`).")
    draw_api_key: str | None = Field(None, description="Image API key. Empty string is ignored — a key is only replaced, never cleared here.")
    api_key: str | None = Field(None, description="Hub key. Empty string is ignored — a key is only replaced, never cleared here.")


@router.patch("/hub", summary="Change hub and drawing settings", response_model=HubOut,
              responses=error_responses(400))
def patch_hub(body: HubIn, db: Session = Depends(get_db)):
    """Admin only. Partial update; returns the full settings. 400 on an unknown `draw_kind`."""
    s = server_row(db, create=True)
    if body.base_url is not None:
        s.hub_base_url = body.base_url.strip()
    if body.img_model is not None:
        s.img_model = body.img_model.strip()
    if body.news_model is not None:
        s.news_model = body.news_model.strip()
    if body.draw_kind is not None:
        if body.draw_kind not in DRAW_KINDS:
            raise HTTPException(400, tr("admin.bad_draw_kind"))
        s.draw_kind = body.draw_kind
    if body.draw_model is not None:
        s.draw_model = body.draw_model.strip()
    if body.draw_base_url is not None:
        s.draw_base_url = body.draw_base_url.strip()
        # свой ключ живёт только при своём адресе: без адреса рисование берёт ключ текста
        if not s.draw_base_url:
            s.draw_api_key = ""
    if body.draw_api_key and body.draw_api_key.strip():
        s.draw_api_key = body.draw_api_key.strip()
    # пустой ключ не стирает заданный: ключ только заменяют
    if body.api_key and body.api_key.strip():
        s.hub_api_key = body.api_key.strip()
    db.commit()
    return _hub_out(db)


class LangIn(BaseModel):
    lang: Literal["ru", "en"] = Field(description="Instance language: UI, rulebook canon, generated texts.")


@router.patch("/lang", summary="Switch the instance language", response_model=LangOut,
              responses=error_responses(400))
def patch_lang(body: LangIn, db: Session = Depends(get_db)):
    """Admin only. Changes the language of the whole instance. Rulebook canon in every campaign
    that the GM has not edited is re-translated; GM edits and player texts stay as they are."""
    if body.lang not in LANGS:
        raise HTTPException(400, tr("admin.bad_lang"))
    old = instance_lang()
    server_row(db, create=True).lang = body.lang
    if old != body.lang:
        for camp in db.query(Campaign).all():
            retranslate(db, camp.id, old, body.lang)
    db.commit()
    set_instance_lang(body.lang)
    return {"lang": body.lang}


class HubCheck(BaseModel):
    base_url: str | None = Field(None, description="Address to test; empty → the stored one.")
    api_key: str | None = Field(None, description="Key to test; empty → the stored one.")
    # draw — адрес и ключ рисования, пустые берутся от текста
    target: Literal["text", "draw"] = Field("text", description="Which stored settings to fall back on: the text hub or the drawing service.")


@router.post("/hub/check", summary="Test the hub connection", response_model=ModelsOut,
             responses=error_responses(400, 502))
def check_hub(body: HubCheck, db: Session = Depends(get_db)):
    """Admin only. Calls `GET /models` on the given (or stored) address with the given (or stored)
    key and returns the model ids. 400 without an address, 502 when the hub does not answer or
    answers with an error."""
    s = server_row(db)
    fb = hub_fallback(db)
    draw = body.target == "draw" and s
    base = ((body.base_url or "").strip() or (draw and s.draw_base_url)
            or (s.hub_base_url if s else "") or fb["base_url"])
    key = ((body.api_key or "").strip() or (draw and s.draw_api_key)
           or (s.hub_api_key if s else "") or fb["api_key"])
    if not base:
        raise HTTPException(400, tr("admin.no_address"))
    try:
        r = httpx.get(f"{base.rstrip('/')}/models",
                      headers={"Authorization": f"Bearer {key}"} if key else {}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, tr("admin.hub_status", status=exc.response.status_code, text=exc.response.text[:200])) from exc
    except Exception as exc:
        raise HTTPException(502, tr("admin.unreachable", exc=exc)) from exc
    rows = data.get("data", data) if isinstance(data, dict) else data
    ids = sorted({str(m.get("id")) for m in rows if isinstance(m, dict) and m.get("id")}) if isinstance(rows, list) else []
    return {"models": ids}


def _defaults() -> dict:
    out = P().default_kit()
    out.pop("wardrobe", None)
    return out


def _prompts_out(db: Session) -> dict:
    kit = P().merge_kit(_defaults(), prompt_overrides(db))
    base = _defaults()
    return {
        "docs": {k: doc_override(db, k) or doc_default(kit, k) for k in DOC_COLUMNS},
        "doc_defaults": {k: doc_default(kit, k) for k in DOC_COLUMNS},
        "kit": kit,
        "defaults": base,
        "news_sections": list(NEWS_SECTIONS),
        "news_slots": P().dispatch.NEWS_SLOTS,
    }


@router.get("/prompts", summary="Read prompt documents and kit", response_model=PromptsOut)
def get_prompts(db: Session = Depends(get_db)):
    """Admin only. The instructions the hub follows when drafting image prompts, dispatches and
    comments: documents (`docs`) and the sectioned kit, each with its built-in default."""
    return _prompts_out(db)


class PromptsIn(BaseModel):
    """Only what was edited: documents by key and kit sections."""

    docs: dict[str, str] = Field(default_factory=dict, description="Document texts by key (`person`, `frame`, `action`, `inpaint`). A text equal to the default is stored as no override.")
    kit: dict = Field(default_factory=dict, description="Kit sections to merge over the defaults (any of the sections in `GET /prompts` → `kit`, except `wardrobe`). `null` inside a section removes that entry.")


@router.patch("/prompts", summary="Edit prompt documents and kit", response_model=PromptsOut,
              responses=error_responses(400))
def patch_prompts(body: PromptsIn, db: Session = Depends(get_db)):
    """Admin only. Merges the sent documents and kit sections over what is stored and returns the
    effective state. 400 on an unknown document key or kit section, or on news templates that do
    not pass the template check."""
    unknown = (set(body.kit) - set(PROMPT_SECTIONS)) | (set(body.docs) - set(DOC_COLUMNS))
    if unknown:
        raise HTTPException(400, tr("admin.unknown_sections", names=', '.join(sorted(unknown))))
    over = prompt_overrides(db)
    if isinstance(body.kit.get("news_templates"), dict):
        merged = P().merge_kit(P().merge_kit(_defaults(), over), {"news_templates": body.kit["news_templates"]})
        errors = P().dispatch.check_templates(merged["news_templates"])
        if errors:
            raise HTTPException(400, tr("admin.bad_templates", errors="; ".join(errors)))
    docs = {k: doc_override(db, k) for k in DOC_COLUMNS}
    s = server_row(db, create=True)
    if body.kit:
        base = _defaults()
        over = strip_defaults(prune_nulls(P().merge_kit(over, body.kit, keep_nulls=True), base), base)
        s.img_prompt_kit = json.dumps(over, ensure_ascii=False) if over else ""
    kit = P().merge_kit(_defaults(), over)
    docs.update({k: v.strip() for k, v in body.docs.items()})
    for key, column in DOC_COLUMNS.items():
        text = docs[key]
        setattr(s, column, "" if text == doc_default(kit, key).strip() else text)
    db.commit()
    return _prompts_out(db)


@router.get("/campaigns", summary="List every campaign on the server", response_model=list[AdminCampaignOut])
def admin_list_campaigns(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Admin only. All campaigns, not just the admin's own, with their GMs and player count."""
    out = []
    for camp in db.query(Campaign).order_by(Campaign.created_at).all():
        members = db.query(CampaignMember).filter_by(campaign_id=camp.id).all()
        out.append({
            "id": camp.id,
            "name": camp.name,
            "slug": camp.slug,
            "created_at": camp.created_at,
            "gms": [m.display_name or m.user.display_name for m in members if m.role == "gm"],
            "players": sum(m.role != "gm" for m in members),
            "member": any(m.user_id == user.id for m in members),
        })
    return out


class UserAdminIn(BaseModel):
    is_admin: bool | None = Field(None, description="Grant or revoke server admin.")
    is_active: bool | None = Field(None, description="`false` blocks the account: its tokens stop working.")


class AccessIn(BaseModel):
    role: Role = Field(description="Role in the campaign: `gm`, `player` or `observer` (read-only).")


def _user_out(db: Session, u: User) -> dict:
    members = db.query(CampaignMember).filter_by(user_id=u.id).all()
    return {
        "id": u.id,
        "login": u.login,
        "display_name": u.display_name,
        "is_admin": u.is_admin,
        "is_active": u.is_active,
        "created_at": u.created_at,
        "campaigns": [
            {"id": m.campaign_id, "name": m.campaign.name, "role": m.role,
             "owner": m.campaign.owner_id == u.id}
            for m in members
        ],
    }


@router.get("/users", summary="List all accounts", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    """Admin only. Every account with its campaign memberships and roles."""
    return [_user_out(db, u) for u in db.query(User).order_by(User.created_at).all()]


@router.patch("/users/{user_id}", summary="Block, unblock or promote an account", response_model=UserOut,
              responses=error_responses(400))
def patch_user(user_id: str, body: UserAdminIn, me: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Admin only. Only the keys sent are changed; blocking writes an audit entry per campaign.
    400 when an admin tries to block or demote themselves."""
    u = _user(db, user_id)
    if (body.is_admin is False or body.is_active is False) and u.id == me.id:
        raise HTTPException(400, tr("admin.self_block"))
    if body.is_admin is not None:
        u.is_admin = body.is_admin
    if body.is_active is not None:
        u.is_active = body.is_active
        for m in db.query(CampaignMember).filter_by(user_id=u.id).all():
            db.add(AuditLog(campaign_id=m.campaign_id, user_id=me.id,
                            action="account_active" if body.is_active else "account_blocked", detail=u.login))
    db.commit()
    return _user_out(db, u)


def _user(db: Session, user_id: str) -> User:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, tr("admin.user_missing"))
    return u


@router.put("/users/{user_id}/campaigns/{campaign_id}", summary="Add a user to a campaign or change the role",
            response_model=UserOut, responses=error_responses(400))
def grant_access(user_id: str, campaign_id: str, body: AccessIn,
                 me: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Admin only. Idempotent: creates the membership or changes its role. The campaign owner
    always stays `gm` (400 otherwise). Audit entry `access_granted` / `role_changed`."""
    u, camp = _user(db, user_id), db.get(Campaign, _campaign(db, campaign_id))
    m = db.query(CampaignMember).filter_by(campaign_id=camp.id, user_id=u.id).first()
    if m and camp.owner_id == u.id and body.role != "gm":
        raise HTTPException(400, tr("admin.owner_stays_gm"))
    if m:
        m.role = body.role
        action = "role_changed"
    else:
        db.add(CampaignMember(campaign_id=camp.id, user_id=u.id, role=body.role, display_name=u.display_name))
        action = "access_granted"
    db.add(AuditLog(campaign_id=camp.id, user_id=me.id, action=action, detail=f"{u.login}: {body.role}"))
    db.commit()
    return _user_out(db, u)


@router.delete("/users/{user_id}/campaigns/{campaign_id}", summary="Remove a user from a campaign",
               response_model=UserOut, responses=error_responses(400))
def revoke_access(user_id: str, campaign_id: str, me: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Admin only. Deletes the membership (no error if there was none). The owner cannot be
    removed (400). Audit entry `access_revoked`."""
    u, camp = _user(db, user_id), db.get(Campaign, _campaign(db, campaign_id))
    if camp.owner_id == u.id:
        raise HTTPException(400, tr("campaigns.owner_revoke"))
    m = db.query(CampaignMember).filter_by(campaign_id=camp.id, user_id=u.id).first()
    if m:
        db.delete(m)
        db.add(AuditLog(campaign_id=camp.id, user_id=me.id, action="access_revoked", detail=u.login))
        db.commit()
    return _user_out(db, u)


def _campaign(db: Session, campaign_id: str) -> str:
    if not db.get(Campaign, campaign_id):
        raise HTTPException(404, tr("admin.campaign_missing"))
    return campaign_id


class ExportIn(BaseModel):
    files: bool = Field(True, description="`true` → zip with uploaded files; `false` → json with rows only.")


@router.post("/campaigns/{campaign_id}/export", summary="Start a campaign export", response_model=TransferStateOut)
def export_campaign(campaign_id: str, body: ExportIn, db: Session = Depends(get_db)):
    """Admin only. Starts a background job; poll `GET /transfers/{id}` until `status` is `done`,
    then download `GET /transfers/{id}/file`."""
    return transfer.job_out(transfer.start_export(_campaign(db, campaign_id), body.files))


@router.post(
    "/campaigns/import", summary="Import a campaign from an archive", response_model=TransferStateOut,
    openapi_extra={"requestBody": {"required": True, "content": {
        "application/zip": {"schema": {"type": "string", "format": "binary"}},
        "application/json": {"schema": {"type": "object"}},
    }}},
)
async def import_campaign(
    request: Request, me: User = Depends(admin_only),
    x_filename: str = Header("", alias="X-Filename", description="Name of the uploaded file (URL-encoded); the extension tells zip from json."),
):
    """Admin only. The request body is the archive itself — a zip from `/export` (with files) or its
    json — streamed as-is, not multipart. Starts a background job; poll `GET /transfers/{id}`:
    when `done`, `campaign_id` is the new campaign."""
    job = transfer.new_import(unquote(x_filename), me.id)
    with open(transfer.upload_path(job), "wb") as fh:
        async for chunk in request.stream():
            fh.write(chunk)
    transfer.start_import(job)
    return transfer.job_out(job)


def _transfer(job_id: str) -> dict:
    job = transfer.get(job_id)
    if not job:
        raise HTTPException(404, tr("admin.transfer_missing"))
    return job


@router.get("/transfers/{job_id}", summary="Poll an export or import job", response_model=TransferStateOut)
def transfer_state(job_id: str):
    """Admin only. 404 when the job is unknown — jobs are kept in memory for a few hours and do
    not survive a server restart."""
    return transfer.job_out(_transfer(job_id))


@router.get("/transfers/{job_id}/file", summary="Download a finished export", response_class=FileResponse,
            responses={200: {"content": {"application/zip": {}, "application/json": {}},
                             "description": "The archive, named as `download` in the job state."},
                       **error_responses(409)})
def transfer_file(job_id: str):
    """Admin only. 409 until the export job is `done`."""
    job = _transfer(job_id)
    if job["status"] != "done" or not job["file"]:
        raise HTTPException(409, tr("admin.transfer_not_ready"))
    return FileResponse(job["file"], filename=job["download"])
