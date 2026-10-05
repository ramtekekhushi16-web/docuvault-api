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


# ============================================================
# 1. UPLOAD NEW DOCUMENT
# ============================================================

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


# ============================================================
# 2. LIST MY DOCUMENTS
# ============================================================

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


# ============================================================
# 3. GET DOCUMENT METADATA
# ============================================================

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


# ============================================================
# 4. UPDATE DOCUMENT METADATA
# ============================================================

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


# ============================================================
# 5. DELETE DOCUMENT
# ============================================================

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

    versions = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id
        )
        .all()
    )

    storage_directory = os.path.abspath(STORAGE_PATH)

    for version in versions:
        version_path = os.path.join(
            storage_directory,
            version.stored_filename,
        )

        if os.path.exists(version_path):
            os.remove(version_path)

    db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document.id
    ).delete(
        synchronize_session=False
    )

    db.delete(document)
    db.commit()

    return {
        "message": "Document deleted successfully"
    }


# ============================================================
# 6. DOWNLOAD CURRENT DOCUMENT VERSION
# ============================================================

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


# ============================================================
# 7. UPLOAD NEW DOCUMENT VERSION
# ============================================================

@router.post(
    "/{document_id}/versions",
    response_model=DocumentResponse,
)
async def upload_new_version(
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a new version of an existing document.
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

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    storage_directory = os.path.abspath(STORAGE_PATH)
    os.makedirs(storage_directory, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}_{file.filename}"

    file_path = os.path.join(
        storage_directory,
        stored_filename,
    )

    try:
        with open(file_path, "wb") as destination:
            destination.write(file_content)

        latest_version = (
            db.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == document.id
            )
            .order_by(
                DocumentVersion.version_number.desc()
            )
            .first()
        )

        next_version_number = (
            latest_version.version_number + 1
            if latest_version
            else 1
        )

        version = DocumentVersion(
            document_id=document.id,
            version_number=next_version_number,
            stored_filename=stored_filename,
            file_size=len(file_content),
            created_by=current_user.id,
        )

        db.add(version)

        document.current_version = next_version_number

        db.commit()
        db.refresh(document)

        return document

    except Exception:
        db.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload new document version",
        )


# ============================================================
# 8. LIST DOCUMENT VERSION HISTORY
# ============================================================

@router.get(
    "/{document_id}/versions",
)
def list_document_versions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all versions of a document.
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

    versions = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id
        )
        .order_by(
            DocumentVersion.version_number.asc()
        )
        .all()
    )

    return [
        {
            "id": version.id,
            "version_number": version.version_number,
            "stored_filename": version.stored_filename,
            "file_size": version.file_size,
            "checksum": version.checksum,
            "created_by": version.created_by,
            "created_at": version.created_at,
        }
        for version in versions
    ]


# ============================================================
# 9. RESTORE PREVIOUS VERSION
# ============================================================

@router.post(
    "/{document_id}/versions/{version_number}/restore",
    response_model=DocumentResponse,
)
def restore_document_version(
    document_id: int,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Restore a previous document version.

    The original version remains unchanged in history.
    The selected version becomes the current version.
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

    version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_number == version_number,
        )
        .first()
    )

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    file_path = os.path.join(
        os.path.abspath(STORAGE_PATH),
        version.stored_filename,
    )

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version file not found in storage",
        )

    document.filename = version.stored_filename
    document.current_version = version.version_number

    db.commit()
    db.refresh(document)

    return document