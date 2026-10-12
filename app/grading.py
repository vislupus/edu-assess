"""Автоматично оценяване на отговори и преобразуване на процент в оценка."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .question_types import is_auto

DEFAULT_GRADE_SCALE: dict[str, float] = {"6": 90, "5": 75, "4": 60, "3": 50}
GRADE_NAMES = {2: "Слаб", 3: "Среден", 4: "Добър", 5: "Мн. добър", 6: "Отличен"}


def percent_to_grade(percent: float, scale: dict | None = None) -> int:
    scale = {str(k): float(v) for k, v in (scale or DEFAULT_GRADE_SCALE).items()} or DEFAULT_GRADE_SCALE
    for g in (6, 5, 4, 3):
        if percent >= scale.get(str(g), DEFAULT_GRADE_SCALE[str(g)]):
            return g
    return 2


def grade_label(grade: float | None) -> str:
    if grade is None:
        return "–"
    g = round(grade)
    return f"{GRADE_NAMES.get(g, '')} ({g})"


@dataclass
class GradeResult:
    fraction: float  # 0..1
    needs_manual: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_correct(self) -> bool:
        return self.fraction >= 0.999


def _norm(s: Any) -> str:
    s = "" if s is None else str(s)
    s = s.replace("„", '"').replace("“", '"').replace("”", '"').replace("’", "'")
    s = re.sub(r"\s+", " ", s).strip().casefold()
    return s


def _norm_loose(s: Any) -> str:
    return _norm(s).rstrip(".,;:!?")


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def grade_response(qtype: str, data: dict, response: Any) -> GradeResult:
    """Връща дял от точките (0..1) за даден отговор."""
    if not is_auto(qtype):
        has = bool(response) and (
            (isinstance(response, dict) and bool(response.get("text") or response.get("upload_id")))
            or isinstance(response, str)
        )
        return GradeResult(0.0, needs_manual=bool(has), details={"answered": bool(has)})

    if response is None or response == "" or response == [] or response == {}:
        return GradeResult(0.0, details={"answered": False})

    if qtype == "single_choice":
        ok = str(response) == data.get("correct")
        return GradeResult(1.0 if ok else 0.0)

    if qtype == "multi_choice":
        chosen = {str(x) for x in response} if isinstance(response, list) else {str(response)}
        correct = set(data.get("correct", []))
        if not correct:
            return GradeResult(0.0)
        if not data.get("partial_credit", True):
            return GradeResult(1.0 if chosen == correct else 0.0)
        hits = len(chosen & correct)
        wrong = len(chosen - correct)
        return GradeResult(_clamp((hits - wrong) / len(correct)), details={"hits": hits, "wrong": wrong})

    if qtype == "true_false":
        stmts = data.get("statements", [])
        if not isinstance(response, dict) or not stmts:
            return GradeResult(0.0)
        per = {}
        for s in stmts:
            val = response.get(s["id"])
            if isinstance(val, str):
                val = val.lower() in {"true", "1", "вярно"}
            per[s["id"]] = val is not None and bool(val) == bool(s["answer"])
        return GradeResult(sum(per.values()) / len(stmts), details={"per": per})

    if qtype == "dropdown_blank":
        blanks = data.get("blanks", {})
        if not isinstance(response, dict) or not blanks:
            return GradeResult(0.0)
        per = {k: _norm(response.get(k)) == _norm(b["correct"]) for k, b in blanks.items()}
        return GradeResult(sum(per.values()) / len(blanks), details={"per": per})

    if qtype == "fill_blank":
        blanks = data.get("blanks", {})
        if not isinstance(response, dict) or not blanks:
            return GradeResult(0.0)
        cs = bool(data.get("case_sensitive"))
        per = {}
        for k, b in blanks.items():
            given = str(response.get(k) or "")
            answers = b.get("answers", [])
            if cs:
                per[k] = any(given.strip() == a.strip() for a in answers)
            else:
                per[k] = any(_norm_loose(given) == _norm_loose(a) for a in answers)
        return GradeResult(sum(per.values()) / len(blanks), details={"per": per})

    if qtype == "ordering":
        correct = data.get("correct_order", [])
        if not isinstance(response, list) or not correct:
            return GradeResult(0.0)
        given = [str(x) for x in response]
        if given == correct:
            return GradeResult(1.0)
        # частичен кредит: елементи на правилна позиция
        hits = sum(1 for i, x in enumerate(given[: len(correct)]) if x == correct[i])
        return GradeResult(_clamp(hits / len(correct) * 0.5), details={"hits": hits})

    if qtype == "matching":
        pairs = data.get("pairs", {})
        if not isinstance(response, dict) or not pairs:
            return GradeResult(0.0)
        per = {lid: str(response.get(lid)) == rid for lid, rid in pairs.items()}
        return GradeResult(sum(per.values()) / len(pairs), details={"per": per})

    if qtype == "grouping":
        items = data.get("items", [])
        if not isinstance(response, dict) or not items:
            return GradeResult(0.0)
        per = {it["id"]: str(response.get(it["id"])) == it["group"] for it in items}
        return GradeResult(sum(per.values()) / len(items), details={"per": per})

    if qtype == "numeric":
        try:
            val = float(str(response).replace(",", "."))
        except (TypeError, ValueError):
            return GradeResult(0.0, details={"invalid": True})
        ok = abs(val - float(data.get("answer", 0))) <= float(data.get("tolerance", 0)) + 1e-9
        return GradeResult(1.0 if ok else 0.0)

    if qtype == "find_errors":
        errors = data.get("errors", [])
        if not isinstance(response, dict) or not errors:
            return GradeResult(0.0)
        per = {}
        for e in errors:
            given = response.get(str(e["index"]))
            per[str(e["index"])] = given is not None and _norm(given) == _norm(e["correct"])
        hits = sum(per.values())
        # Лека санкция за „поправени“ правилни думи
        tokens = data.get("text", "").split()
        err_idx = {str(e["index"]) for e in errors}
        false_pos = sum(
            1
            for k, v in response.items()
            if k not in err_idx and k.isdigit() and int(k) < len(tokens) and _norm(v) != _norm(tokens[int(k)])
        )
        return GradeResult(
            _clamp((hits - 0.5 * false_pos) / len(errors)), details={"per": per, "false": false_pos}
        )

    if qtype == "hotspot":
        markers = data.get("markers", [])
        if not isinstance(response, dict) or not markers:
            return GradeResult(0.0)
        per = {m["id"]: str(response.get(m["id"])) == m["label_id"] for m in markers}
        return GradeResult(sum(per.values()) / len(markers), details={"per": per})

    if qtype in {"reading", "listening"}:
        subs = data.get("sub_questions", [])
        if not isinstance(response, dict) or not subs:
            return GradeResult(0.0)
        total = sum(float(sq.get("points") or 1) for sq in subs) or 1.0
        got = 0.0
        needs_manual = False
        per = {}
        for sq in subs:
            r = grade_response(sq["type"], sq["data"], response.get(sq["id"]))
            per[sq["id"]] = r.fraction
            got += r.fraction * float(sq.get("points") or 1)
            needs_manual = needs_manual or r.needs_manual
        return GradeResult(got / total, needs_manual=needs_manual, details={"per": per})

    return GradeResult(0.0)
