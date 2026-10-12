"""Генериране на въпроси с Google Gemini (REST API, асинхронно).

Използва се `generateContent` с JSON отговор. Когато няма API ключ и
`AI_MOCK=1`, се връщат демонстрационни въпроси, за да може платформата да се
разглежда без външна услуга.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Any

import httpx

from ..config import settings
from ..question_types import QUESTION_TYPES, QuestionDataError, ai_type_catalog, clean_html, normalize_data

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = """Ти си опитен български учител и автор на учебни тестове.
Създаваш въпроси на български език, стриктно съобразени с подадената учебна програма
(теми, очаквани резултати, понятия). Въпросите са точни, еднозначни, подходящи за възрастта
и с ясно верен отговор. Математически и физични формули записвай в KaTeX между $...$
(например $x^2+3x-4=0$). Не измисляй факти извън учебното съдържание.
Отговаряй САМО с валиден JSON без коментари и без markdown."""


class AIError(RuntimeError):
    pass


def ai_available() -> bool:
    return bool(settings.gemini_api_key) or settings.ai_mock


def ai_mode() -> str:
    if settings.gemini_api_key:
        return "gemini"
    if settings.ai_mock:
        return "mock"
    return "off"


def _build_prompt(
    *,
    curriculum_text: str,
    qtype: str,
    count: int,
    difficulty: int,
    topics: list[str],
    instructions: str,
    subject: str,
    grade_label: str,
) -> str:
    meta = QUESTION_TYPES[qtype]
    diff_txt = {
        1: "ниска (възпроизвеждане на знания)",
        2: "средна (разбиране и приложение)",
        3: "висока (анализ, многостъпково решение)",
    }[difficulty]
    topics_txt = "; ".join(topics) if topics else "по избор от цялата програма (разнообразни теми)"
    return f"""УЧЕБНА ПРОГРАМА (контекст):
{curriculum_text}

ЗАДАЧА:
Създай точно {count} въпроса от тип "{qtype}" ({meta["label"]}) по {subject}, {grade_label}.
Теми: {topics_txt}
Трудност: {diff_txt}
{("Допълнителни указания от учителя: " + instructions) if instructions else ""}

ФОРМАТ НА data ЗА ТОЗИ ТИП:
{meta["ai_schema"]}

Върни JSON масив с {count} обекта със следната структура:
[{{"stem":"<текст на въпроса като HTML, напр. <p>...</p>>","topic":"<заглавие на темата от програмата>","difficulty":{difficulty},"points":<точки 1-3>,"data":{{...}}}}]

