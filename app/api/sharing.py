from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.permission import DocumentPermission
from app.models.user import User
from app.schemas.sharing import PermissionCreate, PermissionResponse

router = APIRouter(
    prefix="/api/documents",
    tags=["Sharing & Permissions"],
)


@router.post(
    "/{document_id}/permissions",
    response_model=PermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_permission(
    document_id: int,
    data: PermissionCreate,
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
            detail="Only the document owner can manage permissions",
        )

    user = (
        db.query(User)
        .filter(User.id == data.user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Owner already has full access",
        )

    existing_permission = (
        db.query(DocumentPermission)
        .filter(
            DocumentPermission.document_id == document_id,
            DocumentPermission.user_id == data.user_id,
        )
        .first()
    )

    if existing_permission:
        existing_permission.role = data.role
        db.commit()
        db.refresh(existing_permission)
        return existing_permission

    permission = DocumentPermission(
        document_id=document_id,
        user_id=data.user_id,
        role=data.role,
    )

    db.add(permission)
    db.commit()
    db.refresh(permission)

    return permission


@router.get(
    "/{document_id}/permissions",
    response_model=list[PermissionResponse],
)
def list_permissions(
    document_id: int,
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
            detail="Only the document owner can view permissions",
        )

    return (
        db.query(DocumentPermission)
        .filter(DocumentPermission.document_id == document_id)
        .all()
    )


@router.delete(
    "/{document_id}/permissions/{user_id}"
)
def revoke_permission(
    document_id: int,
    user_id: int,
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
            detail="Only the document owner can revoke permissions",
        )

    permission = (
        db.query(DocumentPermission)
        .filter(
            DocumentPermission.document_id == document_id,
            DocumentPermission.user_id == user_id,
        )
        .first()
    )

    if not permission:
        raise HTTPException(
            status_code=404,
            detail="Permission not found",
        )

    db.delete(permission)
    db.commit()

    return {
        "message": "Permission revoked successfully"
    }