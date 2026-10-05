import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import hash_password
from app.db.session import get_db
from app.models.document import Document
from app.models.share_link import ShareLink
from app.models.user import User
from app.schemas.sharing import (
    ShareLinkCreate,
    ShareLinkCreateResponse,
)

router = APIRouter(
    prefix="/api/documents",
    tags=["Share Links"],
)


@router.post(
    "/{document_id}/share-links",
    response_model=ShareLinkCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_share_link(
    document_id: int,
    data: ShareLinkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the document owner can create share links",
        )

    if data.expires_at:
        expires_at = data.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail="Expiry time must be in the future",
            )
    else:
        expires_at = None

    raw_token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    password_hash = None

    if data.password:
        password_hash = hash_password(data.password)

    share_link = ShareLink(
        document_id=document.id,
        token_hash=token_hash,
        expires_at=expires_at,
        password_hash=password_hash,
        is_one_time=data.is_one_time,
        is_used=False,
        created_by=current_user.id,
    )

    db.add(share_link)
    db.commit()
    db.refresh(share_link)

    return {
        "id": share_link.id,
        "document_id": share_link.document_id,
        "token": raw_token,
        "expires_at": share_link.expires_at,
        "is_one_time": share_link.is_one_time,
        "created_at": share_link.created_at,
    }