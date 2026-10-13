from __future__ import annotations

import io
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageFilter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, object_session

from .. import history as journal
from ..api_schema import AUTH_ERRORS, Ok, error_responses
from ..config import settings
from ..db import SessionLocal, get_db
from ..deps import editor, gm_only, viewer
from ..i18n import campaign_lang, ctr, reset_campaign, tr, use_campaign
from ..models import Attachment, Campaign, Entity, ImageGenJob
from ..hub_draw import HubDrawError, NoEditing, brief, can_edit, draw, edit
from ..server_cfg import campaign_kit, doc_override, draw_conf, hub_conf, parse_kit, wardrobe_for
from ..langpack import prompting as P
from ..translit import slugify, translit
from ..visibility import Viewer, apply_scope, can_see, entity_editable
from .entities import get_visible_entity
from .files import ALLOWED, MAX_BYTES, drop_files

log = logging.getLogger("images")
router = APIRouter(prefix="/api/campaigns/{campaign_id}", responses=AUTH_ERRORS)
worker_router = APIRouter(prefix="/api/worker", tags=["images-worker"])

CANDIDATES_PER_JOB = 4
ACTIVE_STATUSES = ("pending", "claimed", "ready")

# a portrait candidate lives until picked and only the GM sees it; a campaign frame stays
# for good and is open to the table by default
CANDIDATE = "image_candidate"
OUTFIT = "outfit"
SCENE_FRAME = "scene_frame"
# service attachments of an inpaint job: the mask and a prepared copy of the source.
# They live exactly as long as the job and are never served outside
MASK = "image_mask"
SOURCE = "image_source"
JOB_TEMP = (MASK, SOURCE)

# heartbeat shelf life: three missed in a row at the worker's 10 s interval.
# The only evidence of a live worker is a fresh ping; no ping is
# treated as generation switched off, the reason is not distinguished
HEARTBEAT_TTL = 30
_worker_beat: dict = {}
# the job the hub is drawing right now: the stuck-job sweeper leaves it alone
_hub_job: dict = {}

# Exactly one worker holds a claimed job. If it dies (restart, OOM, closed
# console), no one returns the job: it hangs forever and the source image stays
# locked for good. So we pick up stuck jobs ourselves.
# grace — how long to wait after claim before trusting the ping: the first ping with job_id
# does not arrive instantly
CLAIM_GRACE = 90
# "ping is fresh, but the worker is busy with something else" is a weaker signal: several workers
# may be running, and their pings override each other. So on that signal we wait
# longer than the longest honest batch of 4 candidates
CLAIM_IDLE = 12 * 60
MAX_ATTEMPTS = 2
# how long a drawn but unpicked draft lives. A job in ready waits for a person,
# and without a time limit they pile up by the thousand: candidate files are dead weight, and the
# generation form shows last week's frame as fresh on open
DRAFT_TTL = 24 * 3600


def key_out(key: str | None) -> dict:
    """The hub key never leaves the server: only whether it is set and its last four characters."""
    key = key or ""
    return {"api_key_set": bool(key), "api_key_tail": key[-4:]}


def save_wardrobe(camp: Campaign, db: Session, key: str, item: dict | None) -> None:
    """Campaign wardrobe: {"wardrobe": {key: look}}; None means the look is removed."""
    ward = dict(parse_kit(camp.img_prompt_kit).get("wardrobe") or {})
    if item is None:
        ward.pop(key, None)
    else:
        ward[key] = item
    camp.img_prompt_kit = json.dumps({"wardrobe": ward}, ensure_ascii=False) if ward else ""
    db.commit()


def outfit_key(title: str, taken: set[str]) -> str:
    """Look key from the title: it ends up in the card form snapshot, so it
    stays in Latin letters and survives renaming."""
    slug = slugify(title, "outfit", 40)
    key, n = slug, 2
    while key in taken:
        key, n = f"{slug}-{n}", n + 1
    return key


def wardrobe_out(camp: Campaign, gm: bool) -> dict:
    ward = wardrobe_for(camp, gm)
    return {"wardrobe": [{"key": k, **v} for k, v in ward.items()]}


class OutfitIn(BaseModel):
    """An outfit of the campaign wardrobe: a name plus the clothing a prompt draft produced."""

    title: str = Field(max_length=200, description="Outfit name; the key is derived from it (Latin slug) and never changes.")
    wear: list[str] = Field(default=[], description="Clothing phrases, as returned in `slots.wear` of a prompt draft. At least one.")
    image: str = Field(default="", description="URL of a candidate frame used as the outfit thumbnail (`/api/campaigns/{id}/files/{attachment_id}`).")
    visibility: Literal["crew", "gm"] = Field(default="crew", description="`crew`: every player can use the look in the workshop; `gm`: the GM only. Players always create `crew` looks.")


class OutfitOut(BaseModel):
    key: str = Field(description="Outfit key, used as `wardrobe` in prompt drafts.")
    title: str = ""
    wear: list[str] = []
    image: str = ""
    visibility: str = "crew"


class WardrobeOut(BaseModel):
    wardrobe: list[OutfitOut]


class OutfitCreatedOut(WardrobeOut):
    key: str = Field(description="Key of the outfit just created.")


@router.get("/wardrobe", tags=["workshop"], summary="List the campaign wardrobe", response_model=WardrobeOut)
def get_wardrobe(v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Outfits a prompt draft can wear (`wardrobe` field of `POST /image-prompt`). Any editor may read;
    players get only `crew` looks."""
    return wardrobe_out(db.get(Campaign, v.campaign_id), v.is_gm)


def clean_outfit(body: OutfitIn) -> dict:
    title = body.title.strip()
    if not title:
        raise HTTPException(400, tr("images.outfit_no_title"))
    wear = [x.strip() for x in body.wear if x.strip()]
    if not wear:
        raise HTTPException(400, tr("images.outfit_empty"))
    return {"title": title, "wear": wear, "image": body.image.strip(), "visibility": body.visibility}


def keep_outfit_image(db: Session, campaign_id: str, key: str, url: str) -> None:
    """A candidate frame that became a look's thumbnail leaves the drafts — otherwise the cleanup deletes it."""
    a = db.get(Attachment, url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]) if url else None
    if a and a.campaign_id == campaign_id and a.target_type == CANDIDATE:
        a.target_type, a.target_id = OUTFIT, key


@router.post("/wardrobe", tags=["workshop"], summary="Add an outfit to the wardrobe",
             response_model=OutfitCreatedOut, responses=error_responses(400))
def create_outfit(body: OutfitIn, v: Viewer = Depends(editor),
                  db: Session = Depends(get_db)):
    """Store an outfit; its `key` is a slug of the title. 400 when the title or `wear` is empty."""
    item = clean_outfit(body)
    if not v.is_gm:
        item["visibility"] = "crew"
    camp = db.get(Campaign, v.campaign_id)
    ward = campaign_kit(camp).get("wardrobe") or {}
    key = outfit_key(item["title"], set(ward))
    keep_outfit_image(db, camp.id, key, item["image"])
    save_wardrobe(camp, db, key, item)
    return {"key": key, **wardrobe_out(camp, v.is_gm)}


@router.put("/wardrobe/{key}", tags=["workshop"], summary="Replace an outfit",
            response_model=WardrobeOut, responses=error_responses(400))
def update_outfit(key: str, body: OutfitIn, v: Viewer = Depends(gm_only),
                  db: Session = Depends(get_db)):
    """GM only. Replaces the outfit under `key` entirely; the key stays. 404 for an unknown key."""
    camp = db.get(Campaign, v.campaign_id)
    if key not in (campaign_kit(camp).get("wardrobe") or {}):
        raise HTTPException(404, tr("images.outfit_missing"))
    item = clean_outfit(body)
    keep_outfit_image(db, camp.id, key, item["image"])
    save_wardrobe(camp, db, key, item)
    return wardrobe_out(camp, v.is_gm)


