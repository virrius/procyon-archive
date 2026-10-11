"""Новости сектора: отдельный раздел, куда ГМ выпускает депеши журналистов.

Депеши заказываются заданием и пишутся в фоне: ГМ может закрыть окно и вернуться
к черновикам потом — они ждут в задании, пока их не выпустят в эфир или не уберут.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from datetime import datetime as _dt
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import history as journal
from ..api_schema import AUTH_ERRORS, VISIBLE_TO_DOC, Ok, Visibility, default_visibility, error_responses, vis_field
from ..db import SessionLocal, get_db
from ..deps import gm_only, viewer
from ..i18n import ctr, tr
from ..models import Campaign, Clock, Entity, News, NewsJob
from ..langpack import prompting as P
from ..visibility import Viewer, apply_scope, can_see
from .dispatches import DraftIn, campaign_rows, check_draft, news_comments, open_locations, write_drafts
from .entities import peer_brief
from ..server_cfg import campaign_kit

log = logging.getLogger("news")
router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["news"], responses=AUTH_ERRORS)

# хаб отвечает за минуту; задание, которое пишется дольше, уже не допишется —
# сервер перезапускали или хаб завис
STALE = timedelta(minutes=10)


class Comment(BaseModel):
    """A reaction from a network dweller under the story."""

    handle: str = Field("", description="Network handle of the commenter.", examples=["@dockrat_77"])
    who: str = Field("", description="Who they are, in a few words.", examples=["cargo handler, Aketi station"])
    text: str = ""


LEAD_DOC = "One-line gist of the story. With `lead_hidden` the table gets an empty `lead` and reads the text itself."
JOURNALIST_DOC = (
    "Key of the journalist whose voice the story carries; keys and bylines come from `GET …/dispatch-options` "
    "(defaults: `lazarus`, `sterling`, `herald`). Empty — a story without a journalist."
)
LINKS_DOC = "the story is about. Ids that are not in this campaign are dropped silently; players see only links to rows open to them."


class NewsIn(BaseModel):
    headline: str = Field("", examples=["Legion seals the Aketi docks"])
    lead: str = Field("", description=LEAD_DOC)
    lead_hidden: bool = Field(False, description="Hide the lead from players.")
    body: str = Field("", description="Story text. At least one of headline/body must be non-empty (400).")
    comments: list[Comment] = Field([], description="Reactions shown under the story; `POST …/comments` generates them.")
    world_day: int | None = Field(default=None, ge=0, description="Game day of publication; omitted → the campaign's current day.")
    byline: str = Field("", description="Signature line under the story.")
    journalist: str = Field("", description=JOURNALIST_DOC)
    entity_ids: list[str] = Field([], description="Ids of campaign cards (entities) " + LINKS_DOC)
    clock_ids: list[str] = Field([], description="Ids of clocks " + LINKS_DOC)
    visibility: Visibility | None = vis_field()
    visible_to: list[str] = Field([], description=VISIBLE_TO_DOC)


class NewsPatch(BaseModel):
    """Only the keys sent are changed; `null` is ignored except on `world_day`. `journalist` is fixed at creation."""

    headline: str | None = None
    lead: str | None = Field(None, description=LEAD_DOC)
    lead_hidden: bool | None = None
    body: str | None = None
    comments: list[Comment] | None = None
    byline: str | None = None
    world_day: int | None = Field(default=None, ge=0)
    entity_ids: list[str] | None = Field(None, description="Ids of campaign cards (entities) " + LINKS_DOC)
    clock_ids: list[str] | None = Field(None, description="Ids of clocks " + LINKS_DOC)
    visibility: Visibility | None = Field(None, description="New audience.")
    visible_to: list[str] | None = Field(None, description=VISIBLE_TO_DOC)


class NewsJobIn(DraftIn):
    """Order for journalist drafts. With `manual` no LLM runs: the job is `ready` at once with one empty draft the GM writes by hand."""

    manual: bool = Field(False, description="Create one empty draft to write by hand instead of asking the LLM.")


class DraftPatch(BaseModel):
    """Keys of a draft to change; null/omitted keys stay."""

    headline: str | None = None
    lead: str | None = Field(None, description=LEAD_DOC)
    lead_hidden: bool | None = None
    text: str | None = Field(None, description="Draft body (becomes the story `body` on air).")
    comments: list[Comment] | None = None


class NewsLink(BaseModel):
    type: Literal["entity", "clock"]
    id: str
    name: str
    kind: str = Field(description="Entity kind, or `clock`.")
    image_url: str | None = Field(None, description="Entities only; empty when hidden from the viewer.")


class NewsOut(BaseModel):
    id: str
    headline: str
    lead: str = Field(description="Empty for players when `lead_hidden`.")
    body: str
    comments: list[Comment]
    byline: str
    journalist: str
    links: list[NewsLink] = Field(description="Linked entities and clocks the viewer can see.")
    world_day: int | None
    created_at: _dt
    lead_hidden: bool | None = Field(None, description="GM only.")
    visibility: Visibility | None = Field(None, description="GM only.")
    visible_to: list[str] | None = Field(None, description="GM only.")
    entity_ids: list[str] | None = Field(None, description="GM only: raw linked entity ids.")
    clock_ids: list[str] | None = Field(None, description="GM only: raw linked clock ids.")


class NewsDraftOut(BaseModel):
    i: int = Field(description="Index of the draft inside the job — the `{i}` in the draft routes. Stable: dropped and aired drafts keep their index.")
    lens: str | None = Field(None, description="Angle key the draft was written from (see `GET …/dispatch-options` → lenses).")
    angle: str | None = Field(None, description="The angle in the journalist's own words.")
    headline: str | None = None
    lead: str | None = None
    lead_hidden: bool | None = None
    text: str | None = None
    comments: list[Comment] | None = None
    manual: bool | None = Field(None, description="A hand-written draft (no LLM).")


class NewsJobOut(BaseModel):
    id: str
    status: Literal["pending", "ready", "failed"] = Field(description="`pending` — being written in the background (poll); `ready` — drafts await the GM; `failed` — see `error`, then `POST …/retry`.")
    journalist: str
    byline: str
    gm_text: str = Field(description="The GM's account of what happened.")
    links: list[NewsLink]
    lenses: list[str] = Field(description="Angle keys used, one per draft.")
    error: str
    created_at: _dt
    drafts: list[NewsDraftOut] = Field(description="Live drafts only: aired and dropped ones are omitted.")


class NewsJobsSummaryOut(BaseModel):
    pending: int = Field(description="Jobs still being written.")
    drafts: int = Field(description="Live drafts waiting for the GM.")
    failed: int


class AirOut(BaseModel):
    news: NewsOut = Field(description="The published story.")
    job: NewsJobOut | None = Field(description="The job with the draft marked aired; null when no live drafts remain (the job is closed).")


class DropDraftOut(BaseModel):
    job: NewsJobOut | None = Field(description="Null when the job closed with its last draft.")


class CommentsOut(BaseModel):
    comments: list[Comment]


def _links(db: Session, v: Viewer, rows: list) -> dict[str, list[dict]]:
    """Привязки новостей и заданий одним заходом. Стол видит только то, что ему открыто."""
    eids = {i for n in rows for i in (n.entity_ids or [])}
    cids = {i for n in rows for i in (n.clock_ids or [])}
    ents = {e.id: e for e in campaign_rows(db, Entity, v.campaign_id, list(eids))}
    clks = {c.id: c for c in campaign_rows(db, Clock, v.campaign_id, list(cids))}
    out = {}
    for n in rows:
        links = [{"type": "entity", "id": e.id, "name": e.name, "kind": e.kind,
                  "image_url": peer_brief(e, v)["image_url"]}
                 for e in (ents.get(i) for i in n.entity_ids or []) if e and can_see(e, v)]
        links += [{"type": "clock", "id": c.id, "name": c.name, "kind": "clock"}
                  for c in (clks.get(i) for i in n.clock_ids or []) if c and can_see(c, v)]
        out[n.id] = links
    return out


def _out(n: News, v: Viewer, links: list[dict]) -> dict:
    d = {"id": n.id, "headline": n.headline, "lead": n.lead if v.is_gm or not n.lead_hidden else "",
         "body": n.body, "comments": n.comments or [], "byline": n.byline,
         "journalist": n.journalist, "links": links, "world_day": n.world_day, "created_at": n.created_at}
    if v.is_gm:
        d.update(lead_hidden=n.lead_hidden, visibility=n.visibility, visible_to=n.visible_to or [],
                 entity_ids=n.entity_ids or [], clock_ids=n.clock_ids or [])
    return d


def _one(db: Session, v: Viewer, n: News) -> dict:
    return _out(n, v, _links(db, v, [n])[n.id])


def _get(db: Session, v: Viewer, news_id: str) -> News:
    n = db.get(News, news_id)
    if not n or n.campaign_id != v.campaign_id or not can_see(n, v):
        raise HTTPException(404, tr("news.not_found"))
    return n


def _clean_links(db: Session, v: Viewer, patch: dict) -> dict:
    """Привязки — только к записям этой кампании, без повторов."""
    if "entity_ids" in patch:
        patch["entity_ids"] = [e.id for e in campaign_rows(db, Entity, v.campaign_id, patch["entity_ids"])]
    if "clock_ids" in patch:
        patch["clock_ids"] = [c.id for c in campaign_rows(db, Clock, v.campaign_id, patch["clock_ids"])]
    return patch


def _publish(db: Session, v: Viewer, n: News) -> None:
    """Новость выходит в эфир сегодняшним игровым днём, если ГМ не задал другой."""
    if n.world_day is None:
        n.world_day = db.get(Campaign, v.campaign_id).world_day
    db.add(n)
    db.flush()
    journal.log(db, v, "news", "create", target_id=n.id, title=n.headline, detail=n.byline,
                visibility=n.visibility, after={"headline": n.headline, "body": n.body})


# --- задания: заказ депеш и черновики ----------------------------------------------


def _bylines(db: Session, campaign_id: str) -> dict[str, str]:
    kit = campaign_kit(db.get(Campaign, campaign_id))
    return {k: P().dispatch.byline(j, k) for k, j in P().dispatch.journalists_of(kit).items()}


def _expire(db: Session, jobs: list[NewsJob]) -> None:
    now = datetime.now(timezone.utc)
    hung = [j for j in jobs if j.status == "pending" and now - j.updated_at > STALE]
    for j in hung:
        j.status, j.error = "failed", ctr("content.news_silent")
    if hung:
        db.commit()


def _live(job: NewsJob) -> list[dict]:
    return [d for d in job.drafts or [] if not d.get("aired") and not d.get("dropped")]


def _job_out(job: NewsJob, links: list[dict], bylines: dict[str, str]) -> dict:
    keys = ("lens", "angle", "headline", "lead", "lead_hidden", "text", "comments", "manual")
    return {
        "id": job.id, "status": job.status, "journalist": job.journalist,
        "byline": bylines.get(job.journalist, job.journalist), "gm_text": job.gm_text,
        "links": links, "lenses": job.lenses or [], "error": job.error, "created_at": job.created_at,
        "drafts": [{"i": i, **{k: d.get(k) for k in keys}}
                   for i, d in enumerate(job.drafts or []) if not d.get("dropped") and not d.get("aired")],
    }


def _one_job(db: Session, v: Viewer, job: NewsJob) -> dict:
    return _job_out(job, _links(db, v, [job])[job.id], _bylines(db, v.campaign_id))


def _job(db: Session, v: Viewer, job_id: str) -> NewsJob:
    rows = campaign_rows(db, NewsJob, v.campaign_id, [job_id])
    if not rows:
        raise HTTPException(404, tr("news.job_closed"))
    return rows[0]


def _draft(job: NewsJob, i: int) -> list[dict]:
    """Копия черновиков задания: JSONB меняется только присваиванием нового списка."""
    drafts = [dict(d) for d in job.drafts or []]
    if not 0 <= i < len(drafts) or drafts[i].get("dropped"):
        raise HTTPException(404, tr("news.no_draft"))
    return drafts


def _settle(db: Session, job: NewsJob) -> bool:
    """Все черновики выпущены или убраны — заказ закрывается."""
    if job.status == "ready" and not _live(job):
        db.delete(job)
        return True
    return False


def run_job(job_id: str) -> None:
    """Фоновое написание депеш: своя сессия, итог — в самом задании."""
    db = SessionLocal()
    try:
        job = db.get(NewsJob, job_id)
        if not job or job.status != "pending":
            return
        try:
            out = write_drafts(db, job.campaign_id, DraftIn(
                gm_text=job.gm_text, entity_ids=job.entity_ids or [], clock_ids=job.clock_ids or [],
                journalist=job.journalist, lenses=job.lenses or []))
            job.drafts = [{**d, "aired": False} for d in out["dispatches"]]
            job.journalist, job.lenses = out["journalist"], out["lenses"]
            job.status, job.error = "ready", ""
        except HTTPException as exc:
            job.status, job.error = "failed", str(exc.detail)
        except Exception:
            log.exception("news job %s failed", job_id)
            job.status, job.error = "failed", ctr("content.news_failed")
        db.commit()
    finally:
        db.close()


@router.get("/news/jobs", summary="List journalist jobs", response_model=list[NewsJobOut])
def list_news_jobs(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. All jobs, newest first. Jobs stuck `pending` for over 10 minutes are marked `failed` here."""
    jobs = (db.query(NewsJob).filter(NewsJob.campaign_id == v.campaign_id)
            .order_by(NewsJob.created_at.desc()).all())
    _expire(db, jobs)
    links, bylines = _links(db, v, jobs), _bylines(db, v.campaign_id)
    return [_job_out(j, links[j.id], bylines) for j in jobs]


