"""Общи сервизни функции: сериализация, подредба на опит, оценяване на опит, статистики."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .grading import grade_label, grade_response, percent_to_grade
from .models import (
    Answer,
    Assignment,
    AssignmentClassroom,
    Attempt,
    AttemptEvent,
    Classroom,
    ClassroomStudent,
    Question,
    User,
    utcnow,
)
from .question_types import DIFFICULTY_LABELS, is_auto, public_data, type_label

# ---------------------------------------------------------------------------
# Сериализация
# ---------------------------------------------------------------------------


def dt(v: datetime | None) -> str | None:
    return v.replace(microsecond=0).isoformat() + "Z" if v else None


def user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "subject": u.subject,
        "grade_label": u.grade_label,
        "avatar_color": u.avatar_color,
        "initials": u.initials,
    }


def question_dict(q: Question, *, hide_answers: bool = False) -> dict:
    return {
        "id": q.id,
        "test_id": q.test_id,
        "section_key": q.section_key,
        "position": q.position,
        "type": q.type,
        "type_label": type_label(q.type),
        "stem": q.stem,
        "data": public_data(q.type, q.data) if hide_answers else q.data,
        "difficulty": q.difficulty,
        "difficulty_label": DIFFICULTY_LABELS.get(q.difficulty, ""),
        "points": q.points,
        "curriculum_id": q.curriculum_id,
        "topic": q.topic,
        "tags": q.tags,
        "source": q.source,
        "auto": is_auto(q.type),
        "updated_at": dt(q.updated_at),
    }


def classroom_dict(c: Classroom, *, with_members: bool = False) -> dict:
    d = {
        "id": c.id,
        "name": c.name,
        "subject": c.subject,
        "curriculum_id": c.curriculum_id,
        "join_code": c.join_code,
        "teacher_id": c.teacher_id,
        "student_count": len(c.members),
        "created_at": dt(c.created_at),
    }
    if with_members:
        d["students"] = [user_dict(m.student) for m in sorted(c.members, key=lambda m: m.student.full_name)]
    return d


def assignment_dict(a: Assignment) -> dict:
    return {
        "id": a.id,
        "test_id": a.test_id,
        "title": a.title,
        "mode": a.mode,
        "start_at": dt(a.start_at),
        "end_at": dt(a.end_at),
        "time_limit_min": a.time_limit_min,
        "attempts_allowed": a.attempts_allowed,
        "shuffle_questions": a.shuffle_questions,
        "shuffle_options": a.shuffle_options,
        "variants": a.variants,
        "show_results": a.show_results,
        "max_warnings": a.max_warnings,
        "grade_scale": a.grade_scale,
        "status": a.status,
        "classrooms": [{"id": ac.classroom.id, "name": ac.classroom.name} for ac in a.classrooms],
        "created_at": dt(a.created_at),
        "is_open": assignment_is_open(a),
    }


def attempt_dict(at: Attempt) -> dict:
    return {
        "id": at.id,
        "assignment_id": at.assignment_id,
        "student_id": at.student_id,
        "attempt_no": at.attempt_no,
        "status": at.status,
        "variant": at.variant,
        "started_at": dt(at.started_at),
        "deadline_at": dt(at.deadline_at),
        "submitted_at": dt(at.submitted_at),
        "score": round(at.score, 2),
        "max_score": round(at.max_score, 2),
        "percent": round(at.percent, 1),
        "grade": at.grade,
        "grade_label": grade_label(at.grade),
        "warnings": at.warnings,
        "needs_manual": at.needs_manual,
        "teacher_feedback": at.teacher_feedback,
    }


# ---------------------------------------------------------------------------
# Задания и достъп
# ---------------------------------------------------------------------------


def assignment_is_open(a: Assignment, now: datetime | None = None) -> bool:
    now = now or utcnow()
    if a.status != "active":
        return False
    if a.start_at and now < a.start_at:
        return False
    return not (a.end_at and now > a.end_at)


def student_classroom_ids(db: Session, student_id: int) -> list[int]:
    return list(
        db.scalars(select(ClassroomStudent.classroom_id).where(ClassroomStudent.student_id == student_id))
    )


def student_assignments(db: Session, student_id: int) -> list[Assignment]:
    cids = student_classroom_ids(db, student_id)
    if not cids:
        return []
    stmt = (
        select(Assignment)
        .join(AssignmentClassroom, AssignmentClassroom.assignment_id == Assignment.id)
        .where(AssignmentClassroom.classroom_id.in_(cids))
        .distinct()
        .order_by(Assignment.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


def student_can_access(db: Session, a: Assignment, student_id: int) -> bool:
    cids = set(student_classroom_ids(db, student_id))
    return any(ac.classroom_id in cids for ac in a.classrooms)


def assignment_students(db: Session, a: Assignment) -> list[User]:
    cids = [ac.classroom_id for ac in a.classrooms]
    if not cids:
        return []
    stmt = (
        select(User)
        .join(ClassroomStudent, ClassroomStudent.student_id == User.id)
        .where(ClassroomStudent.classroom_id.in_(cids))
        .distinct()
        .order_by(User.full_name)
    )
    return list(db.scalars(stmt).unique())


# ---------------------------------------------------------------------------
# Опити
# ---------------------------------------------------------------------------


def build_layout(a: Assignment, questions: list[Question], variant: int) -> dict:
    """Ред на въпросите и на опциите за конкретен опит (детерминирано по вариант)."""
    rng = random.Random(f"{a.id}:{variant}")
    order = [q.id for q in questions]
    if a.shuffle_questions:
        # разбъркваме в рамките на секция, за да се запазят секциите
        by_section: dict[str | None, list[int]] = {}
        for q in questions:
            by_section.setdefault(q.section_key, []).append(q.id)
        order = []
        for key in dict.fromkeys(q.section_key for q in questions):
            ids = by_section[key]
            rng.shuffle(ids)
            order.extend(ids)
    options: dict[str, list[str]] = {}
    for q in questions:
        key = {
            "single_choice": "options",
            "multi_choice": "options",
            "ordering": "items",
            "matching": "right",
        }.get(q.type)
        # Подреждане и свързване винаги се разбъркват (иначе редът издава отговора)
        if key and q.data.get(key) and (a.shuffle_options or q.type in {"ordering", "matching"}):
            ids = [o["id"] for o in q.data[key]]
            rng.shuffle(ids)
            if q.type == "ordering" and ids == [o["id"] for o in q.data[key]] and len(ids) > 1:
                ids = ids[1:] + ids[:1]
            options[str(q.id)] = ids
    return {"order": order, "options": options}


def start_attempt(db: Session, a: Assignment, student: User) -> tuple[Attempt, str | None]:
    """Връща (опит, грешка). Ако има незавършен опит – връща него."""
    now = utcnow()
    existing = db.scalars(
        select(Attempt)
        .where(Attempt.assignment_id == a.id, Attempt.student_id == student.id)
        .order_by(Attempt.attempt_no)
    ).all()
    for at in existing:
        if at.status == "in_progress":
            if at.deadline_at and now > at.deadline_at + timedelta(seconds=15):
                finalize_attempt(db, at, auto=True)
                continue
            return at, None
    if not assignment_is_open(a, now):
        return None, "Заданието не е активно в момента."
    if a.attempts_allowed and len(existing) >= a.attempts_allowed:
        return None, "Изчерпали сте разрешените опити."
    questions = list(
        db.scalars(select(Question).where(Question.test_id == a.test_id).order_by(Question.position))
    )
    if not questions:
        return None, "Тестът няма въпроси."
    variant = random.randint(1, max(1, a.variants))
    deadline = None
    if a.time_limit_min:
        deadline = now + timedelta(minutes=a.time_limit_min)
    if a.end_at and (deadline is None or a.end_at < deadline):
        deadline = a.end_at
    at = Attempt(
        assignment_id=a.id,
        student_id=student.id,
        attempt_no=len(existing) + 1,
        variant=variant,
        layout=build_layout(a, questions, variant),
        started_at=now,
        deadline_at=deadline,
        max_score=sum(q.points for q in questions),
    )
    db.add(at)
    db.flush()
    db.add(AttemptEvent(attempt_id=at.id, kind="start", detail=f"вариант {variant}"))
    return at, None


def attempt_questions(db: Session, at: Attempt) -> list[Question]:
    qs = {q.id: q for q in db.scalars(select(Question).where(Question.test_id == at.assignment.test_id))}
    order = [qid for qid in at.layout.get("order", []) if qid in qs]
    missing = [qid for qid in qs if qid not in order]
    return [qs[i] for i in order] + [qs[i] for i in sorted(missing)]


def apply_option_order(q: Question, layout: dict, data: dict) -> dict:
    ids = layout.get("options", {}).get(str(q.id))
    if not ids:
        return data
    key = {
        "single_choice": "options",
        "multi_choice": "options",
        "ordering": "items",
        "matching": "right",
    }.get(q.type)
    if not key or key not in data:
        return data
    by_id = {o["id"]: o for o in data[key]}
    data = dict(data)
    data[key] = [by_id[i] for i in ids if i in by_id] + [o for o in data[key] if o["id"] not in ids]
    return data


def attempt_time_left(at: Attempt) -> int | None:
    if not at.deadline_at:
        return None
    return max(0, int((at.deadline_at - utcnow()).total_seconds()))


def attempt_expired(at: Attempt, grace_s: int = 15) -> bool:
    return bool(at.deadline_at and utcnow() > at.deadline_at + timedelta(seconds=grace_s))


def grade_answer(ans: Answer, q: Question) -> None:
    res = grade_response(q.type, q.data, ans.response)
    ans.auto_score = round(res.fraction * q.points, 3)
    ans.is_correct = res.is_correct if is_auto(q.type) else None
    ans.needs_manual = res.needs_manual


def finalize_attempt(db: Session, at: Attempt, *, auto: bool = False, annul: bool = False) -> None:
    """Оценява всички отговори и затваря опита."""
    questions = {q.id: q for q in attempt_questions(db, at)}
    answers = {a.question_id: a for a in at.answers}
    total = 0.0
    needs_manual = False
    for qid, q in questions.items():
        ans = answers.get(qid)
        if ans is None:
            ans = Answer(attempt_id=at.id, question_id=qid, response=None)
            db.add(ans)
            at.answers.append(ans)
        grade_answer(ans, q)
        needs_manual = needs_manual or ans.needs_manual
        total += ans.final_score
    at.max_score = sum(q.points for q in questions.values()) or 1.0
    at.submitted_at = utcnow()
    if annul:
        at.status = "annulled"
        at.score = 0.0
        at.percent = 0.0
        at.grade = 2
        at.needs_manual = False
        db.add(
            AttemptEvent(
                attempt_id=at.id, kind="annulled", detail="анулиран след превишен брой предупреждения"
            )
        )
    else:
        at.status = "submitted"
        at.score = round(total, 2)
        at.percent = round(100 * total / at.max_score, 1)
        at.grade = percent_to_grade(at.percent, at.assignment.grade_scale)
        at.needs_manual = needs_manual
        db.add(AttemptEvent(attempt_id=at.id, kind="autosubmit" if auto else "submit"))
    db.flush()


def recompute_attempt(at: Attempt) -> None:
    """След ръчно оценяване: преизчислява точките, процента и оценката."""
    if at.status == "annulled":
        return
    total = sum(a.final_score for a in at.answers)
    at.score = round(total, 2)
    at.percent = round(100 * total / (at.max_score or 1), 1)
    at.grade = percent_to_grade(at.percent, at.assignment.grade_scale)
    at.needs_manual = any(a.needs_manual and a.manual_score is None for a in at.answers)
    at.graded_at = utcnow()


def register_violation(db: Session, at: Attempt, kind: str, detail: str = "") -> dict:
    """Отчита нарушение в изпитен режим. Връща текущото състояние."""
    a = at.assignment
    now = utcnow()
    # Едно превключване на таб често дава blur + visibilitychange – слива се в едно нарушение
    if at.last_violation_at and (now - at.last_violation_at) < timedelta(seconds=3):
        return {
            "warnings": at.warnings,
            "max_warnings": a.max_warnings,
            "status": at.status,
            "coalesced": True,
        }
    at.last_violation_at = now
    at.warnings += 1
    db.add(AttemptEvent(attempt_id=at.id, kind="violation", detail=f"{kind} {detail}".strip()[:255]))
    if at.warnings > a.max_warnings:
        finalize_attempt(db, at, annul=True)
    db.flush()
    return {"warnings": at.warnings, "max_warnings": a.max_warnings, "status": at.status, "coalesced": False}


# ---------------------------------------------------------------------------
# Резултати и статистика
# ---------------------------------------------------------------------------


def assignment_results(db: Session, a: Assignment) -> dict:
    students = assignment_students(db, a)
    attempts = list(
        db.scalars(
            select(Attempt)
            .where(Attempt.assignment_id == a.id)
            .order_by(Attempt.student_id, Attempt.attempt_no)
        )
    )
    by_student: dict[int, list[Attempt]] = {}
    for at in attempts:
        by_student.setdefault(at.student_id, []).append(at)
    rows = []
    submitted = in_progress = not_started = 0
    percents: list[float] = []
    grades: list[float] = []
    for s in students:
        ats = by_student.get(s.id, [])
        best = None
        finished = [x for x in ats if x.status in {"submitted", "annulled"}]
        if finished:
            best = max(finished, key=lambda x: (x.percent, x.attempt_no))
        current = next((x for x in ats if x.status == "in_progress"), None)
        if best is not None:
            submitted += 1
            percents.append(best.percent)
            if best.grade is not None:
                grades.append(best.grade)
            status = best.status
        elif current is not None:
            in_progress += 1
            status = "in_progress"
        else:
            not_started += 1
            status = "not_started"
        rows.append(
            {
                "student": user_dict(s),
                "status": status,
                "attempts": [attempt_dict(x) for x in ats],
                "best": attempt_dict(best) if best else None,
                "current": attempt_dict(current) if current else None,
            }
        )
    # по въпроси
    questions = list(
        db.scalars(select(Question).where(Question.test_id == a.test_id).order_by(Question.position))
    )
    finished_ids = [at.id for at in attempts if at.status == "submitted"]
    per_question = []
    if finished_ids:
        stats = db.execute(
            select(
                Answer.question_id,
                func.count(Answer.id),
                func.sum(func.coalesce(Answer.manual_score, Answer.auto_score, 0.0)),
                func.sum(func.coalesce(Answer.is_correct, 0)),
            )
            .where(Answer.attempt_id.in_(finished_ids))
            .group_by(Answer.question_id)
        ).all()
        smap = {row[0]: row for row in stats}
        for i, q in enumerate(questions):
            row = smap.get(q.id)
            n = row[1] if row else 0
            earned = float(row[2] or 0) if row else 0.0
            per_question.append(
                {
                    "id": q.id,
                    "n": i + 1,
                    "type": q.type,
                    "type_label": type_label(q.type),
                    "topic": q.topic,
                    "points": q.points,
                    "answered": n,
                    "avg_percent": round(100 * earned / (n * q.points), 1) if n and q.points else 0.0,
                    "correct": int(row[3] or 0) if row else 0,
                }
            )
    else:
        per_question = [
            {
                "id": q.id,
                "n": i + 1,
                "type": q.type,
                "type_label": type_label(q.type),
                "topic": q.topic,
                "points": q.points,
                "answered": 0,
                "avg_percent": 0.0,
                "correct": 0,
            }
            for i, q in enumerate(questions)
        ]
    avg_percent = round(sum(percents) / len(percents), 1) if percents else None
    avg_grade = round(sum(grades) / len(grades), 2) if grades else None
    dist = {str(g): sum(1 for x in grades if int(x) == g) for g in (2, 3, 4, 5, 6)}
    return {
        "assignment": assignment_dict(a),
        "summary": {
            "total": len(students),
            "submitted": submitted,
            "in_progress": in_progress,
            "not_started": not_started,
            "avg_percent": avg_percent,
            "avg_grade": avg_grade,
            "avg_grade_label": grade_label(avg_grade) if avg_grade else "–",
            "grade_distribution": dist,
            "needs_manual": sum(1 for at in attempts if at.needs_manual and at.status == "submitted"),
        },
        "rows": rows,
        "per_question": per_question,
    }


def question_counts_by_test(db: Session, test_ids: list[int]) -> dict[int, tuple[int, float]]:
    if not test_ids:
        return {}
    rows = db.execute(
        select(Question.test_id, func.count(Question.id), func.sum(Question.points))
        .where(Question.test_id.in_(test_ids))
        .group_by(Question.test_id)
    ).all()
    return {r[0]: (r[1], float(r[2] or 0)) for r in rows}


def safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
