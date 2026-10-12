"""Регистър на типовете въпроси: етикети, валидация/нормализация и описание за AI.

Всеки тип описва структурата на `Question.data` и формата на отговора на ученика.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import nh3

# ---------------------------------------------------------------------------
# HTML санитизация (Quill + KaTeX формули)
# ---------------------------------------------------------------------------

_ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "u",
    "s",
    "sub",
    "sup",
    "span",
    "ol",
    "ul",
    "li",
    "blockquote",
    "pre",
    "code",
    "h1",
    "h2",
    "h3",
    "h4",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    "div",
}
_ALLOWED_ATTRS = {
    "*": {"class"},
    "span": {"class", "data-value"},
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height"},
    "li": {"data-list", "class"},
}


def clean_html(html: str | None) -> str:
    if not html:
        return ""
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes={"http", "https", "data", "mailto"},
        link_rel="noopener noreferrer",
    )


def clean_text(text: Any) -> str:
    """Кратък текст (опции, етикети): без HTML тагове, но KaTeX `$…$` се запазва."""
    if text is None:
        return ""
    s = str(text)
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def new_id(prefix: str = "o") -> str:
    return f"{prefix}{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Описание на типовете
# ---------------------------------------------------------------------------

DIFFICULTY_LABELS = {1: "Ниска трудност", 2: "Средна трудност", 3: "Висока трудност"}

SUB_QUESTION_TYPES = {"single_choice", "multi_choice", "true_false", "fill_blank", "open", "dropdown_blank"}

QUESTION_TYPES: dict[str, dict[str, Any]] = {
    "single_choice": {
        "label": "С един верен отговор",
        "icon": "circle-dot",
        "auto": True,
        "group": "Избор",
        "ai_schema": '{"options":[{"id":"a","text":"..."},{"id":"b","text":"..."},{"id":"c","text":"..."},'
        '{"id":"d","text":"..."}],"correct":"b"} – точно 4 опции, само една вярна.',
    },
    "multi_choice": {
        "label": "С повече от един верен отговор",
        "icon": "list-checks",
        "auto": True,
        "group": "Избор",
        "ai_schema": '{"options":[{"id":"a","text":"..."},...],"correct":["a","c"]} – 4–6 опции, 2–3 верни.',
    },
    "true_false": {
        "label": "Вярно / грешно",
        "icon": "toggle-left",
        "auto": True,
        "group": "Избор",
        "ai_schema": '{"statements":[{"id":"s1","text":"...","answer":true},{"id":"s2","text":"...","answer":false}]}'
        " – 3–5 твърдения.",
    },
    "dropdown_blank": {
        "label": "Избери в празното поле",
        "icon": "chevrons-down-up",
        "auto": True,
        "group": "Попълване",
        "ai_schema": '{"text":"Врабчето [[1]] по оградата. Борис беше [[2]] от успеха си.",'
        '"blanks":{"1":{"options":["подскача","плува","лети"],"correct":"подскача"},'
        '"2":{"options":["щастлив","тъжен","гладен"],"correct":"щастлив"}}} – 1–3 празни места [[n]].',
    },
    "fill_blank": {
        "label": "Попълни празното поле",
        "icon": "text-cursor-input",
        "auto": True,
        "group": "Попълване",
        "ai_schema": '{"text":"Столицата на България е [[1]].","blanks":{"1":{"answers":["София"]}}}'
        " – 1–3 празни места [[n]]; в answers са всички приемливи варианти.",
    },
    "ordering": {
        "label": "Подреди отговорите",
        "icon": "arrow-down-up",
        "auto": True,
        "group": "Подреждане",
        "ai_schema": '{"items":[{"id":"i1","text":"..."},...],"correct_order":["i3","i1","i2","i4"]}'
        " – 4–6 елемента; correct_order съдържа всички id в правилния ред.",
    },
    "matching": {
        "label": "Свържи отговорите",
        "icon": "git-compare-arrows",
        "auto": True,
        "group": "Подреждане",
        "ai_schema": '{"left":[{"id":"l1","text":"..."}],"right":[{"id":"r1","text":"..."}],"pairs":{"l1":"r1"}}'
        " – 3–5 двойки; right може да има 1 допълнителен (грешен) елемент.",
    },
    "grouping": {
        "label": "Групирай отговорите",
        "icon": "layout-grid",
        "auto": True,
        "group": "Подреждане",
        "ai_schema": '{"groups":[{"id":"g1","name":"..."},{"id":"g2","name":"..."}],'
        '"items":[{"id":"i1","text":"...","group":"g1"},...]} – 2–3 групи, 6–8 елемента.',
    },
    "numeric": {
        "label": "Определяне на величина",
        "icon": "sliders-horizontal",
        "auto": True,
        "group": "Числов",
        "ai_schema": '{"answer":75,"tolerance":0,"unit":"m","min":0,"max":120,"step":1,"widget":"input"}'
        ' – widget е "input" или "slider"; tolerance е допустимо отклонение.',
    },
    "find_errors": {
        "label": "Открий грешките",
        "icon": "spell-check",
        "auto": True,
        "group": "Текст",
        "ai_schema": '{"text":"Плаваме по реката с малък парахот.","errors":[{"index":5,"correct":"параход."}]}'
        " – text съдържа 2–5 умишлени грешки; index е 0-базиран номер на думата (разделител интервал),"
        " correct е правилната дума заедно с пунктуацията след нея.",
    },
    "open": {
        "label": "Отворен въпрос",
        "icon": "pen-line",
        "auto": False,
        "group": "Свободен",
        "ai_schema": '{"model_answer":"Примерен отговор / критерии за оценяване","min_words":20}',
    },
    "file_upload": {
        "label": "Отговор с файл",
        "icon": "upload",
        "auto": False,
        "group": "Свободен",
        "ai_schema": '{"instructions":"Качете файл с ...","allowed_ext":["pdf","jpg","png","docx"],"max_mb":10}',
    },
    "hotspot": {
        "label": "Маркирай и назови",
        "icon": "map-pin",
        "auto": True,
        "group": "Изображение",
        "ai_schema": '{"image_url":"","labels":[{"id":"k1","text":"..."}],'
        '"markers":[{"id":"m1","x":35.5,"y":40.2,"label_id":"k1"}]} – без изображение AI оставя image_url празен'
        " и учителят качва картинка; x,y са проценти.",
    },
    "reading": {
        "label": "Четене с разбиране",
        "icon": "book-open-text",
        "auto": True,
        "group": "Комплексен",
        "ai_schema": '{"passage":"<p>Текст от 120–200 думи...</p>","sub_questions":[{"id":"q1","type":"single_choice",'
        '"stem":"...","points":1,"data":{...}},{"id":"q2","type":"true_false","stem":"...","points":1,"data":{...}}]}'
        " – 3–4 подвъпроса от типове single_choice, multi_choice, true_false, fill_blank, open.",
    },
    "listening": {
        "label": "Слушане с разбиране",
        "icon": "headphones",
        "auto": True,
        "group": "Комплексен",
        "ai_schema": '{"audio_url":"","transcript":"Текст, който учителят ще запише като аудио (80–150 думи)",'
        '"sub_questions":[{"id":"q1","type":"single_choice","stem":"...","points":1,"data":{...}}]}'
        " – 3–4 подвъпроса; audio_url остава празен – учителят качва аудио.",
    },
}

TYPE_ORDER = list(QUESTION_TYPES.keys())


def type_label(t: str) -> str:
    return QUESTION_TYPES.get(t, {}).get("label", t)


def is_auto(t: str) -> bool:
    return bool(QUESTION_TYPES.get(t, {}).get("auto", False))


# ---------------------------------------------------------------------------
# Валидация и нормализация
# ---------------------------------------------------------------------------


class QuestionDataError(ValueError):
    pass


def _opts(raw: Any, prefix: str = "o", min_n: int = 2) -> list[dict]:
    if not isinstance(raw, list):
        raise QuestionDataError("Липсват опции.")
    out = []
    for i, o in enumerate(raw):
        if isinstance(o, str):
            o = {"id": f"{prefix}{i + 1}", "text": o}
        if not isinstance(o, dict):
            continue
        text = clean_text(o.get("text") or o.get("name"))
        if not text:
            continue
        out.append({"id": str(o.get("id") or f"{prefix}{i + 1}"), "text": text})
    if len(out) < min_n:
        raise QuestionDataError(f"Необходими са поне {min_n} елемента.")
    ids = [o["id"] for o in out]
    if len(set(ids)) != len(ids):
        for i, o in enumerate(out):
            o["id"] = f"{prefix}{i + 1}"
    return out


def _blank_keys(text: str) -> list[str]:
    return re.findall(r"\[\[(\w+)\]\]", text)


def normalize_data(qtype: str, data: Any, *, allow_sub: bool = True) -> dict:
    """Проверява и нормализира `data` за даден тип. Хвърля QuestionDataError."""
    if qtype not in QUESTION_TYPES:
        raise QuestionDataError(f"Непознат тип въпрос: {qtype}")
    if not isinstance(data, dict):
        data = {}

    if qtype == "single_choice":
        options = _opts(data.get("options"))
        correct = str(data.get("correct") or "")
        if correct not in {o["id"] for o in options}:
            raise QuestionDataError("Не е посочен верен отговор.")
        return {"options": options, "correct": correct}

    if qtype == "multi_choice":
        options = _opts(data.get("options"))
        ids = {o["id"] for o in options}
        correct = [str(c) for c in (data.get("correct") or []) if str(c) in ids]
        if not correct:
            raise QuestionDataError("Не е посочен верен отговор.")
        return {
            "options": options,
            "correct": sorted(set(correct)),
            "partial_credit": bool(data.get("partial_credit", True)),
        }

    if qtype == "true_false":
        raw = data.get("statements")
        if not isinstance(raw, list) or not raw:
            raise QuestionDataError("Липсват твърдения.")
        statements = []
        for i, s in enumerate(raw):
            if not isinstance(s, dict):
                continue
            text = clean_text(s.get("text"))
            if not text:
                continue
            ans = s.get("answer")
            if isinstance(ans, str):
                ans = ans.strip().lower() in {"true", "вярно", "да", "1"}
            statements.append({"id": str(s.get("id") or f"s{i + 1}"), "text": text, "answer": bool(ans)})
        if not statements:
            raise QuestionDataError("Липсват твърдения.")
        return {"statements": statements}

    if qtype == "dropdown_blank":
        text = clean_text(data.get("text"))
        keys = _blank_keys(text)
        if not keys:
            raise QuestionDataError("Текстът трябва да съдържа поне едно празно място [[1]].")
        blanks_raw = data.get("blanks") or {}
        blanks = {}
        for k in keys:
            b = blanks_raw.get(k) if isinstance(blanks_raw, dict) else None
            if not isinstance(b, dict):
                raise QuestionDataError(f"Липсват опции за празно място [[{k}]].")
            options = [clean_text(o) for o in (b.get("options") or []) if clean_text(o)]
            correct = clean_text(b.get("correct"))
            if correct and correct not in options:
                options.append(correct)
            if len(options) < 2 or not correct:
                raise QuestionDataError(f"Празно място [[{k}]] се нуждае от поне 2 опции и верен отговор.")
            blanks[k] = {"options": options, "correct": correct}
        return {"text": text, "blanks": blanks}

    if qtype == "fill_blank":
        text = clean_text(data.get("text"))
        keys = _blank_keys(text)
        if not keys:
            raise QuestionDataError("Текстът трябва да съдържа поне едно празно място [[1]].")
        blanks_raw = data.get("blanks") or {}
        blanks = {}
        for k in keys:
            b = blanks_raw.get(k) if isinstance(blanks_raw, dict) else None
            answers = []
            if isinstance(b, dict):
                answers = [clean_text(a) for a in (b.get("answers") or []) if clean_text(a)]
            elif isinstance(b, list):
                answers = [clean_text(a) for a in b if clean_text(a)]
            elif isinstance(b, str):
                answers = [clean_text(b)]
            if not answers:
                raise QuestionDataError(f"Липсва верен отговор за празно място [[{k}]].")
            blanks[k] = {"answers": answers}
        return {"text": text, "blanks": blanks, "case_sensitive": bool(data.get("case_sensitive", False))}

    if qtype == "ordering":
        items = _opts(data.get("items"), prefix="i", min_n=2)
        ids = [i["id"] for i in items]
        order = [str(x) for x in (data.get("correct_order") or []) if str(x) in ids]
        if sorted(order) != sorted(ids):
            order = ids  # редът на подаване е верният
        return {"items": items, "correct_order": order}

    if qtype == "matching":
        left = _opts(data.get("left"), prefix="l", min_n=2)
        right = _opts(data.get("right"), prefix="r", min_n=2)
        rids = {r["id"] for r in right}
        pairs_raw = data.get("pairs") or {}
        pairs = {}
        for item in left:
            target = pairs_raw.get(item["id"]) if isinstance(pairs_raw, dict) else None
            if str(target) not in rids:
                raise QuestionDataError(f"Липсва съответствие за „{item['text']}“.")
            pairs[item["id"]] = str(target)
        return {"left": left, "right": right, "pairs": pairs}

    if qtype == "grouping":
        groups = _opts(data.get("groups"), prefix="g", min_n=2)
        gids = {g["id"] for g in groups}
        items = []
        for i, it in enumerate(data.get("items") or []):
            if not isinstance(it, dict):
                continue
            text = clean_text(it.get("text"))
            grp = str(it.get("group") or "")
            if not text or grp not in gids:
                continue
            items.append({"id": str(it.get("id") or f"i{i + 1}"), "text": text, "group": grp})
        if len(items) < 2:
            raise QuestionDataError("Необходими са поне 2 елемента, разпределени в групи.")
        return {"groups": [{"id": g["id"], "name": g["text"]} for g in groups], "items": items}

    if qtype == "numeric":
        try:
            answer = float(data.get("answer"))
        except (TypeError, ValueError):
            raise QuestionDataError("Липсва числов отговер.") from None
        tol = float(data.get("tolerance") or 0)
        widget = data.get("widget") if data.get("widget") in {"input", "slider"} else "input"
        out = {
            "answer": answer,
            "tolerance": abs(tol),
            "unit": clean_text(data.get("unit")),
            "widget": widget,
        }
        for k in ("min", "max", "step"):
            if data.get(k) not in (None, ""):
                try:
                    out[k] = float(data[k])
                except (TypeError, ValueError):
                    pass
        if widget == "slider":
            out.setdefault("min", 0.0)
            out.setdefault("max", max(answer * 2, 10.0))
            out.setdefault("step", 1.0)
        return out

    if qtype == "find_errors":
        text = clean_text(data.get("text"))
        tokens = text.split()
        if not tokens:
            raise QuestionDataError("Липсва текст.")
        errors = []
        seen = set()
        for e in data.get("errors") or []:
            if not isinstance(e, dict):
                continue
            try:
                idx = int(e.get("index"))
            except (TypeError, ValueError):
                continue
            correct = clean_text(e.get("correct"))
            if idx < 0 or idx >= len(tokens) or not correct or idx in seen:
                continue
            seen.add(idx)
            errors.append({"index": idx, "correct": correct})
        if not errors:
            raise QuestionDataError("Посочете поне една грешка в текста.")
        errors.sort(key=lambda e: e["index"])
        return {"text": text, "errors": errors}

    if qtype == "open":
        return {
            "model_answer": clean_html(data.get("model_answer") or ""),
            "min_words": int(data.get("min_words") or 0),
        }

    if qtype == "file_upload":
        exts = [clean_text(x).lstrip(".").lower() for x in (data.get("allowed_ext") or [])]
        return {
            "instructions": clean_html(data.get("instructions") or ""),
            "allowed_ext": [e for e in exts if e] or ["pdf", "jpg", "jpeg", "png", "docx", "txt"],
            "max_mb": min(int(data.get("max_mb") or 10), 50),
        }

    if qtype == "hotspot":
        labels = _opts(data.get("labels"), prefix="k", min_n=1)
        lids = {lb["id"] for lb in labels}
        markers = []
        for i, m in enumerate(data.get("markers") or []):
            if not isinstance(m, dict):
                continue
            try:
                x, y = float(m.get("x")), float(m.get("y"))
            except (TypeError, ValueError):
                continue
            lab = str(m.get("label_id") or "")
            if lab not in lids:
                continue
            markers.append(
                {"id": str(m.get("id") or f"m{i + 1}"), "x": round(x, 2), "y": round(y, 2), "label_id": lab}
            )
        return {"image_url": clean_text(data.get("image_url")), "labels": labels, "markers": markers}

    if qtype in {"reading", "listening"}:
        if not allow_sub:
            raise QuestionDataError("Комплексен тип не може да е подвъпрос.")
        subs = []
        for i, sq in enumerate(data.get("sub_questions") or []):
            if not isinstance(sq, dict):
                continue
            st = sq.get("type")
            if st not in SUB_QUESTION_TYPES:
                continue
            try:
                sdata = normalize_data(st, sq.get("data"), allow_sub=False)
            except QuestionDataError:
                continue
            try:
                pts = float(sq.get("points") or 1)
            except (TypeError, ValueError):
                pts = 1.0
            subs.append(
                {
                    "id": str(sq.get("id") or f"q{i + 1}"),
                    "type": st,
                    "stem": clean_html(sq.get("stem") or ""),
                    "points": pts,
                    "data": sdata,
                }
            )
        if not subs:
            raise QuestionDataError("Необходим е поне един подвъпрос.")
        out: dict[str, Any] = {"sub_questions": subs}
        if qtype == "reading":
            out["passage"] = clean_html(data.get("passage") or data.get("passage_html") or "")
        else:
            out["audio_url"] = clean_text(data.get("audio_url"))
            out["transcript"] = clean_text(data.get("transcript"))
        return out

    raise QuestionDataError(f"Непознат тип въпрос: {qtype}")


def public_data(qtype: str, data: dict) -> dict:
    """Версия на `data` без верните отговори – изпраща се на ученика по време на решаване."""
    d = dict(data or {})
    if qtype == "single_choice" or qtype == "multi_choice":
        d.pop("correct", None)
    elif qtype == "true_false":
        d["statements"] = [{"id": s["id"], "text": s["text"]} for s in d.get("statements", [])]
    elif qtype == "dropdown_blank":
        d["blanks"] = {k: {"options": v["options"]} for k, v in d.get("blanks", {}).items()}
    elif qtype == "fill_blank":
        d["blanks"] = {k: {} for k in d.get("blanks", {})}
    elif qtype == "ordering":
        d.pop("correct_order", None)
    elif qtype == "matching":
        d.pop("pairs", None)
    elif qtype == "grouping":
        d["items"] = [{"id": i["id"], "text": i["text"]} for i in d.get("items", [])]
    elif qtype == "numeric":
        d.pop("answer", None)
        d.pop("tolerance", None)
    elif qtype == "find_errors":
        d.pop("errors", None)
    elif qtype == "open":
        d.pop("model_answer", None)
    elif qtype == "hotspot":
        d["markers"] = [{"id": m["id"], "x": m["x"], "y": m["y"]} for m in d.get("markers", [])]
    elif qtype in {"reading", "listening"}:
        d.pop("transcript", None)
        d["sub_questions"] = [
            {**sq, "data": public_data(sq["type"], sq["data"])} for sq in d.get("sub_questions", [])
        ]
    return d


def ai_type_catalog() -> str:
    lines = []
    for key, meta in QUESTION_TYPES.items():
        lines.append(f'- "{key}" ({meta["label"]}): data = {meta["ai_schema"]}')
    return "\n".join(lines)
