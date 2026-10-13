"""Drawing over an API. Two protocols: openai — the standard POST /images/generations, one request
per candidate; async — an asynchronous Image API (POST /images/generate → task →
polling → binary image), where all candidates of a batch are queued at once and awaited together.

Area editing (edit) exists only in the standard protocol: POST /images/edits with an image and
a mask, where transparent means repaint.

The admin doesn't choose the protocol: we try the standard one first, and if the service doesn't
know that URL (404/405 on the very first request), the async one. What the service understood is
remembered by its URL."""
from __future__ import annotations

import base64
import io
import logging
import math
import time

import httpx
from PIL import Image, ImageOps

from .i18n import ctr

log = logging.getLogger("hub_draw")

# aspect ratios the async API accepts: the others from its docs return 422
RATIOS = ("1:1", "9:16", "16:9")
# gpt-image sizes; a service that doesn't know them draws without size
OPENAI_SIZES = ("1024x1024", "1024x1536", "1536x1024")
POLL_EVERY = 2
TIMEOUT = 15 * 60


class HubDrawError(Exception):
    pass


class NoEndpoint(HubDrawError):
    """The service doesn't know the standard drawing URL — try the other protocol."""


class NoEditing(HubDrawError):
    """The service can't edit an area."""


# service URL → the protocol it answered to
PROTOCOLS: dict[str, str] = {}
# URLs where area editing returned 404/405
NO_EDITS: set[str] = set()


def nearest_ratio(width: int, height: int) -> str:
    want = math.log(width / height)
    return min(RATIOS, key=lambda r: abs(math.log(int(r.split(":")[0]) / int(r.split(":")[1])) - want))


def nearest_size(width: int, height: int) -> str:
    want = math.log(width / height)
    return min(OPENAI_SIZES, key=lambda s: abs(math.log(int(s.split("x")[0]) / int(s.split("x")[1])) - want))


def can_edit(base_url: str) -> bool:
    """Whether the configured service can edit an area: only the standard protocol can."""
    base = base_url.rstrip("/")
    return base not in NO_EDITS and PROTOCOLS.get(base, "openai") == "openai"


