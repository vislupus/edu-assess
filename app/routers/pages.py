"""HTML страници (Jinja2). Динамичните части се зареждат от JSON API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.gemini import ai_mode
from ..auth import CurrentUser, Teacher, login_user, logout_user, optional_user
from ..db import get_db
from ..models import Assignment, Attempt, Classroom, Curriculum, Question, Test, User
from ..question_types import QUESTION_TYPES, TYPE_ORDER

QTYPES_LIST = [
    (
        k,
        QUESTION_TYPES[k]["label"],
        QUESTION_TYPES[k]["icon"],
        QUESTION_TYPES[k]["auto"],
        QUESTION_TYPES[k]["group"],
    )
    for k in TYPE_ORDER
]
from ..services import assignment_is_open
from ..templating import render

router = APIRouter(include_in_schema=False)


# --- вход / изход --------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User | None, Depends(optional_user)],
):
    if user:
        return RedirectResponse("/", status_code=303)
    users = db.scalars(select(User).order_by(User.role.desc(), User.grade_label, User.full_name)).all()
    teachers = [u for u in users if u.role == "teacher"]
    students: dict[str, list[User]] = {}
    for u in users:
        if u.role == "student":
            students.setdefault(u.grade_label or "", []).append(u)
    return render(request, "login.html", teachers=teachers, students=students, user=None)


@router.post("/login")
def login_submit(request: Request, db: Annotated[Session, Depends(get_db)], user_id: Annotated[int, Form()]):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(400, "Непознат потребител.")
    login_user(request, u)
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login", status_code=303)


@router.get("/auth/sso/callback")
def sso_callback(request: Request):
    """Заготовка за външна SSO система.

    Когато SSO бъде свързана, тук се проверява токенът/assertion-ът, намира се
    (или се създава) потребител по `User.external_id` и се извиква `login_user()`.
    """
    raise HTTPException(501, "SSO интеграцията предстои. Използвайте демо входа от /login.")


# --- начало -------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def home(request: Request, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    if user.role == "teacher":
        classes = db.scalars(select(Classroom).where(Classroom.teacher_id == user.id)).all()
        tests = db.scalar(select(func.count(Test.id)).where(Test.owner_id == user.id)) or 0
        bank = (
            db.scalar(
                select(func.count(Question.id)).where(
                    Question.owner_id == user.id, Question.test_id.is_(None)
                )
            )
            or 0
        )
        assignments = db.scalars(
            select(Assignment)
            .where(Assignment.teacher_id == user.id)
            .order_by(Assignment.created_at.desc())
            .limit(6)
        ).all()
        rows = []
        needs_manual_total = 0
        for a in assignments:
            ats = db.scalars(select(Attempt).where(Attempt.assignment_id == a.id)).all()
            nm = sum(1 for x in ats if x.needs_manual and x.status == "submitted")
            needs_manual_total += nm
            rows.append(
                {
                    "a": a,
                    "open": assignment_is_open(a),
                    "submitted": sum(1 for x in ats if x.status in {"submitted", "annulled"}),
                    "in_progress": sum(1 for x in ats if x.status == "in_progress"),
                    "needs_manual": nm,
                }
            )
        students = sum(len(c.members) for c in classes)
        return render(
            request,
            "teacher/dashboard.html",
            user=user,
            classes=classes,
            tests_count=tests,
            bank_count=bank,
            students_count=students,
            rows=rows,
            needs_manual_total=needs_manual_total,
            ai_mode=ai_mode(),
        )
    return render(request, "student/home.html", user=user)


# --- учител -------------------------------------------------------------------


@router.get("/classes", response_class=HTMLResponse)
def classes_page(request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    curricula = db.scalars(select(Curriculum).order_by(Curriculum.grade)).all()
    return render(request, "teacher/classes.html", user=teacher, curricula=curricula)


@router.get("/classes/{cid}", response_class=HTMLResponse)
def class_page(cid: int, request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    c = db.get(Classroom, cid)
    if not c or c.teacher_id != teacher.id:
        raise HTTPException(404)
    curricula = db.scalars(select(Curriculum).order_by(Curriculum.grade)).all()
    assignments = (
        db.scalars(
            select(Assignment)
            .join(Assignment.classrooms)
            .where(Assignment.teacher_id == teacher.id)
            .order_by(Assignment.created_at.desc())
        )
        .unique()
        .all()
    )
    assignments = [a for a in assignments if any(ac.classroom_id == c.id for ac in a.classrooms)]
    return render(
        request,
        "teacher/class_detail.html",
        user=teacher,
        classroom=c,
        curricula=curricula,
        assignments=assignments,
    )


@router.get("/bank", response_class=HTMLResponse)
def bank_page(request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    curricula = db.scalars(select(Curriculum).order_by(Curriculum.grade)).all()
    return render(
        request,
        "teacher/bank.html",
        user=teacher,
        curricula=curricula,
        qtypes=QUESTION_TYPES,
        type_order=TYPE_ORDER,
        qtypes_list=QTYPES_LIST,
    )


@router.get("/tests", response_class=HTMLResponse)
def tests_page(request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    curricula = db.scalars(select(Curriculum).order_by(Curriculum.grade)).all()
    return render(request, "teacher/tests.html", user=teacher, curricula=curricula)


@router.get("/tests/new", response_class=HTMLResponse)
def test_new_page(request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    curricula = db.scalars(select(Curriculum).order_by(Curriculum.grade)).all()
    return render(
        request,
        "teacher/test_new.html",
        user=teacher,
        curricula=curricula,
        qtypes_list=QTYPES_LIST,
        ai_mode=ai_mode(),
    )


@router.get("/tests/{tid}/edit", response_class=HTMLResponse)
def test_edit_page(tid: int, request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    t = db.get(Test, tid)
    if not t or t.owner_id != teacher.id:
        raise HTTPException(404)
    curricula = db.scalars(select(Curriculum).order_by(Curriculum.grade)).all()
    return render(
        request,
        "teacher/test_edit.html",
        user=teacher,
        test=t,
        curricula=curricula,
        qtypes_list=QTYPES_LIST,
        ai_mode=ai_mode(),
    )


@router.get("/tests/{tid}/print", response_class=HTMLResponse)
def test_print_page(
    tid: int, request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)], key: int = 0
):
    t = db.get(Test, tid)
    if not t or t.owner_id != teacher.id:
        raise HTTPException(404)
    return render(
        request, "teacher/test_print.html", user=teacher, test=t, answer_key=bool(key), qtypes=QUESTION_TYPES
    )


@router.get("/tests/{tid}/assign", response_class=HTMLResponse)
def assign_page(tid: int, request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    t = db.get(Test, tid)
    if not t or t.owner_id != teacher.id:
        raise HTTPException(404)
    classes = db.scalars(
        select(Classroom).where(Classroom.teacher_id == teacher.id).order_by(Classroom.name)
    ).all()
    classes_json = [{"id": c.id, "name": c.name, "n": len(c.members)} for c in classes]
    return render(request, "teacher/assign.html", user=teacher, test=t, classes_json=classes_json)


@router.get("/assignments", response_class=HTMLResponse)
def assignments_page(request: Request, teacher: Teacher):
    return render(request, "teacher/assignments.html", user=teacher)


@router.get("/assignments/{aid}", response_class=HTMLResponse)
def assignment_page(aid: int, request: Request, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    a = db.get(Assignment, aid)
    if not a or a.teacher_id != teacher.id:
        raise HTTPException(404)
    return render(request, "teacher/assignment_detail.html", user=teacher, assignment=a)


@router.get("/attempts/{atid}/review", response_class=HTMLResponse)
def review_page(atid: int, request: Request, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    at = db.get(Attempt, atid)
    if not at:
        raise HTTPException(404)
    if user.role == "teacher" and at.assignment.teacher_id != user.id:
        raise HTTPException(404)
    if user.role == "student" and at.student_id != user.id:
        raise HTTPException(404)
    return render(request, "review.html", user=user, attempt=at)


@router.get("/curricula", response_class=HTMLResponse)
def curricula_page(request: Request, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    curricula = db.scalars(select(Curriculum).order_by(Curriculum.grade, Curriculum.subject)).all()
    return render(request, "curricula.html", user=user, curricula=curricula)


# --- ученик -------------------------------------------------------------------


@router.get("/attempts/{atid}", response_class=HTMLResponse)
def attempt_page(atid: int, request: Request, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    at = db.get(Attempt, atid)
    if not at or at.student_id != user.id:
        raise HTTPException(404)
    if at.status != "in_progress":
        return RedirectResponse(f"/attempts/{atid}/review", status_code=303)
    return render(request, "student/player.html", user=user, attempt=at, exam=at.assignment.is_exam)


@router.get("/my-results", response_class=HTMLResponse)
def my_results_page(request: Request, user: CurrentUser):
    if user.role != "student":
        return RedirectResponse("/assignments", status_code=303)
    return render(request, "student/results.html", user=user)
