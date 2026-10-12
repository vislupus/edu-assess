"""API: възлагане на тестове и резултати."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import Teacher
from ..db import get_db, get_db_write
from ..models import Assignment, AssignmentClassroom, Attempt, Classroom, Question, Test, User, utcnow
from ..services import assignment_dict, assignment_results

router = APIRouter(prefix="/api", tags=["assignments"])


class AssignmentIn(BaseModel):
    test_id: int
    title: str | None = None
    mode: str = "practice"
    classroom_ids: list[int] = Field(default_factory=list)
    start_at: datetime | None = None
    end_at: datetime | None = None
    time_limit_min: int | None = None
    attempts_allowed: int = 1
    shuffle_questions: bool = False
    shuffle_options: bool = False
    variants: int = 1
    show_results: str = "immediately"
    max_warnings: int = 3
    grade_scale: dict[str, float] | None = None


class AssignmentPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    end_at: datetime | None = None
    attempts_allowed: int | None = None


def own_assignment(db: Session, aid: int, teacher: User) -> Assignment:
    a = db.get(Assignment, aid)
    if not a or a.teacher_id != teacher.id:
        raise HTTPException(404, "Заданието не е намерено.")
    return a


def _naive(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    if d.tzinfo is not None:
        from datetime import UTC

        d = d.astimezone(UTC).replace(tzinfo=None)
    return d


@router.get("/assignments")
def list_assignments(teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    rows = db.scalars(
        select(Assignment).where(Assignment.teacher_id == teacher.id).order_by(Assignment.created_at.desc())
    ).all()
    out = []
    for a in rows:
        d = assignment_dict(a)
        attempts = db.scalars(select(Attempt).where(Attempt.assignment_id == a.id)).all()
        d["submitted"] = sum(1 for x in attempts if x.status in {"submitted", "annulled"})
        d["in_progress"] = sum(1 for x in attempts if x.status == "in_progress")
        d["needs_manual"] = sum(1 for x in attempts if x.needs_manual and x.status == "submitted")
        out.append(d)
    return out


@router.post("/assignments", status_code=201)
def create_assignment(body: AssignmentIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    t = db.get(Test, body.test_id)
    if not t or t.owner_id != teacher.id:
        raise HTTPException(404, "Тестът не е намерен.")
    if not db.scalar(select(Question.id).where(Question.test_id == t.id).limit(1)):
        raise HTTPException(400, "Тестът няма въпроси.")
    classrooms = [
        c
        for c in db.scalars(select(Classroom).where(Classroom.id.in_(body.classroom_ids or [-1])))
        if c.teacher_id == teacher.id
    ]
    if not classrooms:
        raise HTTPException(400, "Изберете поне един клас.")
    if body.mode not in {"practice", "exam"}:
        raise HTTPException(400, "Невалиден режим.")
    a = Assignment(
        test_id=t.id,
        teacher_id=teacher.id,
        title=(body.title or t.title).strip()[:255],
        mode=body.mode,
        start_at=_naive(body.start_at) or utcnow(),
        end_at=_naive(body.end_at),
        time_limit_min=body.time_limit_min if body.time_limit_min and body.time_limit_min > 0 else None,
        attempts_allowed=max(0, body.attempts_allowed),
        shuffle_questions=body.shuffle_questions,
        shuffle_options=body.shuffle_options,
        variants=max(1, min(body.variants, 10)),
        show_results=body.show_results
        if body.show_results in {"immediately", "after_end", "never"}
        else "immediately",
        max_warnings=max(0, min(body.max_warnings, 10)),
        grade_scale=body.grade_scale or {},
    )
    if a.is_exam and not a.attempts_allowed:
        a.attempts_allowed = 1
    db.add(a)
    db.flush()
    for c in classrooms:
        db.add(AssignmentClassroom(assignment_id=a.id, classroom_id=c.id))
    t.status = "ready"
    db.flush()
    return assignment_dict(a)


@router.get("/assignments/{aid}")
def get_assignment(aid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    return assignment_dict(own_assignment(db, aid, teacher))


@router.patch("/assignments/{aid}")
def patch_assignment(
    aid: int, body: AssignmentPatch, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]
):
    a = own_assignment(db, aid, teacher)
    if body.title:
        a.title = body.title.strip()[:255]
    if body.status in {"active", "closed"}:
        a.status = body.status
    if body.end_at is not None:
        a.end_at = _naive(body.end_at)
    if body.attempts_allowed is not None:
        a.attempts_allowed = max(0, body.attempts_allowed)
    db.flush()
    return assignment_dict(a)


@router.delete("/assignments/{aid}", status_code=204)
def delete_assignment(aid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    a = own_assignment(db, aid, teacher)
    for at in db.scalars(select(Attempt).where(Attempt.assignment_id == a.id)):
        db.delete(at)
    db.delete(a)
    db.flush()


@router.get("/assignments/{aid}/results")
def results(aid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    return assignment_results(db, own_assignment(db, aid, teacher))
