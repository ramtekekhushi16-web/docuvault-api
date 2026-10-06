import hashlib
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import STORAGE_PATH
from app.core.security import verify_password
from app.db.session import get_db
from app.models.document import Document
from app.models.share_link import ShareLink
from app.utils.encryption import decrypt_data


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
    # --------------------------------------------------------
    # Hash the raw share token
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Check expiration
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Check one-time link
    # --------------------------------------------------------
    if share_link.is_one_time and share_link.is_used:
        raise HTTPException(
            status_code=410,
            detail="Share link has already been used",
        )

    # --------------------------------------------------------
    # Check optional password
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Find document
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Build stored file path
    # --------------------------------------------------------
    file_path = os.path.join(
        STORAGE_PATH,
        document.filename,
    )

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        )

    # --------------------------------------------------------
    # Read encrypted file
    # --------------------------------------------------------
    try:
        with open(file_path, "rb") as source:
            encrypted_content = source.read()
    except OSError:
        raise HTTPException(
            status_code=500,
            detail="Unable to read document file",
        )

    # --------------------------------------------------------
    # Decrypt file before sending it
    # --------------------------------------------------------
    try:
        decrypted_content = decrypt_data(
            encrypted_content
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to decrypt document",
        )

    # --------------------------------------------------------
    # Mark one-time link as used
    # --------------------------------------------------------
    if share_link.is_one_time:
        share_link.is_used = True
        db.commit()

    # --------------------------------------------------------
    # Return decrypted document
    # --------------------------------------------------------
    return Response(
        content=decrypted_content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document.original_filename}"'
            )
        },
    )