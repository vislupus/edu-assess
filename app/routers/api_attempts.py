"""API: решаване на тестове от ученици, изпитен режим, преглед и ръчно оценяване."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import CurrentUser, Student, Teacher
from ..db import get_db, get_db_write
from ..models import Answer, Assignment, Attempt, Question, User, utcnow
from ..question_types import is_auto
from ..services import (
    apply_option_order,
    assignment_dict,
    assignment_is_open,
    attempt_dict,
    attempt_expired,
    attempt_questions,
    attempt_time_left,
    finalize_attempt,
    question_dict,
    recompute_attempt,
    register_violation,
    start_attempt,
    student_assignments,
    student_can_access,
    user_dict,
)

router = APIRouter(prefix="/api", tags=["attempts"])


class AnswerIn(BaseModel):
    response: Any = None


class ViolationIn(BaseModel):
    kind: str = "focus"
    detail: str = ""


class GradeIn(BaseModel):
    answers: dict[str, dict[str, Any]] = {}
    feedback: str | None = None


def _student_attempt(db: Session, atid: int, student: User) -> Attempt:
    at = db.get(Attempt, atid)
    if not at or at.student_id != student.id:
        raise HTTPException(404, "Опитът не е намерен.")
    return at


def _ensure_live(db: Session, at: Attempt) -> None:
    if at.status != "in_progress":
        raise HTTPException(409, "Опитът е приключен.")
    if attempt_expired(at):
        finalize_attempt(db, at, auto=True)
        raise HTTPException(409, "Времето изтече – тестът беше предаден автоматично.")
    if not assignment_is_open(at.assignment) and at.assignment.status != "active":
        finalize_attempt(db, at, auto=True)
        raise HTTPException(409, "Заданието е затворено.")


def _student_assignment_state(db: Session, a: Assignment, student: User) -> dict:
    ats = db.scalars(
        select(Attempt)
        .where(Attempt.assignment_id == a.id, Attempt.student_id == student.id)
        .order_by(Attempt.attempt_no)
    ).all()
    current = next((x for x in ats if x.status == "in_progress"), None)
    finished = [x for x in ats if x.status != "in_progress"]
    best = max(finished, key=lambda x: (x.percent, x.attempt_no)) if finished else None
    can_start = (
        assignment_is_open(a)
        and (not a.attempts_allowed or len(ats) < a.attempts_allowed)
        and current is None
    )
    d = assignment_dict(a)
    d.update(
        {
            "teacher": a.teacher.full_name,
            "subject": a.test.subject,
            "question_count": len(a.test.questions),
            "attempts_used": len(ats),
            "current": attempt_dict(current) if current else None,
            "best": attempt_dict(best) if best else None,
            "can_start": can_start,
            "can_resume": current is not None,
            "results_visible": results_visible(a),
        }
    )
    return d


def results_visible(a: Assignment) -> bool:
    if a.show_results == "never":
        return False
    if a.show_results == "after_end":
        return a.status == "closed" or (a.end_at is not None and utcnow() > a.end_at)
    return True


@router.get("/my/assignments")
def my_assignments(student: Student, db: Annotated[Session, Depends(get_db)]):
    return [_student_assignment_state(db, a, student) for a in student_assignments(db, student.id)]


@router.get("/my/attempts")
def my_attempts(student: Student, db: Annotated[Session, Depends(get_db)]):
    ats = db.scalars(
        select(Attempt)
        .where(Attempt.student_id == student.id, Attempt.status != "in_progress")
        .order_by(Attempt.submitted_at.desc())
    ).all()
    out = []
    for at in ats:
        d = attempt_dict(at)
        d["assignment"] = {
            "id": at.assignment.id,
            "title": at.assignment.title,
            "mode": at.assignment.mode,
            "subject": at.assignment.test.subject,
        }
        d["results_visible"] = results_visible(at.assignment)
        out.append(d)
    return out


@router.post("/assignments/{aid}/start")
def start(aid: int, student: Student, db: Annotated[Session, Depends(get_db_write)]):
    a = db.get(Assignment, aid)
    if not a or not student_can_access(db, a, student.id):
        raise HTTPException(404, "Заданието не е намерено.")
    at, err = start_attempt(db, a, student)
    if err:
        raise HTTPException(409, err)
    return attempt_dict(at)


@router.get("/attempts/{atid}")
def get_attempt(atid: int, student: Student, db: Annotated[Session, Depends(get_db_write)]):
    """Съдържание на опита за решаване (без верни отговори)."""
    at = _student_attempt(db, atid, student)
    if at.status == "in_progress" and attempt_expired(at):
        finalize_attempt(db, at, auto=True)
    a = at.assignment
    questions = attempt_questions(db, at)
    answers = {x.question_id: x.response for x in at.answers}
    qs = []
    for i, q in enumerate(questions):
        d = question_dict(q, hide_answers=True)
        d["data"] = apply_option_order(q, at.layout, d["data"])
        d["n"] = i + 1
        d["response"] = answers.get(q.id)
        qs.append(d)
    sections = [{"key": s["key"], "title": s["title"]} for s in a.test.sections]
    return {
        "attempt": attempt_dict(at),
        "assignment": {**assignment_dict(a), "subject": a.test.subject, "description": a.test.description},
        "sections": sections,
        "questions": qs,
        "time_left": attempt_time_left(at),
        "server_time": utcnow().isoformat() + "Z",
    }


@router.put("/attempts/{atid}/answers/{qid}")
def save_answer(
    atid: int, qid: int, body: AnswerIn, student: Student, db: Annotated[Session, Depends(get_db_write)]
):
    at = _student_attempt(db, atid, student)
    _ensure_live(db, at)
    q = db.get(Question, qid)
    if not q or q.test_id != at.assignment.test_id:
        raise HTTPException(404, "Въпросът не е част от теста.")
    ans = db.scalar(select(Answer).where(Answer.attempt_id == at.id, Answer.question_id == qid))
    if ans is None:
        ans = Answer(attempt_id=at.id, question_id=qid)
        db.add(ans)
    ans.response = body.response
    ans.updated_at = utcnow()
    db.flush()
    return {"ok": True, "time_left": attempt_time_left(at)}


@router.post("/attempts/{atid}/violation")
def violation(atid: int, body: ViolationIn, student: Student, db: Annotated[Session, Depends(get_db_write)]):
    at = _student_attempt(db, atid, student)
    if at.status != "in_progress":
        return {"warnings": at.warnings, "max_warnings": at.assignment.max_warnings, "status": at.status}
    if not at.assignment.is_exam:
        return {"warnings": 0, "max_warnings": 0, "status": at.status, "ignored": True}
    return register_violation(db, at, body.kind[:32], body.detail[:200])


@router.post("/attempts/{atid}/submit")
def submit(atid: int, student: Student, db: Annotated[Session, Depends(get_db_write)]):
    at = _student_attempt(db, atid, student)
    if at.status != "in_progress":
        return attempt_dict(at)
    finalize_attempt(db, at)
    d = attempt_dict(at)
    d["results_visible"] = results_visible(at.assignment)
    return d


# --- преглед (ученик и учител) ----------------------------------------------


def _review_payload(db: Session, at: Attempt, *, teacher_view: bool) -> dict:
    a = at.assignment
    questions = attempt_questions(db, at)
    answers = {x.question_id: x for x in at.answers}
    qs = []
    for i, q in enumerate(questions):
        ans = answers.get(q.id)
        d = question_dict(q)
        d["data"] = apply_option_order(q, at.layout, d["data"])
        d["n"] = i + 1
        d["response"] = ans.response if ans else None
        d["auto_score"] = ans.auto_score if ans else 0.0
        d["manual_score"] = ans.manual_score if ans else None
        d["final_score"] = ans.final_score if ans else 0.0
        d["is_correct"] = ans.is_correct if ans else None
        d["needs_manual"] = ans.needs_manual if ans else (not is_auto(q.type))
        d["feedback"] = ans.feedback if ans else ""
        qs.append(d)
    return {
        "attempt": attempt_dict(at),
        "student": user_dict(at.student),
        "assignment": {**assignment_dict(a), "subject": a.test.subject},
        "sections": [{"key": s["key"], "title": s["title"]} for s in a.test.sections],
        "questions": qs,
        "events": [
            {"kind": e.kind, "detail": e.detail, "at": e.created_at.isoformat() + "Z"} for e in at.events
        ]
        if teacher_view
        else [],
        "teacher_view": teacher_view,
    }


@router.get("/attempts/{atid}/review")
def review(atid: int, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    at = db.get(Attempt, atid)
    if not at:
        raise HTTPException(404, "Опитът не е намерен.")
    if user.role == "teacher":
        if at.assignment.teacher_id != user.id:
            raise HTTPException(404, "Опитът не е намерен.")
        return _review_payload(db, at, teacher_view=True)
    if at.student_id != user.id:
        raise HTTPException(404, "Опитът не е намерен.")
    if at.status == "in_progress":
        raise HTTPException(409, "Опитът още не е предаден.")
    if not results_visible(at.assignment):
        raise HTTPException(403, "Резултатите ще бъдат достъпни по-късно.")
    return _review_payload(db, at, teacher_view=False)


@router.post("/attempts/{atid}/grade")
def grade(atid: int, body: GradeIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    at = db.get(Attempt, atid)
    if not at or at.assignment.teacher_id != teacher.id:
        raise HTTPException(404, "Опитът не е намерен.")
    if at.status == "in_progress":
        raise HTTPException(409, "Опитът още не е предаден.")
    qmap = {q.id: q for q in attempt_questions(db, at)}
    amap = {x.question_id: x for x in at.answers}
    for qid_s, payload in body.answers.items():
        try:
            qid = int(qid_s)
        except ValueError:
            continue
        q = qmap.get(qid)
        if not q:
            continue
        ans = amap.get(qid)
        if ans is None:
            ans = Answer(attempt_id=at.id, question_id=qid)
            db.add(ans)
            at.answers.append(ans)
        if "manual_score" in payload:
            ms = payload.get("manual_score")
            if ms is None or ms == "":
                ans.manual_score = None
            else:
                try:
                    ans.manual_score = max(0.0, min(float(ms), q.points))
                except (TypeError, ValueError):
                    pass
        if "feedback" in payload:
            ans.feedback = str(payload.get("feedback") or "")[:2000]
    if body.feedback is not None:
        at.teacher_feedback = body.feedback[:4000]
    recompute_attempt(at)
    db.flush()
    return attempt_dict(at)


@router.post("/attempts/{atid}/reopen")
def reopen(atid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    """Учителят анулира/нулира опит, за да може ученикът да реши отново."""
    at = db.get(Attempt, atid)
    if not at or at.assignment.teacher_id != teacher.id:
        raise HTTPException(404, "Опитът не е намерен.")
    db.delete(at)
    db.flush()
    return {"ok": True}
