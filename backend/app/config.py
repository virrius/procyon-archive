import os
import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://procyon:procyon@db:5432/procyon"
    jwt_secret: str = ""
    jwt_ttl_hours: int = 720
    upload_dir: str = "/data/uploads"
    worker_token: str = ""
    admin_password: str = ""
    # book rules text is not part of the repository: <book_dir>/<lang>.json, if present
    book_dir: str = "/data/book"

    class Config:
        env_prefix = "PA_"


def _stored_secret(folder: str) -> str:
    """Without PA_JWT_SECRET, the secret is created on first start and kept next to the uploads."""
    path = os.path.join(folder, ".jwt_secret")
    try:
        with open(path, encoding="utf-8") as f:
            if s := f.read().strip():
                return s
    except OSError:
        pass
    s = secrets.token_urlsafe(48)
    try:
        os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
    except OSError:
        pass
    return s


settings = Settings()
if not settings.jwt_secret:
    settings.jwt_secret = _stored_secret(settings.upload_dir)