@router.delete("/wardrobe/{key}", tags=["workshop"], summary="Remove an outfit", response_model=WardrobeOut)
def delete_outfit(key: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Removes the outfit and its thumbnail file. 404 for an unknown key."""
    camp = db.get(Campaign, v.campaign_id)
    if key not in (campaign_kit(camp).get("wardrobe") or {}):
        raise HTTPException(404, tr("images.outfit_missing"))
    for a in db.query(Attachment).filter_by(campaign_id=camp.id, target_type=OUTFIT, target_id=key):
        drop_files(a)
        db.delete(a)
    save_wardrobe(camp, db, key, None)
    return wardrobe_out(camp, v.is_gm)


PromptKind = Literal["person", "frame", "action"]
FrameView = Literal["ship", "handheld", "structure", "planet", "landscape", "interior"]


class PromptDraftIn(BaseModel):
    """A free description (any language) plus the GM's choices: direction, frame subtype, register."""

    text: str = Field(description="What to draw, in any language — the hub turns it into the prompt.",
                      examples=["A weathered xenos smuggler with a scarred cheek, bronze collar ring"])
    kind: PromptKind = Field(default="person", description="`person` — a portrait; `frame` — a scene; `action` — a scene with people doing something.")
    register: str = Field(default="", description="Setting register key from `GET /registers`; empty = none.")
    view: FrameView = Field(default="interior", description="Frame subtype (frames only).")
    wardrobe: str = Field(default="", description="Outfit key from `GET /wardrobe`; its clothes overwrite the drafted ones.")
    who: Literal["", "human", "xenos"] = Field(default="", description="Portrait: force the species; empty lets the hub decide.")
    sex: Literal["", "male", "female"] = Field(default="", description="Portrait: force the sex; empty lets the hub decide.")
    people: Literal["", "none", "some"] = Field(default="", description="Frame: `none` — nobody in shot, `some` — people present, empty — whatever fits.")
    seed_key: str = Field(default="", description="Entity id: keeps a xenos character tied to one animal kin across drafts.")
    candidates: int = Field(default=4, ge=1, le=4, description="How many candidates the job will draw (4 for portraits, 1 for frames): the hub writes one take per candidate.")


class PromptDraftOut(BaseModel):
    slots: dict = Field(description="Parts of the picture as the hub wrote them; edit and send to `/image-prompt/rebuild`.")
    wardrobe: str = ""
    prompt: str = Field(description="The prompt for the drawing model. Send it verbatim as `prompt` of an image job.")
    prompts: list[str] = Field(description="One prompt per take (the job draws them as its candidates when `params.slots` is passed).")
    view: str | None = Field(default=None, description="Frame subtype; null for portraits.")
    register: str = ""




def hub_call(camp: Campaign, system: str, text: str, schema: dict,
             temperature: float = 0.3, max_tokens: int = 900,
             model: str = "", timeout: float = 120,
             stop: list[str] | None = None, attempts: int = 1, base_url: str = "", api_key: str = "",
             where: str = "") -> dict:
    """Call to the LLM hub with structured output. Returns the parsed answer; broken JSON means a retry.
    Address, model and key are the image hub's unless the call brings its own; where — where the GM finds them."""
    hub = hub_conf(object_session(camp))
    base_url = base_url or hub["base_url"]
    model = model or hub["model"]
    api_key = api_key or hub["api_key"]
    unset = [tr(f"images.hub_unset.{name}") for name, value in
             (("address", base_url), ("model", model), ("key", api_key)) if not value]
    if unset:
        raise HTTPException(400, tr("images.hub_unset.message", where=where or tr("images.hub_unset.where"),
                                    names=", ".join(unset)))
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        # frame slots need a default of 0.3: below 0.5 the output is noticeably more stable, half
        # of the defects were not an instruction error but run-to-run variance
        "temperature": temperature,
        # a reasoning model does not fit here: it eats thousands of tokens before
        # it starts answering and returns empty content
        "max_tokens": max_tokens,
        "response_format": schema,
    }
    if stop:
        body["stop"] = stop
    for attempt in range(attempts):
        try:
            r = httpx.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=timeout,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            log.warning("hub: %s", exc)
            raise HTTPException(502, tr("images.hub_no_answer", exc=brief(exc))) from exc
        try:
            return json.loads(content or "")
        except ValueError as exc:
            if attempt + 1 == attempts:
                raise HTTPException(502, tr("images.hub_bad_json", exc=exc)) from exc
    raise HTTPException(502, tr("images.hub_silent"))


def dress(slots: dict, wear: list[str]) -> dict:
    """A look goes into the clothing part word for word — both in the first draft and when the look changes."""
    return {**slots, "wear": wear, "outfit": "They wear " + "; ".join(wear) + "."}


def draft_slots(camp: Campaign, kind: str, register: str, text: str,
                view: str = "interior", wardrobe: str = "", who: str = "", sex: str = "",
                people: str = "", seed_key: str = "", takes: int = CANDIDATES_PER_JOB) -> dict:
    """Prompt for the drawing model: the hub writes the parts of what is visible, code joins them and adds the style,
    the frame and the anchor."""
    kit = campaign_kit(camp)
    doc = doc_override(object_session(camp), kind) or P().prose.DOCS[kind]
    wear = P().kit.outfit_slots(kit, wardrobe).get("wear") if kind == "person" and wardrobe else None
    xeno = {"person": lambda: P().prose.cast_rule(who, sex, seed_key, text),
            "action": lambda: P().prose.xeno_seed()}.get(kind, lambda: "")()
    people = people if kind != "person" else ""
    system = P().prose.system_prompt(doc, kit, kind, register, view, {"wear": wear} if wear else None, xeno,
                                     people, takes)
    schema = P().prose.schema(kind, view, kit, register, people, takes, wear=not wear)
    parsed = P().prose.fold_time(hub_call(camp, system, text, schema, max_tokens=3000))
    if wear:
        parsed = dress(parsed, wear)
    # the hub may have invented arms in the paragraph: code adds shoulder anatomy only on the GM's word
    parsed["four_arms"] = P().prose.gm_four_arms(text)
    if people == "none":
        parsed["people"] = "none"
    return {
        # slots go out: the paragraph and anchor are reassembled into a line by code, the clothing is for the wardrobe
        "slots": parsed,
        "wardrobe": wardrobe,
        "prompt": P().prose.build(kind, parsed, view, kit, register),
        "prompts": P().prose.prompts(kind, parsed, view, kit, register),
        "view": view if kind == "frame" else None,
        "register": register,
    }


def draft_inpaint_prompt(camp: Campaign, system: str, text: str) -> dict:
    parsed = hub_call(camp, system, text, P().INPAINT_PROMPT_SCHEMA)
    return {"prompt": translit(str(parsed.get("prompt", "")).strip())}


def check_draft_choices(kind: str, view: str, register: str, kit: dict) -> None:
    """Check the GM's choices. Registers come from the kit: ones added by the admin are as valid as those in code."""
    if kind not in P().KINDS:
        raise HTTPException(400, tr("images.bad_kind", options=', '.join(P().KINDS)))
    if view not in P().VIEWS:
        raise HTTPException(400, tr("images.bad_view", options=', '.join(P().VIEWS)))
    # an empty register is a valid choice: the vocabulary of a corner of the setting is added only
    # when the GM named that corner
    regs = P().prose.live_registers(kit)
    if register and register not in regs:
        raise HTTPException(400, tr("images.bad_register", options=', '.join(regs)))


class RegisterOut(BaseModel):
    key: str
    title: str
    hint: str


class RegistersOut(BaseModel):
    registers: list[RegisterOut]


