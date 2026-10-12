"""API: качване на файлове (изображения, аудио, отговори с файл)."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..auth import CurrentUser
from ..config import settings
from ..db import get_db, get_db_write
from ..models import Upload

router = APIRouter(tags=["uploads"])

ALLOWED = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "svg",
    "mp3",
    "wav",
    "ogg",
    "m4a",
    "pdf",
    "docx",
    "doc",
    "txt",
    "xlsx",
    "pptx",
    "zip",
}


@router.post("/api/uploads", status_code=201)
async def upload(file: UploadFile, user: CurrentUser, db: Annotated[Session, Depends(get_db_write)]):
    name = Path(file.filename or "file").name
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise HTTPException(400, f"Неподдържан файлов формат: .{ext}")
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    stored = f"{secrets.token_hex(12)}.{ext}"
    dest = settings.uploads_path / stored
    size = 0
    limit = settings.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    while chunk := await file.read(1024 * 256):
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"Файлът надвишава {settings.max_upload_mb} MB.")
        chunks.append(chunk)
    # записът на диск е блокиращ – изпълнява се в thread pool, за да не спира event loop-а
    await run_in_threadpool(dest.write_bytes, b"".join(chunks))
    up = Upload(
        owner_id=user.id,
        filename=name[:255],
        stored_name=stored,
        mime=file.content_type or "application/octet-stream",
        size=size,
    )
    db.add(up)
    db.flush()
    return {"id": up.id, "filename": up.filename, "url": f"/files/{stored}", "size": size, "mime": up.mime}


@router.get("/files/{stored_name}")
def get_file(stored_name: str, user: CurrentUser, db: Annotated[Session, Depends(get_db)]):
    if "/" in stored_name or ".." in stored_name:
        raise HTTPException(404)
    path = settings.uploads_path / stored_name
    if not path.exists():
        raise HTTPException(404)
    up = db.query(Upload).filter(Upload.stored_name == stored_name).first()
    filename = up.filename if up else stored_name
    return FileResponse(
        path, media_type=up.mime if up else None, filename=filename, content_disposition_type="inline"
    )
