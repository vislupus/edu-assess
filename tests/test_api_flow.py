"""Интеграционен тест: учител създава клас/тест/задание, ученик решава; изпитен режим."""

from conftest import login


def test_login_required(client):
    client.post("/logout")
    assert client.get("/api/classes").status_code == 401
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_teacher_full_flow_and_exam_annulment(client):
    login(client, "m.ivanova")
    cur = client.get("/api/curricula").json()
    math = next(c for c in cur if c["code"] == "math-8")

    c = client.post("/api/classes", json={"name": "Тестов клас", "curriculum_id": math["id"]}).json()
    students = client.get("/api/students?grade=7а").json()
    assert len(students) == 5
    r = client.post(
        f"/api/classes/{c['id']}/students", json={"student_ids": [s["id"] for s in students[:2]]}
    ).json()
    assert r["student_count"] == 2
    r = client.delete(f"/api/classes/{c['id']}/students/{students[0]['id']}").json()
    assert r["student_count"] == 1

    t = client.post("/api/tests", json={"title": "API тест", "curriculum_id": math["id"]}).json()
    q = client.post(
        f"/api/tests/{t['id']}/questions",
        json={
            "type": "single_choice",
            "stem": "<p>2+2?</p>",
            "data": {"options": ["3", "4"], "correct": "o2"},
            "points": 2,
        },
    )
    assert q.status_code == 201
    q2 = client.post(
        f"/api/tests/{t['id']}/questions",
        json={"type": "open", "stem": "<p>Обяснете.</p>", "data": {}, "points": 3},
    ).json()
    bad = client.post(
        f"/api/tests/{t['id']}/questions",
        json={"type": "single_choice", "stem": "<p>x</p>", "data": {"options": ["a"]}},
    )
    assert bad.status_code == 422

    # AI (демо режим) запълва контейнер
    r = client.patch(
        f"/api/tests/{t['id']}",
        json={
            "title": "API тест",
            "sections": [
                {"key": "s1", "title": "Ръчни", "source": "manual"},
                {
                    "key": "ai",
                    "title": "AI",
                    "type": "true_false",
                    "count": 2,
                    "source": "ai",
                    "topics": ["2. Вектори"],
                },
            ],
        },
    )
    assert r.status_code == 200
    r = client.post(f"/api/tests/{t['id']}/generate", json={})
    assert r.status_code == 200 and r.json()["mode"] == "mock"
    assert len(r.json()["results"][0]["added"]) == 2
    full = client.get(f"/api/tests/{t['id']}").json()
    assert full["question_count"] == 4

    a = client.post(
        "/api/assignments",
        json={
            "test_id": t["id"],
            "mode": "exam",
            "classroom_ids": [c["id"]],
            "time_limit_min": 30,
            "max_warnings": 3,
            "show_results": "immediately",
        },
    ).json()
    assert a["mode"] == "exam" and a["attempts_allowed"] == 1

    # ученикът
    student = students[1]
    client.post("/logout")
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    db = SessionLocal()
    uname = db.scalar(select(User.username).where(User.id == student["id"]))
    db.close()
    login(client, uname)
    mine = client.get("/api/my/assignments").json()
    mine_a = next(x for x in mine if x["id"] == a["id"])
    assert mine_a["can_start"]
    at = client.post(f"/api/assignments/{a['id']}/start").json()
    data = client.get(f"/api/attempts/{at['id']}").json()
    assert data["time_left"] is not None and 0 < data["time_left"] <= 1800
    first = data["questions"][0]
    assert "correct" not in first["data"]  # верните отговори не се изпращат
    qid = next(x["id"] for x in data["questions"] if x["type"] == "single_choice")
    r = client.put(f"/api/attempts/{at['id']}/answers/{qid}", json={"response": "o2"})
    assert r.status_code == 200
    client.put(f"/api/attempts/{at['id']}/answers/{q2['id']}", json={"response": {"text": "<p>Защото.</p>"}})

    # 3 предупреждения, 4-то нарушение анулира (с изчакване заради сливането на събития)
    import time

    from app.models import Attempt

    for i in range(1, 5):
        r = client.post(f"/api/attempts/{at['id']}/violation", json={"kind": "tab"}).json()
        if i <= 3:
            assert r["warnings"] == i and r["status"] == "in_progress"
        else:
            assert r["status"] == "annulled"
        # заобикаляме 3-секундното сливане
        db = SessionLocal()
        obj = db.get(Attempt, at["id"])
        obj.last_violation_at = None
        db.commit()
        db.close()
        time.sleep(0.01)
    rev = client.get(f"/api/attempts/{at['id']}/review").json()
    assert rev["attempt"]["grade"] == 2 and rev["attempt"]["status"] == "annulled"
    assert client.put(f"/api/attempts/{at['id']}/answers/{qid}", json={"response": "o1"}).status_code == 409
    assert client.post(f"/api/assignments/{a['id']}/start").status_code == 409  # опитите са изчерпани

    # учителят вижда резултатите
    client.post("/logout")
    login(client, "m.ivanova")
    res = client.get(f"/api/assignments/{a['id']}/results").json()
    assert res["summary"]["submitted"] == 1
    row = next(r for r in res["rows"] if r["student"]["id"] == student["id"])
    assert row["status"] == "annulled" and row["best"]["warnings"] == 4


