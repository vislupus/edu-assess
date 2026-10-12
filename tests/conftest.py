import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="edu-assess-test-"))
os.environ["DATABASE_PATH"] = str(_tmp / "test.db")
os.environ["UPLOADS_DIR"] = str(_tmp / "uploads")
os.environ["AI_MOCK"] = "1"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str) -> dict:
    """Влиза като демо потребител по username и връща данните му."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        u = db.scalar(select(User).where(User.username == username))
        assert u, username
        r = client.post("/login", data={"user_id": u.id}, follow_redirects=False)
        assert r.status_code == 303
        return {"id": u.id, "role": u.role, "full_name": u.full_name}
    finally:
        db.close()
