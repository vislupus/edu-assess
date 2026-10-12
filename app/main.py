"""FastAPI приложение.

Стартиране: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2}`
(или `./run.sh`). Всеки процес обслужва синхронните операции в thread pool
(`WORKER_THREADS`), а SQLite работи в WAL режим – виж `app/db.py`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import init_db, startup_lock, write_session
from .routers import (
    api_assignments,
    api_attempts,
    api_classes,
    api_curricula,
    api_questions,
    api_tests,
    api_uploads,
    pages,
)
from .seed import seed
from .templating import render

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO, format="%(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("edu_assess")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Повече нишки за синхронни крайни точки (по подразбиране anyio дава 40)
    anyio.to_thread.current_default_thread_limiter().total_tokens = settings.worker_threads
    init_db()
    with startup_lock():
        db = write_session()
        try:
            if seed(db):
                log.info("Заредени демо данни.")
            db.commit()
        except Exception:  # pragma: no cover
            db.rollback()
            raise
        finally:
            db.close()
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie,
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=False,
)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

for r in (
    api_classes,
    api_questions,
    api_tests,
    api_assignments,
    api_attempts,
    api_uploads,
    api_curricula,
    pages,
):
    app.include_router(r.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303 and exc.headers and exc.headers.get("Location"):
        return RedirectResponse(exc.headers["Location"], status_code=303)
    if request.url.path.startswith("/api/") or request.headers.get("accept", "").startswith(
        "application/json"
    ):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    if exc.status_code in (401, 403, 404, 409, 501):
        return render(request, "error.html", user=None, status=exc.status_code, detail=exc.detail)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}
