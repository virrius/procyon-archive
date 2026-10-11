from __future__ import annotations

import json
import os

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import history as journal
from ..api_schema import AUTH_ERRORS, Ok, error_responses
from ..db import get_db
from ..deps import gm_only
from ..i18n import ctr, instance_lang, tr
from ..models import Attachment, ContentBlock
from ..visibility import Viewer
from .files import drop_files

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["rules"], responses=AUTH_ERRORS)

# вырезки — кухня ГМа: и раздел, и его содержимое лежат в блоках с этим владельцем
OWNER = "rules"
SECTION, TEXT, SHOT, SEED = "section", "text", "shot", "seed"

# картинка вырезки: либо залитый файл (att:<id>), либо страница книги (media:<каталог>/<файл>).
# Каталог у страницы свой: у русской книги assets/rules, у английской — assets/rules_en,
# и вырезка помнит, из какой книги она, когда язык экземпляра сменится
ATT, MEDIA = "att:", "media:"
ASSETS = "/data/assets"


def rules_dir(lang: str | None = None) -> str:
    return "rules_en" if (lang or instance_lang()) == "en" else "rules"


def book_index(lang: str | None = None) -> dict:
    with open(os.path.join(ASSETS, rules_dir(lang), "index.json"), encoding="utf-8") as fh:
        return json.load(fh)


def page_ref(file: str, lang: str | None = None) -> str:
    return f"{MEDIA}{rules_dir(lang)}/{file}"


def page_src(content: str) -> str:
    """media:<каталог>/<файл> → путь картинки; без каталога — запись до двух книг, русская."""
    ref = content[len(MEDIA):]
    return f"/media/{ref}" if "/" in ref else f"/media/rules/{ref}"


class SectionIn(BaseModel):
    title: str = Field("", max_length=200, description="Section heading; empty → Untitled.",
                       examples=["Ship combat"])
    note: str = Field("", description="Free note shown under the heading.")


class SectionPatch(BaseModel):
    title: str | None = Field(None, max_length=200)
    note: str | None = None
    order: int | None = Field(None, description="Position among sections (ascending).")


class ItemIn(BaseModel):
    kind: Literal["text", "shot"] = Field(TEXT, description="`text` — a written clipping; `shot` — an image clipping.")
    title: str = Field("", max_length=200)
    text: str = Field("", description="The clipping itself (`text` kind only).")
    attachment_id: str = Field("", description="`shot` kind: id of an uploaded file (`POST /upload`). The file is re-attached to the section.")
    media: str = Field("", description="`shot` kind: a rendered book page, `file` from `GET /rules/book`. Either this or `attachment_id`.")


class ItemPatch(BaseModel):
    title: str | None = Field(None, max_length=200)
    text: str | None = Field(None, description="Applied to `text` clippings only.")
    order: int | None = Field(None, description="Position inside the section (ascending).")


class RulesItemOut(BaseModel):
    id: str
    kind: Literal["text", "shot"]
    title: str
    order: int
    text: str = Field(description="Clipping text; empty for `shot`.")
    src: str = Field(description="Image URL for `shot` (`/api/campaigns/{id}/files/{attachment_id}` or a `/media/…` book page); empty for `text`.")
    attachment_id: str = Field(description="Set when the image is an uploaded file; empty for book pages and text.")


class RulesSectionOut(BaseModel):
    id: str
    title: str
    note: str
    order: int
    items: list[RulesItemOut] = Field(default_factory=list)


class RulesSectionBriefOut(BaseModel):
    id: str
    title: str
    note: str
    order: int


class ReseedOut(BaseModel):
    restored: list[str] = Field(description="Titles of the book sections that were missing and came back.")


class BookPageOut(BaseModel):
    file: str = Field(description="File name to pass as `media` when adding a `shot` clipping.")
    label: str = Field(description="Page label from the book, may be empty.")
    src: str = Field(description="Image URL under `/media/`.")


class BookSectionOut(BaseModel):
    title: str
    pages: list[BookPageOut]


def blocks(db: Session, v: Viewer, kind: str | tuple[str, ...], parent: str | None = None):
    kinds = (kind,) if isinstance(kind, str) else kind
    q = (db.query(ContentBlock)
         .filter(ContentBlock.campaign_id == v.campaign_id,
                 ContentBlock.entity_type == OWNER,
                 ContentBlock.block_type.in_(kinds)))
    if parent is not None:
        q = q.filter(ContentBlock.entity_id == parent)
    return q.order_by(ContentBlock.order, ContentBlock.created_at).all()


def get_block(db: Session, v: Viewer, block_id: str, kind: str) -> ContentBlock:
    b = db.get(ContentBlock, block_id)
    if (not b or b.campaign_id != v.campaign_id or b.entity_type != OWNER
            or b.block_type != kind):
        raise HTTPException(404, tr("rules.not_found"))
    return b


def next_order(db: Session, v: Viewer, kind: str | tuple[str, ...], parent: str) -> int:
    rows = blocks(db, v, kind, parent)
    return (rows[-1].order + 1) if rows else 0


