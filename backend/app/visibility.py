"""Server-side knowledge model.

Nothing a viewer is not allowed to see leaves the process: rows are filtered and
GM-only JSON fields (``gm_*``) are stripped before serialisation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Query

GM_PREFIX = "gm_"

SCOPES = ("crew", "selected", "owner", "gm")

# whose "only me" it is: for entities and clocks it is owner_member_id, for other rows the author
AUTHOR_COLUMNS = {
    "attachments": "uploaded_by",
    "content_blocks": "created_by",
    "entity_links": "created_by",
    "map_markers": "created_by",
    "map_strokes": "created_by",
}


def owner_attr(model_or_row: Any) -> Any:
    """Owner column of a model, or its value on a row; None means there is no owner."""
    name = AUTHOR_COLUMNS.get(getattr(model_or_row, "__tablename__", ""), "owner_member_id")
    return getattr(model_or_row, name, None)


class Viewer:
    """Effective audience. GM impersonating a player is a plain player here."""

    def __init__(
        self,
        user_id: str,
        campaign_id: str,
        member_id: str | None,
        role: str,
        is_real_gm: bool,
        acting_as: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.campaign_id = campaign_id
        self.member_id = member_id
        self.role = role
        self.is_real_gm = is_real_gm
        self.acting_as = acting_as

    @property
    def is_gm(self) -> bool:
        return self.role == "gm"

    @property
    def can_edit(self) -> bool:
        return self.role in ("gm", "player")


def can_see(obj: Any, viewer: Viewer, owner_member_id: str | None = None) -> bool:
    if viewer.is_gm:
        return True
    scope = getattr(obj, "visibility", "crew")
    if scope == "crew":
        return True
    owner = owner_member_id if owner_member_id is not None else owner_attr(obj)
    mine = bool(owner) and owner == viewer.member_id
    if scope == "selected":
        # the author never drops out of their own circle: "selected" with nobody checked acts like "only me"
        return mine or viewer.member_id in (getattr(obj, "visible_to", None) or [])
    if scope == "owner":
        return mine
    return False  # gm


def scope_filter(model, viewer: Viewer):
    """SQL-level predicate mirroring :func:`can_see` (JSONB containment for `selected`)."""
    if viewer.is_gm:
        return None
    conds = [model.visibility == "crew"]
    if viewer.member_id:
        conds.append(
            (model.visibility == "selected")
            & model.visible_to.contains([viewer.member_id])
        )
        owner = owner_attr(model)
        if owner is not None:
            conds.append(model.visibility.in_(("owner", "selected")) & (owner == viewer.member_id))
    return or_(*conds)


def apply_scope(q: Query, model, viewer: Viewer) -> Query:
    f = scope_filter(model, viewer)
    return q if f is None else q.filter(f)


def strip_gm_fields(fields: dict | None, viewer: Viewer) -> dict:
    fields = fields or {}
    if viewer.is_gm:
        return fields
    return {k: v for k, v in fields.items() if not k.startswith(GM_PREFIX)}


# what the GM may hide field by field, and what replaces the hidden value;
# an entry's name and kind are never hidden — otherwise it can't be recognized in a list
HIDEABLE: dict[str, Any] = {
    "image_url": "",
    "summary": "",
    "faction_ids": [],
    "location_ids": [],
}

# the crew's standing with a faction is visible to everyone who can see the entry itself
ALWAYS_OPEN: dict[str, frozenset[str]] = {"faction": frozenset({"stance", "deeds"})}


# the table always sees an entry's status
NEVER_HIDDEN = frozenset({"status"})


def hidden_keys(e) -> set[str]:
    """Keys of an entry hidden from the table field by field."""
    return {str(k) for k in (e.hidden_fields or [])} - ALWAYS_OPEN.get(e.kind, frozenset()) - NEVER_HIDDEN


SHARED_KINDS = ("ship",)  # shared crew resource — any player edits it, not only the owner
ANY_PLAYER = "*"  # special owner_member_id value: the GM opened the entry to any player


def entity_editable(e, v: Viewer) -> bool:
    """Editable by the GM, any player on a shared crew resource, the entry's owner —
    or any player if the GM opened the entry to everyone (owner_member_id == ANY_PLAYER)."""
    if v.is_gm or e.kind in SHARED_KINDS or e.owner_member_id == ANY_PLAYER:
        return True
    return bool(v.member_id) and e.owner_member_id == v.member_id


def public_entity(e, viewer: Viewer, peers: dict[str, str] | None = None) -> dict:
    hidden: set[str] = set() if viewer.is_gm else hidden_keys(e)
    fields = {k: v for k, v in strip_gm_fields(e.fields, viewer).items() if k not in hidden}
    data = {
        "id": e.id,
        "kind": e.kind,
        "name": e.name,
        "alias": e.alias,
        "summary": e.summary,
        "image_url": e.image_url,
        "status": e.status,
        "faction_ids": e.faction_ids or [],
        "location_ids": e.location_ids or [],
        "fields": fields,
        "owner_member_id": e.owner_member_id,
        "archived": e.archived,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }
    for key, blank in HIDEABLE.items():
        if key in hidden:
            data[key] = blank
    # names of linked entries: a link on an open entry stays readable even when
    # the linked entry itself is hidden from the table — it just can't be opened
    if peers is not None:
        linked = [*data["faction_ids"], *data["location_ids"], *(v for v in fields.values() if isinstance(v, str))]
        data["peer_names"] = {i: peers[i] for i in linked if i in peers}
    # the list of hidden keys goes to everyone: a player sees "unknown" instead of a blank
    data["hidden_fields"] = [k for k in (e.hidden_fields or []) if str(k) in hidden_keys(e)]
    # the entry's audience goes to whoever may edit it: otherwise the player's picker
    # shows the default "everyone" instead of the real scope and overwrites it on edit
    if entity_editable(e, viewer):
        data["visibility"] = e.visibility
        data["visible_to"] = e.visible_to or []
    return data
