"""News drafts: a sector event through the eyes of one of the campaign's journalists."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, object_session

from ..api_schema import AUTH_ERRORS
from ..db import get_db
from ..deps import gm_only
from ..i18n import tr
from ..models import Campaign, Clock, ContentBlock, Entity
from ..langpack import prompting


def D():
    return prompting().dispatch


from ..visibility import Viewer
from ..server_cfg import campaign_kit, hub_conf
from .images import hub_call

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["news"], responses=AUTH_ERRORS)


class DraftIn(BaseModel):
    """What happened, in the GM's words, plus the records the story is about. Journalist and lenses are optional."""

    gm_text: str = Field("", description="The event as the GM tells it; the journalist rewrites it in their voice. Required unless entities or clocks are linked.",
                         examples=["The Legion impounded the crew's freighter at Aketi docks over forged manifests."])
    entity_ids: list[str] = Field([], description="Entities the story is about; only their crew-visible blocks reach the LLM. Unknown ids are dropped.")
    clock_ids: list[str] = Field([], description="Clocks the story is about (their owners count as involved).")
    journalist: str = Field("", description="Journalist key from `GET …/dispatch-options`; empty → one is picked.")
    lenses: list[str] = Field([], description="Angle keys from `GET …/dispatch-options` → `lenses`, one per draft (three drafts); empty → picked at random.")


class JournalistOut(BaseModel):
    key: str = Field(description="Value for `journalist` in a job or story.")
    title: str = Field(description="Name and stance, for a picker.")
    byline: str = Field(description="Signature line that goes under the story.")
    signature: str


class LensOut(BaseModel):
    key: str = Field(description="Value for `lenses[]` in a job.")
    text: str = Field(description="What the angle means.")


class DispatchOptionsOut(BaseModel):
    journalists: list[JournalistOut]
    lenses: list[LensOut]


def valid_ids(ids: list[str]) -> list[str]:
    """Only real uuids, no repeats, in the order picked: a malformed id would crash the database query."""
    out = []
    for raw in ids:
        try:
            key = str(uuid.UUID(str(raw)))
        except ValueError:
            continue
        if key not in out:
            out.append(key)
    return out


def campaign_rows(db: Session, model, campaign_id: str, ids: list[str]) -> list:
    ids = valid_ids(ids)
    if not ids:
        return []
    rows = {r.id: r for r in db.query(model).filter(model.campaign_id == campaign_id, model.id.in_(ids))}
    return [rows[i] for i in ids if i in rows]


@router.get("/dispatch-options", summary="Journalists and lenses to order from", response_model=DispatchOptionsOut)
def dispatch_options(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. The campaign's journalists (voice of a story) and lenses (angle of a draft) — the keys
    `POST …/news/jobs` accepts. Read before ordering drafts."""
    kit = campaign_kit(db.get(Campaign, v.campaign_id))
    return {
        "journalists": [{"key": k, "title": str(j.get("title") or k), "byline": D().byline(j, k),
                         "signature": str(j.get("signature") or "")}
                        for k, j in D().journalists_of(kit).items()],
        "lenses": [{"key": k, "text": t} for k, t in D().lenses_of(kit).items()],
    }


def check_draft(db: Session, campaign_id: str, body: DraftIn) -> str:
    """The order is doable: the journalist exists and there is something to write about. Returns the journalist key."""
    kit = campaign_kit(db.get(Campaign, campaign_id))
    journalist = D().pick_journalist(kit, body.journalist)
    if not journalist:
        raise HTTPException(400, tr("news.no_journalist"))
    if not (body.gm_text.strip() or campaign_rows(db, Entity, campaign_id, body.entity_ids)
            or campaign_rows(db, Clock, campaign_id, body.clock_ids)):
        raise HTTPException(400, tr("news.need_input"))
    return journalist


def open_locations(db: Session, campaign_id: str) -> list[Entity]:
    """Places open to the table: the journalist and the locals take planets and stations only from these."""
    return (db.query(Entity)
            .filter(Entity.campaign_id == campaign_id, Entity.kind == "location",
                    Entity.visibility == "crew", Entity.archived.is_(False))
            .order_by(Entity.name).all())


def news_hub(camp: Campaign) -> dict:
    """What writes dispatches and comments: the server hub with the news model."""
    return {**hub_conf(object_session(camp), "news"),
            "timeout": D().DISPATCH_TIMEOUT, "stop": D().DISPATCH_STOP,
            "attempts": D().DISPATCH_ATTEMPTS, "temperature": D().TEMPERATURE}


def news_comments(camp: Campaign, kit: dict, locations: list, *, headline: str = "", lead: str = "",
                  body: str = "") -> list[dict]:
    """Five comments from net locals on a story."""
    system, text = D().comments_prompt(kit, headline=headline, lead=lead, body=body, locations=locations)
    parsed = hub_call(camp, system, text, D().COMMENTS_SCHEMA, max_tokens=D().COMMENTS_MAX_TOKENS, **news_hub(camp))
    return D().clean_comments(parsed.get("comments"))


def write_drafts(db: Session, campaign_id: str, body: DraftIn) -> dict:
    """Three dispatches about an event. Writes nothing to the database: the GM decides what goes on the air."""
    journalist = check_draft(db, campaign_id, body)
    camp = db.get(Campaign, campaign_id)
    kit = campaign_kit(camp)
    staff = D().journalists_of(kit)[journalist]

    clocks = campaign_rows(db, Clock, campaign_id, body.clock_ids)
    entities = campaign_rows(db, Entity, campaign_id, body.entity_ids)
    # whoever's plan is on the clock is involved too, even if the GM did not link them
    owners = campaign_rows(db, Entity, campaign_id,
                           [c.owner_id for c in clocks if c.owner_type == "entity" and c.owner_id])
    entities += [o for o in owners if o.id not in {e.id for e in entities}]

    names = {e.id: e.name for e in entities}
    goals = [(c, names.get(c.owner_id, "") if c.owner_type == "entity" else "") for c in clocks]
    known = []
    for e in entities:
        # only what is open to the table: the model cannot keep backstage material secret and retells it
        blocks = (db.query(ContentBlock)
                  .filter_by(campaign_id=campaign_id, entity_type="entity",
                             entity_id=e.id, visibility="crew")
                  .order_by(ContentBlock.order, ContentBlock.created_at).all())
        known.append((e, blocks))
    locations = open_locations(db, campaign_id)

    lenses = D().pick_lenses(kit, body.lenses)
    system, text = D().dispatch_prompt(kit, journalist, gm_text=body.gm_text, entities=known, goals=goals,
                                   locations=locations, lenses=lenses)
    parsed = hub_call(camp, system, text, D().DISPATCH_SCHEMA, max_tokens=D().MAX_TOKENS, **news_hub(camp))
    items = [d for d in (parsed.get("dispatches") or []) if isinstance(d, dict)][:3]
    lead = D().clean(parsed.get("lead"))
    texts = D().compose(lead, items, str(staff.get("signature") or ""))
    # comments are shared by the three drafts — about the gist, not one dispatch; if they fail, the draft has a button
    try:
        comments = news_comments(camp, kit, locations, lead=lead)
    except HTTPException:
        comments = []
    return {
        "dispatches": [
            {"lens": lenses[i] if i < len(lenses) else "", "angle": D().clean(d.get("angle")),
             "headline": D().clean(d.get("headline")), "lead": lead, "text": texts[i],
             "comments": [dict(x) for x in comments]}
            for i, d in enumerate(items)
        ],
        "journalist": journalist,
        "lenses": lenses,
    }
