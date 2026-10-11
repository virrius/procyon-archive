from __future__ import annotations

import logging

from sqlalchemy import text

from .db import engine

log = logging.getLogger("dbpatch")

# (table, column, type + null/default clause)
_COLUMNS: list[tuple[str, str, str]] = [
    ("content_blocks", "created_by_gm", "boolean not null default false"),
    ("content_blocks", "edited_by", "varchar(64) null"),
    ("content_blocks", "links", "jsonb not null default '[]'::jsonb"),
    # entity_links may survive from an older, narrower shape of the table
    ("entity_links", "label", "varchar(120) not null default ''"),
    ("entity_links", "created_by", "varchar(64) null"),
    ("entity_links", "visibility", "varchar(20) not null default 'crew'"),
    ("entity_links", "visible_to", "jsonb not null default '[]'::jsonb"),
    ("entities", "faction_ids", "jsonb not null default '[]'::jsonb"),
    ("entities", "location_ids", "jsonb not null default '[]'::jsonb"),
    ("entities", "hidden_fields", "jsonb not null default '[]'::jsonb"),
    ("entities", "gen_form", "jsonb not null default '{}'::jsonb"),
    ("board_cards", "key", "varchar(64) not null default ''"),
    ("board_cards", "clock_id", "varchar(64) null"),
    ("board_cards", "block_id", "varchar(64) null"),
    ("board_cards", "notes", "jsonb not null default '[]'::jsonb"),
    ("board_cards", "font_size", "integer not null default 14"),
    ("board_cards", "h", "double precision not null default 0"),
    ("board_cards", "ink", "jsonb not null default '[]'::jsonb"),
    ("messages", "sender_reveal", "boolean not null default false"),
    ("messages", "world_day", "integer null"),
    ("news", "entity_ids", "jsonb not null default '[]'::jsonb"),
    ("news", "clock_ids", "jsonb not null default '[]'::jsonb"),
    ("news", "lead", "text not null default ''"),
    ("news", "lead_hidden", "boolean not null default false"),
    ("news", "comments", "jsonb not null default '[]'::jsonb"),
    ("news", "world_day", "integer null"),
    ("map_markers", "icon", "varchar(20) not null default 'dot'"),
    ("clocks", "color", "varchar(20) not null default 'amber'"),
    ("clocks", "kind", "varchar(60) not null default ''"),
    ("clocks", "owner_member_id", "varchar(64) not null default '*'"),
    ("image_gen_jobs", "negative_prompt", "text not null default ''"),
    ("image_gen_jobs", "width", "integer not null default 768"),
    ("image_gen_jobs", "height", "integer not null default 960"),
    ("image_gen_jobs", "n_images", "integer not null default 4"),
    ("image_gen_jobs", "kind", "varchar(20) not null default 'txt2img'"),
    ("image_gen_jobs", "source_attachment_id", "varchar(64) null"),
    ("image_gen_jobs", "denoise", "double precision not null default 1.0"),
    ("image_gen_jobs", "crop_box", "varchar(60) not null default ''"),
    ("attachments", "crop_box", "varchar(60) not null default ''"),
    ("image_gen_jobs", "claimed_at", "timestamptz null"),
    ("image_gen_jobs", "attempts", "integer not null default 0"),
    ("campaigns", "img_meta_prompt", "text not null default ''"),
    ("campaigns", "img_object_prompt", "text not null default ''"),
    ("campaigns", "img_scene_prompt", "text not null default ''"),
    ("campaigns", "img_inpaint_prompt", "text not null default ''"),
    ("campaigns", "img_prompt_kit", "text not null default ''"),
    ("image_gen_jobs", "seed", "integer not null default 0"),
    ("image_gen_jobs", "params", "jsonb not null default '{}'::jsonb"),
    ("campaigns", "img_renderer", "varchar(20) not null default 'zimage'"),
    ("campaigns", "img_base_url", "varchar(300) not null default ''"),
    ("campaigns", "img_model", "varchar(100) not null default ''"),
    ("campaigns", "img_api_key", "varchar(200) not null default ''"),
    ("campaigns", "world_day", "integer not null default 0"),
    ("campaigns", "news_base_url", "varchar(300) not null default ''"),
    ("campaigns", "news_model", "varchar(100) not null default ''"),
    ("campaigns", "news_api_key", "varchar(200) not null default ''"),
    ("server_settings", "img_prose_person", "text not null default ''"),
    ("server_settings", "img_prose_frame", "text not null default ''"),
    ("server_settings", "img_prose_action", "text not null default ''"),
    ("server_settings", "draw_model", "varchar(100) not null default ''"),
    ("server_settings", "draw_kind", "varchar(20) not null default ''"),
    ("server_settings", "draw_base_url", "varchar(300) not null default ''"),
    ("server_settings", "draw_api_key", "varchar(200) not null default ''"),
    ("server_settings", "lang", "varchar(5) not null default ''"),
    ("users", "password_default", "boolean not null default false"),
    ("users", "token_version", "integer not null default 0"),
]

# осевые шаблоны промптов заменены единым редактируемым мета-промптом (см. Campaign.img_meta_prompt)
_DROP_TABLES: list[str] = ["prompt_templates"]

# img_llm_* переименованы в img_base_url/img_model/img_api_key под конвенцию OpenAI SDK
_DROP_COLUMNS: list[tuple[str, str]] = [
    # «режим тишины» кадров прожил недолго: ГМ убирает лишний кадр глазом в галерее
    ("campaigns", "frames_draft"),
    ("campaigns", "img_llm_url"),
    ("campaigns", "img_llm_model"),
    ("campaigns", "img_llm_key"),
]

# (index name, table, column) — matches what create_all would emit for a fresh DB
_INDEXES: list[tuple[str, str, str]] = [
    ("ix_entity_links_campaign_id", "entity_links", "campaign_id"),
    ("ix_entity_links_from_id", "entity_links", "from_id"),
    ("ix_entity_links_to_id", "entity_links", "to_id"),
    ("ix_content_blocks_entity_id", "content_blocks", "entity_id"),
    ("ix_content_blocks_entity_type", "content_blocks", "entity_type"),
    ("ix_board_cards_key", "board_cards", "key"),
    ("ix_clocks_kind", "clocks", "kind"),
    ("ix_image_gen_jobs_kind", "image_gen_jobs", "kind"),
]

_DROP_NOT_NULL: list[tuple[str, str]] = [
    # заявки на сцену не привязаны к карточке
    ("image_gen_jobs", "entity_id"),
]


def _statements() -> list[str]:
    out = [
        f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{column}" {ddl}'
        for table, column, ddl in _COLUMNS
    ]
    out += [
        f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({column})"
        for name, table, column in _INDEXES
    ]
    out += [
        f'ALTER TABLE {table} ALTER COLUMN "{column}" DROP NOT NULL'
        for table, column in _DROP_NOT_NULL
    ]
    out += [f"DROP TABLE IF EXISTS {table}" for table in _DROP_TABLES]
    out += [
        f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{column}"'
        for table, column in _DROP_COLUMNS
    ]
    return out


def patch_schema() -> None:
    """Idempotent DDL top-up for databases created before the current models."""
    for sql in _statements():
        # own transaction per statement: Postgres aborts the whole tx on any error
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as exc:
            log.warning("dbpatch skipped [%s]: %s", sql, exc)
