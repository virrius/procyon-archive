import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from psycopg.errors import StringDataRightTruncation
from sqlalchemy.exc import DataError

from .api_schema import API_DESCRIPTION, API_TITLE, API_VERSION, TAGS, error_responses
from .db import Base, engine
from .dbpatch import patch_schema
from . import i18n
from .routers import (
    admin,
    auth,
    boards,
    boards_agent,
    campaigns,
    clocks,
    comms,
    dispatches,
    entities,
    files,
    history,
    images,
    misc,
    news,
    rules,
    worldmap,
)
from .seed import ensure_admin


def operation_id(route: APIRoute) -> str:
    """Function name as operationId: tool generators take it as the tool name (≤64 chars)."""
    return route.name


# docs and the schema under /api: the web proxy forwards only that prefix
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    openapi_tags=TAGS,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    generate_unique_id_function=operation_id,
    # 422 тоже `{"detail": "…"}`: схема ошибки валидации одна на все ручки
    responses=error_responses(422),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

CAMPAIGN_PATH = re.compile(r"^/api/campaigns/([0-9a-f-]{36})(?:/|$)")


@app.middleware("http")
async def request_lang(request: Request, call_next):
    """Язык ответа — читателя; язык того, что ляжет в кампанию, — самой кампании."""
    token = i18n.use(i18n.pick(request.headers.get("accept-language")))
    hit = CAMPAIGN_PATH.match(request.url.path)
    camp = i18n.use_campaign(hit.group(1) if hit else None)
    try:
        return await call_next(request)
    finally:
        i18n.reset_campaign(camp)
        i18n.reset(token)


LOCATIONS = ("body", "query", "path", "header", "cookie")
PROBLEMS = {
    "missing": "missing",
    "less_than_equal": "le", "greater_than_equal": "ge", "less_than": "lt", "greater_than": "gt",
    "string_too_long": "text_long", "string_too_short": "text_short",
    "too_long": "list_long", "too_short": "list_short",
    "literal_error": "choice", "enum": "choice",
    "int_parsing": "integer", "int_type": "integer", "int_from_float": "integer",
    "float_parsing": "number", "float_type": "number",
    "bool_parsing": "bool", "bool_type": "bool",
    "string_type": "text", "list_type": "list", "dict_type": "object",
    "model_type": "object", "model_attributes_type": "object",
    "json_invalid": "json",
}


def field_name(loc: tuple) -> str:
    where, *rest = loc or ("",)
    name = ""
    for p in rest if where in LOCATIONS else loc:
        name += f"[{p}]" if isinstance(p, int) else (f".{p}" if name else str(p))
    return name if name[:1] not in ("", "[") else f"{where}{name}"


def problem(err: dict) -> str:
    ctx = err.get("ctx") or {}
    limit = next((ctx[k] for k in ("le", "ge", "lt", "gt", "max_length", "min_length") if k in ctx), "")
    expected = str(ctx.get("expected", "")).replace(" or ", ", ")
    code = PROBLEMS.get(err.get("type", ""), "invalid")
    text = i18n.tr(f"errors.validation.{code}", limit=limit, expected=expected)
    loc = ("body",) if code == "json" else tuple(err.get("loc") or ())
    return f"{field_name(loc)}: {text}"


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "; ".join(problem(e) for e in exc.errors()[:3])})


@app.exception_handler(DataError)
async def data_error(request: Request, exc: DataError):
    """Слишком длинное значение — ошибка запроса; id не того вида (не UUID) — такой строки нет.
    Сессию закрывает get_db, транзакция откатывается."""
    if isinstance(exc.orig, StringDataRightTruncation):
        return JSONResponse(status_code=400, content={"detail": i18n.tr("errors.too_long")})
    return JSONResponse(status_code=404, content={"detail": i18n.tr("errors.not_found")})


for r in (campaigns, auth, entities, clocks, comms, news, dispatches, worldmap, boards, boards_agent,
          files, images, rules, history, misc, admin):
    app.include_router(r.router)
# the GPU worker's private protocol: a separate token, not part of the public contract
app.include_router(images.worker_router, include_in_schema=False)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    patch_schema()
    ensure_admin()
    images.start_background()


@app.get("/api/health", tags=["system"], summary="Liveness check", response_model=dict[str, bool])
def health() -> dict:
    """`{"ok": true}` when the API process is up. No login."""
    return {"ok": True}
