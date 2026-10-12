"""Сесии и достъп.

Няма регистрация: демо потребителите влизат от страницата /login, а в бъдеще
външната SSO система ще извиква `login_user()` след успешна проверка
(виж `routers/pages.py: sso_callback` – заготовка).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import User


def login_user(request: Request, user: User) -> None:
    request.session.clear()
    request.session["uid"] = user.id
    request.session["role"] = user.role


def logout_user(request: Request) -> None:
    request.session.clear()


def _load_user(request: Request, db: Session) -> User | None:
    uid = request.session.get("uid")
    if not uid:
        return None
    return db.get(User, uid)


def optional_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User | None:
    return _load_user(request, db)


def current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    user = _load_user(request, db)
    if not user:
        if request.url.path.startswith("/api/"):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Необходим е вход.")
        raise HTTPException(status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def require_teacher(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "teacher":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Само за учители.")
    return user


def require_student(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Само за ученици.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
Teacher = Annotated[User, Depends(require_teacher)]
Student = Annotated[User, Depends(require_student)]
