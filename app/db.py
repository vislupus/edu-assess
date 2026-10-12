"""SQLite достъп, настроен за много едновременни потребители.

* WAL режим – четенията не блокират записите и обратно.
* `BEGIN IMMEDIATE` за сесии за запис – избягва взаимни блокировки при
  повишаване от четене към запис.
* Автоматичен повторен опит при `database is locked`.
* Синхронните крайни точки на FastAPI се изпълняват в thread pool, така че
  event loop-ът никога не се блокира от SQLite.
"""

from __future__ import annotations

import contextlib
import fcntl
import logging
import random
import time
from collections.abc import Callable, Generator, Iterator
from typing import TypeVar

from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import QueuePool

from .config import settings

log = logging.getLogger(__name__)

T = TypeVar("T")


class Base(DeclarativeBase):
    pass


settings.db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    poolclass=QueuePool,
    pool_size=settings.db_pool_size,
    max_overflow=10,
    pool_pre_ping=False,
    connect_args={
        "check_same_thread": False,
        "timeout": settings.db_busy_timeout_ms / 1000,
        # Сами управляваме транзакциите (виж do_begin по-долу)
        "isolation_level": None,
    },
)


@event.listens_for(engine, "connect")
def _on_connect(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute(f"PRAGMA busy_timeout={settings.db_busy_timeout_ms}")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA temp_store=MEMORY")
    cur.execute("PRAGMA cache_size=-32000")  # ~32 MB на връзка
    cur.execute("PRAGMA mmap_size=268435456")
    cur.close()


@event.listens_for(engine, "begin")
def _do_begin(conn) -> None:
    # Сесиите за запис взимат RESERVED lock веднага, за да не се налага
    # повишаване от SHARED към RESERVED по средата на транзакцията.
    if conn.get_execution_options().get("sqlite_write"):
        conn.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        conn.exec_driver_sql("BEGIN")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Сесия за четене (DEFERRED транзакция)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_write() -> Generator[Session, None, None]:
    """Сесия за запис (IMMEDIATE транзакция, commit при успех)."""
    db = SessionLocal()
    try:
        db.connection(execution_options={"sqlite_write": True})
        yield db
        if db.in_transaction():
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def write_session() -> Session:
    """Ръчно създадена сесия за запис (извън dependency injection)."""
    db = SessionLocal()
    db.connection(execution_options={"sqlite_write": True})
    return db


def with_retry[T](fn: Callable[[], T], attempts: int = 6) -> T:
    """Изпълнява fn() и повтаря при „database is locked“ с експоненциално изчакване."""
    delay = 0.05
    for i in range(attempts):
        try:
            return fn()
        except OperationalError as exc:  # pragma: no cover - зависи от натоварването
            msg = str(exc).lower()
            if "locked" not in msg and "busy" not in msg or i == attempts - 1:
                raise
            log.warning("SQLite busy, retry %d: %s", i + 1, msg)
            time.sleep(delay + random.random() * delay)
            delay *= 2
    raise RuntimeError("unreachable")


@contextlib.contextmanager
def startup_lock() -> Iterator[None]:
    """Междупроцесен lock (WEB_CONCURRENCY > 1): само един процес инициализира базата."""
    lock_path = settings.db_path.with_suffix(".init.lock")
    with open(lock_path, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def init_db() -> None:
    from . import models  # noqa: F401  (регистрира таблиците)

    with startup_lock():
        Base.metadata.create_all(engine, checkfirst=True)