@router.get("/registers", tags=["workshop"], summary="List setting registers", response_model=RegistersOut)
def get_registers(v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Registers (angles of the setting) a prompt draft may take: built-in ones plus those added in Admin space."""
    kit = campaign_kit(db.get(Campaign, v.campaign_id))
    return {"registers": [{"key": k, "title": str(r.get("title") or k), "hint": str(r.get("hint") or "")}
                          for k, r in P().prose.live_registers(kit).items()]}


@router.post("/image-prompt", tags=["images"], summary="Draft an image prompt through the hub",
             response_model=PromptDraftOut, responses=error_responses(400, 502))
def create_image_prompt(
    body: PromptDraftIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Turn a free description (any language) into the prompt for the drawing model via the LLM hub.
    Always draft here and pass `prompt` to the job verbatim: jobs accept Latin script only (400 otherwise)
    and the hub applies rules a hand-written prompt loses. 400 — empty text or bad kind/view/register,
    or the hub is not configured; 502 — the hub failed."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, tr("images.describe"))
    body.register = P().norm_register(body.register)
    camp = db.get(Campaign, v.campaign_id)
    check_draft_choices(body.kind, body.view, body.register, campaign_kit(camp))
    if body.wardrobe not in wardrobe_for(camp, v.is_gm):
        body.wardrobe = ""
    return draft_slots(camp, body.kind, body.register, text, body.view, body.wardrobe,
                       body.who, body.sex, body.people, body.seed_key, body.candidates)


class PromptRebuildIn(BaseModel):
    """Edited `slots` of a draft plus the same choices: rebuild the prompt string without the hub."""

    slots: dict = Field(description="`slots` from a draft, edited.")
    kind: PromptKind = "person"
    register: str = ""
    view: FrameView = "interior"
    wardrobe: str = Field(default="", description="Outfit key to dress the slots in.")


@router.post("/image-prompt/rebuild", tags=["images"], summary="Rebuild a prompt from edited slots",
             response_model=PromptDraftOut, responses=error_responses(400, 409, 502))
def rebuild_image_prompt(
    body: PromptRebuildIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Reassemble the prompt from edited `slots` in code — instant, no hub call. 400 — the slots have
    no `takes`."""
    body.register = P().norm_register(body.register)
    camp = db.get(Campaign, v.campaign_id)
    kit = campaign_kit(camp)
    check_draft_choices(body.kind, body.view, body.register, kit)
    if not isinstance(body.slots.get("takes"), list):
        raise HTTPException(400, tr("images.no_takes"))
    if body.wardrobe not in wardrobe_for(camp, v.is_gm):
        body.wardrobe = ""
    wear = P().kit.outfit_slots(kit, body.wardrobe).get("wear") if body.kind == "person" and body.wardrobe else None
    if wear:
        body.slots = dress(body.slots, wear)
    return {
        "slots": body.slots,
        "wardrobe": body.wardrobe,
        "prompt": P().prose.build(body.kind, body.slots, body.view, kit, body.register),
        "prompts": P().prose.prompts(body.kind, body.slots, body.view, kit, body.register),
        "view": body.view if body.kind == "frame" else None,
        "register": body.register,
    }


class InpaintPromptIn(BaseModel):
    """What should appear in the painted area (any language) plus the prompt the source was drawn with."""

    text: str = Field(description="What to put into the masked area, any language.")
    base_prompt: str = Field(default="", description="Prompt the source image was drawn with (`GET /inpaint-base/{id}`).")


class InpaintPromptOut(BaseModel):
    prompt: str = Field(description="Prompt for the edit job — pass it verbatim.")


class InpaintBaseOut(BaseModel):
    prompt: str = Field(description="Prompt the image was drawn with; empty when unknown.")
    caption: str


def source_prompt(db: Session, campaign_id: str, a: Attachment) -> str:
    """The prompt the source was drawn with: the job is not deleted after picking, and
    an area edit without the source prompt degenerates into redrawing the whole frame.

    For a campaign frame the attachment points to the job directly, for a portrait to the card,
    so there we take the card's latest finished job.
    """
    job = None
    if a.target_type in (SCENE_FRAME, CANDIDATE) and a.target_id:
        job = db.get(ImageGenJob, a.target_id)
    elif a.target_type == "entity" and a.target_id:
        job = (
            db.query(ImageGenJob)
            .filter(ImageGenJob.campaign_id == campaign_id,
                    ImageGenJob.entity_id == a.target_id, ImageGenJob.prompt != "")
            .order_by(ImageGenJob.created_at.desc())
            .first()
        )
    if not job or job.campaign_id != campaign_id:
        return ""
    return job.prompt or ""


@router.get("/inpaint-base/{attachment_id}", tags=["frames"], summary="Prompt behind an image",
            response_model=InpaintBaseOut, responses=error_responses(403, 409, 415))
def get_inpaint_base(
    attachment_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """The prompt an entity portrait or a campaign frame was drawn with — feed it to `/inpaint-prompt`.
    Same access rules as creating an edit job (see `POST /inpaint-jobs`)."""
    src = inpaint_source(db, v, attachment_id)
    return {"prompt": source_prompt(db, v.campaign_id, src), "caption": src.caption}


@router.post("/inpaint-prompt", tags=["frames"], summary="Draft a prompt for an area edit",
             response_model=InpaintPromptOut, responses=error_responses(400, 502))
def create_inpaint_prompt(
    body: InpaintPromptIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Turn the GM's request into the prompt for the masked area via the hub, with the source prompt as
    context. 400 — empty text or hub not configured; 502 — hub failed."""
    text = body.text.strip()
    if not text:
        raise HTTPException(400, tr("images.describe_inpaint"))
    camp = db.get(Campaign, v.campaign_id)
    said = "\n".join([
        f"ORIGINAL PROMPT: {body.base_prompt.strip() or '(unknown)'}",
        f"MASKED AREA REQUEST: {text}",
    ])
    return draft_inpaint_prompt(camp, doc_override(db, "inpaint") or P().DEFAULT_INPAINT_META_PROMPT, said)


JobStatus = Literal["pending", "claimed", "ready", "failed", "done"]


class CandidateOut(BaseModel):
    id: str = Field(description="Attachment id — pass it to `pick` / `keep`.")
    url: str = Field(description="`/api/campaigns/{campaign_id}/files/{id}` — the image (needs the token).")


class ImageJobOut(BaseModel):
    id: str
    entity_id: str | None = Field(description="Card the portrait is for; null for campaign frames.")
    kind: Literal["txt2img", "inpaint"] = Field(description="`txt2img` — drawn from the prompt; `inpaint` — an area of a source image redrawn by mask.")
    prompt: str
    width: int
    height: int
    n_images: int = Field(description="Candidates requested: 4 for portraits and edits, 1 for frames.")
    denoise: float = Field(description="Edit strength (inpaint): 1.0 rewrites the area, lower keeps the source shape.")
    status: JobStatus = Field(description="`pending` → `claimed` (drawing; finished candidates appear as they come) → `ready` (choose) | `failed` (see `error`); `done` after pick/keep.")
    error: str
    candidates: list[CandidateOut] = Field(description="Filled while `claimed`/`ready`.")
    expires_at: datetime | None = Field(default=None, description="`ready` only: when the unpicked candidates are deleted together with the job.")
    source_url: str | None = Field(description="Inpaint: the image being edited.")
    params: dict = Field(description="Draft choices and slots the job was built from (what was sent in `params`).")
    created_at: datetime


class ActiveJobOut(BaseModel):
    job: ImageJobOut | None = Field(description="The open job, or null when nothing is pending/claimed/ready.")


def job_out(job: ImageGenJob, db: Session) -> dict:
    candidates = []
    # claimed — candidates already drawn: show them without waiting for the batch
    if job.status in ("ready", "claimed"):
        rows = (
            db.query(Attachment)
            .filter(Attachment.campaign_id == job.campaign_id, Attachment.target_id == job.id,
                    Attachment.target_type.in_((CANDIDATE, SCENE_FRAME)))
            .order_by(Attachment.created_at)
            .all()
        )
        candidates = [
            {"id": a.id, "url": f"/api/campaigns/{job.campaign_id}/files/{a.id}"} for a in rows
        ]
    src = job.source_attachment_id
    return {
        "id": job.id,
        "entity_id": job.entity_id,
        "kind": job.kind or "txt2img",
        "prompt": job.prompt,
        "width": job.width,
        "height": job.height,
        "n_images": job.n_images,
        "denoise": job.denoise,
        "status": job.status,
        "error": job.error,
        "candidates": candidates,
        "expires_at": job.created_at + timedelta(seconds=DRAFT_TTL) if job.status == "ready" else None,
        "source_url": f"/api/campaigns/{job.campaign_id}/files/{src}" if src else None,
        "params": job.params or {},
        "created_at": job.created_at,
    }


def worker_fresh() -> bool:
    return bool(_worker_beat) and time.time() - _worker_beat["ts"] <= HEARTBEAT_TTL


def reap_stale_jobs(db: Session) -> None:
    """Return to the queue the jobs held by a dead worker.

    A live worker pings every 10 s and names the job it is working on: such a job is
    left alone however long it takes to draw — the worker keeps its own per-candidate
    limit. If the ping is gone, no one is drawing and the job is lost. If there is a ping, but about
    another job, the signal is weaker (several workers may be running), and such a job waits longer.

    The first time it goes back to pending: most often the worker was just restarted and will
    finish it itself. The second time it is marked failed, so a failing job does not loop forever.
    """
    rows = db.query(ImageGenJob).filter(ImageGenJob.status == "claimed").all()
    if not rows:
        return
    now = datetime.now(timezone.utc)
    fresh = worker_fresh()
    live = (_worker_beat.get("job") or {}).get("id") if fresh else None
    changed = False
    for job in rows:
        claimed = job.claimed_at
        if claimed and claimed.tzinfo is None:
            claimed = claimed.replace(tzinfo=timezone.utc)
        age = (now - claimed).total_seconds() if claimed else float("inf")
        if age <= CLAIM_GRACE or job.id in (_hub_job.get("id"), live):
            continue
        if fresh and age < CLAIM_IDLE:
            continue
        lang = campaign_lang(job.campaign_id)
        if job.attempts >= MAX_ATTEMPTS:
            job.status, job.error = "failed", tr("content.lost_final", lang=lang)
        else:
            job.status, job.error = "pending", tr("content.lost_error", lang=lang)
        job.claimed_at = None
        changed = True
    if changed:
        db.commit()


def sweep_stale_drafts(db: Session) -> None:
    """Delete finished drafts no one came back for.

    `ready` waits for a person's choice, so the job waits for it with no time limit: a calibration
    batch of a thousand frames was left lying around as gigabytes of candidates, and
    the frame form on open picked up a week-old draft as its own unfinished
    frame. Saved frames and portraits are left alone — their status is
    `done`, and the attachment is no longer a candidate. The deadline is visible in the feed (`expires_at`).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=DRAFT_TTL)
    rows = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.status == "ready", ImageGenJob.created_at < cutoff)
        .all()
    )
    if not rows:
        return
    for job in rows:
        drop_job_attachments(db, job, (CANDIDATE, *JOB_TEMP))
        db.delete(job)
    db.commit()
    log.info("expired drafts removed: %d", len(rows))


def get_own_job(db: Session, campaign_id: str, job_id: str) -> ImageGenJob:
    job = db.get(ImageGenJob, job_id)
    if not job or job.campaign_id != campaign_id:
        raise HTTPException(404, tr("images.not_found"))
    return job


def editable_entity(db: Session, v: Viewer, entity_id: str) -> Entity:
    """A card whose portrait may be generated: generation changes the card,
    so the right to do it is the right to edit, not the GM role."""
    e = get_visible_entity(db, v, entity_id)
    if not entity_editable(e, v):
        raise HTTPException(403, tr("images.generate_denied"))
    return e


# --- card generation: create a job, track it, pick -------------------------------
# available not only to the GM: a player generates for cards they can edit


class ImageJobIn(BaseModel):
    """A drawing request. `prompt` must come from `POST /image-prompt` verbatim."""

    prompt: str = Field(description="Prompt for the drawing model, Latin script only (400 otherwise). Take it from `/image-prompt` unchanged.",
                        examples=["Painterly sci-fi concept art with visible brush strokes... A full-body view of a single person..."])
    seed: int = Field(default=0, description="0 — random; any other value makes two builds of the prompt comparable.")
    width: int = Field(default=832, description="Pixels, clamped to 256–1536. Native sizes: 832×1216, 1216×832, 1344×768, 1024×1024, 768×1344.")
    height: int = Field(default=1216, description="Pixels, clamped to 256–1536.")
    params: dict = Field(default={}, description="Draft choices to remember with the attempt (`kind`, `view`, `register`, `slots`, `wardrobe`, `hand`). With `slots` from `/image-prompt` each candidate is drawn from its own take; without them the candidates get the same prompt with different camera hints. ≤16 KB.")


MAX_PARAMS_BYTES = 16_000


MIN_SIDE, MAX_SIDE = 256, 1536
# the drawing model's encoder cannot read Cyrillic — the prompt must be in English
CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")
PROMPT_MAX = 3200
# Z-Image-Turbo barely changes the frame from seed to seed: a line without hub variants (edited
# by hand or sent via API without slots) is repeated by the candidates with a camera angle hint
COMPOSITION_HINTS = ("", "alternate pose and framing, ", "different camera angle, ",
                     "varied composition and lighting, ")


def check_prompt(prompt: str) -> str:
    prompt = prompt.strip()
    if not prompt:
        raise HTTPException(400, tr("images.prompt_required"))
    if CYRILLIC.search(prompt):
        raise HTTPException(400, tr("images.prompt_english"))
    return prompt


def candidate_prompts(db: Session, v: Viewer, params: dict, prompt: str, n_images: int) -> list[str]:
    """A line for each candidate: the hub variants, or without them, the same line with a camera angle hint.
    The worker and API drawing take this list the same way."""
    if n_images < 2:
        return []
    slots = params.get("slots") or {}
    if not params.get("hand") and slots.get("takes") and params.get("kind") in P().KINDS:
        kit = campaign_kit(db.get(Campaign, v.campaign_id))
        out = P().prose.prompts(params["kind"], slots, params.get("view") or "interior", kit,
                                P().norm_register(params.get("register") or ""))
        if len(out) >= n_images:
            return [prompt] + [p[:PROMPT_MAX] for p in out[1:n_images]]
    return [f"{COMPOSITION_HINTS[i % len(COMPOSITION_HINTS)]}{prompt}"[:PROMPT_MAX] for i in range(n_images)]


