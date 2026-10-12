"""API: тестове, секции (контейнери), AI генериране и попълване от банката."""

from __future__ import annotations

import asyncio
import random
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..ai.gemini import AIError, ai_mode, generate_questions
from ..auth import Teacher
from ..curricula import curriculum_context
from ..db import get_db, get_db_write, write_session
from ..models import Assignment, Curriculum, Question, Test, User, utcnow
from ..question_types import QUESTION_TYPES
from ..services import question_counts_by_test, question_dict
from .api_questions import QuestionIn, apply_question

router = APIRouter(prefix="/api", tags=["tests"])

SECTION_FIELDS = ("key", "title", "type", "count", "difficulty", "topics", "points", "source", "instructions")


class TestIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    curriculum_id: int | None = None
    sections: list[dict[str, Any]] | None = None
    settings: dict[str, Any] | None = None
    status: str | None = None


class TestPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    curriculum_id: int | None = None
    sections: list[dict[str, Any]] | None = None
    settings: dict[str, Any] | None = None
    status: str | None = None


class ReorderIn(BaseModel):
    order: list[dict[str, Any]]  # [{id, section_key}]


class FromBankIn(BaseModel):
    question_ids: list[int]
    section_key: str | None = None


class GenerateIn(BaseModel):
    section_key: str | None = None  # None = всички AI секции


class FillIn(BaseModel):
    section_key: str


def _clean_sections(raw: list[dict[str, Any]] | None) -> list[dict]:
    out = []
    for i, s in enumerate(raw or []):
        if not isinstance(s, dict):
            continue
        key = str(s.get("key") or f"s{i + 1}")[:32]
        typ = s.get("type") if s.get("type") in QUESTION_TYPES else ""
        try:
            count = max(0, min(int(s.get("count") or 0), 30))
        except (TypeError, ValueError):
            count = 0
        try:
            difficulty = int(s.get("difficulty") or 2)
        except (TypeError, ValueError):
            difficulty = 2
        try:
            points = max(0.25, min(float(s.get("points") or 1), 100))
        except (TypeError, ValueError):
            points = 1.0
        topics = [str(t)[:255] for t in (s.get("topics") or []) if str(t).strip()]
        out.append(
            {
                "key": key,
                "title": str(s.get("title") or f"Част {i + 1}")[:120],
                "type": typ,
                "count": count,
                "difficulty": difficulty if difficulty in (1, 2, 3) else 2,
                "topics": topics,
                "points": points,
                "source": s.get("source") if s.get("source") in {"manual", "ai", "bank"} else "manual",
                "instructions": str(s.get("instructions") or "")[:1000],
            }
        )
    if not out:
        out = [
            {
                "key": "s1",
                "title": "Задачи",
                "type": "",
                "count": 0,
                "difficulty": 2,
                "topics": [],
                "points": 1,
                "source": "manual",
                "instructions": "",
            }
        ]
    keys = [s["key"] for s in out]
    if len(set(keys)) != len(keys):
        for i, s in enumerate(out):
            s["key"] = f"s{i + 1}"
    return out


def own_test(db: Session, tid: int, teacher: User) -> Test:
    t = db.get(Test, tid)
    if not t or t.owner_id != teacher.id:
        raise HTTPException(404, "Тестът не е намерен.")
    return t


def test_dict(db: Session, t: Test, *, with_questions: bool = False) -> dict:
    counts = question_counts_by_test(db, [t.id]).get(t.id, (0, 0.0))
    n_assign = db.scalar(select(func.count(Assignment.id)).where(Assignment.test_id == t.id)) or 0
    d = {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "subject": t.subject,
        "grade_label": t.grade_label,
        "curriculum_id": t.curriculum_id,
        "sections": t.sections,
        "settings": t.settings,
        "status": t.status,
        "question_count": counts[0],
        "total_points": counts[1],
        "assignment_count": n_assign,
        "created_at": t.created_at.isoformat() + "Z",
        "updated_at": t.updated_at.isoformat() + "Z",
    }
    if with_questions:
        d["questions"] = [question_dict(q) for q in t.questions]
    return d


