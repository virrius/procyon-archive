"""What the OpenAPI document says about itself: shared types, error shape, tags and the
guide an agent reads before its first call. Routers import from here so the vocabulary
(visibility scopes, error envelope, tag names) is one and the same everywhere."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

API_TITLE = "Procyon Archive API"
API_VERSION = "1.0.0"

Visibility = Literal["crew", "selected", "owner", "gm"]
Role = Literal["gm", "player", "observer"]

VISIBILITY_DOC = (
    "Who may see this row: `gm` — the GM only; `owner` — the owner or author; "
    "`selected` — members listed in `visible_to`; `crew` — the whole table. "
    "Omitted by a GM → `gm` (nothing leaks until opened on purpose); omitted by a player → `crew`. "
    "Players cannot set `gm`."
)
VISIBLE_TO_DOC = "Member ids (from `GET /campaigns/{campaign_id}` → `members[].id`) for `selected`."


def vis_field(description: str = VISIBILITY_DOC):
    """`visibility` input field: declared without a default so the schema does not promise `crew`
    while the server picks `gm` for a GM. Resolve the actual value with :func:`default_visibility`."""
    return Field(default=None, description=description)


def default_visibility(viewer, value: str | None) -> str:
    """The one rule for every content row: GM's unspecified row is GM-only, a player's is for the crew."""
    if value:
        return value
    return "gm" if viewer.is_gm else "crew"


class ErrorOut(BaseModel):
    """Every non-2xx answer: a human-readable reason in the request's language (`Accept-Language: ru|en`)."""

    detail: str = Field(description="What went wrong, for the caller to show or act on.")


class Ok(BaseModel):
    ok: bool = True


def error_responses(*codes: int) -> dict:
    """`responses=` for a router or an operation, by status code."""
    texts = {
        400: "Bad input (unknown kind, bad id, duplicate, text in the wrong alphabet), or a service this call needs is not configured (LLM hub: a server admin sets it with `PATCH /api/admin/hub`).",
        401: "No token, expired token or disabled account. Log in again.",
        403: "The role may not do this (player on a GM-only action, observer writing), or the account still has its default password: until it is changed, every call except `GET /auth/me` and `POST /auth/password` answers 403.",
        404: "Not found (a malformed id included) — or exists but is not visible to this viewer (the API does not tell which).",
        409: "State conflict: login taken, view-as-crew is read-only, job already running.",
        410: "The file behind this row is gone from disk.",
        413: "Upload too large.",
        415: "Unsupported media type.",
        422: "The request does not match the schema: `detail` names the field and the problem (`segments: must be ≤ 24`).",
        502: "The LLM hub or the drawing service is configured but failed to answer.",
    }
    return {c: {"model": ErrorOut, "description": texts.get(c, "")} for c in codes}


# default set for anything behind a login inside a campaign
AUTH_ERRORS = error_responses(401, 403, 404)

# --- tags: one per area, in the order the agent should meet them ---------------------------

TAGS: list[dict] = [
    {"name": "system", "description": "Health, instance language and the vocabulary (`/meta`). No login needed for `/health`, `/lang` and `/meta`."},
    {"name": "auth", "description": "Login → bearer token; who am I; change password."},
    {"name": "campaigns", "description": "Campaigns you belong to, members (their ids drive `visible_to` and `X-View-As`), game time, player accounts."},
    {"name": "entities", "description": (
        "Records of the campaign: characters, NPCs, factions, ships, locations, jobs, items. "
        "`kind` decides which `fields` keys and `status` values exist — read `GET /meta` → `kinds`. "
        "Anything without a field of its own (occupation, role, look) goes into `summary` (public) or a "
        "`gm_*` field / a block (secret). "
        "Keys starting with `gm_` are GM-only; `hidden_fields` hides single keys from players. "
        "`DELETE` archives, `DELETE …/purge` deletes for good."
    )},
    {"name": "blocks", "description": "Text blocks attached to an entity, clock, marker or map: descriptions, rumors, secrets. Each block has its own visibility."},
    {"name": "links", "description": "Directed, labelled links between two entities (`works for`, `where to find`). Each link has its own visibility."},
    {"name": "clocks", "description": "Progress clocks: `filled` of `segments`; tick, complete, reopen. Owner may be an entity."},
    {"name": "messages", "description": "In-fiction mail to the crew: drafts the GM delivers; per-member read/pinned state."},
    {"name": "news", "description": "Sector news: GM writes items or orders journalist drafts (a job), then airs them to the table."},
    {"name": "map", "description": "Sector maps with numbered markers and freehand strokes; markers may link to an entity."},
    {"name": "boards", "description": "Story boards — the GM's pinboard (cards, threads). GM only; canvas coordinates for the browser."},
    {"name": "boards-agent", "description": (
        "The same boards for a caller that cannot see the canvas: `GET /boards-dump` lists boards, "
        "`GET /boards/{id}/dump` is a readable snapshot (cards by key, grid cells), "
        "`POST /boards/{id}/batch` places a whole scene in one atomic request. "
        "Cards are addressed by a human key (`gregor-varg`); entities and clocks by **name** (ambiguous → 400 with candidates)."
    )},
    {"name": "files", "description": "Uploads and attachments (images, documents) on entities, messages, markers; the file itself at `/files/{id}`."},
    {"name": "images", "description": (
        "Portraits and campaign frames drawn by the local worker or an image API. Draft a prompt through the hub "
        "(`POST /image-prompt`), create a job, poll it until `ready`, pick a candidate. Unpicked candidates expire in 24 h."
    )},
    {"name": "frames", "description": "Campaign frames (scene images not tied to a card) and area edits by mask (inpaint)."},
    {"name": "workshop", "description": "Image workshop settings: wardrobe, registers, per-entity generation form, worker status."},
    {"name": "rules", "description": "Rulebook sections and clippings the GM keeps for the table."},
    {"name": "history", "description": "Campaign journal: who changed what; cursor-paged; filtered by the viewer's visibility."},
    {"name": "search", "description": "Full-text lookup across records, blocks, clocks and news — the way to turn a name into an id."},
    {"name": "admin", "description": "Server admin: LLM hub and prompts, users, campaign import/export, instance language."},
]

