from __future__ import annotations

import logging

from sqlalchemy import text

from .db import engine

log = logging.getLogger("dbpatch")

# The schema of live databases catches up with the models: create_all adds new tables, while columns
# added to or removed from the models are patched here. Every entry is idempotent;
# entries that have already run on all known databases are removed from here.

# (table, column, type + null/default clause)
_COLUMNS: list[tuple[str, str, str]] = [
    ("campaigns", "sheet_setup", "JSONB NOT NULL DEFAULT '{}'::jsonb"),
]

_DROP_TABLES: list[str] = [
    # discussion "notes": the UI was removed on 2026-10-09, the table is empty on both instances
    "notes",
    # old-style clock ticks: clock history has long been read from the event log
    "clock_events",
]

_DROP_COLUMNS: list[tuple[str, str]] = [
    # slot-assembly instructions and the renderer: there is now one assembly, in prose
    ("campaigns", "img_meta_prompt"),
    ("campaigns", "img_object_prompt"),
    ("campaigns", "img_scene_prompt"),
    ("campaigns", "img_inpaint_prompt"),
    ("campaigns", "img_renderer"),
    ("server_settings", "img_meta_prompt"),
    ("server_settings", "img_object_prompt"),
    ("server_settings", "img_scene_prompt"),
    # the hub is a server setting, campaigns no longer have it
    ("campaigns", "img_base_url"),
    ("campaigns", "img_model"),
    ("campaigns", "img_api_key"),
    ("campaigns", "news_base_url"),
    ("campaigns", "news_model"),
    ("campaigns", "news_api_key"),
    # the drawing model doesn't read the negative prompt (Z-Image, cfg 1.0)
    ("image_gen_jobs", "negative_prompt"),
    # fields nobody reads: knowledge status and the map layout of earlier versions
    ("entities", "knowledge_status"),
    ("entity_links", "knowledge_status"),
    ("content_blocks", "knowledge_status"),
    ("clocks", "knowledge_status"),
    ("messages", "knowledge_status"),
    ("news", "knowledge_status"),
    ("map_nodes", "knowledge_status"),
    ("map_markers", "knowledge_status"),
    ("map_strokes", "knowledge_status"),
    ("attachments", "knowledge_status"),
    ("map_nodes", "order"),
    ("map_nodes", "x"),
    ("map_nodes", "y"),
    ("map_nodes", "node_kind"),
    ("map_nodes", "color"),
    ("map_markers", "orbit"),
    ("map_markers", "status"),
    ("map_markers", "layer"),
    ("map_strokes", "layer"),
]


def _statements() -> list[str]:
    out = [
        f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}" {ddl}'
        for table, column, ddl in _COLUMNS
    ]
    out += [f"DROP TABLE IF EXISTS {table}" for table in _DROP_TABLES]
    out += [
        f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{column}"'
        for table, column in _DROP_COLUMNS
    ]
    return out


def patch_schema() -> None:
    """Bring a live database schema up to date. A failed statement is an error in the log: a silently skipped ALTER
    would surface later as a failed insert."""
    for sql in _statements():
        # one transaction per statement: after an error Postgres rolls back the whole transaction
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            log.exception("dbpatch failed [%s]", sql)