@router.get("/tests")
def list_tests(teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    tests = db.scalars(select(Test).where(Test.owner_id == teacher.id).order_by(Test.updated_at.desc())).all()
    counts = question_counts_by_test(db, [t.id for t in tests])
    out = []
    for t in tests:
        c = counts.get(t.id, (0, 0.0))
        out.append({**test_dict(db, t), "question_count": c[0], "total_points": c[1]})
    return out


@router.post("/tests", status_code=201)
def create_test(body: TestIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    cur = db.get(Curriculum, body.curriculum_id) if body.curriculum_id else None
    t = Test(
        owner_id=teacher.id,
        title=body.title.strip(),
        description=body.description,
        curriculum_id=cur.id if cur else None,
        subject=cur.subject if cur else teacher.subject,
        grade_label=cur.grade_label if cur else None,
        sections=_clean_sections(body.sections),
        settings=body.settings or {},
    )
    db.add(t)
    db.flush()
    return test_dict(db, t, with_questions=True)


@router.get("/tests/{tid}")
def get_test(tid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db)]):
    return test_dict(db, own_test(db, tid, teacher), with_questions=True)


@router.patch("/tests/{tid}")
def update_test(tid: int, body: TestPatch, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    """Частична промяна: променят се само изрично подадените полета."""
    t = own_test(db, tid, teacher)
    sent = body.model_fields_set
    if body.title is not None and body.title.strip():
        t.title = body.title.strip()[:255]
    if body.description is not None:
        t.description = body.description
    if "curriculum_id" in sent and body.curriculum_id != t.curriculum_id:
        cur = db.get(Curriculum, body.curriculum_id) if body.curriculum_id else None
        t.curriculum_id = cur.id if cur else None
        if cur:
            t.subject, t.grade_label = cur.subject, cur.grade_label
    if body.sections is not None:
        t.sections = _clean_sections(body.sections)
        valid = {s["key"] for s in t.sections}
        for q in t.questions:
            if q.section_key not in valid:
                q.section_key = t.sections[0]["key"]
    if body.settings is not None:
        t.settings = body.settings
    if body.status in {"draft", "ready"}:
        t.status = body.status
    t.updated_at = utcnow()
    db.flush()
    return test_dict(db, t, with_questions=True)


@router.delete("/tests/{tid}", status_code=204)
def delete_test(tid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    t = own_test(db, tid, teacher)
    if db.scalar(select(func.count(Assignment.id)).where(Assignment.test_id == t.id)):
        raise HTTPException(409, "Тестът е възложен – първо изтрийте заданията му.")
    db.delete(t)
    db.flush()


@router.post("/tests/{tid}/duplicate", status_code=201)
def duplicate_test(tid: int, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    t = own_test(db, tid, teacher)
    copy = Test(
        owner_id=teacher.id,
        title=f"{t.title} (копие)",
        description=t.description,
        subject=t.subject,
        grade_label=t.grade_label,
        curriculum_id=t.curriculum_id,
        sections=t.sections,
        settings=t.settings,
        status="draft",
    )
    db.add(copy)
    db.flush()
    for q in t.questions:
        db.add(
            Question(
                owner_id=teacher.id,
                test_id=copy.id,
                section_key=q.section_key,
                position=q.position,
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
        )
    db.flush()
    return test_dict(db, copy)


# --- въпроси в теста ---------------------------------------------------------


@router.post("/tests/{tid}/questions", status_code=201)
def add_question(tid: int, body: QuestionIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    t = own_test(db, tid, teacher)
    pos = (db.scalar(select(func.max(Question.position)).where(Question.test_id == t.id)) or -1) + 1
    q = Question(owner_id=teacher.id, test_id=t.id, position=pos, source="manual")
    apply_question(q, body)
    if not q.section_key:
        q.section_key = t.sections[0]["key"] if t.sections else "s1"
    if q.curriculum_id is None:
        q.curriculum_id = t.curriculum_id
    db.add(q)
    t.updated_at = utcnow()
    db.flush()
    return question_dict(q)


@router.post("/tests/{tid}/reorder")
def reorder(tid: int, body: ReorderIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    t = own_test(db, tid, teacher)
    qmap = {q.id: q for q in t.questions}
    valid = {s["key"] for s in t.sections}
    for i, item in enumerate(body.order):
        q = qmap.get(int(item.get("id", 0)))
        if not q:
            continue
        q.position = i
        if item.get("section_key") in valid:
            q.section_key = item["section_key"]
    t.updated_at = utcnow()
    db.flush()
    return {"ok": True}


@router.post("/tests/{tid}/questions/from-bank", status_code=201)
def add_from_bank(
    tid: int, body: FromBankIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]
):
    t = own_test(db, tid, teacher)
    section = body.section_key if body.section_key in {s["key"] for s in t.sections} else t.sections[0]["key"]
    pos = (db.scalar(select(func.max(Question.position)).where(Question.test_id == t.id)) or -1) + 1
    added = []
    for qid in body.question_ids:
        src = db.get(Question, qid)
        if not src or src.owner_id != teacher.id:
            continue
        q = Question(
            owner_id=teacher.id,
            test_id=t.id,
            section_key=section,
            position=pos,
            type=src.type,
            stem=src.stem,
            data=src.data,
            difficulty=src.difficulty,
            points=src.points,
            curriculum_id=src.curriculum_id,
            topic=src.topic,
            tags=src.tags,
            source="bank",
            source_question_id=src.id,
        )
        pos += 1
        db.add(q)
        added.append(q)
    t.updated_at = utcnow()
    db.flush()
    return [question_dict(q) for q in added]


@router.post("/tests/{tid}/fill-from-bank")
def fill_from_bank(tid: int, body: FillIn, teacher: Teacher, db: Annotated[Session, Depends(get_db_write)]):
    """Попълва контейнер със случайни въпроси от банката по зададените критерии."""
    t = own_test(db, tid, teacher)
    section = next((s for s in t.sections if s["key"] == body.section_key), None)
    if not section:
        raise HTTPException(404, "Секцията не е намерена.")
    have = sum(1 for q in t.questions if q.section_key == section["key"])
    need = max(0, int(section.get("count") or 0) - have)
    if need == 0:
        return {"added": [], "message": "Секцията вече е запълнена."}
    stmt = select(Question).where(Question.owner_id == teacher.id, Question.test_id.is_(None))
    if section.get("type"):
        stmt = stmt.where(Question.type == section["type"])
    if t.curriculum_id:
        stmt = stmt.where(Question.curriculum_id == t.curriculum_id)
    if section.get("difficulty"):
        stmt = stmt.where(Question.difficulty == section["difficulty"])
    if section.get("topics"):
        stmt = stmt.where(Question.topic.in_(section["topics"]))
    used = {q.source_question_id for q in t.questions if q.source_question_id}
    pool = [q for q in db.scalars(stmt) if q.id not in used]
    random.shuffle(pool)
    chosen = pool[:need]
    pos = (db.scalar(select(func.max(Question.position)).where(Question.test_id == t.id)) or -1) + 1
    added = []
    for src in chosen:
        q = Question(
            owner_id=teacher.id,
            test_id=t.id,
            section_key=section["key"],
            position=pos,
            type=src.type,
            stem=src.stem,
            data=src.data,
            difficulty=src.difficulty,
            points=float(section.get("points") or src.points),
            curriculum_id=src.curriculum_id,
            topic=src.topic,
            tags=src.tags,
            source="bank",
            source_question_id=src.id,
        )
        pos += 1
        db.add(q)
        added.append(q)
    t.updated_at = utcnow()
    db.flush()
    msg = None if len(added) == need else f"В банката има само {len(added)} подходящи въпроса (нужни {need})."
    return {"added": [question_dict(q) for q in added], "message": msg}


# --- AI генериране -----------------------------------------------------------


def _load_test_for_ai(tid: int, teacher_id: int) -> tuple[dict, dict | None, dict[str, int]]:
    db = next(get_db())
    try:
        t = db.get(Test, tid)
        if not t or t.owner_id != teacher_id:
            raise HTTPException(404, "Тестът не е намерен.")
        cur = db.get(Curriculum, t.curriculum_id) if t.curriculum_id else None
        counts: dict[str, int] = {}
        for q in t.questions:
            counts[q.section_key or ""] = counts.get(q.section_key or "", 0) + 1
        info = {
            "id": t.id,
            "sections": t.sections,
            "subject": t.subject or (cur.subject if cur else ""),
            "grade_label": t.grade_label or (cur.grade_label if cur else ""),
            "curriculum_id": t.curriculum_id,
        }
        cur_info = None
        if cur:
            cur_info = {"id": cur.id, "subject": cur.subject, "grade_label": cur.grade_label, "obj": cur}
        return info, cur_info, counts
    finally:
        db.close()


def _insert_generated(
    tid: int, teacher_id: int, section_key: str, items: list[dict], cur_id: int | None, points: float
) -> list[dict]:
    db = write_session()
    try:
        t = db.get(Test, tid)
        pos = (db.scalar(select(func.max(Question.position)).where(Question.test_id == tid)) or -1) + 1
        out = []
        for it in items:
            q = Question(
                owner_id=teacher_id,
                test_id=tid,
                section_key=section_key,
                position=pos,
                type=it["type"],
                stem=it["stem"],
                data=it["data"],
                difficulty=it["difficulty"],
                points=points or it["points"],
                curriculum_id=cur_id,
                topic=it.get("topic"),
                source="ai",
            )
            pos += 1
            db.add(q)
            out.append(q)
        if t:
            t.updated_at = utcnow()
        db.commit()
        return [question_dict(q) for q in out]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/tests/{tid}/generate")
async def generate(tid: int, body: GenerateIn, teacher: Teacher):
    """Запълва AI контейнерите на теста с въпроси, генерирани по учебната програма."""
    if ai_mode() == "off":
        raise HTTPException(503, "AI генерирането не е конфигурирано (липсва GEMINI_API_KEY).")
    info, cur_info, counts = await run_in_threadpool(_load_test_for_ai, tid, teacher.id)
    if not cur_info:
        raise HTTPException(400, "Изберете учебна програма за теста, за да може AI да генерира по нея.")
    cur = cur_info["obj"]
    targets = [
        s
        for s in info["sections"]
        if s.get("source") == "ai"
        and s.get("type")
        and (body.section_key is None or s["key"] == body.section_key)
    ]
    if not targets:
        raise HTTPException(
            400, "Няма AI контейнери за генериране. Задайте тип и източник „AI“ на контейнер."
        )

    sem = asyncio.Semaphore(3)

    async def run(section: dict) -> dict:
        need = int(section.get("count") or 0) - counts.get(section["key"], 0)
        if need <= 0:
            return {"section_key": section["key"], "added": [], "message": "Контейнерът вече е запълнен."}
        ctx = curriculum_context(cur, section.get("topics") or [])
        async with sem:
            try:
                items = await generate_questions(
                    curriculum_text=ctx,
                    subject=cur.subject,
                    grade_label=cur.grade_label,
                    qtype=section["type"],
                    count=need,
                    difficulty=int(section.get("difficulty") or 2),
                    topics=section.get("topics") or [],
                    instructions=section.get("instructions") or "",
                )
            except AIError as exc:
                return {"section_key": section["key"], "added": [], "error": str(exc)}
        added = await run_in_threadpool(
            _insert_generated,
            tid,
            teacher.id,
            section["key"],
            items,
            cur_info["id"],
            float(section.get("points") or 0),
        )
        return {"section_key": section["key"], "added": added}

    results = await asyncio.gather(*(run(s) for s in targets))
    return {"mode": ai_mode(), "results": results}


class RegenerateIn(BaseModel):
    instructions: str = ""


@router.post("/questions/{qid}/regenerate")
async def regenerate_question(qid: int, body: RegenerateIn, teacher: Teacher):
    """Заменя съдържанието на един въпрос с ново, генерирано от AI (същият тип/тема/трудност)."""
    if ai_mode() == "off":
        raise HTTPException(503, "AI генерирането не е конфигурирано (липсва GEMINI_API_KEY).")

    def load() -> dict:
        db = next(get_db())
        try:
            q = db.get(Question, qid)
            if not q or q.owner_id != teacher.id:
                raise HTTPException(404, "Въпросът не е намерен.")
            cur = db.get(Curriculum, q.curriculum_id) if q.curriculum_id else None
            if not cur:
                raise HTTPException(400, "Въпросът не е свързан с учебна програма.")
            return {
                "type": q.type,
                "difficulty": q.difficulty,
                "topic": q.topic,
                "ctx": curriculum_context(cur, [q.topic] if q.topic else []),
                "subject": cur.subject,
                "grade_label": cur.grade_label,
            }
        finally:
            db.close()

    info = await run_in_threadpool(load)
    try:
        items = await generate_questions(
            curriculum_text=info["ctx"],
            subject=info["subject"],
            grade_label=info["grade_label"],
            qtype=info["type"],
            count=1,
            difficulty=info["difficulty"],
            topics=[info["topic"]] if info["topic"] else [],
            instructions=body.instructions,
        )
    except AIError as exc:
        raise HTTPException(502, str(exc)) from exc

    def save() -> dict:
        db = write_session()
        try:
            q = db.get(Question, qid)
            it = items[0]
            q.stem, q.data, q.source = it["stem"], it["data"], "ai"
            if it.get("topic"):
                q.topic = it["topic"]
            db.commit()
            return question_dict(q)
        finally:
            db.close()

    return await run_in_threadpool(save)


@router.get("/ai/status")
def ai_status(teacher: Teacher):
    return {"mode": ai_mode(), "available": ai_mode() != "off"}
