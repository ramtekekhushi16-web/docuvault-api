import os
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import STORAGE_PATH
from app.core.dependencies import (
    check_document_permission,
    get_current_user,
)
from app.db.session import get_db
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentUpdate


router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a new document.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    storage_directory = os.path.abspath(STORAGE_PATH)
    os.makedirs(storage_directory, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}_{file.filename}"

    file_path = os.path.join(
        storage_directory,
        stored_filename,
    )

    try:
        file_content = await file.read()

        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )

        with open(file_path, "wb") as destination:
            destination.write(file_content)

        document = Document(
            owner_id=current_user.id,
            filename=stored_filename,
            original_filename=file.filename,
            content_type=file.content_type
            or "application/octet-stream",
            description=description,
            current_version=1,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            stored_filename=stored_filename,
            file_size=len(file_content),
            created_by=current_user.id,
        )

        db.add(version)
        db.commit()

        return document

    except HTTPException:
        db.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        raise

    except Exception:
        db.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )


@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List documents owned by the current user.
    """

    documents = (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return documents


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get document metadata.
    """

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    check_document_permission(
        document,
        current_user,
        db,
        "Viewer",
    )

    return document


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
)
def update_document(
    document_id: int,
    data: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update document metadata.
    """

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    check_document_permission(
        document,
        current_user,
        db,
        "Editor",
    )

    document.description = data.description

    db.commit()
    db.refresh(document)

    return document


@router.delete(
    "/{document_id}",
)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a document.

    Only the owner can delete it.
    """

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the document owner can delete this document",
        )

    # Find all versions belonging to this document.
    versions = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id
        )
        .all()
    )

    storage_directory = os.path.abspath(STORAGE_PATH)

    # Delete physical files from storage.
    for version in versions:
        version_path = os.path.join(
            storage_directory,
            version.stored_filename,
        )

        if os.path.exists(version_path):
            os.remove(version_path)

    # Delete version database records first.
    # They contain foreign keys pointing to the document.
    db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document.id
    ).delete(
        synchronize_session=False
    )

    # Delete the document itself.
    db.delete(document)

    db.commit()

    return {
        "message": "Document deleted successfully"
    }


@router.get(
    "/{document_id}/download",
)
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download the current document version.
    """

    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    check_document_permission(
        document,
        current_user,
        db,
        "Viewer",
    )

    version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_number
            == document.current_version,
        )
        .first()
    )

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document version not found",
        )

    file_path = os.path.join(
        os.path.abspath(STORAGE_PATH),
        version.stored_filename,
    )

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical file not found in storage",
        )

    return FileResponse(
        path=file_path,
        filename=document.original_filename,
        media_type=document.content_type,
    )