@router.get("/news/jobs/summary", summary="Count jobs and waiting drafts", response_model=NewsJobsSummaryOut)
def news_jobs_summary(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. How many jobs are being written, how many drafts wait, how many failed — for a menu badge."""
    jobs = db.query(NewsJob).filter(NewsJob.campaign_id == v.campaign_id).all()
    _expire(db, jobs)
    return {"pending": sum(j.status == "pending" for j in jobs),
            "drafts": sum(len(_live(j)) for j in jobs if j.status == "ready"),
            "failed": sum(j.status == "failed" for j in jobs)}


@router.post("/news/jobs", summary="Order journalist drafts", response_model=NewsJobOut,
             responses=error_responses(400))
def order_news_job(body: NewsJobIn, tasks: BackgroundTasks, v: Viewer = Depends(gm_only),
                   db: Session = Depends(get_db)):
    """GM only. Starts a background job: the LLM hub writes three drafts (one per lens) in the chosen
    journalist's voice from `gm_text` and the linked entities/clocks (only crew-visible blocks are fed to it).
    Returns the job with `status: pending`; poll `GET …/news/jobs/{job_id}` until `ready` or `failed`,
    then `air`, `edit` or `drop` each draft by its index `i`. With `manual: true` the job is `ready`
    immediately with one empty draft. 400 — unknown journalist, or neither text nor links given."""
    if body.manual:
        journalist = P().dispatch.pick_journalist(campaign_kit(db.get(Campaign, v.campaign_id)), body.journalist)
        if not journalist:
            raise HTTPException(400, tr("news.no_journalist"))
        status, drafts = "ready", [{"headline": "", "lead": "", "text": "", "comments": [],
                                    "manual": True, "aired": False}]
    else:
        journalist = check_draft(db, v.campaign_id, body)
        status, drafts = "pending", []
    job = NewsJob(campaign_id=v.campaign_id, status=status, journalist=journalist, gm_text=body.gm_text,
                  lenses=body.lenses, drafts=drafts,
                  **_clean_links(db, v, {"entity_ids": body.entity_ids, "clock_ids": body.clock_ids}))
    db.add(job)
    db.commit()
    if status == "pending":
        tasks.add_task(run_job, job.id)
    return _one_job(db, v, job)


@router.get("/news/jobs/{job_id}", summary="Get a job and its drafts", response_model=NewsJobOut)
def get_news_job(job_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. 404 once the job is closed (all drafts aired or dropped) or dropped."""
    job = _job(db, v, job_id)
    _expire(db, [job])
    return _one_job(db, v, job)


@router.patch("/news/jobs/{job_id}/drafts/{i}", summary="Edit a draft", response_model=NewsJobOut)
def edit_news_draft(job_id: str, i: int, body: DraftPatch, v: Viewer = Depends(gm_only),
                    db: Session = Depends(get_db)):
    """GM only. Changes the given keys of draft `i` (index from the job's `drafts[].i`). 404 — no such live draft."""
    job = _job(db, v, job_id)
    drafts = _draft(job, i)
    drafts[i].update(body.model_dump(exclude_none=True))
    job.drafts = drafts
    db.commit()
    return _one_job(db, v, job)


@router.post("/news/jobs/{job_id}/drafts/{i}/air", summary="Publish a draft to the table", response_model=AirOut,
             responses=error_responses(400))
def air_news_draft(job_id: str, i: int, body: DraftPatch, v: Viewer = Depends(gm_only),
                   db: Session = Depends(get_db)):
    """GM only. Applies the body's last-minute edits, then creates a news item (`visibility: crew`,
    `world_day` = current game day, journal `create`) from draft `i` and marks it aired.
    The job closes (`job: null`) when no live drafts remain. 400 — already aired, or headline and text both empty."""
    job = _job(db, v, job_id)
    drafts = _draft(job, i)
    d = drafts[i]
    if d.get("aired"):
        raise HTTPException(400, tr("news.already_aired"))
    d.update(body.model_dump(exclude_none=True))
    if not (str(d.get("headline") or "").strip() or str(d.get("text") or "").strip()):
        raise HTTPException(400, tr("news.empty_news"))
    n = News(campaign_id=v.campaign_id, headline=d.get("headline") or "", lead=d.get("lead") or "",
             lead_hidden=bool(d.get("lead_hidden")),
             body=d.get("text") or "", comments=d.get("comments") or [], byline=_bylines(db, v.campaign_id).get(job.journalist, ""), journalist=job.journalist,
             entity_ids=job.entity_ids or [], clock_ids=job.clock_ids or [])
    _publish(db, v, n)
    d.update(aired=True, news_id=n.id)
    job.drafts = drafts
    closed = _settle(db, job)
    db.commit()
    return {"news": _one(db, v, n), "job": None if closed else _one_job(db, v, job)}


@router.post("/news/jobs/{job_id}/drafts/{i}/comments", summary="Generate reactions for a draft",
             response_model=CommentsOut, responses=error_responses(502))
def draft_news_comments(job_id: str, i: int, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Asks the LLM hub for network reactions to draft `i` and stores them on the draft
    (replacing previous ones). Synchronous; 502 when the hub fails."""
    job = _job(db, v, job_id)
    drafts = _draft(job, i)
    d = drafts[i]
    d["comments"] = _comments(db, v, d.get("headline") or "", d.get("lead") or "", d.get("text") or "")
    job.drafts = drafts
    db.commit()
    return {"comments": d["comments"]}


@router.delete("/news/jobs/{job_id}/drafts/{i}", summary="Discard a draft", response_model=DropDraftOut)
def drop_news_draft(job_id: str, i: int, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Marks draft `i` dropped; the job closes (`job: null`) when it was the last live draft."""
    job = _job(db, v, job_id)
    drafts = _draft(job, i)
    drafts[i]["dropped"] = True
    job.drafts = drafts
    closed = _settle(db, job)
    db.commit()
    return {"job": None if closed else _one_job(db, v, job)}


@router.post("/news/jobs/{job_id}/retry", summary="Retry a failed job", response_model=NewsJobOut,
             responses=error_responses(400))
def retry_news_job(job_id: str, tasks: BackgroundTasks, v: Viewer = Depends(gm_only),
                   db: Session = Depends(get_db)):
    """GM only. A `failed` job goes back to `pending` and is written again. 400 — the job is not failed."""
    job = _job(db, v, job_id)
    if job.status != "failed":
        raise HTTPException(400, tr("news.nothing_to_retry"))
    job.status, job.error = "pending", ""
    db.commit()
    tasks.add_task(run_job, job.id)
    return _one_job(db, v, job)


@router.delete("/news/jobs/{job_id}", summary="Discard a job with its drafts", response_model=Ok)
def drop_news_job(job_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Deletes the job and every unaired draft; already aired stories stay."""
    db.delete(_job(db, v, job_id))
    db.commit()
    return {"ok": True}


# --- лента ------------------------------------------------------------------------


@router.get("/news", summary="List published news", response_model=list[NewsOut])
def list_news(v: Viewer = Depends(viewer), db: Session = Depends(get_db),
              limit: int | None = Query(None, ge=1, description="Page size; omitted → all."),
              offset: int = Query(0, ge=0)):
    """Stories visible to the viewer, newest first. Players get an empty `lead` where it is hidden."""
    q = db.query(News).filter(News.campaign_id == v.campaign_id)
    q = apply_scope(q, News, v).order_by(News.created_at.desc()).offset(offset)
    rows = (q.limit(limit) if limit else q).all()
    links = _links(db, v, rows)
    return [_out(n, v, links[n.id]) for n in rows]


@router.post("/news", summary="Publish a story by hand", response_model=NewsOut, responses=error_responses(400))
def create_news(body: NewsIn, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. A story written without a journalist job. Omitted `visibility` → `gm` (open it with
    `visibility: crew` to publish to the table); omitted `world_day` → current game day. Journal: `create`.
    400 — headline and body both empty."""
    if not (body.headline.strip() or body.body.strip()):
        raise HTTPException(400, tr("news.empty_news"))
    data = body.model_dump()
    data["visibility"] = default_visibility(v, body.visibility)
    n = News(campaign_id=v.campaign_id, **_clean_links(db, v, data))
    _publish(db, v, n)
    db.commit()
    return _one(db, v, n)


@router.patch("/news/{news_id}", summary="Edit a story", response_model=NewsOut)
def patch_news(news_id: str, body: NewsPatch, v: Viewer = Depends(gm_only),
               db: Session = Depends(get_db)):
    """GM only. Only the keys sent are changed. Journal: `update` (lead changes are not journaled —
    the table reads the journal)."""
    n = _get(db, v, news_id)
    patch = _clean_links(db, v, {k: val for k, val in body.model_dump(exclude_unset=True).items()
                                 if val is not None or k == "world_day"})
    # журнал видит стол: спрятанная суть в нём не светится
    before, after = journal.changes(n, patch, keys=tuple(k for k in patch if k not in ("lead", "lead_hidden")))
    for k, val in patch.items():
        setattr(n, k, val)
    if after:
        journal.log(db, v, "news", "update", target_id=n.id, title=n.headline, detail=n.byline,
                    visibility=n.visibility, before=before, after=after)
    db.commit()
    return _one(db, v, n)


def _comments(db: Session, v: Viewer, headline: str, lead: str, body: str) -> list[dict]:
    camp = db.get(Campaign, v.campaign_id)
    return news_comments(camp, campaign_kit(camp), open_locations(db, v.campaign_id),
                          headline=headline, lead=lead, body=body)


@router.post("/news/{news_id}/comments", summary="Generate reactions for a story", response_model=NewsOut,
             responses=error_responses(502))
def write_news_comments(news_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Asks the LLM hub for network reactions and replaces the story's `comments`. Synchronous; 502 when the hub fails."""
    n = _get(db, v, news_id)
    n.comments = _comments(db, v, n.headline, n.lead, n.body)
    db.commit()
    return _one(db, v, n)


@router.delete("/news/{news_id}", summary="Delete a story", response_model=Ok)
def delete_news(news_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Removes the story; journal `delete` keeps its headline and body."""
    n = _get(db, v, news_id)
    journal.log(db, v, "news", "delete", target_id=n.id, title=n.headline, detail=n.byline,
                visibility=n.visibility, before={"headline": n.headline, "body": n.body})
    db.delete(n)
    db.commit()
    return {"ok": True}
