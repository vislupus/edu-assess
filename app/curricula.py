"""Зареждане на учебните програми от data/curricula/*.json в базата."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Curriculum

ROMAN = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
}


def parse_grade(label: str) -> int:
    m = re.match(r"\s*([IVX]+)", label or "")
    if m and m.group(1) in ROMAN:
        return ROMAN[m.group(1)]
    m = re.search(r"(\d+)", label or "")
    return int(m.group(1)) if m else 0


def upsert_curriculum(db: Session, data: dict, code: str | None = None) -> Curriculum:
    code = (
        code
        or data.get("code")
        or re.sub(r"\W+", "-", f"{data.get('subject', '')}-{data.get('grade', '')}").lower()
    )
    grade = int(data.get("grade_number") or parse_grade(str(data.get("grade", ""))))
    cur = db.scalar(select(Curriculum).where(Curriculum.code == code))
    if cur is None:
        cur = Curriculum(code=code, subject="", grade=0, grade_label="", title="", data={})
        db.add(cur)
    cur.subject = data.get("subject", "")
    cur.grade = grade
    cur.grade_label = str(data.get("grade", f"{grade} клас"))
    cur.title = f"{cur.subject} – {cur.grade_label}"
    cur.data = data
    return cur


def load_curricula_from_disk(db: Session) -> int:
    n = 0
    path = settings.curricula_path
    if not path.exists():
        return 0
    for f in sorted(path.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        upsert_curriculum(db, data, code=data.get("code") or f.stem)
        n += 1
    db.flush()
    return n


def curriculum_context(cur: Curriculum, topics: list[str] | None = None, max_chars: int = 14000) -> str:
    """Текстов контекст за AI: избрани теми (или всички) с очаквани резултати и понятия."""
    d = cur.data
    wanted = {t.strip() for t in (topics or []) if t and t.strip()}
    lines = [
        f"Учебен предмет: {d.get('subject')}",
        f"Клас: {d.get('grade')}",
        f"Обхват: {d.get('scope', '')}",
    ]
    if d.get("goals"):
        lines.append("Цели: " + " ".join(d["goals"]))
    lines.append("")
    lines.append("ТЕМИ ОТ УЧЕБНОТО СЪДЪРЖАНИЕ:")
    for t in d.get("topics", []):
        if wanted and t.get("title") not in wanted:
            continue
        lines.append(f"## {t.get('title')}")
        if t.get("subtopics"):
            lines.append("Подтеми: " + "; ".join(t["subtopics"]))
        if t.get("results"):
            lines.append("Очаквани резултати: " + " ".join(t["results"]))
        if t.get("concepts"):
            lines.append("Нови понятия: " + ", ".join(t["concepts"]))
    if d.get("formulas"):
        lines.append("")
        lines.append("Формули (KaTeX): " + " | ".join(d["formulas"]))
    text = "\n".join(lines)
    return text[:max_chars]
