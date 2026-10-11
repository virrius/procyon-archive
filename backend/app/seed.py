"""Первый запуск: на пустой базе заводим админа с паролем по умолчанию.

Демо-кампании нет: кампания стартует с фракциями, местами и картой книги
(book_lore.seed_campaign), а готовые кампании заливаются импортом (samples/).
"""
from __future__ import annotations

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
        db.add(User(
            login=ADMIN_LOGIN, password_hash=hash_password(ADMIN_PASSWORD),
            display_name="Admin", is_admin=True, password_default=True,
        ))
        db.commit()
        print(f"[seed] admin account created: {ADMIN_LOGIN} / {ADMIN_PASSWORD} — change the password")
    finally:
        db.close()