def test_practice_submit_grade_and_manual_grading(client):
    client.post("/logout")
    login(client, "g.petrov")
    classes = client.get("/api/classes").json()
    tests = client.get("/api/tests").json()
    a = client.post(
        "/api/assignments",
        json={
            "test_id": tests[0]["id"],
            "mode": "practice",
            "classroom_ids": [classes[0]["id"]],
            "attempts_allowed": 0,
        },
    ).json()
    client.post("/logout")
    login(client, "a.dimitrov")
    at = client.post(f"/api/assignments/{a['id']}/start").json()
    data = client.get(f"/api/attempts/{at['id']}").json()
    open_q = next(q for q in data["questions"] if q["type"] == "open")
    # отговаряме вярно на единичния избор, като вземем верния отговор от базата
    from app.db import SessionLocal
    from app.models import Question

    sc = next(q for q in data["questions"] if q["type"] == "single_choice")
    db = SessionLocal()
    correct = db.get(Question, sc["id"]).data["correct"]
    db.close()
    client.put(f"/api/attempts/{at['id']}/answers/{sc['id']}", json={"response": correct})
    client.put(
        f"/api/attempts/{at['id']}/answers/{open_q['id']}",
        json={"response": {"text": "<p>Национална катастрофа е...</p>"}},
    )
    r = client.post(f"/api/attempts/{at['id']}/submit").json()
    assert r["status"] == "submitted" and r["needs_manual"] is True and r["score"] == sc["points"]
    # преглед от ученика – вижда верните отговори
    rev = client.get(f"/api/attempts/{at['id']}/review").json()
    assert rev["questions"][0]["data"] and not rev["teacher_view"]
    # учителят оценява отворения въпрос
    client.post("/logout")
    login(client, "g.petrov")
    g = client.post(
        f"/api/attempts/{at['id']}/grade",
        json={"answers": {str(open_q["id"]): {"manual_score": 3, "feedback": "Добре"}}, "feedback": "Браво"},
    ).json()
    assert g["score"] == sc["points"] + 3 and g["needs_manual"] is False
    assert client.post(f"/api/attempts/{at['id']}/reopen").json()["ok"]


def test_bank_and_curriculum_upload(client):
    client.post("/logout")
    login(client, "e.nikolova")
    stats = client.get("/api/bank/stats").json()
    assert stats["total"] >= 10
    r = client.post(
        "/api/curricula",
        files={
            "file": (
                "x.json",
                '{"subject":"Физика","grade":"VII клас","topics":[{"title":"Движение","results":[],"concepts":[]}]}'.encode(),
                "application/json",
            )
        },
    )
    assert r.status_code == 201 and r.json()["grade"] == 7
    assert (
        client.post("/api/curricula", files={"file": ("x.json", b"{bad", "application/json")}).status_code
        == 400
    )
    assert client.get("/api/ai/status").json()["mode"] == "mock"
