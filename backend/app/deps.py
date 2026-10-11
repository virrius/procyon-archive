from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import Depends, Header, HTTPException, Path, Request, Security
from fastapi.security import APIKeyCookie, APIKeyQuery, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .i18n import tr
from .models import Campaign, CampaignMember, User
from .security import read_token
from .visibility import Viewer

PUBLIC_VIEW = "crew"  # X-View-As: витрина «как видят игроки», без конкретного участника

# три способа предъявить токен — все попадают в securitySchemes и в кнопку Authorize
bearer_scheme = HTTPBearer(
    auto_error=False, scheme_name="bearer",
    description="`Authorization: Bearer <token>` — the token from `POST /api/auth/login`. The way for API clients.",
)
query_scheme = APIKeyQuery(
    name="token", auto_error=False, scheme_name="token_query",
    description="`?token=<token>` — only for `<img src>` and downloads where headers cannot be set. The token lands in URLs and logs; prefer the header.",
)
cookie_scheme = APIKeyCookie(
    name="pa_token", auto_error=False, scheme_name="token_cookie",
    description="Browser session cookie set by the web app (`pa_token` or `pa_token_<instance>`). Not for API clients.",
)


def _own_ports(request: Request) -> set[int]:
    """Порт, на котором браузер открыл этот экземпляр. Прокси перед API срезает его из Host,
    поэтому смотрим и Origin/Referer."""
    ports = set()
    host = request.headers.get("host", "")
    for raw in (f"//{host}", request.headers.get("origin", ""), request.headers.get("referer", "")):
        try:
            port = urlsplit(raw).port
        except ValueError:
            continue
        if port:
            ports.add(port)
    return ports


def session_user(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    token: str | None = Security(query_scheme),
    _cookie: str | None = Security(cookie_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Bearer header for API calls; cookie or ?token= so <img src> works too."""
    if bearer and bearer.scheme.lower() == "bearer" and bearer.credentials:
        raws = [bearer.credentials]
    elif token:
        raws = [token]
    else:
        # куки не различают порты: рядом лежат токены соседнего экземпляра на том же хосте — свой первым
        own = {f"pa_token_{p}" for p in _own_ports(request)}
        jar = [(k, v) for k, v in request.cookies.items() if k == "pa_token" or k.startswith("pa_token_")]
        raws = [v for k, v in sorted(jar, key=lambda kv: kv[0] not in own)]
    raws = [r.strip() for r in raws if r.strip()]
    if not raws:
        raise HTTPException(401, tr("auth.no_token"))
    uids = [u for u in map(read_token, raws) if u]
    if not uids:
        raise HTTPException(401, tr("auth.bad_token"))
    for uid in uids:
        user = db.get(User, uid)
        if user and user.is_active:
            return user
    raise HTTPException(401, tr("auth.unknown_user"))


def current_user(user: User = Depends(session_user)) -> User:
    """Пока пароль по умолчанию не сменён, учётке открыты только `/auth/me` и `/auth/password`."""
    if user.password_default:
        raise HTTPException(403, tr("auth.password_default"))
    return user


VIEW_AS_DOC = (
    "GM only: look through a player's eyes. `crew` — what the whole table sees (read-only: writes answer 409); "
    "`<member_id>` — as that member, with their rights. Other roles ignore the header. "
    "GM-only operations (journal, boards, rules editing, admin) ignore it too: players have no access to them at all (403)."
)


CAMPAIGN_ID = Path(..., description="Campaign id from `GET /api/campaigns`.")


def _membership(campaign_id: str, user: User, db: Session) -> CampaignMember:
    if not db.get(Campaign, campaign_id):
        raise HTTPException(404, tr("auth.campaign_missing"))
    me = (
        db.query(CampaignMember)
        .filter_by(campaign_id=campaign_id, user_id=user.id)
        .one_or_none()
    )
    if not me:
        raise HTTPException(403, tr("auth.not_member"))
    return me


def viewer(
    campaign_id: str = CAMPAIGN_ID,
    x_view_as: str | None = Header(default=None, alias="X-View-As", description=VIEW_AS_DOC),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Viewer:
    me = _membership(campaign_id, user, db)
    role, member_id, acting_as = me.role, me.id, None
    if x_view_as == PUBLIC_VIEW and me.role == "gm":
        # витрина для стола: видно только то, что открыто всему экипажу
        role, member_id, acting_as = "player", "", PUBLIC_VIEW
    elif x_view_as and me.role == "gm":
        target = db.get(CampaignMember, x_view_as)
        if not target or target.campaign_id != campaign_id:
            raise HTTPException(400, tr("auth.bad_view_as"))
        role, member_id, acting_as = "player", target.id, target.id

    return Viewer(
        user_id=user.id,
        campaign_id=campaign_id,
        member_id=member_id,
        role=role,
        is_real_gm=me.role == "gm",
        acting_as=acting_as,
    )


def gm_only(
    campaign_id: str = CAMPAIGN_ID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Viewer:
    """X-View-As здесь не действует: операция ГМа идёт от него самого."""
    me = _membership(campaign_id, user, db)
    if me.role != "gm":
        raise HTTPException(403, tr("auth.gm_only"))
    return Viewer(user_id=user.id, campaign_id=campaign_id, member_id=me.id, role="gm", is_real_gm=True)


def editor(v: Viewer = Depends(viewer)) -> Viewer:
    """Право записи. ГМ «глазами игрока» пишет от лица этого игрока и в его правах."""
    if v.acting_as == PUBLIC_VIEW:
        raise HTTPException(409, tr("auth.public_read_only"))
    if v.role == "observer":
        raise HTTPException(403, tr("auth.read_only_role"))
    return v


def admin_only(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, tr("auth.admin_only"))
    return user