API_DESCRIPTION = """
Archive of a tabletop campaign (Scum & Villainy): records of people, factions, ships and places,
progress clocks, mail, sector news, maps, story boards, portraits and frames, rules.
The game master (GM) runs it; players see only what the GM has opened to them.

## Start here

1. `POST /api/auth/login` `{login, password}` → `token`. Send `Authorization: Bearer <token>` on every call.
2. `GET /api/meta` → the vocabulary: entity kinds with their `fields` and `statuses`, visibility scopes,
   block and message types. Read it once before writing anything.
3. `GET /api/campaigns` → the campaigns you belong to, with your `role` and `member_id`.
   Every content path lives under `/api/campaigns/{campaign_id}/…`.
4. `GET /api/campaigns/{campaign_id}` → `members` (their `id` is what `visible_to`, `owner_member_id`
   and `X-View-As` take) and the game day.

## Roles

`gm` sees and edits everything. `player` sees what is open to them and edits their own cards.
`observer` reads only. A GM may look through a player's eyes with the header
`X-View-As: crew` (what the whole table sees; writes are refused with 409) or `X-View-As: <member_id>`.

## Visibility — the spoiler rule

Every content row (entity, block, link, note, clock, message, news item, marker, stroke, attachment)
carries `visibility`: `gm` → GM only; `owner` → the owner/author; `selected` → members in `visible_to`;
`crew` → the whole table. **A GM who omits `visibility` gets `gm`.** Open a row on purpose, never by accident.
One exception: an uploaded file defaults to `crew` because it follows its parent — a file on a hidden card
or an undelivered message stays hidden with it.
Players cannot create `gm` rows. On entities, `fields` keys starting with `gm_` never reach players and
`hidden_fields` hides single keys (players see "unknown"). `owner_member_id` is a member id, or `"*"` so
any player may edit the card.

## Ids and lookup

Ids are UUID strings. To turn a name into an id: `GET …/entities?q=` (cards), `GET …/search?q=`
(cards, blocks, messages, news), `GET …/clocks`, `GET …/boards-dump`. Links are found from
either end: `GET …/entities/{entity_id}/links`. The boards batch takes entity and clock **names** directly.

## Writing

`POST` returns the created object (only the browser canvas writes `/board-cards` and `/board-edges`
answer with an id). `PATCH` takes only the keys to change and returns the object;
on entities `fields` merges key by key and `null` removes a key. Most writes land in the campaign
journal (`GET …/history`, GM only).

## Long operations

Portraits, frames and journalist drafts are jobs: `POST` creates one (`status: pending`), poll `GET`
until `ready` or `failed`, then `pick` / `keep` / `air`. Image prompts must be drafted through the hub
(`POST …/image-prompt`) and sent verbatim — prompts are accepted in Latin script only.

## Errors

Non-2xx answers are `{"detail": "…"}` in the request language (`Accept-Language: ru|en`, default = instance language):
400 bad input · 401 no or expired token · 403 the role may not · 404 not found or not visible ·
409 state conflict · 413/415 upload limits · 422 schema validation ·
502 LLM hub or drawing service failed. A 400 about the hub means it is not configured: check
`GET …/image-worker/status` → `hub` before drafting prompts.
""".strip()
