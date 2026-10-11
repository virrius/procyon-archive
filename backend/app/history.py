from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .models import CampaignMember, Event
from .visibility import Viewer

SNAP_LEN = 4000  # снимок текста в журнале: полотна режем, лента не архив
TITLE_LEN = 200
DETAIL_LEN = 400


def _short(val: Any) -> Any:
    if isinstance(val, str):
        return val[:SNAP_LEN]
    if isinstance(val, (list, dict, int, float, bool)) or val is None:
        return val
    return str(val)[:SNAP_LEN]


def snapshot(data: dict | None) -> dict:
    return {k: _short(v) for k, v in (data or {}).items()}


def changes(obj: Any, patch: dict, keys: tuple[str, ...] | None = None) -> tuple[dict, dict]:
    """Что реально меняется. Вызывать до применения патча."""
    before: dict = {}
    after: dict = {}
    for key, val in patch.items():
        if keys is not None and key not in keys:
            continue
        old = getattr(obj, key, None)
        if old == val:
            continue
        before[key] = old
        after[key] = val
    return snapshot(before), snapshot(after)


def changes_map(old: dict, new: dict) -> tuple[dict, dict]:
    """То же, что changes, но для двух словарей (fields сущности, тело формы)."""
    before = {k: old.get(k) for k, val in new.items() if old.get(k) != val}
    after = {k: val for k, val in new.items() if old.get(k) != val}
    return snapshot(before), snapshot(after)


def actor_name(db: Session, v: Viewer) -> str:
    if not v.member_id:
        return ""
    m = db.get(CampaignMember, v.member_id)
    if not m:
        return ""
    name = (m.display_name or "").strip()
    if not name and m.user is not None:
        name = (m.user.display_name or m.user.login or "").strip()
    return name


def log(
    db: Session,
    v: Viewer,
    source: str,
    action: str,
    *,
    target_id: str = "",
    title: str = "",
    entity_id: str | None = None,
    detail: str = "",
    visibility: str = "",
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Строка журнала. Коммитит вызывающий — событие идёт той же транзакцией."""
    db.add(
        Event(
            campaign_id=v.campaign_id,
            source=source,
            action=action,
            actor_member_id=v.member_id or None,
            actor_name=actor_name(db, v),
            by_gm=v.is_real_gm and not v.acting_as,
            target_id=target_id or "",
            target_title=(title or "")[:TITLE_LEN],
            entity_id=entity_id,
            detail=(detail or "")[:DETAIL_LEN],
            visibility=visibility or "",
            before=snapshot(before),
            after=snapshot(after),
        )
    )
