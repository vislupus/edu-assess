"""API: учебни програми."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, Teacher
from ..curricula import upsert_curriculum
from ..db import get_db, get_db_write
from ..models import Curriculum

router = APIRouter(prefix="/api", tags=["curricula"])


def cur_dict(c: Curriculum, *, full: bool = False) -> dict:
    d = {
        "id": c.id,
        "code": c.code,
        "subject": c.subject,
        "grade": c.grade,
        "grade_label": c.grade_label,
        "title": c.title,
        "topics": [t.get("title") for t in c.topics],
    }
    if full:
        d["data"] = c.data
    return d


@router.get("/curricula")
def list_curricula(user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    return [
        cur_dict(c) for c in db.scalars(select(Curriculum).order_by(Curriculum.grade, Curriculum.subject))
    ]


@router.get("/curricula/{cid}")
def get_curriculum(cid: int, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    c = db.get(Curriculum, cid)
    if not c:
        raise HTTPException(404)
    return cur_dict(c, full=True)


@router.post("/curricula", status_code=201)
async def upload_curriculum(
    file: UploadFile, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]
):
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(413, "Файлът е твърде голям.")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Невалиден JSON файл.") from exc
    if not isinstance(data, dict) or not data.get("subject") or not isinstance(data.get("topics"), list):
        raise HTTPException(400, "Очакват се полета subject, grade и topics (виж data/curricula/*.json).")
    c = upsert_curriculum(db, data)
    db.flush()
    return cur_dict(c)
