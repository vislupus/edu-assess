"""Настройки на приложението (четат се от средата / .env)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ЕдуТест"
    secret_key: str = "change-me-in-production-please"
    debug: bool = False

    # Данни
    data_dir: Path = BASE_DIR / "data"
    database_path: Path | None = None  # по подразбиране data/db/edu_assess.db
    uploads_dir: Path | None = None  # по подразбиране data/uploads
    max_upload_mb: int = 20

    # Натоварване: нишки за синхронни операции на процес (виж WEB_CONCURRENCY за процеси)
    worker_threads: int = 40
    db_pool_size: int = 40
    db_busy_timeout_ms: int = 10_000

    # AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_s: float = 90.0
    ai_mock: bool = False  # демо режим без реален AI (когато няма ключ)

    # Сесии
    session_cookie: str = "edu_session"
    session_max_age: int = 60 * 60 * 12

    @property
    def db_path(self) -> Path:
        return self.database_path or (self.data_dir / "db" / "edu_assess.db")

    @property
    def uploads_path(self) -> Path:
        return self.uploads_dir or (self.data_dir / "uploads")

    @property
    def curricula_path(self) -> Path:
        return self.data_dir / "curricula"


settings = Settings()
