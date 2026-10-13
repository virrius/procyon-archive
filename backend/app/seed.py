"""First run: on an empty database, create the admin — with the password from PA_ADMIN_PASSWORD or the default.

There is no demo campaign: a campaign starts with the book's factions, locations and map
(book_lore.seed_campaign), and ready-made campaigns are brought in by import (samples/).
"""
from __future__ import annotations

from .config import settings
from .db import SessionLocal
from .models import User
from .security import hash_password

ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "admin"


def ensure_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(User.id).first():
            return
        password = settings.admin_password or ADMIN_PASSWORD
        default = password == ADMIN_PASSWORD
        db.add(User(
            login=ADMIN_LOGIN, password_hash=hash_password(password),
            display_name="Admin", is_admin=True, password_default=default,
        ))
        db.commit()
        print(f"[seed] admin account created: {ADMIN_LOGIN} / "
              + (f"{ADMIN_PASSWORD} — change the password" if default else "password from PA_ADMIN_PASSWORD"))
    finally:
        db.close()
