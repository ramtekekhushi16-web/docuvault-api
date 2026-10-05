import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import STORAGE_PATH
from app.core.security import verify_password
from app.db.session import get_db
from app.models.document import Document
from app.models.share_link import ShareLink

router = APIRouter(
    prefix="/api/share",
    tags=["Public Share Access"],
)


@router.get("/{token}")
def access_shared_document(
    token: str,
    password: str | None = None,
    db: Session = Depends(get_db),
):
    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    share_link = (
        db.query(ShareLink)
        .filter(ShareLink.token_hash == token_hash)
        .first()
    )

    if not share_link:
        raise HTTPException(
            status_code=404,
            detail="Share link not found",
        )

    if share_link.expires_at:
        expires_at = share_link.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=410,
                detail="Share link has expired",
            )

    if share_link.is_one_time and share_link.is_used:
        raise HTTPException(
            status_code=410,
            detail="Share link has already been used",
        )

    if share_link.password_hash:
        if not password:
            raise HTTPException(
                status_code=401,
                detail="Password required",
            )

        if not verify_password(
            password,
            share_link.password_hash,
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid share link password",
            )

    document = (
        db.query(Document)
        .filter(Document.id == share_link.document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = (
        f"{STORAGE_PATH}/{document.filename}"
    )

    try:
        response = FileResponse(
            path=file_path,
            filename=document.original_filename,
            media_type=document.content_type,
        )

        if share_link.is_one_time:
            share_link.is_used = True
            db.commit()

        return response

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        )