"""API: банка с въпроси и въпроси в тестове."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import Teacher
from ..db import get_db, get_db_write
from ..models import Question, Test, User
from ..question_types import QUESTION_TYPES, QuestionDataError, clean_html, normalize_data
from ..services import question_dict

router = APIRouter(prefix="/api", tags=["questions"])


class QuestionIn(BaseModel):
    type: str
    stem: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    difficulty: int = 2
    points: float = 1.0
    curriculum_id: int | None = None
    topic: str | None = None
    tags: str = ""
    section_key: str | None = None


def apply_question(q: Question, body: QuestionIn) -> None:
    if body.type not in QUESTION_TYPES:
        raise HTTPException(400, "Непознат тип въпрос.")
    try:
        data = normalize_data(body.type, body.data)
    except QuestionDataError as exc:
        raise HTTPException(422, str(exc)) from exc
    q.type = body.type
    q.stem = clean_html(body.stem)
    q.data = data
    q.difficulty = body.difficulty if body.difficulty in (1, 2, 3) else 2
    q.points = max(0.25, min(float(body.points or 1), 100))
    q.curriculum_id = body.curriculum_id
    q.topic = (body.topic or "")[:255] or None
    q.tags = (body.tags or "")[:255]
    if body.section_key is not None:
        q.section_key = body.section_key


def own_question(db: Session, qid: int, teacher: User) -> Question:
    q = db.get(Question, qid)
    if not q or q.owner_id != teacher.id:
        raise HTTPException(404, "Въпросът не е намерен.")
    return q


@router.get("/question-types")
def question_types():
    return [
        {"key": k, "label": v["label"], "icon": v["icon"], "auto": v["auto"], "group": v["group"]}
        for k, v in QUESTION_TYPES.items()
    ]


@router.get("/bank")
def list_bank(
    teacher: Teacher,
    db: Annotated[Session, Depends(get_db)],
    curriculum_id: int | None = None,
    type: str = "",
    difficulty: int | None = None,
    topic: str = "",
    q: str = "",
    limit: int = 200,
):
    stmt = select(Question).where(Question.owner_id == teacher.id, Question.test_id.is_(None))
    if curriculum_id:
        stmt = stmt.where(Question.curriculum_id == curriculum_id)
    if type:
        stmt = stmt.where(Question.type == type)
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty)
    if topic:
        stmt = stmt.where(Question.topic == topic)
    if q:
        stmt = stmt.where(Question.stem.ilike(f"%{q}%"))
    stmt = stmt.order_by(Question.updated_at.desc()).limit(min(limit, 500))
    return [question_dict(x) for x in db.scalars(stmt)]


@router.get("/bank/stats")
def bank_stats(teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    rows = db.execute(
        select(Question.type, func.count(Question.id))
        .where(Question.owner_id == teacher.id, Question.test_id.is_(None))
        .group_by(Question.type)
    ).all()
    return {"by_type": {r[0]: r[1] for r in rows}, "total": sum(r[1] for r in rows)}


@router.post("/bank", status_code=201)
def create_bank_question(body: QuestionIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    q = Question(owner_id=teacher.id, test_id=None, source="manual")
    apply_question(q, body)
    db.add(q)
    db.flush()
    return question_dict(q)


@router.get("/questions/{qid}")
def get_question(qid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    return question_dict(own_question(db, qid, teacher))


@router.put("/questions/{qid}")
def update_question(
    qid: int, body: QuestionIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]
):
    q = own_question(db, qid, teacher)
    apply_question(q, body)
    db.flush()
    return question_dict(q)


@router.delete("/questions/{qid}", status_code=204)
def delete_question(qid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    q = own_question(db, qid, teacher)
    db.delete(q)
    db.flush()


@router.post("/questions/{qid}/to-bank", status_code=201)
def copy_to_bank(qid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    q = own_question(db, qid, teacher)
    copy = Question(
        owner_id=teacher.id,
        test_id=None,
        type=q.type,
        stem=q.stem,
        data=q.data,
        difficulty=q.difficulty,
        points=q.points,
        curriculum_id=q.curriculum_id,
        topic=q.topic,
        tags=q.tags,
        source=q.source,
        source_question_id=q.id,
    )
    db.add(copy)
    db.flush()
    return question_dict(copy)


@router.post("/questions/{qid}/duplicate", status_code=201)
def duplicate_question(qid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    q = own_question(db, qid, teacher)
    copy = Question(
        owner_id=teacher.id,
        test_id=q.test_id,
        section_key=q.section_key,
        position=q.position + 1,
        type=q.type,
        stem=q.stem,
        data=q.data,
        difficulty=q.difficulty,
        points=q.points,
        curriculum_id=q.curriculum_id,
        topic=q.topic,
        tags=q.tags,
        source=q.source,
    )
    db.add(copy)
    if q.test_id:
        for other in db.scalars(
            select(Question).where(Question.test_id == q.test_id, Question.position > q.position)
        ):
            other.position += 1
        test = db.get(Test, q.test_id)
        if test:
            test.updated_at = func.now()
    db.flush()
    return question_dict(copy)