def brief(exc: Exception) -> str:
    """Failure reason without the service URL: players see this text too."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


def _failed(what: str, exc: Exception) -> HubDrawError:
    log.warning("drawing service: %s", exc)
    return HubDrawError(ctr(what, exc=brief(exc)))


def _detail(r: httpx.Response) -> str:
    try:
        j = r.json()
        err = j.get("error")
        return str(j.get("detail") or (err.get("message") if isinstance(err, dict) else err) or r.text)[:300]
    except ValueError:
        return r.text[:300]


def draw(base_url: str, api_key: str, model: str, prompts: list[str],
         width: int, height: int, seed: int, alive=lambda: True, on_image=lambda png: None) -> int:
    """One PNG per line of prompts, fitted to width×height by cropping; each finished
    one goes straight to on_image. alive tells whether the job is still alive: a cancelled one
    is not awaited. Returns how many images were delivered."""
    base = base_url.rstrip("/")
    args = (base, api_key, model, prompts, width, height, seed, alive, on_image)
    if PROTOCOLS.get(base, "openai") == "openai":
        try:
            done = draw_openai(*args)
            PROTOCOLS[base] = "openai"
            return done
        except NoEndpoint:
            pass
    PROTOCOLS[base] = "async"
    return draw_async(*args)


def draw_openai(base: str, api_key: str, model: str, prompts: list[str],
                width: int, height: int, seed: int, alive, on_image) -> int:
    size = nearest_size(width, height)
    done = 0
    with httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=300) as http:
        for prompt in prompts:
            if not alive():
                return done
            body = {"model": model, "prompt": prompt, "n": 1, "size": size}
            try:
                r = http.post(f"{base}/images/generations", json=body)
                if r.status_code == 400 and "size" in r.text:
                    body.pop("size")
                    r = http.post(f"{base}/images/generations", json=body)
            except httpx.HTTPError as exc:
                raise _failed("content.draw_no_answer", exc) from exc
            if r.status_code in (404, 405) and not done:
                raise NoEndpoint(ctr("content.draw_refused", code=r.status_code, detail=_detail(r)))
            if r.status_code != 200:
                raise HubDrawError(ctr("content.draw_refused", code=r.status_code, detail=_detail(r)))
            on_image(fit_png(_openai_image(r), width, height))
            done += 1
    return done


def _openai_image(r: httpx.Response) -> bytes:
    item = (r.json().get("data") or [{}])[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        try:
            return httpx.get(item["url"], timeout=120).raise_for_status().content
        except httpx.HTTPError as exc:
            raise _failed("content.draw_no_download", exc) from exc
    raise HubDrawError(ctr("content.draw_no_image"))


def edit(base_url: str, api_key: str, model: str, prompt: str,
         source_png: bytes, mask_png: bytes, count: int,
         alive=lambda: True, on_image=lambda png: None) -> int:
    """count variants of editing an area of source_png by mask (white means repaint), each
    fitted to the source size and sent straight to on_image. Returns how many were delivered."""
    base = base_url.rstrip("/")
    if not can_edit(base):
        raise NoEditing(ctr("content.edit_unsupported"))
    with Image.open(io.BytesIO(source_png)) as im:
        width, height = im.size
    files = {
        "image": ("source.png", source_png, "image/png"),
        "mask": ("mask.png", openai_mask(mask_png), "image/png"),
    }
    data = {"model": model, "prompt": prompt, "n": "1", "size": nearest_size(width, height)}
    done = 0
    with httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=300) as http:
        for _ in range(count):
            if not alive():
                return done
            body = dict(data)
            try:
                r = http.post(f"{base}/images/edits", data=body, files=files)
                if r.status_code == 400 and "size" in r.text:
                    body.pop("size")
                    r = http.post(f"{base}/images/edits", data=body, files=files)
            except httpx.HTTPError as exc:
                raise _failed("content.draw_no_answer", exc) from exc
            if r.status_code in (404, 405) and not done:
                NO_EDITS.add(base)
                raise NoEditing(ctr("content.edit_unsupported"))
            if r.status_code != 200:
                raise HubDrawError(ctr("content.draw_refused", code=r.status_code, detail=_detail(r)))
            PROTOCOLS[base] = "openai"
            on_image(fit_png(_openai_image(r), width, height))
            done += 1
    return done


def openai_mask(mask_png: bytes) -> bytes:
    """The standard API mask is RGBA where transparent means repaint; ours is white.
    The model reads a blurred edge as permission to draw past the border, so
    alpha is hard; a soft seam comes from compositing with the original mask on our side."""
    with Image.open(io.BytesIO(mask_png)) as mi:
        alpha = mi.convert("L").point(lambda p: 0 if p >= 128 else 255)
        out = Image.new("RGBA", mi.size, (0, 0, 0, 255))
        out.putalpha(alpha)
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def draw_async(base: str, api_key: str, model: str, prompts: list[str],
                    width: int, height: int, seed: int, alive, on_image) -> int:
    headers = {"Authorization": f"Bearer {api_key}"}
    ratio = nearest_ratio(width, height)
    with httpx.Client(headers=headers, timeout=60) as http:
        uids = []
        for i, prompt in enumerate(prompts):
            options = {"aspect_ratio": ratio}
            if seed:
                options["seed"] = seed + i
            try:
                r = http.post(f"{base}/images/generate",
                              json={"model": model, "prompt": prompt, "translate": False, "options": options})
            except httpx.HTTPError as exc:
                raise _failed("content.draw_no_answer", exc) from exc
            if r.status_code != 200:
                raise HubDrawError(ctr("content.draw_refused", code=r.status_code, detail=_detail(r)))
            uids.append(r.json()["task_uid"])

        done: set[str] = set()
        deadline = time.time() + TIMEOUT
        while len(done) < len(uids):
            if time.time() > deadline:
                raise HubDrawError(ctr("content.draw_timeout", min=TIMEOUT // 60))
            if not alive():
                return len(done)
            time.sleep(POLL_EVERY)
            for uid in uids:
                if uid in done:
                    continue
                try:
                    st = http.get(f"{base}/images/tasks/{uid}")
                    # the service may not find a fresh task for a while
                    if st.status_code == 404:
                        continue
                    st.raise_for_status()
                    task = st.json()
                    if task.get("status") in ("failed", "error"):
                        raise HubDrawError(ctr("content.draw_task_failed", why=task.get('error') or task.get('status')))
                    if task.get("status") != "finished":
                        continue
                    res = http.get(f"{base}/images/tasks/{uid}/result")
                    res.raise_for_status()
                except httpx.HTTPError as exc:
                    raise _failed("content.draw_no_download", exc) from exc
                done.add(uid)
                on_image(fit_png(res.content, width, height))
    return len(done)


def fit_png(data: bytes, width: int, height: int) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img = ImageOps.fit(img, (width, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
