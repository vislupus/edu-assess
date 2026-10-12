"""API: класни стаи и ученици."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import Teacher
from ..db import get_db, get_db_write
from ..models import Classroom, ClassroomStudent, Curriculum, User
from ..services import classroom_dict, user_dict

router = APIRouter(prefix="/api", tags=["classes"])


class ClassroomIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str | None = None
    curriculum_id: int | None = None


class StudentsIn(BaseModel):
    student_ids: list[int]


def _own_class(db: Session, cid: int, teacher: User) -> Classroom:
    c = db.get(Classroom, cid)
    if not c or c.teacher_id != teacher.id:
        raise HTTPException(404, "Класът не е намерен.")
    return c


@router.get("/students")
def list_students(teacher: Teacher, db: Annotated[Session, Depends(get_db)], q: str = "", grade: str = ""):
    stmt = select(User).where(User.role == "student").order_by(User.grade_label, User.full_name)
    if q:
        stmt = stmt.where(User.full_name.ilike(f"%{q}%"))
    if grade:
        stmt = stmt.where(User.grade_label == grade)
    return [user_dict(u) for u in db.scalars(stmt)]


@router.get("/classes")
def list_classes(teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    rows = db.scalars(
        select(Classroom).where(Classroom.teacher_id == teacher.id).order_by(Classroom.name)
    ).all()
    return [classroom_dict(c) for c in rows]


@router.post("/classes", status_code=201)
def create_class(body: ClassroomIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    if body.curriculum_id and not db.get(Curriculum, body.curriculum_id):
        raise HTTPException(400, "Невалидна учебна програма.")
    c = Classroom(
        name=body.name.strip(),
        teacher_id=teacher.id,
        subject=body.subject or teacher.subject,
        curriculum_id=body.curriculum_id,
    )
    db.add(c)
    db.flush()
    return classroom_dict(c)


@router.get("/classes/{cid}")
def get_class(cid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    return classroom_dict(_own_class(db, cid, teacher), with_members=True)


@router.patch("/classes/{cid}")
def update_class(
    cid: int, body: ClassroomIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]
):
    c = _own_class(db, cid, teacher)
    c.name = body.name.strip()
    c.subject = body.subject or c.subject
    c.curriculum_id = body.curriculum_id
    db.flush()
    return classroom_dict(c, with_members=True)


@router.delete("/classes/{cid}", status_code=204)
def delete_class(cid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    c = _own_class(db, cid, teacher)
    db.delete(c)
    db.flush()


@router.post("/classes/{cid}/students")
def add_students(cid: int, body: StudentsIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    c = _own_class(db, cid, teacher)
    existing = {m.student_id for m in c.members}
    for sid in body.student_ids:
        if sid in existing:
            continue
        u = db.get(User, sid)
        if not u or u.role != "student":
            continue
        db.add(ClassroomStudent(classroom_id=c.id, student_id=sid))
        existing.add(sid)
    db.flush()
    db.refresh(c)
    return classroom_dict(c, with_members=True)


@router.delete("/classes/{cid}/students/{sid}")
def remove_student(cid: int, sid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    c = _own_class(db, cid, teacher)
    m = db.get(ClassroomStudent, {"classroom_id": c.id, "student_id": sid})
    if m:
        db.delete(m)
        db.flush()
    db.refresh(c)
    return classroom_dict(c, with_members=True)
