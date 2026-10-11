from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..api_schema import Role, error_responses
from ..db import get_db
from ..deps import session_user
from ..i18n import tr
from ..models import AuditLog, CampaignMember, User
from ..security import hash_password, make_token, verify_password
from ..seed import ADMIN_PASSWORD

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    login: str = Field(description="Case-insensitive.", examples=["gm"])
    password: str


class TokenOut(BaseModel):
    token: str = Field(description="Bearer token for `Authorization: Bearer <token>`; valid for 30 days.")
    user_id: str
    display_name: str
    is_admin: bool = Field(description="Server admin: may create campaigns and use `/api/admin/*`.")


class PasswordIn(BaseModel):
    old_password: str = Field(default="", description="Not checked while the account still has its default password.")
    new_password: str = Field(min_length=4)


@router.post("/login", summary="Log in and get a token", response_model=TokenOut,
             responses=error_responses(401))
def login(body: LoginIn, db: Session = Depends(get_db)):
    """The only call that takes a password. 401 — wrong login/password or a blocked account."""
    u = db.query(User).filter(User.login == body.login.strip().lower()).first()
    if not u or not verify_password(body.password, u.password_hash) or not u.is_active:
        raise HTTPException(401, tr("auth.bad_credentials"))
    db.add(AuditLog(user_id=u.id, action="login", detail=u.login))
    db.commit()
    return TokenOut(
        token=make_token(u.id, u.token_version or 0), user_id=u.id, display_name=u.display_name, is_admin=u.is_admin
    )


class MyMembership(BaseModel):
    campaign_id: str
    member_id: str = Field(description="Your member id in that campaign.")
    role: Role
    name: str
    slug: str


class MeOut(BaseModel):
    id: str
    login: str
    display_name: str
    is_admin: bool
    password_default: bool = Field(description="True until the seeded default password is changed; until then every other call answers 403, except `POST /api/auth/password`.")
    campaigns: list[MyMembership]


@router.get("/me", summary="Who am I", response_model=MeOut, responses=error_responses(401))
def me(user: User = Depends(session_user), db: Session = Depends(get_db)):
    """The account behind the token and its campaign memberships (same data as `GET /api/campaigns`)."""
    memberships = db.query(CampaignMember).filter_by(user_id=user.id).all()
    return {
        "id": user.id,
        "login": user.login,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "password_default": user.password_default,
        "campaigns": [
            {
                "campaign_id": m.campaign_id,
                "member_id": m.id,
                "role": m.role,
                "name": m.campaign.name,
                "slug": m.campaign.slug,
            }
            for m in memberships
        ],
    }


class PasswordOut(BaseModel):
    ok: bool = True
    token: str = Field(description="New bearer token: tokens issued before the change stop working.")


@router.post("/password", summary="Change my password", response_model=PasswordOut,
             responses=error_responses(400, 401, 403))
def change_password(
    body: PasswordIn, user: User = Depends(session_user), db: Session = Depends(get_db)
):
    """400 — too short or the default password; 403 — the old password is wrong. Every token issued before the change, this one included, stops working; use the one returned."""
    # пароль по умолчанию известен всем — старый у такой учётки не спрашиваем
    if not user.password_default and not verify_password(body.old_password, user.password_hash):
        raise HTTPException(403, tr("auth.wrong_password"))
    if len(body.new_password) < 4:
        raise HTTPException(400, tr("auth.password_short"))
    if body.new_password == ADMIN_PASSWORD:
        raise HTTPException(400, tr("auth.password_is_default"))
    user.password_hash = hash_password(body.new_password)
    user.password_default = False
    user.token_version = (user.token_version or 0) + 1
    db.add(AuditLog(user_id=user.id, action="password_change", detail=user.login))
    db.commit()
    return {"ok": True, "token": make_token(user.id, user.token_version)}