def build_job(db: Session, v: Viewer, body: ImageJobIn, entity_id: str | None, n_images: int) -> ImageGenJob:
    prompt = check_prompt(body.prompt)
    if len(json.dumps(body.params)) > MAX_PARAMS_BYTES:
        raise HTTPException(400, tr("images.params_too_big"))
    prompt = prompt[:PROMPT_MAX]
    params = {**body.params, "prompts": candidate_prompts(db, v, body.params, prompt, n_images)}
    return ImageGenJob(
        campaign_id=v.campaign_id, entity_id=entity_id, prompt=prompt,
        width=max(MIN_SIDE, min(MAX_SIDE, body.width)),
        height=max(MIN_SIDE, min(MAX_SIDE, body.height)),
        n_images=n_images, created_by=v.member_id,
        seed=max(0, min(2**31 - 1, body.seed or 0)),
        params=params,
    )


@router.post("/entities/{entity_id}/image-jobs", tags=["images"], summary="Queue a portrait for a card",
             response_model=ImageJobOut, responses=error_responses(400))
def create_image_job(
    entity_id: str, body: ImageJobIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Create a portrait job (4 candidates) for a card you may edit. Poll `GET /image-jobs/{id}` until
    `ready`, then `POST /image-jobs/{id}/pick`. Each call is a new attempt in the card's workshop feed;
    unpicked attempts expire after 24 h. 400 — non-Latin prompt or oversized params."""
    editable_entity(db, v, entity_id)
    # each job is a new attempt in the studio feed; earlier ones live alongside until picked
    job = build_job(db, v, body, entity_id=entity_id, n_images=CANDIDATES_PER_JOB)
    db.add(job)
    db.flush()
    db.commit()
    return job_out(job, db)


def is_new_inpaint(job: ImageGenJob) -> bool:
    """A mask edit of an unpicked variant: the result becomes a new attempt
    instead of replacing the saved image."""
    return job.kind == "inpaint" and (job.params or {}).get("mode") == "new"


def list_attempts(db: Session, v: Viewer, entity_id: str | None) -> list[dict]:
    """Studio feed: your own open attempts — drawing, waiting to be picked, or failed."""
    fresh = datetime.now(timezone.utc) - timedelta(seconds=DRAFT_TTL)
    q = db.query(ImageGenJob).filter(
        ImageGenJob.campaign_id == v.campaign_id,
        ImageGenJob.created_by == v.member_id,
        ImageGenJob.kind.in_(("txt2img", "inpaint")),
        ImageGenJob.status.in_(ACTIVE_STATUSES) | (
            (ImageGenJob.status == "failed") & (ImageGenJob.created_at >= fresh)),
    )
    q = q.filter(ImageGenJob.entity_id == entity_id if entity_id
                 else ImageGenJob.entity_id.is_(None))
    rows = q.order_by(ImageGenJob.created_at.desc()).limit(SCENE_HISTORY).all()
    return [job_out(j, db) for j in rows]


@router.get("/entities/{entity_id}/image-jobs", tags=["images"], summary="List my open attempts for a card",
            response_model=list[ImageJobOut])
def list_entity_attempts(entity_id: str, v: Viewer = Depends(editor),
                         db: Session = Depends(get_db)):
    """The caller's own unfinished attempts for this card (drawing, awaiting a pick, or failed within 24 h), newest first."""
    editable_entity(db, v, entity_id)
    return list_attempts(db, v, entity_id)


MAX_FORM_BYTES = 16_000  # a form snapshot, not storage: slots and prompt fit in it with room to spare


class GenFormOut(BaseModel):
    form: dict = Field(description="Snapshot of the generation form (direction, subtype, register, format, outfit; the description only when it was edited); `{}` when nothing was stored.")


class GenFormIn(BaseModel):
    form: dict = Field(description="Any JSON object ≤16 KB; stored as-is on the card, GM kitchen — never shown to players.")


@router.get("/entities/{entity_id}/gen-form", tags=["workshop"], summary="Last generation form of a card",
            response_model=GenFormOut)
def get_gen_form(entity_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """What the card was last generated with. Open to whoever may generate for the card."""
    return {"form": editable_entity(db, v, entity_id).gen_form or {}}


@router.put("/entities/{entity_id}/gen-form", tags=["workshop"], summary="Store the generation form of a card",
            response_model=Ok, responses=error_responses(400))
def put_gen_form(
    entity_id: str, body: GenFormIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Replace the stored form snapshot. 400 — larger than 16 KB."""
    e = editable_entity(db, v, entity_id)
    form = body.form
    if len(json.dumps(form)) > MAX_FORM_BYTES:
        raise HTTPException(400, tr("images.form_too_big"))
    e.gen_form = form
    db.commit()
    return {"ok": True}


@router.get("/entities/{entity_id}/image-jobs/active", tags=["images"], summary="Open portrait job of a card",
            response_model=ActiveJobOut)
def get_active_entity_job(
    entity_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """The latest portrait job of the card that is still pending, drawing or awaiting a pick; null otherwise."""
    editable_entity(db, v, entity_id)
    job = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.entity_id == entity_id,
                ImageGenJob.kind == "txt2img", ImageGenJob.status.in_(ACTIVE_STATUSES))
        .order_by(ImageGenJob.created_at.desc())
        .first()
    )
    return {"job": job_out(job, db) if job else None}


class WorkerJobOut(BaseModel):
    id: str | None = None
    progress: str | None = Field(default=None, description="Human-readable progress of the job being drawn, e.g. `2/4`.")


class WorkerStatusOut(BaseModel):
    state: Literal["online", "degraded", "offline"] = Field(description="`online` — the worker or an image API can draw; `degraded` — worker alive but ComfyUI is down; `offline` — nobody draws, jobs wait in the queue.")
    age_s: float | None = Field(description="Seconds since the worker's last heartbeat; null when none.")
    comfy: str | None = Field(description="ComfyUI state reported by the worker.")
    checkpoint: str | None = Field(description="Model drawing now (worker checkpoint or the API model label).")
    inpaint_checkpoint: str | None = Field(description="How the worker edits areas.")
    job: WorkerJobOut | None = Field(description="Job being drawn right now.")
    edit: bool = Field(description="Whether area editing (inpaint) is available: a live worker, or an image API that supports edits.")
    hub: bool = Field(description="Whether the LLM hub is configured, i.e. `POST /image-prompt` can draft prompts. If false, a server admin sets it with `PATCH /api/admin/hub`.")
    queue: dict[str, int] = Field(description="Jobs of this campaign by status: pending, claimed, ready.")
    last_error: str | None = Field(description="Error of the last failed job within an hour.")


@router.get("/image-worker/status", tags=["workshop"], summary="Who draws and what is queued",
            response_model=WorkerStatusOut)
def image_worker_status(v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Drawing capacity: worker heartbeat or the configured image API, queue of this campaign, last error.
    Check `state` before queueing many jobs; `edit` tells whether inpaint jobs will be served;
    `hub` whether prompts can be drafted at all."""
    beat = _worker_beat
    age = time.time() - beat["ts"] if beat else None
    drawer = draw_conf(db)
    # area edits go to the worker while it is alive; without it, to the service if it can do them
    editing = worker_fresh() or bool(drawer and can_edit(drawer["base_url"]))
    if drawer:
        state = "online"
        beat = {"checkpoint": drawer["label"], "job": _hub_job.get("job")}
    elif age is None or age > HEARTBEAT_TTL:
        state = "offline"
    elif beat.get("comfy") == "up":
        state = "online"
    else:
        state = "degraded"

    rows = (
        db.query(ImageGenJob.status)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.status.in_(ACTIVE_STATUSES))
        .all()
    )
    queue = {s: 0 for s in ACTIVE_STATUSES}
    for (status,) in rows:
        queue[status] = queue.get(status, 0) + 1

    last_failed = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.status == "failed",
                ImageGenJob.updated_at > datetime.now(timezone.utc) - timedelta(hours=1))
        .order_by(ImageGenJob.created_at.desc())
        .first()
    )
    return {
        "state": state,
        "age_s": round(age, 1) if age is not None else None,
        "comfy": beat.get("comfy") if beat else None,
        "checkpoint": beat.get("checkpoint") if beat else None,
        "inpaint_checkpoint": beat.get("inpaint_checkpoint") if beat else None,
        "job": beat.get("job") if state != "offline" else None,
        "edit": editing,
        "hub": all(hub_conf(db).get(x) for x in ("base_url", "api_key", "model")),
        "queue": queue,
        "last_error": last_failed.error if last_failed else None,
    }


# --- campaign frames: a job without a card, one image, straight to the gallery ------

SCENE_HISTORY = 24


@router.post("/scene-jobs", tags=["frames"], summary="Queue a campaign frame",
             response_model=ImageJobOut, responses=error_responses(400))
