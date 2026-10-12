"""Тест за натоварване: много ученици едновременно решават тест.

Стартирайте сървъра (./run.sh) и след това:
    uv run python scripts/loadtest.py --students 15 --rounds 20 --base http://localhost:8000

Всеки „ученик“ влиза, започва опит по първото активно упражнение, записва
отговори паралелно (autosave) и предава. Отчитат се latency и грешки.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time

import httpx


async def student_flow(base: str, user_id: int, rounds: int, lat: list[float], errors: list[str]) -> None:
    async with httpx.AsyncClient(base_url=base, timeout=30) as c:
        r = await c.post("/login", data={"user_id": user_id}, follow_redirects=False)
        if r.status_code not in (303, 302):
            errors.append(f"login {user_id}: {r.status_code}")
            return
        r = await c.get("/api/my/assignments")
        if r.status_code != 200:
            errors.append(f"assignments {user_id}: {r.status_code} {r.text[:80]}")
            return
        practice = [a for a in r.json() if a["mode"] == "practice" and (a["can_start"] or a["can_resume"])]
        if not practice:
            errors.append(f"student {user_id}: няма активно упражнение")
            return
        a = practice[0]
        if a["can_resume"]:
            at_id = a["current"]["id"]
        else:
            r = await c.post(f"/api/assignments/{a['id']}/start")
            if r.status_code != 200:
                errors.append(f"start {user_id}: {r.status_code} {r.text[:80]}")
                return
            at_id = r.json()["id"]
        r = await c.get(f"/api/attempts/{at_id}")
        qs = r.json()["questions"]
        for _ in range(rounds):
            q = random.choice(qs)
            resp = _random_response(q)
            t0 = time.perf_counter()
            r = await c.put(f"/api/attempts/{at_id}/answers/{q['id']}", json={"response": resp})
            lat.append(time.perf_counter() - t0)
            if r.status_code != 200:
                errors.append(f"save {user_id}: {r.status_code} {r.text[:80]}")
        t0 = time.perf_counter()
        r = await c.post(f"/api/attempts/{at_id}/submit")
        lat.append(time.perf_counter() - t0)
        if r.status_code != 200:
            errors.append(f"submit {user_id}: {r.status_code} {r.text[:80]}")


def _random_response(q: dict):
    d = q["data"]
    t = q["type"]
    if t == "single_choice":
        return random.choice(d["options"])["id"]
    if t == "multi_choice":
        return [o["id"] for o in d["options"] if random.random() < 0.5]
    if t == "true_false":
        return {s["id"]: random.random() < 0.5 for s in d["statements"]}
    if t in {"dropdown_blank"}:
        return {k: random.choice(b["options"]) for k, b in d["blanks"].items()}
    if t == "fill_blank":
        return {k: random.choice(["24", "10", "София"]) for k in d["blanks"]}
    if t == "ordering":
        ids = [i["id"] for i in d["items"]]
        random.shuffle(ids)
        return ids
    if t == "matching":
        return {l["id"]: random.choice(d["right"])["id"] for l in d["left"]}
    if t == "grouping":
        return {i["id"]: random.choice(d["groups"])["id"] for i in d["items"]}
    if t == "numeric":
        return random.choice([49, 48, 50])
    if t == "open":
        return {"text": "<p>Отговор от теста за натоварване.</p>"}
    return None


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--students", type=int, default=15)
    p.add_argument("--rounds", type=int, default=20)
    p.add_argument("--first-student-id", type=int, default=4, help="id на първия ученик (демо: 4..18)")
    args = p.parse_args()
    lat: list[float] = []
    errors: list[str] = []
    ids = list(range(args.first_student_id, args.first_student_id + args.students))
    t0 = time.perf_counter()
    await asyncio.gather(*(student_flow(args.base, uid, args.rounds, lat, errors) for uid in ids))
    total = time.perf_counter() - t0
    if lat:
        lat.sort()
        print(f"Заявки: {len(lat)} за {total:.2f}s  ({len(lat) / total:.0f} req/s)")
        print(
            f"Latency ms: median={statistics.median(lat) * 1000:.1f} p95={lat[int(len(lat) * 0.95)] * 1000:.1f} max={lat[-1] * 1000:.1f}"
        )
    print(f"Грешки: {len(errors)}")
    for e in errors[:10]:
        print(" -", e)


if __name__ == "__main__":
    asyncio.run(main())
