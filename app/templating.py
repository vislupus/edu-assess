"""Jinja2 среда с помощни филтри."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from .config import settings
from .grading import grade_label
from .question_types import DIFFICULTY_LABELS, type_label

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

MONTHS = ["ян.", "февр.", "март", "апр.", "май", "юни", "юли", "авг.", "септ.", "окт.", "ноем.", "дек."]


def fmt_dt(v: datetime | None, with_time: bool = True) -> str:
    if not v:
        return "–"
    s = f"{v.day} {MONTHS[v.month - 1]} {v.year}"
    if with_time:
        s += f", {v:%H:%M}"
    return s


def tojson_attr(v: Any) -> Markup:
    return Markup(json.dumps(v, ensure_ascii=False).replace("<", "\\u003c"))


templates.env.filters["dt"] = fmt_dt
templates.env.filters["isodt"] = lambda v: (v.replace(microsecond=0).isoformat() + "Z") if v else ""
templates.env.filters["grade_label"] = grade_label
templates.env.filters["type_label"] = type_label
templates.env.filters["difficulty_label"] = lambda d: DIFFICULTY_LABELS.get(d, "")
templates.env.filters["jsonattr"] = tojson_attr
templates.env.globals["app_name"] = settings.app_name


def render(request: Request, name: str, **ctx: Any):
    return templates.TemplateResponse(request, name, ctx)