def make(v: Viewer, kind: str, parent: str, title: str, content: str, order: int):
    return ContentBlock(
        campaign_id=v.campaign_id, entity_type=OWNER, entity_id=parent,
        block_type=kind, title=title[:200], content=content, order=order,
        created_by=v.member_id, created_by_gm=True, visibility="gm",
    )


def item_out(b: ContentBlock, cid: str) -> dict:
    src, att_id = "", ""
    if b.block_type == SHOT:
        if b.content.startswith(ATT):
            att_id = b.content[len(ATT):]
            src = f"/api/campaigns/{cid}/files/{att_id}"
        elif b.content.startswith(MEDIA):
            src = page_src(b.content)
    return {"id": b.id, "kind": b.block_type, "title": b.title, "order": b.order,
            "text": b.content if b.block_type == TEXT else "",
            "src": src, "attachment_id": att_id}


def seed_from_book(db: Session, v: Viewer) -> None:
    """Первый заход: раскладываем страницы из assets/rules по разделам как есть.
    Дальше раздел живёт своей жизнью — ГМ правит и сносит что угодно, и второй раз
    мы не вмешиваемся: об этом помнит блок-отметка."""
    if blocks(db, v, SEED, ""):
        return
    db.add(make(v, SEED, "", ctr("content.rules_seeded"), "", 0))
    try:
        book = book_index()
    except (OSError, ValueError):
        return
    for i, sec in enumerate(book.get("sections", [])):
        section = make(v, SECTION, "", sec.get("title", ""), sec.get("note", ""), i)
        db.add(section)
        db.flush()
        for j, page in enumerate(sec.get("pages", [])):
            label = page.get("label", "")
            db.add(make(v, SHOT, section.id, ctr("content.page", label=label) if label else "",
                        page_ref(page.get("file", "")), j))