def create_scene_job(body: ImageJobIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """A frame not tied to any card: one candidate, drawn for the table (any editor, not only the GM).
    Poll `GET /scene-jobs/{id}` until `ready`, then `POST /scene-jobs/{id}/keep` to put it in the gallery."""
    job = build_job(db, v, body, entity_id=None, n_images=1)
    db.add(job)
    db.flush()
    db.commit()
    return job_out(job, db)


def own_scene_job(db: Session, v: Viewer, job_id: str) -> ImageGenJob:
    """Your own frame job: a draft belongs to whoever created it until it is saved.
    A mask edit of a frame is not tied to a card either — it is filtered out by kind, otherwise
    the generation screen would pick it up as its own unfinished frame."""
    job = db.get(ImageGenJob, job_id)
    if (not job or job.campaign_id != v.campaign_id or job.entity_id is not None
            or not ((job.kind or "txt2img") == "txt2img" or is_new_inpaint(job))
            or job.created_by != v.member_id):
        raise HTTPException(404, tr("images.not_found"))
    return job


@router.get("/scene-jobs", tags=["frames"], summary="List my open frame attempts", response_model=list[ImageJobOut])
def list_scene_jobs(v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """The caller's own unfinished frame jobs and frame edits (drawing, awaiting keep, or failed within 24 h), newest first."""
    return list_attempts(db, v, None)


@router.get("/scene-jobs/{job_id}", tags=["frames"], summary="Get a frame job", response_model=ImageJobOut)
def get_scene_job(job_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """A frame job of the caller (404 for someone else's). Poll until `status` is `ready` or `failed`."""
    return job_out(own_scene_job(db, v, job_id), db)


class SceneFrameOut(BaseModel):
    id: str = Field(description="Attachment id — also the source for an area edit.")
    url: str
    caption: str
    width: int
    height: int
    mine: bool = Field(description="The caller created it (may caption and delete it).")
    created_at: datetime
    visibility: str | None = Field(default=None, description="GM only: `crew` — on the table, `gm` — hidden.")
    prompt: str | None = Field(default=None, description="GM only: the prompt the frame was drawn with.")


class KeepIn(BaseModel):
    caption: str = Field(default="", description="Caption shown in the gallery, ≤300 chars.")
    candidate_id: str = Field(default="", description="Which candidate to keep; a frame has one, so it may be omitted. Edits by mask have four.")


@router.post("/scene-jobs/{job_id}/keep", tags=["frames"], summary="Keep a drawn frame in the gallery",
             response_model=SceneFrameOut, responses=error_responses(409))
def keep_scene_frame(
    job_id: str, body: KeepIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Save the candidate to the campaign gallery: it opens to the table (`visibility: crew`), gets the
    caption, the other candidates are deleted and the job is closed. 409 — the job is not `ready`."""
    job = own_scene_job(db, v, job_id)
    if job.status != "ready":
        raise HTTPException(409, tr("images.frame_not_ready"))
    rows = (
        db.query(Attachment)
        .filter_by(campaign_id=v.campaign_id, target_type=CANDIDATE, target_id=job.id)
        .order_by(Attachment.created_at)
        .all()
    )
    if body.candidate_id:
        frame = next((a for a in rows if a.id == body.candidate_id), None)
    else:
        frame = rows[0] if rows else None
    if not frame:
        raise HTTPException(404, tr("images.frame_missing"))
    for a in rows:
        if a.id != frame.id:
            drop_files(a)
            db.delete(a)
    drop_job_attachments(db, job, JOB_TEMP)
    frame.target_type = SCENE_FRAME
    frame.visibility = "crew"
    frame.visible_to = []
    frame.caption = body.caption.strip()[:300]
    job.status = "done"
    journal.log(db, v, "file", "upload", target_id=frame.id,
                title=frame.caption or ctr("content.frame"), detail=frame.mime,
                visibility=frame.visibility)
    db.commit()
    return frame_out(frame, v, {job.id: job})


@router.delete("/scene-jobs/{job_id}", tags=["frames"], summary="Discard a frame job", response_model=Ok)
def cancel_scene_job(job_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Delete the job and all its candidates. Only the caller's own jobs."""
    job = own_scene_job(db, v, job_id)
    drop_job_attachments(db, job, (CANDIDATE, SCENE_FRAME, *JOB_TEMP))
    db.delete(job)
    db.commit()
    return {"ok": True}


# --- frame gallery: the same attachment, but with a caption and its own visibility --------


def frame_out(a: Attachment, v: Viewer, jobs: dict[str, ImageGenJob]) -> dict:
    job = jobs.get(a.target_id or "")
    data = {
        "id": a.id,
        "url": f"/api/campaigns/{a.campaign_id}/files/{a.id}",
        "caption": a.caption,
        "width": job.width if job else 0,
        "height": job.height if job else 0,
        # a player captions and removes their own frame, and does not touch others'
        "mine": bool(a.uploaded_by) and a.uploaded_by == v.member_id,
        "created_at": a.created_at,
    }
    if v.is_gm:
        data["visibility"] = a.visibility
        data["prompt"] = job.prompt if job else ""
    return data


@router.get("/scene-frames", tags=["frames"], summary="Campaign frame gallery", response_model=list[SceneFrameOut])
def list_scene_frames(
    v: Viewer = Depends(viewer), db: Session = Depends(get_db),
    limit: int | None = Query(None, ge=1, description="Page size; omitted — all."),
    offset: int = Query(0, ge=0, description="Rows to skip."),
):
    """Kept frames, newest first. Players see only frames open to the table."""
    q = db.query(Attachment).filter(
        Attachment.campaign_id == v.campaign_id, Attachment.target_type == SCENE_FRAME
    )
    rows = (apply_scope(q, Attachment, v).order_by(Attachment.created_at.desc())
            .offset(offset).limit(limit).all())
    ids = [a.target_id for a in rows if a.target_id]
    jobs = (
        {j.id: j for j in db.query(ImageGenJob).filter(ImageGenJob.id.in_(ids)).all()}
        if ids else {}
    )
    return [frame_out(a, v, jobs) for a in rows]


def get_frame(db: Session, v: Viewer, frame_id: str) -> Attachment:
    a = db.get(Attachment, frame_id)
    if (not a or a.campaign_id != v.campaign_id or a.target_type != SCENE_FRAME
            or not can_see(a, v)):
        raise HTTPException(404, tr("images.not_found"))
    return a


def own_frame(db: Session, v: Viewer, frame_id: str) -> Attachment:
    """A frame is edited and removed by the GM or by whoever created it."""
    a = get_frame(db, v, frame_id)
    if not v.is_gm and a.uploaded_by != v.member_id:
        raise HTTPException(403, tr("images.frame_not_yours"))
    return a


class SceneFramePatch(BaseModel):
    """Only the keys sent are changed."""

    caption: str | None = Field(default=None, description="≤300 chars.")
    visibility: Literal["crew", "gm"] | None = Field(default=None, description="GM only. A frame has no owner or addressee: it is either on the table or GM-only.")


@router.patch("/scene-frames/{frame_id}", tags=["frames"], summary="Caption or hide a frame",
              response_model=SceneFrameOut, responses=error_responses(403))
def patch_scene_frame(
    frame_id: str, body: SceneFramePatch, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Change the caption (author or GM) or the visibility (GM only, 403 otherwise). Journaled."""
    a = own_frame(db, v, frame_id)
    if body.visibility is not None:
        # only the GM decides what the table sees
        if not v.is_gm:
            raise HTTPException(403, tr("images.frame_vis_gm"))
        a.visibility = body.visibility
    if body.caption is not None:
        a.caption = body.caption.strip()[:300]
    journal.log(db, v, "file", "update", target_id=a.id, title=a.caption or ctr("content.frame"),
                detail=a.mime, visibility=a.visibility)
    db.commit()
    jobs = {}
    if a.target_id:
        job = db.get(ImageGenJob, a.target_id)
        if job:
            jobs[job.id] = job
    return frame_out(a, v, jobs)


@router.delete("/scene-frames/{frame_id}", tags=["frames"], summary="Delete a frame",
               response_model=Ok, responses=error_responses(403))
def delete_scene_frame(
    frame_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Remove the frame and its file (author or GM). Journaled."""
    a = own_frame(db, v, frame_id)
    job = db.get(ImageGenJob, a.target_id) if a.target_id else None
    journal.log(db, v, "file", "delete", target_id=a.id, title=a.caption or ctr("content.frame"),
                detail=a.mime, visibility=a.visibility)
    drop_files(a)
    db.delete(a)
    if job and job.campaign_id == v.campaign_id and job.entity_id is None:
        db.delete(job)
    db.commit()
    return {"ok": True}


# --- inpaint: redraw an area of a saved image by mask ------------------------------

# below this maximum the mask is considered empty — the brush did not touch the canvas
MASK_MIN_WHITE = 16
# mask edge blur radius: a fraction of the frame's shorter side
FEATHER_DIVISOR = 170
# margin of surroundings around the painted area, as a fraction of its size on each side
CROP_PAD = 0.55
# the cut-out piece is scaled to this side: the model's working resolution
INPAINT_TARGET = 1024
INPAINT_BUSY = ("pending", "claimed")


def inpaint_source(db: Session, v: Viewer, attachment_id: str) -> Attachment:
    """What can be redrawn: a card's saved portrait or a campaign frame.
    Generation candidates are excluded — pick first, then edit."""
    a = db.get(Attachment, attachment_id)
    if not a or a.campaign_id != v.campaign_id or not can_see(a, v):
        raise HTTPException(404, tr("images.not_found"))
    if not a.mime.startswith("image/") or a.mime == "image/svg+xml":
        raise HTTPException(415, tr("images.raster_only"))
    if a.target_type == CANDIDATE:
        parent = db.get(ImageGenJob, a.target_id) if a.target_id else None
        if not parent or parent.campaign_id != v.campaign_id or parent.created_by != v.member_id:
            raise HTTPException(403, tr("images.own_variants_only"))
        if parent.kind != "txt2img" and not is_new_inpaint(parent):
            raise HTTPException(409, tr("images.take_variant_first"))
    elif a.target_type == SCENE_FRAME:
        if not v.is_gm and a.uploaded_by != v.member_id:
            raise HTTPException(403, tr("images.frame_not_yours"))
    elif a.target_type == "entity":
        if not v.is_gm:
            raise HTTPException(403, tr("images.portrait_gm"))
    else:
        raise HTTPException(409, tr("images.redraw_targets"))
    return a


def crop_window(mask: Image.Image, w: int, h: int) -> tuple[int, int, int, int] | None:
    """The piece of the frame around the painted area that goes to the model.

    Inpainting over the whole canvas is the main cause of "asked for a drone, got a piece of a ship":
    the painted area takes up a couple of percent of the frame, only a handful of cells of it remain
    in the latent, while the prompt describes the whole frame — so the model draws
    what is around. A piece around the mask gives the area the model's full resolution.

    Empty means the mask already covers the whole frame, nothing to crop.
    """
    bbox = mask.point(lambda p: 255 if p >= MASK_MIN_WHITE else 0).getbbox()
    if not bbox:
        return None
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    # margin around the mask: without surroundings the model does not know what to fit the object into
    side = max(bw, bh) * (1 + 2 * CROP_PAD)
    side = int(min(max(side, MIN_SIDE), w, h))
    side -= side % 8
    if side >= min(w, h) * 0.9:
        return None
    cx, cy = (bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2
    x = max(0, min(w - side, cx - side // 2))
    y = max(0, min(h - side, cy - side // 2))
    return x - x % 8, y - y % 8, side, side


def prepare_inpaint_pair(
    src: Attachment, mask_raw: bytes
) -> tuple[bytes, bytes, int, int, str]:
    """Bring the source and the mask to one size that is a multiple of 8, blur the mask edge and
    cut out a working piece around the painted area.

    The multiple of 8 is a latent requirement: otherwise the decoded frame drifts off the
    original by a couple of pixels and the mask composite leaves a strip along the edge.
    A hard brush edge leaves a visible seam, so the mask is blurred.

    Returns the pair for the worker, the size of the whole prepared frame, and the cut-out
    window "x,y,w,h" — the candidates are pasted back by it (see stitch_candidate).
    """
    path = os.path.join(settings.upload_dir, src.campaign_id, src.url)
    if not os.path.exists(path):
        raise HTTPException(410, tr("images.source_gone"))
    try:
        with Image.open(path) as im:
            full = im.convert("RGB")
            full_size = (full.width, full.height)
            box = (0, 0, full.width - full.width % 8, full.height - full.height % 8)
            full = full.crop(box)
            w, h = full.size
            if w < MIN_SIDE or h < MIN_SIDE:
                raise HTTPException(422, tr("images.too_small"))
        with Image.open(io.BytesIO(mask_raw)) as mi:
            mask = mi.convert("L")
            # the mask is drawn over the image at full size, so it is cropped
            # the same way as the source rather than scaled to the frame — otherwise a shift of up to 7 px
            if mask.size != full_size:
                mask = mask.resize(full_size, Image.LANCZOS)
            mask = mask.crop(box)
            if mask.getextrema()[1] < MASK_MIN_WHITE:
                raise HTTPException(400, tr("images.mask_empty"))

        window = crop_window(mask, w, h)
        crop = ""
        if window:
            x, y, cw, ch = window
            full = full.crop((x, y, x + cw, y + ch))
            mask = mask.crop((x, y, x + cw, y + ch))
            crop = f"{x},{y},{cw},{ch}"
            # a small piece is scaled up to the model's working resolution: at 300 px it draws
            # mush; it is pasted back with downscaling anyway
            if max(full.size) != INPAINT_TARGET:
                side = INPAINT_TARGET - INPAINT_TARGET % 8
                full = full.resize((side, side), Image.LANCZOS)
                mask = mask.resize((side, side), Image.LANCZOS)

        mask = mask.filter(
            ImageFilter.GaussianBlur(max(3, min(mask.size) // FEATHER_DIVISOR)))
        src_buf, mask_buf = io.BytesIO(), io.BytesIO()
        full.save(src_buf, "PNG")
        mask.save(mask_buf, "PNG")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — broken file or unknown format
        raise HTTPException(422, tr("images.read_failed", exc=exc)) from exc
    return src_buf.getvalue(), mask_buf.getvalue(), w, h, crop


def stitch_candidate(db: Session, job: ImageGenJob, data: bytes) -> bytes:
    """Paste the redrawn piece back into the whole frame.

    The worker saw only the window around the mask — the candidate arrives as a piece. It is returned
    to its place by the job's mask: outside the mask the original pixels stay, so the frame does not
    drift in color from the trip through the VAE.
    """
    src = db.get(Attachment, job.source_attachment_id) if job.source_attachment_id else None
    mask_row = (
        db.query(Attachment).filter_by(target_type=MASK, target_id=job.id).first()
    )
    if not src or not mask_row:
        return data
    src_path = os.path.join(settings.upload_dir, src.campaign_id, src.url)
    mask_path = os.path.join(settings.upload_dir, mask_row.campaign_id, mask_row.url)
    if not os.path.exists(src_path) or not os.path.exists(mask_path):
        return data
    try:
        x, y, cw, ch = (int(n) for n in job.crop_box.split(",")) if job.crop_box else (0, 0, job.width, job.height)
        with Image.open(src_path) as im:
            full = im.convert("RGB").crop((0, 0, job.width, job.height))
        with Image.open(io.BytesIO(data)) as ci:
            piece = ci.convert("RGB").resize((cw, ch), Image.LANCZOS)
        with Image.open(mask_path) as mi:
            mask = mi.convert("L").resize((cw, ch), Image.LANCZOS)
        full.paste(piece, (x, y), mask)
        out = io.BytesIO()
        full.save(out, "PNG")
        return out.getvalue()
    except Exception:  # noqa: BLE001 — the piece was not pasted in, return it as it came
        return data


def store_job_blob(job: ImageGenJob, data: bytes, target_type: str, name: str) -> Attachment:
    folder = os.path.join(settings.upload_dir, job.campaign_id)
    os.makedirs(folder, exist_ok=True)
    stored = f"{uuid.uuid4()}.png"
    with open(os.path.join(folder, stored), "wb") as fh:
        fh.write(data)
    return Attachment(
        campaign_id=job.campaign_id, filename=name, url=stored, mime="image/png",
        size=len(data), target_type=target_type, target_id=job.id,
        visibility="gm", uploaded_by=job.created_by,
    )


def own_inpaint_job(db: Session, v: Viewer, job_id: str) -> ImageGenJob:
    job = db.get(ImageGenJob, job_id)
    if (not job or job.campaign_id != v.campaign_id or job.kind != "inpaint"
            or (not v.is_gm and job.created_by != v.member_id)):
        raise HTTPException(404, tr("images.not_found"))
    return job


@router.post("/inpaint-jobs", tags=["frames"], summary="Queue an area edit by mask",
             response_model=ImageJobOut, responses=error_responses(400, 403, 409, 410, 413, 415, 422))
async def create_inpaint_job(
    source_attachment_id: str = Form(..., description="Attachment to edit: an entity portrait (GM only), a campaign frame (author or GM) or your own unpicked candidate."),
    prompt: str = Form(..., description="Prompt from `POST /inpaint-prompt`, verbatim; Latin script only."),
    denoise: float = Form(default=1.0, description="0.2–1.0: 1.0 repaints the area from scratch, lower keeps the source shape. Ignored when an image API draws."),
    text: str = Form(default="", description="The GM's request in plain words, kept with the attempt (≤1000 chars)."),
    mask: UploadFile = File(..., description="PNG/JPEG the size of the image: white = repaint, black = keep. Soft edges are fine."),
    v: Viewer = Depends(editor),
    db: Session = Depends(get_db),
):
    """Multipart request. Four candidates are drawn for the painted area and composited back into the
    full frame; poll `GET /inpaint-jobs/{id}`, then `pick`. One open edit per image (409 while it runs).
    400 — empty mask or non-Latin prompt; 410 — source file gone; 413/415 — mask too big or not an image;
    422 — image too small or unreadable."""
    src = inpaint_source(db, v, source_attachment_id)
    if mask.content_type not in ALLOWED:
        raise HTTPException(415, tr("images.mask_type", type=mask.content_type))
    raw = await mask.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, tr("images.mask_heavy"))
    prompt = check_prompt(prompt)
    busy = (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.kind == "inpaint",
                ImageGenJob.source_attachment_id == src.id,
                ImageGenJob.status.in_(INPAINT_BUSY))
        .first()
    )
    if busy:
        raise HTTPException(409, tr("images.edit_busy"))
    # the GM usually does not cancel a failed edit but closes the window: its mask and the copy
    # of the source would otherwise stay on disk forever
    for stale in (
        db.query(ImageGenJob)
        .filter(ImageGenJob.campaign_id == v.campaign_id, ImageGenJob.kind == "inpaint",
                ImageGenJob.source_attachment_id == src.id, ImageGenJob.status == "failed")
        .all()
    ):
        drop_job_attachments(db, stale, (CANDIDATE, *JOB_TEMP))
        db.delete(stale)
    strength = max(0.2, min(1.0, denoise))
    src_png, mask_png, width, height, crop = prepare_inpaint_pair(src, raw)
    params = {"mode": "replace", "text": text.strip()[:1000]}
    entity_id = src.target_id if src.target_type == "entity" else None
    if src.target_type == CANDIDATE:
        # the variant is not picked yet: the edit goes into the same feed as the variant itself
        parent = db.get(ImageGenJob, src.target_id)
        params |= {"mode": "new", "from_job": parent.id}
        entity_id = parent.entity_id
    job = ImageGenJob(
        campaign_id=v.campaign_id, kind="inpaint", params=params,
        # a portrait edit stays with the card: that way it is visible in audit and cleanup
        entity_id=entity_id,
        source_attachment_id=src.id, prompt=prompt[:PROMPT_MAX],
        # keep the full size: the candidate is pasted back into the whole frame, and the edit window
        # and gallery show the source's proportions, not the piece's
        width=width, height=height, crop_box=crop, n_images=CANDIDATES_PER_JOB,
        denoise=strength, created_by=v.member_id,
    )
    db.add(job)
    db.flush()
    db.add(store_job_blob(job, src_png, SOURCE, "source.png"))
    db.add(store_job_blob(job, mask_png, MASK, "mask.png"))
    db.commit()
    return job_out(job, db)


@router.get("/inpaint-jobs/{job_id}", tags=["frames"], summary="Get an edit job", response_model=ImageJobOut)
def get_inpaint_job(job_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)):
    """Poll until `status` is `ready` or `failed`. Players get 404 for someone else's edit."""
    return job_out(own_inpaint_job(db, v, job_id), db)


def drop_job_attachments(db: Session, job: ImageGenJob, types: tuple[str, ...]) -> None:
    rows = (
        db.query(Attachment)
        .filter(Attachment.campaign_id == job.campaign_id, Attachment.target_id == job.id,
                Attachment.target_type.in_(types))
        .all()
    )
    for a in rows:
        drop_files(a)
        db.delete(a)


class InpaintPickIn(BaseModel):
    candidate_id: str = Field(description="`candidates[].id` of the job.")
    keep_source: bool = Field(default=False, description="Keep the original image as a separate attachment; by default it is replaced.")


class InpaintPickOut(BaseModel):
    ok: bool = True
    url: str = Field(description="File URL of the new image.")
    frame_id: str = Field(description="Attachment id of the new image (it took the source's place).")


@router.post("/inpaint-jobs/{job_id}/pick", tags=["frames"], summary="Accept an edit candidate",
             response_model=InpaintPickOut, responses=error_responses(409))
def pick_inpaint_job(
    job_id: str, body: InpaintPickIn, v: Viewer = Depends(editor),
    db: Session = Depends(get_db),
):
    """The chosen candidate takes the source's place: same target, visibility and caption; a card
    portrait moves to it when it pointed at the source. Other candidates are deleted. 409 — not `ready`,
    the source was deleted, or the job edits an unpicked candidate (save that one via its own pick/keep)."""
    job = own_inpaint_job(db, v, job_id)
    if job.status != "ready":
        raise HTTPException(409, tr("images.edit_not_ready"))
    if is_new_inpaint(job):
        raise HTTPException(409, tr("images.variant_edit_target"))
    src = db.get(Attachment, job.source_attachment_id) if job.source_attachment_id else None
    if not src or src.campaign_id != job.campaign_id:
        raise HTTPException(409, tr("images.source_deleted"))
    rows = (
        db.query(Attachment)
        .filter_by(campaign_id=job.campaign_id, target_type=CANDIDATE, target_id=job.id)
        .all()
    )
    winner = next((a for a in rows if a.id == body.candidate_id), None)
    if not winner:
        raise HTTPException(404, tr("images.candidate_missing"))

    old_url = f"/api/campaigns/{job.campaign_id}/files/{src.id}"
    new_url = f"/api/campaigns/{job.campaign_id}/files/{winner.id}"
    winner.caption = src.caption
    winner.visibility = src.visibility
    winner.visible_to = list(src.visible_to or [])
    if src.target_type == SCENE_FRAME:
        # a frame needs its job alongside: the gallery takes the size and prompt from it
        winner.target_type = SCENE_FRAME
        winner.target_id = job.id
    else:
        winner.target_type = "entity"
        winner.target_id = src.target_id
        ent = db.get(Entity, src.target_id) if src.target_id else None
        if ent and ent.campaign_id == job.campaign_id and ent.image_url == old_url:
            ent.image_url = new_url

    for a in rows:
        if a.id != winner.id:
            drop_files(a)
            db.delete(a)
    drop_job_attachments(db, job, JOB_TEMP)
    if not body.keep_source:
        drop_files(src)
        db.delete(src)
    job.status = "done"
    journal.log(db, v, "file", "update", target_id=winner.id,
                title=winner.caption or ctr("content.image_edit"),
                entity_id=winner.target_id if winner.target_type == "entity" else None,
                detail=winner.mime, visibility=winner.visibility)
    db.commit()
    return {"ok": True, "url": new_url, "frame_id": winner.id}


@router.delete("/inpaint-jobs/{job_id}", tags=["frames"], summary="Discard an edit job", response_model=Ok)
def cancel_inpaint_job(
    job_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Delete the edit job, its candidates and mask. The source image is untouched."""
    job = own_inpaint_job(db, v, job_id)
    drop_job_attachments(db, job, (CANDIDATE, *JOB_TEMP))
    db.delete(job)
    db.commit()
    return {"ok": True}


class AgainIn(BaseModel):
    prompt: str = Field(default="", description="Replacement prompt (Latin only); empty = reuse the previous one.")


@router.post("/inpaint-jobs/{job_id}/again", tags=["frames"], summary="Redraw an edit with the same mask",
             response_model=ImageJobOut, responses=error_responses(400, 410))
def again_inpaint_job(
    job_id: str, body: AgainIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """A new edit job with the same source and mask, with the old or a corrected prompt; the previous
    attempt stays in the feed. Only your own jobs. 410 — the mask was already removed."""
    old = own_inpaint_job(db, v, job_id)
    if old.created_by != v.member_id:
        raise HTTPException(404, tr("images.not_found"))
    blobs = {
        a.target_type: a
        for a in db.query(Attachment).filter(
            Attachment.campaign_id == old.campaign_id, Attachment.target_id == old.id,
            Attachment.target_type.in_(JOB_TEMP)).all()
    }
    if set(blobs) != set(JOB_TEMP):
        raise HTTPException(410, tr("images.mask_dropped"))
    prompt = check_prompt(body.prompt or old.prompt)
    params = dict(old.params or {})
    params["hand"] = bool(params.get("hand")) or prompt != old.prompt
    job = ImageGenJob(
        campaign_id=old.campaign_id, kind="inpaint", entity_id=old.entity_id,
        source_attachment_id=old.source_attachment_id, prompt=prompt[:PROMPT_MAX],
        width=old.width, height=old.height, crop_box=old.crop_box,
        n_images=old.n_images, denoise=old.denoise, created_by=v.member_id, params=params,
    )
    db.add(job)
    db.flush()
    for kind, a in blobs.items():
        path = os.path.join(settings.upload_dir, a.campaign_id, a.url)
        if not os.path.exists(path):
            raise HTTPException(410, tr("images.mask_missing"))
        with open(path, "rb") as fh:
            db.add(store_job_blob(job, fh.read(), kind, a.filename))
    db.commit()
    return job_out(job, db)


def job_entity_gate(db: Session, v: Viewer, job: ImageGenJob) -> Entity | None:
    """Generic /image-jobs/{id} routes are only for card jobs (txt2img):
    campaign frames and mask edits have their own routes with their own rights, and a mask edit
    of a portrait stays GM-only — the right to edit the card does not open it.
    A card job is open to those who edit the card; a job without a card is
    a frame draft, and the generic route still lets only the GM touch it."""
    if (job.kind or "txt2img") != "txt2img" and not is_new_inpaint(job):
        raise HTTPException(404, tr("images.not_found"))
    if job.entity_id:
        return editable_entity(db, v, job.entity_id)
    if not v.is_real_gm:
        raise HTTPException(403, tr("images.gm_only"))
    return None


@router.get("/image-jobs/{job_id}", tags=["images"], summary="Get a portrait job", response_model=ImageJobOut)
def get_image_job(job_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Poll until `status` is `ready` (then pick) or `failed` (see `error`). Portrait jobs only — frames
    and edits have their own routes. Open to whoever may edit the card."""
    job = get_own_job(db, v.campaign_id, job_id)
    job_entity_gate(db, v, job)
    return job_out(job, db)


class PickIn(BaseModel):
    candidate_id: str = Field(description="`candidates[].id` of the job.")
    set_avatar: bool = Field(default=True, description="Make it the card portrait (`image_url`); false keeps it in the card's media only.")


class PickOut(BaseModel):
    ok: bool = True
    image_url: str = Field(description="The card's portrait URL after the pick.")
    attachment_url: str = Field(description="File URL of the chosen candidate.")


@router.post("/image-jobs/{job_id}/pick", tags=["images"], summary="Choose a portrait candidate",
             response_model=PickOut, responses=error_responses(403, 409))
def pick_image_job(
    job_id: str, body: PickIn, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Keep one candidate as a card attachment open to the table (and as the portrait unless
    `set_avatar` is false); the others are deleted and the job closes. 409 — not `ready`;
    403 — a player picking an avatar the GM has hidden."""
    job = get_own_job(db, v.campaign_id, job_id)
    if job.status != "ready":
        raise HTTPException(409, tr("images.job_not_ready"))
    entity = job_entity_gate(db, v, job)
    if entity is None:
        raise HTTPException(404, tr("images.not_found"))
    # the GM may have hidden the portrait from the table: the server does not accept an image_url edit from a player
    # (see patch_entity) — picking a candidate must not be a way around that
    if body.set_avatar and not v.is_real_gm and "image_url" in (entity.hidden_fields or []):
        raise HTTPException(403, tr("images.portrait_locked"))
    rows = (
        db.query(Attachment)
        .filter_by(campaign_id=v.campaign_id, target_type=CANDIDATE, target_id=job.id)
        .all()
    )
    winner = next((a for a in rows if a.id == body.candidate_id), None)
    if not winner:
        raise HTTPException(404, tr("images.candidate_missing"))
    winner.target_type = "entity"
    winner.target_id = entity.id
    winner.visibility = "crew"
    url = f"/api/campaigns/{v.campaign_id}/files/{winner.id}"
    if body.set_avatar:
        entity.image_url = url
    for a in rows:
        if a.id != winner.id:
            drop_files(a)
            db.delete(a)
    drop_job_attachments(db, job, JOB_TEMP)
    job.status = "done"
    db.commit()
    return {"ok": True, "image_url": entity.image_url, "attachment_url": url}


@router.delete("/image-jobs/{job_id}", tags=["images"], summary="Discard a portrait job", response_model=Ok)
def cancel_image_job(job_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)):
    """Delete the job with all its candidates. Open to whoever may edit the card."""
    job = get_own_job(db, v.campaign_id, job_id)
    job_entity_gate(db, v, job)
    drop_job_attachments(db, job, (CANDIDATE, SCENE_FRAME, *JOB_TEMP))
    db.delete(job)
    db.commit()
    return {"ok": True}


# --- worker: take a job, bring candidates, report an error ---------------------


def worker_auth(authorization: str | None = Header(default=None)) -> None:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not settings.worker_token or token != settings.worker_token:
        raise HTTPException(401, "invalid worker token")


class HeartbeatIn(BaseModel):
    comfy: str = "unknown"
    checkpoint: str | None = None
    inpaint_checkpoint: str | None = None
    job_id: str | None = None
    progress: str | None = None


@worker_router.post("/heartbeat")
def worker_heartbeat(body: HeartbeatIn, _: None = Depends(worker_auth)):
    # only the snapshot is stored; freshness is computed on read, so there is no expiry
    # writer and a backend restart is cured by the very first ping
    _worker_beat.clear()
    _worker_beat.update({
        "ts": time.time(),
        "comfy": body.comfy,
        "checkpoint": body.checkpoint,
        "inpaint_checkpoint": body.inpaint_checkpoint,
        "job": {"id": body.job_id, "progress": body.progress} if body.job_id else None,
    })
    return {"ok": True}


@worker_router.get("/image-jobs/next")
def next_image_job(
    caps: str = "", _: None = Depends(worker_auth), db: Session = Depends(get_db)
):
    """caps — what the worker can do, comma-separated. A worker without inpaint must not get
    an edit job: it would draw an ordinary image from its prompt and silently replace the frame."""
    can = {c.strip() for c in caps.split(",") if c.strip()}
    q = db.query(ImageGenJob).filter_by(status="pending")
    if "inpaint" not in can:
        q = q.filter(ImageGenJob.kind == "txt2img")
    if draw_conf(db):
        q = q.filter(ImageGenJob.kind != "txt2img")
    job = q.order_by(ImageGenJob.created_at).first()
    if not job:
        return {"job": None}
    claim_job(job)
    db.commit()
    return {"job": {
        "id": job.id, "campaign_id": job.campaign_id, "kind": job.kind or "txt2img",
        "prompt": job.prompt,
        "width": job.width, "height": job.height,
        "n_images": job.n_images or CANDIDATES_PER_JOB, "denoise": job.denoise,
        "seed": job.seed or 0,
        # a line per candidate (see candidate_prompts); empty means one line for all
        "prompts": (job.params or {}).get("prompts") or [],
    }}


def claim_job(job: ImageGenJob) -> None:
    job.status = "claimed"
    job.claimed_at = datetime.now(timezone.utc)
    job.attempts = (job.attempts or 0) + 1


def add_candidate(db: Session, job: ImageGenJob, data: bytes, filename: str, mime: str) -> None:
    folder = os.path.join(settings.upload_dir, job.campaign_id)
    os.makedirs(folder, exist_ok=True)
    stored = f"{uuid.uuid4()}{os.path.splitext(filename)[1][:12] or '.png'}"
    with open(os.path.join(folder, stored), "wb") as fh:
        fh.write(data)
    db.add(Attachment(
        campaign_id=job.campaign_id, filename=filename or stored, url=stored,
        mime=mime, size=len(data),
        target_type=CANDIDATE, target_id=job.id,
        visibility="selected",
        visible_to=[job.created_by] if job.created_by else [],
        uploaded_by=job.created_by,
    ))


def job_blob_row(db: Session, job_id: str, target_type: str) -> tuple[Attachment, str]:
    a = (
        db.query(Attachment)
        .filter_by(target_type=target_type, target_id=job_id)
        .first()
    )
    if not a:
        raise HTTPException(404, f"{target_type} not found")
    return a, os.path.join(settings.upload_dir, a.campaign_id, a.url)


def job_blob(db: Session, job_id: str, target_type: str) -> FileResponse:
    a, path = job_blob_row(db, job_id, target_type)
    if not os.path.exists(path):
        raise HTTPException(410, "file missing on disk")
    return FileResponse(path, media_type=a.mime, filename=a.filename)


@worker_router.get("/image-jobs/{job_id}/source")
def worker_job_source(
    job_id: str, _: None = Depends(worker_auth), db: Session = Depends(get_db)
):
    """Prepared copy of the source: its size is a multiple of 8 and matches the mask."""
    return job_blob(db, job_id, SOURCE)


@worker_router.get("/image-jobs/{job_id}/mask")
def worker_job_mask(
    job_id: str, _: None = Depends(worker_auth), db: Session = Depends(get_db)
):
    return job_blob(db, job_id, MASK)


@worker_router.get("/image-jobs/{job_id}/state")
def worker_job_state(
    job_id: str, _: None = Depends(worker_auth), db: Session = Depends(get_db)
):
    """Whether the job is alive: the GM may cancel it mid-batch — the worker checks between
    candidates and does not burn GPU on work already thrown away."""
    job = db.get(ImageGenJob, job_id)
    return {"status": job.status if job else "gone"}


@worker_router.post("/image-jobs/{job_id}/candidates")
async def upload_candidates(
    job_id: str,
    files: list[UploadFile] = File(...),
    _: None = Depends(worker_auth),
    db: Session = Depends(get_db),
):
    job = db.get(ImageGenJob, job_id)
    if not job or job.status != "claimed":
        raise HTTPException(404, "job not found or not claimed")
    if not files:
        raise HTTPException(400, "no files")
    # candidates await the decision of the job's author and are visible only to them (and the GM): card
    # jobs are no longer created only by the GM, so "gm" no longer fits them —
    # a player author got four broken images. The winner is opened by "pick"
    for f in files[:CANDIDATES_PER_JOB]:
        if f.content_type not in ALLOWED:
            raise HTTPException(415, f"unsupported type {f.content_type}")
        data = await f.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "file too large")
        if job.kind == "inpaint" and job.crop_box:
            data = stitch_candidate(db, job, data)
        add_candidate(db, job, data, f.filename or "", f.content_type)
    job.status = "ready"
    db.commit()
    return {"ok": True}


@worker_router.post("/image-jobs/{job_id}/fail")
def fail_image_job(
    job_id: str, error: str = Form(...), _: None = Depends(worker_auth),
    db: Session = Depends(get_db),
):
    job = db.get(ImageGenJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job.status != "claimed":
        # the job was already cancelled, recreated or picked up by the stuck-job sweeper — a stale
        # failure report must not kill work that is not its own
        return {"ok": False, "ignored": job.status}
    job.status = "failed"
    job.claimed_at = None
    job.error = error[:2000]
    db.commit()
    return {"ok": True}


# --- API drawing: the server takes txt2img jobs itself while no worker is drawing ---

HUB_IDLE = 3


def _job_status(job_id: str) -> str | None:
    db = SessionLocal()
    try:
        job = db.get(ImageGenJob, job_id)
        return job.status if job else None
    finally:
        db.close()


def hub_draw_once() -> bool:
    """One job from the hub. False means there is nothing to draw or nothing to draw with."""
    db = SessionLocal()
    lang = None
    try:
        conf = draw_conf(db)
        if not conf:
            return False
        # area edits go to the worker while it is alive (see next_image_job)
        kinds = ("txt2img",)
        if not worker_fresh() and can_edit(conf["base_url"]):
            kinds += ("inpaint",)
        job = (
            db.query(ImageGenJob)
            .filter(ImageGenJob.status == "pending", ImageGenJob.kind.in_(kinds))
            .order_by(ImageGenJob.created_at)
            .with_for_update(skip_locked=True)
            .first()
        )
        if not job:
            return False
        claim_job(job)
        db.commit()
        lang = use_campaign(job.campaign_id)
        count = job.n_images or CANDIDATES_PER_JOB
        variants = (job.params or {}).get("prompts") or [job.prompt]
        prompts = [variants[i % len(variants)] for i in range(count)]
        job_id, kind = job.id, job.kind
        _hub_job.update(id=job_id, job={"id": job_id, "progress": None})
        added: list[int] = []

        def got(data: bytes) -> None:
            db.expire_all()
            j = db.get(ImageGenJob, job_id)
            if j and j.status == "claimed":
                if kind == "inpaint":
                    data = stitch_candidate(db, j, data)
                add_candidate(db, j, data, f"candidate_{len(added)}.png", "image/png")
                db.commit()
                added.append(1)

        def alive() -> bool:
            return _job_status(job_id) == "claimed"

        try:
            unset = [ctr(f"content.draw_{name}") for name, value in
                     (("url", conf["base_url"]), ("key", conf["api_key"])) if not value]
            if unset:
                raise HubDrawError(ctr("content.draw_unset", names=", ".join(unset)))
            if kind == "inpaint":
                with open(job_blob_row(db, job_id, SOURCE)[1], "rb") as fh:
                    src_png = fh.read()
                with open(job_blob_row(db, job_id, MASK)[1], "rb") as fh:
                    mask_png = fh.read()
                edit(conf["base_url"], conf["api_key"], conf["model"], job.prompt,
                     src_png, mask_png, count, alive=alive, on_image=got)
            else:
                draw(conf["base_url"], conf["api_key"], conf["model"], prompts,
                     job.width, job.height, job.seed or 0, alive=alive, on_image=got)
            error = ""
            requeue = False
        except Exception as exc:  # noqa: BLE001 — any hub failure fails the job with a message
            if not isinstance(exc, HubDrawError):
                log.exception("hub draw %s", job_id)
            error = str(exc) if isinstance(exc, HubDrawError) else ctr("content.draw_failed", exc=brief(exc))
            requeue = isinstance(exc, NoEditing)
        db.expire_all()
        job = db.get(ImageGenJob, job_id)
        # the job may have been cancelled while the hub was drawing
        if not job or job.status != "claimed":
            return True
        # the service cannot edit — the edit waits for the worker, the service will not take it again (can_edit)
        if requeue and not added:
            job.status, job.claimed_at, job.attempts = "pending", None, (job.attempts or 1) - 1
            db.commit()
            return True
        # part of the batch is ready — there is a choice, the failure of the rest does not take it away
        if added:
            job.status = "ready"
        else:
            job.status, job.claimed_at = "failed", None
            job.error = (error or ctr("content.draw_none"))[:2000]
        db.commit()
        return True
    finally:
        if lang is not None:
            reset_campaign(lang)
        _hub_job.clear()
        db.close()


# housekeeping does not wait for requests: reading the feed or the badge changes nothing
HOUSEKEEP_EVERY = 10


def housekeeping() -> None:
    """Stuck worker jobs go back to the queue or to failed; expired drafts and news jobs are removed."""
    from .news import fail_stale_jobs

    db = SessionLocal()
    try:
        reap_stale_jobs(db)
        sweep_stale_drafts(db)
        fail_stale_jobs(db)
    finally:
        db.close()


def background_loop() -> None:
    last = 0.0
    while True:
        busy = False
        try:
            if time.time() - last >= HOUSEKEEP_EVERY:
                last = time.time()
                housekeeping()
            busy = hub_draw_once()
        except Exception as exc:  # noqa: BLE001 — the loop must not die
            log.warning("background: %s", exc)
        if not busy:
            time.sleep(HUB_IDLE)


def start_background() -> None:
    threading.Thread(target=background_loop, daemon=True, name="background").start()
