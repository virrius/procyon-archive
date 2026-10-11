from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import history as journal
from ..api_schema import AUTH_ERRORS, VISIBLE_TO_DOC, Ok, Visibility, error_responses
from ..config import settings
from ..db import get_db
from ..deps import editor, viewer
from ..i18n import tr
from ..models import Attachment, Entity, Message
from ..visibility import Viewer, apply_scope, can_see, entity_editable, hidden_keys

router = APIRouter(prefix="/api/campaigns/{campaign_id}", tags=["files"], responses=AUTH_ERRORS)

ALLOWED = {
    "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
    "application/pdf", "audio/mpeg", "audio/ogg", "audio/wav", "text/plain",
}
MAX_BYTES = 25 * 1024 * 1024
# доска — холст ГМа: загруженное на неё стол не видит
BOARD_TARGETS = ("board", "board_card")

TargetType = Literal["entity", "message", "marker", "map", "clock", "board", "board_card", "scene_frame", "rules"]
CROP_DOC = ("Preview frame in pixels of the original, `\"x,y,w,h\"`; empty = whole image. "
            "The file is never cut, only thumbnails.")


class AttachmentOut(BaseModel):
    id: str
    filename: str
    mime: str
    caption: str
    target_type: str | None = Field(description="What the file hangs on: entity, message, marker, map, clock, board, board_card; `null` = loose.")
    target_id: str | None
    size: int = Field(description="Bytes.")
    visibility: Visibility | None = Field(default=None, description="GM only; `null` for players.")
    visible_to: list[str] = Field(default=[], description="GM only; empty for players.")
    uploaded_by: str | None = Field(default=None, description="Member id of the uploader.")
    crop_box: str = Field(default="", description=CROP_DOC)
    url: str = Field(description="`/api/campaigns/{campaign_id}/files/{id}` — the file itself (`?w=240|480|960` for a thumbnail).")
    created_at: datetime | None = None


class AttachmentPatch(BaseModel):
    """Only the keys sent change. Visibility, audience and caption: GM only. `crop_box`: GM, the uploader, or whoever may edit the record it hangs on."""

    visibility: Visibility | None = None
    visible_to: list[str] | None = Field(default=None, description=VISIBLE_TO_DOC)
    caption: str | None = Field(default=None, max_length=300)
    crop_box: str | None = Field(default=None, description=CROP_DOC, examples=["120,40,600,600"])


def attachment_item(a: Attachment, v: Viewer) -> dict:
    return {"id": a.id, "filename": a.filename, "mime": a.mime, "caption": a.caption,
            "target_type": a.target_type, "target_id": a.target_id, "size": a.size,
            "visibility": a.visibility if v.is_gm else None,
            "visible_to": (a.visible_to or []) if v.is_gm else [],
            "uploaded_by": a.uploaded_by, "crop_box": a.crop_box,
            "url": f"/api/campaigns/{v.campaign_id}/files/{a.id}", "created_at": a.created_at}


@router.post("/upload", summary="Upload a file", response_model=AttachmentOut,
             responses=error_responses(413, 415))
async def upload(
    file: UploadFile = File(..., description="png, jpeg, webp, gif, svg, pdf, mp3, ogg, wav or txt; 25 MB max."),
    target_type: TargetType | None = Form(default=None, description="What the file hangs on; omit for a loose file."),
    target_id: str | None = Form(default=None, description="Id of that target."),
    caption: str = Form(default=""),
    visibility: Visibility | None = Form(default=None, description=(
        "Omitted → `crew`: unlike other rows, a file follows its parent — one on a hidden card or an "
        "undelivered message stays hidden with it. Send `gm` to hide the file itself. A player's `gm` "
        "becomes `crew`; board uploads are always `gm`.")),
    v: Viewer = Depends(editor),
    db: Session = Depends(get_db),
):
    """Multipart upload. The answer carries `url` to use as an entity `image_url` or to download.
    Journal entry. 415: type not allowed. 413: over 25 MB."""
    if file.content_type not in ALLOWED:
        raise HTTPException(415, tr("files.unsupported_type", type=file.content_type))
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, tr("files.too_large"))
    # файл живёт при родителе: на закрытой карточке или в неотправленном письме его и так не видно,
    # а интерфейс грузит портреты и фоны карт без видимости — умолчание `crew`, как было
    visibility = visibility or "crew"
    if not v.is_gm and visibility == "gm":
        visibility = "crew"
    if target_type in BOARD_TARGETS:
        visibility = "gm"
    folder = os.path.join(settings.upload_dir, v.campaign_id)
    os.makedirs(folder, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1][:12]
    stored = f"{uuid.uuid4()}{ext}"
    with open(os.path.join(folder, stored), "wb") as fh:
        fh.write(data)
    a = Attachment(
        campaign_id=v.campaign_id,
        filename=file.filename or stored,
        url=stored,
        mime=file.content_type,
        size=len(data),
        target_type=target_type,
        target_id=target_id,
        caption=caption,
        visibility=visibility,
        uploaded_by=v.member_id,
    )
    db.add(a)
    db.flush()
    journal.log(db, v, "file", "upload", target_id=a.id, title=a.filename,
                entity_id=a.target_id if a.target_type == "entity" else None,
                detail=a.mime, visibility=a.visibility)
    db.commit()
    return attachment_item(a, v)