Важно: всички id в data са кратки низове; верните отговори трябва да са коректни; текстовете да не съдържат номерация на въпроса."""


def _extract_json(text: str) -> Any:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("["), text.rfind("]")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


async def _call_gemini(prompt: str) -> str:
    url = GEMINI_URL.format(model=settings.gemini_model)
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.8},
    }
    async with httpx.AsyncClient(timeout=settings.gemini_timeout_s) as client:
        resp = await client.post(url, params={"key": settings.gemini_api_key}, json=body)
    if resp.status_code != 200:
        detail = resp.text[:400]
        log.error("Gemini error %s: %s", resp.status_code, detail)
        raise AIError(f"Gemini върна грешка {resp.status_code}: {detail}")
    payload = resp.json()
    try:
        return payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise AIError("Неочакван отговор от Gemini.") from exc


def _normalize_generated(raw: Any, qtype: str, difficulty: int, count: int) -> list[dict]:
    if isinstance(raw, dict):
        raw = raw.get("questions") or raw.get("items") or [raw]
    if not isinstance(raw, list):
        raise AIError("AI не върна списък с въпроси.")
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            data = normalize_data(qtype, item.get("data"))
        except QuestionDataError as exc:
            log.warning("Пропуснат AI въпрос (%s): %s", qtype, exc)
            continue
        stem = clean_html(item.get("stem") or "")
        if not stem:
            continue
        try:
            pts = float(item.get("points") or 1)
        except (TypeError, ValueError):
            pts = 1.0
        out.append(
            {
                "type": qtype,
                "stem": stem,
                "data": data,
                "topic": str(item.get("topic") or "")[:255],
                "difficulty": int(item.get("difficulty") or difficulty),
                "points": max(0.5, min(pts, 10)),
            }
        )
        if len(out) >= count:
            break
    if not out:
        raise AIError("AI не върна нито един валиден въпрос. Опитайте отново.")
    return out


async def generate_questions(
    *,
    curriculum_text: str,
    subject: str,
    grade_label: str,
    qtype: str,
    count: int,
    difficulty: int = 2,
    topics: list[str] | None = None,
    instructions: str = "",
) -> list[dict]:
    if qtype not in QUESTION_TYPES:
        raise AIError(f"Непознат тип: {qtype}")
    count = max(1, min(int(count), 15))
    difficulty = difficulty if difficulty in (1, 2, 3) else 2
    topics = topics or []

    if not settings.gemini_api_key:
        if settings.ai_mock:
            await asyncio.sleep(0.3)
            return mock_questions(
                qtype=qtype, count=count, difficulty=difficulty, topics=topics, subject=subject
            )
        raise AIError("Не е конфигуриран GEMINI_API_KEY. Добавете го в .env или включете AI_MOCK=1 за демо.")

    prompt = _build_prompt(
        curriculum_text=curriculum_text,
        qtype=qtype,
        count=count,
        difficulty=difficulty,
        topics=topics,
        instructions=instructions,
        subject=subject,
        grade_label=grade_label,
    )
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            text = await _call_gemini(prompt)
            raw = _extract_json(text)
            return _normalize_generated(raw, qtype, difficulty, count)
        except (json.JSONDecodeError, AIError) as exc:
            last_exc = exc
            log.warning("AI опит %d неуспешен: %s", attempt + 1, exc)
    raise AIError(str(last_exc) if last_exc else "Неуспешно генериране.")


# ---------------------------------------------------------------------------
# Демо генератор (без външна услуга)
# ---------------------------------------------------------------------------


def mock_questions(*, qtype: str, count: int, difficulty: int, topics: list[str], subject: str) -> list[dict]:
    topic = topics[0] if topics else subject
    out = []
    for i in range(count):
        n = i + 1
        stem = f"<p><em>[Демо AI]</em> Въпрос {n} по тема „{topic}“.</p>"
        data: dict
        if qtype == "single_choice":
            data = {
                "options": [
                    {"id": "a", "text": "Вариант А"},
                    {"id": "b", "text": "Вариант Б"},
                    {"id": "c", "text": "Вариант В"},
                    {"id": "d", "text": "Вариант Г"},
                ],
                "correct": random.choice("abcd"),
            }
        elif qtype == "multi_choice":
            data = {
                "options": [
                    {"id": "a", "text": "Твърдение 1"},
                    {"id": "b", "text": "Твърдение 2"},
                    {"id": "c", "text": "Твърдение 3"},
                    {"id": "d", "text": "Твърдение 4"},
                ],
                "correct": ["a", "c"],
            }
        elif qtype == "true_false":
            data = {
                "statements": [
                    {"id": "s1", "text": "Първо твърдение", "answer": True},
                    {"id": "s2", "text": "Второ твърдение", "answer": False},
                    {"id": "s3", "text": "Трето твърдение", "answer": True},
                ]
            }
        elif qtype == "dropdown_blank":
            data = {
                "text": "Изберете [[1]] дума и след това [[2]] дума.",
                "blanks": {
                    "1": {"options": ["правилната", "грешната"], "correct": "правилната"},
                    "2": {"options": ["следващата", "предишната"], "correct": "следващата"},
                },
            }
        elif qtype == "fill_blank":
            data = {"text": "Столицата на България е [[1]].", "blanks": {"1": {"answers": ["София"]}}}
        elif qtype == "ordering":
            data = {
                "items": [
                    {"id": "i1", "text": "Първо"},
                    {"id": "i2", "text": "Второ"},
                    {"id": "i3", "text": "Трето"},
                    {"id": "i4", "text": "Четвърто"},
                ],
                "correct_order": ["i1", "i2", "i3", "i4"],
            }
        elif qtype == "matching":
            data = {
                "left": [
                    {"id": "l1", "text": "Понятие 1"},
                    {"id": "l2", "text": "Понятие 2"},
                    {"id": "l3", "text": "Понятие 3"},
                ],
                "right": [
                    {"id": "r1", "text": "Определение 1"},
                    {"id": "r2", "text": "Определение 2"},
                    {"id": "r3", "text": "Определение 3"},
                    {"id": "r4", "text": "Излишно"},
                ],
                "pairs": {"l1": "r1", "l2": "r2", "l3": "r3"},
            }
        elif qtype == "grouping":
            data = {
                "groups": [{"id": "g1", "name": "Група А"}, {"id": "g2", "name": "Група Б"}],
                "items": [
                    {"id": "i1", "text": "Елемент 1", "group": "g1"},
                    {"id": "i2", "text": "Елемент 2", "group": "g2"},
                    {"id": "i3", "text": "Елемент 3", "group": "g1"},
                    {"id": "i4", "text": "Елемент 4", "group": "g2"},
                ],
            }
        elif qtype == "numeric":
            data = {"answer": 42, "tolerance": 0, "unit": "", "widget": "input"}
        elif qtype == "find_errors":
            data = {
                "text": "Тази изречение съдържа две грешки в думите.",
                "errors": [{"index": 0, "correct": "Това"}, {"index": 4, "correct": "две"}],
            }
            data["text"] = "Тази изречение съдържа двe грешки в думите."
        elif qtype == "open":
            data = {"model_answer": "<p>Примерен модел на отговор.</p>", "min_words": 20}
        elif qtype == "file_upload":
            data = {
                "instructions": "<p>Качете файл с решението.</p>",
                "allowed_ext": ["pdf", "jpg", "png"],
                "max_mb": 10,
            }
        elif qtype == "hotspot":
            data = {
                "image_url": "",
                "labels": [{"id": "k1", "text": "Обект 1"}, {"id": "k2", "text": "Обект 2"}],
                "markers": [
                    {"id": "m1", "x": 30, "y": 40, "label_id": "k1"},
                    {"id": "m2", "x": 70, "y": 60, "label_id": "k2"},
                ],
            }
        elif qtype == "reading":
            data = {
                "passage": "<p>Кратък текст за четене с разбиране, който съдържа няколко факта за проверка.</p>",
                "sub_questions": [
                    {
                        "id": "q1",
                        "type": "single_choice",
                        "stem": "<p>За какво се разказва в текста?</p>",
                        "points": 1,
                        "data": {
                            "options": [{"id": "a", "text": "За факти"}, {"id": "b", "text": "За нищо"}],
                            "correct": "a",
                        },
                    },
                    {
                        "id": "q2",
                        "type": "true_false",
                        "stem": "<p>Преценете твърденията.</p>",
                        "points": 1,
                        "data": {"statements": [{"id": "s1", "text": "Текстът е кратък.", "answer": True}]},
                    },
                ],
            }
        elif qtype == "listening":
            data = {
                "audio_url": "",
                "transcript": "Текст за прочитане на глас от учителя.",
                "sub_questions": [
                    {
                        "id": "q1",
                        "type": "single_choice",
                        "stem": "<p>Какво чухте?</p>",
                        "points": 1,
                        "data": {
                            "options": [{"id": "a", "text": "Текст"}, {"id": "b", "text": "Музика"}],
                            "correct": "a",
                        },
                    }
                ],
            }
        else:
            data = {}
        out.append(
            {
                "type": qtype,
                "stem": stem,
                "data": normalize_data(qtype, data),
                "topic": topic,
                "difficulty": difficulty,
                "points": 1.0,
            }
        )
    return out


__all__ = ["AIError", "ai_available", "ai_mode", "ai_type_catalog", "generate_questions"]