@router.get("/rules", summary="List rule sections with clippings", response_model=list[RulesSectionOut])
def list_rules(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Sections in order, each with its clippings. On the first call for a campaign the
    sections are seeded from the rendered rulebook (`assets/rules`); after that they are the GM's own."""
    seed_from_book(db, v)
    db.commit()
    return [
        {"id": s.id, "title": s.title, "note": s.content, "order": s.order,
         "items": [item_out(b, v.campaign_id) for b in blocks(db, v, (SHOT, TEXT), s.id)]}
        for s in blocks(db, v, SECTION, "")
    ]


@router.post("/rules/sections", summary="Create a rule section", response_model=RulesSectionOut)
def create_rules_section(body: SectionIn, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Appends an empty section at the end; writes a journal entry (`rules/section-add`)."""
    s = make(v, SECTION, "", body.title or ctr("content.untitled"), body.note,
             next_order(db, v, SECTION, ""))
    db.add(s)
    db.flush()
    journal.log(db, v, "rules", "section-add", target_id=s.id, title=s.title)
    db.commit()
    return {"id": s.id, "title": s.title, "note": s.content, "order": s.order, "items": []}


@router.patch("/rules/sections/{section_id}", summary="Rename or reorder a section",
              response_model=RulesSectionBriefOut)
def patch_rules_section(section_id: str, body: SectionPatch,
                        v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Only the keys sent are changed. Returns the section without its items."""
    s = get_block(db, v, section_id, SECTION)
    if body.title is not None:
        s.title = body.title[:200]
    if body.note is not None:
        s.content = body.note
    if body.order is not None:
        s.order = body.order
    db.commit()
    return {"id": s.id, "title": s.title, "note": s.content, "order": s.order}


@router.delete("/rules/sections/{section_id}", summary="Delete a section with its clippings",
               response_model=Ok)
def delete_rules_section(section_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Deletes the section and every clipping in it; uploaded files of image clippings are
    removed from disk, book pages stay. Journal entry `rules/section-delete`. `POST /rules/reseed`
    brings deleted book sections back."""
    s = get_block(db, v, section_id, SECTION)
    items = blocks(db, v, (SHOT, TEXT), s.id)
    journal.log(db, v, "rules", "section-delete", target_id=s.id, title=s.title,
                detail=ctr("content.clippings", n=len(items)),
                before={"title": s.title, "note": s.content,
                        "items": [b.title or b.content[:80] for b in items]})
    for b in items:
        forget_shot(db, v, b)
        db.delete(b)
    db.delete(s)
    db.commit()
    return {"ok": True}


def forget_shot(db: Session, v: Viewer, b: ContentBlock) -> None:
    """Залитый файл уходит вместе с вырезкой; страница книги остаётся на диске —
    она общая и вернётся, если ГМ снова добавит её в раздел."""
    if b.block_type != SHOT or not b.content.startswith(ATT):
        return
    a = db.get(Attachment, b.content[len(ATT):])
    if a and a.campaign_id == v.campaign_id:
        db.delete(a)
        db.flush()
        drop_files(a)


@router.post("/rules/reseed", summary="Restore missing book sections", response_model=ReseedOut,
             responses=error_responses(404))
def reseed_rules(v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Re-adds the rulebook sections that are currently absent (matched by title) with
    their pages; sections the GM edited are left as they are. 404 when the book pages are not
    rendered on this server."""
    try:
        book = book_index()
    except (OSError, ValueError):
        raise HTTPException(404, tr("rules.set_not_rendered")) from None
    have = {s.title for s in blocks(db, v, SECTION, "")}
    order = next_order(db, v, SECTION, "")
    back = []
    for sec in book.get("sections", []):
        title = sec.get("title", "")
        if title in have:
            continue
        section = make(v, SECTION, "", title, sec.get("note", ""), order)
        db.add(section)
        db.flush()
        for j, page in enumerate(sec.get("pages", [])):
            label = page.get("label", "")
            db.add(make(v, SHOT, section.id, ctr("content.page", label=label) if label else "",
                        page_ref(page.get("file", "")), j))
        journal.log(db, v, "rules", "section-restore", target_id=section.id, title=title)
        back.append(title)
        order += 1
    db.commit()
    return {"restored": back}


@router.get("/rules/book", summary="List rendered rulebook pages", response_model=list[BookSectionOut])
def list_rules_book_pages(v: Viewer = Depends(gm_only)):
    """GM only. The rulebook and playbook pages rendered on this server, grouped as in the book.
    Use `file` as `media` in `POST /rules/sections/{id}/items`. Empty list when nothing is rendered."""
    try:
        book = book_index()
    except (OSError, ValueError):
        return []
    return [
        {"title": sec.get("title", ""),
         "pages": [{"file": p.get("file", ""), "label": p.get("label", ""),
                    "src": page_src(page_ref(p.get("file", "")))}
                   for p in sec.get("pages", [])]}
        for sec in book.get("sections", [])
    ]


@router.post("/rules/sections/{section_id}/items", summary="Add a clipping to a section",
             response_model=RulesItemOut, responses=error_responses(404, 422))
def create_rules_item(section_id: str, body: ItemIn,
                      v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. `text` clipping: `title` + `text`. `shot` clipping: `attachment_id` (an uploaded
    file, which gets re-attached to the section) or `media` (a book page from `GET /rules/book`);
    neither → 422, unknown file/page → 404. Appended last; journal entry `rules/item-add`."""
    s = get_block(db, v, section_id, SECTION)
    order = next_order(db, v, (SHOT, TEXT), s.id)

    if body.kind == SHOT:
        if body.attachment_id:
            a = db.get(Attachment, body.attachment_id)
            if not a or a.campaign_id != v.campaign_id:
                raise HTTPException(404, tr("rules.attachment_missing"))
            a.target_type, a.target_id = OWNER, s.id
            content = f"{ATT}{a.id}"
        elif body.media:
            name = os.path.basename(body.media)
            if not os.path.exists(os.path.join(ASSETS, rules_dir(), name)):
                raise HTTPException(404, tr("rules.no_such_page"))
            content = page_ref(name)
        else:
            raise HTTPException(422, tr("rules.image_clip_source"))
    else:
        content = body.text

    b = make(v, SHOT if body.kind == SHOT else TEXT, s.id, body.title, content, order)
    db.add(b)
    db.flush()
    journal.log(db, v, "rules", "item-add", target_id=b.id, title=b.title or s.title,
                detail=s.title)
    db.commit()
    return item_out(b, v.campaign_id)


@router.patch("/rules/items/{item_id}", summary="Edit or reorder a clipping", response_model=RulesItemOut)
def patch_rules_item(item_id: str, body: ItemPatch,
                     v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. Only the keys sent are changed; `text` is ignored on image clippings."""
    b = db.get(ContentBlock, item_id)
    if (not b or b.campaign_id != v.campaign_id or b.entity_type != OWNER
            or b.block_type not in (TEXT, SHOT)):
        raise HTTPException(404, tr("rules.not_found"))
    if body.title is not None:
        b.title = body.title[:200]
    if body.text is not None and b.block_type == TEXT:
        b.content = body.text
    if body.order is not None:
        b.order = body.order
    db.commit()
    return item_out(b, v.campaign_id)


@router.delete("/rules/items/{item_id}", summary="Delete a clipping", response_model=Ok)
def delete_rules_item(item_id: str, v: Viewer = Depends(gm_only), db: Session = Depends(get_db)):
    """GM only. An uploaded image file is removed from disk; a book page stays. Journal entry
    `rules/item-delete`."""
    b = db.get(ContentBlock, item_id)
    if (not b or b.campaign_id != v.campaign_id or b.entity_type != OWNER
            or b.block_type not in (TEXT, SHOT)):
        raise HTTPException(404, tr("rules.not_found"))
    journal.log(db, v, "rules", "item-delete", target_id=b.id, title=b.title,
                before={"title": b.title, "content": b.content[:200]})
    forget_shot(db, v, b)
    db.delete(b)
    db.commit()
    return {"ok": True}