# ширины миниатюр, которые готовы отдавать: список закрыт, иначе первый обход
# страницы наплодит сотню перекодировок
THUMB_WIDTHS = (240, 480, 960)
THUMB_DIR = "thumb"


def crop_of(a: Attachment, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Рамка превью в пикселях картинки, обрезанная по её краям. Пусто или рамка во
    весь кадр — None: резать нечего."""
    if not (a.crop_box or ""):
        return None
    try:
        x, y, cw, ch = (int(round(float(n))) for n in a.crop_box.split(","))
    except (TypeError, ValueError):
        return None
    x, y = max(0, min(x, w - 1)), max(0, min(y, h - 1))
    cw, ch = min(cw, w - x), min(ch, h - y)
    if cw < 1 or ch < 1 or (x, y, cw, ch) == (0, 0, w, h):
        return None
    return x, y, cw, ch


def stored_path(a: Attachment) -> str | None:
    """Файл вложения на диске; None — url уводит из папки кампании."""
    folder = os.path.realpath(os.path.join(settings.upload_dir, a.campaign_id))
    path = os.path.realpath(os.path.join(folder, a.url or ""))
    return path if path.startswith(folder + os.sep) else None


def thumb_path(a: Attachment, width: int, cropped: bool = True) -> str | None:
    """Миниатюра нужной ширины, рисуется один раз и остаётся на диске рядом с файлом.
    Если у вложения задана рамка превью — миниатюра рисуется по ней, оригинал цел.

    `cropped=False` — миниатюра всего кадра: рамка про то, как снимок смотрится
    портретом карточки, а в списке вложений файл показываем как он есть."""
    src = stored_path(a)
    if not src or not a.mime.startswith("image/") or a.mime == "image/svg+xml":
        return None
    folder = os.path.join(settings.upload_dir, a.campaign_id, THUMB_DIR)
    dst = os.path.join(folder, f"{a.id}-{width}{'' if cropped else '-full'}.webp")
    if os.path.exists(dst):
        return dst
    try:
        from PIL import Image

        os.makedirs(folder, exist_ok=True)
        with Image.open(src) as im:
            box = crop_of(a, im.width, im.height) if cropped else None
            if box is None and im.width <= width:
                return None  # мельче запрошенного и без рамки — оригинал и есть миниатюра
            im = im.convert("RGB")
            if box:
                x, y, cw, ch = box
                im = im.crop((x, y, x + cw, y + ch))
            im.thumbnail((width, width * 4), Image.LANCZOS)
            im.save(dst, "WEBP", quality=82, method=4)
    except Exception:  # битый файл или нет кодека — отдадим оригинал
        return None
    return dst


def drop_thumbs(a: Attachment) -> None:
    """Убрать миниатюры, оставив оригинал: файл переписали, превью от старого."""
    folder = os.path.join(settings.upload_dir, a.campaign_id, THUMB_DIR)
    _remove(os.path.join(folder, f"{a.id}-{w}{tail}.webp")
            for w in THUMB_WIDTHS for tail in ("", "-full"))


def drop_files(a: Attachment) -> None:
    """Убрать оригинал и все его миниатюры."""
    path = stored_path(a)
    if path:
        _remove([path])
    drop_thumbs(a)


def _remove(paths) -> None:
    for path in paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


@router.get(
    "/files/{attachment_id}", summary="Download a file or its thumbnail", response_class=FileResponse,
    responses={
        200: {"content": {"image/*": {}, "application/pdf": {}, "audio/*": {}, "text/plain": {},
                          "application/octet-stream": {}},
              "description": "The file bytes (original mime), or an `image/webp` thumbnail when `w` is given."},
        **error_responses(404, 410),
    },
)
def get_file(
    attachment_id: str,
    w: int | None = Query(default=None, description="Thumbnail width: 240, 480 or 960 (images only; other values return the original)."),
    crop: int = Query(default=1, description="`1`: thumbnail inside the attachment's `crop_box`; `0`: thumbnail of the whole image."),
    v: Viewer = Depends(viewer),
    db: Session = Depends(get_db),
):
    """Binary answer, not JSON. Visibility of the attachment applies. Accepts `?token=` for
    `<img src>`. `Cache-Control: no-cache` so an edited crop box shows at once."""
    a = db.get(Attachment, attachment_id)
    if not a or a.campaign_id != v.campaign_id or not can_see(a, v):
        raise HTTPException(404, tr("files.not_found"))
    if not v.is_gm and a.target_type == "entity" and a.target_id:
        e = db.get(Entity, a.target_id)
        if e and e.campaign_id == a.campaign_id and hidden_portrait(e, a):
            raise HTTPException(404, tr("files.not_found"))
    path = stored_path(a)
    if not path:
        raise HTTPException(404, tr("files.not_found"))
    if not os.path.exists(path):
        raise HTTPException(410, tr("files.missing"))
    # рамку превью правят на месте, адрес файла при этом не меняется: без сверки
    # браузер держал бы старую миниатюру и кадрирование выглядело бы сломанным
    head = {"Cache-Control": "no-cache"}
    if w in THUMB_WIDTHS:
        small = thumb_path(a, w, cropped=bool(crop))
        if small:
            return FileResponse(small, media_type="image/webp", filename=a.filename,
                                headers=head)
    return FileResponse(path, media_type=a.mime, filename=a.filename, headers=head)


def hidden_portrait(e: Entity, a: Attachment) -> bool:
    """Портрет, закрытый ГМом от стола, не отдаём и как вложение карточки."""
    return ("image_url" in hidden_keys(e)
            and (e.image_url or "").split("?")[0].endswith(f"/files/{a.id}"))


def with_visible_targets(db: Session, v: Viewer, rows: list[Attachment]) -> list[Attachment]:
    """Вложение карточки или письма видно только вместе с ним."""
    if v.is_gm:
        return rows
    ids = {kind: [a.target_id for a in rows if a.target_type == kind and a.target_id]
           for kind in ("entity", "message")}
    ents = {e.id: e for e in db.query(Entity).filter(
        Entity.campaign_id == v.campaign_id, Entity.id.in_(ids["entity"]))} if ids["entity"] else {}
    msgs = {m.id: m for m in db.query(Message).filter(
        Message.campaign_id == v.campaign_id, Message.id.in_(ids["message"]))} if ids["message"] else {}

    def shown(a: Attachment) -> bool:
        if a.target_type in BOARD_TARGETS:
            return False
        if a.target_type == "entity":
            e = ents.get(a.target_id)
            return bool(e) and can_see(e, v) and not hidden_portrait(e, a)
        if a.target_type == "message":
            m = msgs.get(a.target_id)
            return bool(m) and m.status != "draft" and can_see(m, v)
        return True

    return [a for a in rows if shown(a)]


@router.get("/attachments", summary="List attachments", response_model=list[AttachmentOut])
def list_attachments(
    target_type: str | None = Query(default=None, description="Filter by what the file hangs on (entity, message, marker…)."),
    target_id: str | None = Query(default=None, description="Filter by the target's id."),
    limit: int | None = Query(None, ge=1, description="Page size; omitted — all."),
    offset: int = Query(0, ge=0),
    v: Viewer = Depends(viewer),
    db: Session = Depends(get_db),
):
    """Newest first. Players get only files whose own visibility and whose parent (record or
    delivered message) are open to them; board uploads are never listed to players.
    The page is cut before that filter, so a player's page may be shorter than `limit`."""
    q = db.query(Attachment).filter(Attachment.campaign_id == v.campaign_id)
    if target_type:
        q = q.filter(Attachment.target_type == target_type)
    if target_id:
        q = q.filter(Attachment.target_id == target_id)
    rows = (apply_scope(q, Attachment, v).order_by(Attachment.created_at.desc())
            .offset(offset).limit(limit).all())
    return [attachment_item(a, v) for a in with_visible_targets(db, v, rows)]


def can_crop(db: Session, a: Attachment, v: Viewer) -> bool:
    """Кадрировать превью может тот, кто правит саму карточку, и тот, кто принёс файл:
    рамка — оформление снимка, а не решение о том, кому его показывать."""
    if v.is_gm or (a.uploaded_by and a.uploaded_by == v.member_id):
        return True
    if a.target_type != "entity" or not a.target_id:
        return False
    e = db.get(Entity, a.target_id)
    return bool(e and e.campaign_id == v.campaign_id and entity_editable(e, v))


@router.get("/attachments/{attachment_id}", summary="Get an attachment's metadata", response_model=AttachmentOut)
def get_attachment(
    attachment_id: str, v: Viewer = Depends(viewer), db: Session = Depends(get_db)
):
    """Metadata only; the bytes are at `url`. 404 also when the file is closed to the viewer."""
    a = db.get(Attachment, attachment_id)
    if not a or a.campaign_id != v.campaign_id or not can_see(a, v):
        raise HTTPException(404, tr("files.not_found"))
    return attachment_item(a, v)


@router.patch("/attachments/{attachment_id}", summary="Update an attachment", response_model=AttachmentOut,
              responses=error_responses(403))
def patch_attachment(
    attachment_id: str,
    body: AttachmentPatch,
    v: Viewer = Depends(editor),
    db: Session = Depends(get_db),
):
    """Visibility, audience and caption are GM-only (403 for players); `crop_box` may be set by the
    GM, the uploader, or anyone who may edit the record the file hangs on. Changing the crop box
    drops cached thumbnails. Journal entry."""
    a = db.get(Attachment, attachment_id)
    if not a or a.campaign_id != v.campaign_id or not can_see(a, v):
        raise HTTPException(404, tr("files.not_found"))
    patch = body.model_dump(exclude_unset=True)
    # видимость вложения держит ГМ: файл лежит у него, стол его просто не видит
    if set(patch) - {"crop_box"} and not v.is_gm:
        raise HTTPException(403, tr("files.gm_only"))
    if "crop_box" in patch and not can_crop(db, a, v):
        raise HTTPException(403, tr("files.not_yours"))
    if "visibility" in patch:
        a.visibility = patch["visibility"] or "crew"
    if "visible_to" in patch:
        a.visible_to = list(patch["visible_to"] or [])
    if "caption" in patch:
        a.caption = str(patch["caption"] or "")[:300]
    # рамка превью правится в любой момент: оригинал цел, режем только миниатюры
    if "crop_box" in patch:
        a.crop_box = str(patch["crop_box"] or "").strip()[:60]
        drop_thumbs(a)
    journal.log(db, v, "file", "update", target_id=a.id, title=a.filename,
                entity_id=a.target_id if a.target_type == "entity" else None,
                detail=a.caption, visibility=a.visibility)
    db.commit()
    return attachment_item(a, v)


@router.delete("/attachments/{attachment_id}", summary="Delete an attachment", response_model=Ok,
               responses=error_responses(403))
def delete_attachment(
    attachment_id: str, v: Viewer = Depends(editor), db: Session = Depends(get_db)
):
    """Removes the row, the file and its thumbnails. GM deletes any; a player only what they
    uploaded (403 otherwise). Journal entry."""
    a = db.get(Attachment, attachment_id)
    if not a or a.campaign_id != v.campaign_id or not can_see(a, v):
        raise HTTPException(404, tr("files.not_found"))
    # свой файл убирает загрузивший, чужой — только ГМ
    if not v.is_gm and a.uploaded_by != v.member_id:
        raise HTTPException(403, tr("files.not_yours"))
    journal.log(db, v, "file", "delete", target_id=a.id, title=a.filename,
                entity_id=a.target_id if a.target_type == "entity" else None,
                detail=a.mime, visibility=a.visibility)
    db.delete(a)
    db.commit()
    drop_files(a)
    return {"ok": True}
