import os
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import STORAGE_PATH
from app.core.dependencies import (
    check_document_permission,
    get_current_user,
)
from app.db.session import get_db

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.permission import DocumentPermission
from app.models.share_link import ShareLink
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentUpdate

from app.utils.audit import create_audit_log
from app.utils.encryption import decrypt_data, encrypt_data


router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


# ============================================================
# 1. UPLOAD DOCUMENT
# ============================================================

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    description: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a new document.

    The file is encrypted with AES-256-GCM before being
    written to disk.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File cannot be empty",
        )

    os.makedirs(STORAGE_PATH, exist_ok=True)

    stored_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(
        STORAGE_PATH,
        stored_filename,
    )

    try:
        # Encrypt before storing on disk
        encrypted_content = encrypt_data(file_content)

        with open(file_path, "wb") as destination:
            destination.write(encrypted_content)

        # Create document metadata
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

        # Create first immutable version
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            stored_filename=stored_filename,
            file_size=len(file_content),
            created_by=current_user.id,
        )

        db.add(version)
        db.commit()

        # Audit log
        create_audit_log(
            db=db,
            user_id=current_user.id,
            document_id=document.id,
            action="DOCUMENT_UPLOADED",
            details=f"Uploaded document: {file.filename}",
        )

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
# 3. SEARCH DOCUMENTS
# ============================================================

@router.get(
    "/search",
    response_model=list[DocumentResponse],
)
def search_documents(
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full-text search over document metadata.

    Searches:
    - original filename
    - stored filename
    - description

    PostgreSQL uses:
    - tsvector
    - plainto_tsquery
    - GIN index

    Only documents owned by the current user are returned.
    """

    query_text = q.strip()

    if not query_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty",
        )

    search_query = func.plainto_tsquery(
        "english",
        query_text,
    )

    documents = (
        db.query(Document)
        .filter(
            Document.owner_id == current_user.id,
            Document.search_vector.op("@@")(search_query),
        )
        .order_by(
            func.ts_rank(
                Document.search_vector,
                search_query,
            ).desc()
        )
        .all()
    )

    return documents


# ============================================================
# 4. GET DOCUMENT METADATA
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
        document=document,
        current_user=current_user,
        db=db,
        required_role="Viewer",
    )

    return document


# ============================================================
# 5. UPDATE DOCUMENT METADATA
# ============================================================

@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
)
def update_document(
    document_id: int,
    document_data: DocumentUpdate,
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
        document=document,
        current_user=current_user,
        db=db,
        required_role="Editor",
    )

    document.description = document_data.description

    db.commit()
    db.refresh(document)

    # Audit log
    create_audit_log(
        db=db,
        user_id=current_user.id,
        document_id=document.id,
        action="DOCUMENT_UPDATED",
        details="Document metadata updated",
    )

    return document


# ============================================================
# 6. DELETE DOCUMENT
# ============================================================


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a document.

    Only the document owner can delete the document.
    Related versions, permissions, share links, and audit-log
    references are handled before deleting the document.
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
            detail="Only the document owner can delete the document",
        )

    # ---------------------------------------------------------
    # 1. Create deletion audit log
    # ---------------------------------------------------------
    create_audit_log(
        db=db,
        user_id=current_user.id,
        document_id=document.id,
        action="DOCUMENT_DELETED",
        details=f"Deleted document: {document.original_filename}",
    )

    # IMPORTANT:
    # Flush the new audit log to PostgreSQL before running
    # the UPDATE below. Otherwise the bulk UPDATE cannot see
    # the newly-created audit record.
    db.flush()

    # ---------------------------------------------------------
    # 2. Remove document references from existing audit logs
    # ---------------------------------------------------------
    db.query(AuditLog).filter(
        AuditLog.document_id == document.id
    ).update(
        {
            AuditLog.document_id: None
        },
        synchronize_session=False,
    )

    # ---------------------------------------------------------
    # 3. Delete document permissions
    # ---------------------------------------------------------
    db.query(DocumentPermission).filter(
        DocumentPermission.document_id == document.id
    ).delete(
        synchronize_session=False
    )

    # ---------------------------------------------------------
    # 4. Delete share links
    # ---------------------------------------------------------
    db.query(ShareLink).filter(
        ShareLink.document_id == document.id
    ).delete(
        synchronize_session=False
    )

    # ---------------------------------------------------------
    # 5. Find all document versions
    # ---------------------------------------------------------
    versions = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id
        )
        .all()
    )

    # ---------------------------------------------------------
    # 6. Remove encrypted files from storage
    # ---------------------------------------------------------
    for version in versions:
        file_path = os.path.join(
            STORAGE_PATH,
            version.stored_filename,
        )

        if os.path.exists(file_path):
            os.remove(file_path)

    # ---------------------------------------------------------
    # 7. Delete document version records
    # ---------------------------------------------------------
    db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document.id
    ).delete(
        synchronize_session=False
    )

    # ---------------------------------------------------------
    # 8. Delete document
    # ---------------------------------------------------------
    db.delete(document)

    # ---------------------------------------------------------
    # 9. Commit transaction
    # ---------------------------------------------------------
    db.commit()

    return {
        "message": "Document deleted successfully",
        "document_id": document_id,
    }


# ============================================================
# 7. DOWNLOAD CURRENT DOCUMENT
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
    Download and decrypt the current document version.
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
        document=document,
        current_user=current_user,
        db=db,
        required_role="Viewer",
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
            detail="Current document version not found",
        )

    file_path = os.path.join(
        STORAGE_PATH,
        version.stored_filename,
    )

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found",
        )

    # Read encrypted file
    with open(file_path, "rb") as source:
        encrypted_content = source.read()

    # Decrypt
    try:
        decrypted_content = decrypt_data(
            encrypted_content
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to decrypt document",
        )

    # Audit log
    create_audit_log(
        db=db,
        user_id=current_user.id,
        document_id=document.id,
        action="DOCUMENT_DOWNLOADED",
        details=f"Downloaded version {document.current_version}",
    )

    return Response(
        content=decrypted_content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document.original_filename}"'
            )
        },
    )


# ============================================================
# 8. UPLOAD NEW DOCUMENT VERSION
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
    Upload a new immutable version of an existing document.
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
        document=document,
        current_user=current_user,
        db=db,
        required_role="Editor",
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
            detail="File cannot be empty",
        )

    os.makedirs(STORAGE_PATH, exist_ok=True)

    new_version_number = document.current_version + 1

    stored_filename = (
        f"{uuid.uuid4().hex}_{file.filename}"
    )

    file_path = os.path.join(
        STORAGE_PATH,
        stored_filename,
    )

    try:
        # Encrypt before storing
        encrypted_content = encrypt_data(
            file_content
        )

        with open(file_path, "wb") as destination:
            destination.write(encrypted_content)

        version = DocumentVersion(
            document_id=document.id,
            version_number=new_version_number,
            stored_filename=stored_filename,
            file_size=len(file_content),
            created_by=current_user.id,
        )

        db.add(version)

        document.filename = stored_filename
        document.current_version = new_version_number
        document.original_filename = file.filename
        document.content_type = (
            file.content_type
            or "application/octet-stream"
        )

        db.commit()
        db.refresh(document)

        # Audit log
        create_audit_log(
            db=db,
            user_id=current_user.id,
            document_id=document.id,
            action="VERSION_CREATED",
            details=(
                f"Created document version "
                f"{new_version_number}"
            ),
        )

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
            detail="Failed to upload new document version",
        )


# ============================================================
# 9. LIST DOCUMENT VERSION HISTORY
# ============================================================

@router.get(
    "/{document_id}/versions",
)
def list_versions(
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
        document=document,
        current_user=current_user,
        db=db,
        required_role="Viewer",
    )

    versions = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id
        )
        .order_by(
            DocumentVersion.version_number.desc()
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
# 10. RESTORE PREVIOUS VERSION
# ============================================================

@router.post(
    "/{document_id}/versions/{version_number}/restore",
    response_model=DocumentResponse,
)
def restore_version(
    document_id: int,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Restore a previous version.

    The original version is never modified.
    Restoration creates a new immutable version.
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
        document=document,
        current_user=current_user,
        db=db,
        required_role="Editor",
    )

    version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_number
            == version_number,
        )
        .first()
    )

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    file_path = os.path.join(
        STORAGE_PATH,
        version.stored_filename,
    )

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version file not found",
        )

    # Read encrypted historical version
    with open(file_path, "rb") as source:
        encrypted_content = source.read()

    # Decrypt historical version
    try:
        decrypted_content = decrypt_data(
            encrypted_content
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to decrypt selected version",
        )

    # Create a new immutable snapshot
    new_version_number = (
        document.current_version + 1
    )

    restored_filename = (
        f"{uuid.uuid4().hex}_{document.original_filename}"
    )

    restored_path = os.path.join(
        STORAGE_PATH,
        restored_filename,
    )

    try:
        # Encrypt restored content again
        restored_encrypted_content = encrypt_data(
            decrypted_content
        )

        with open(
            restored_path,
            "wb",
        ) as destination:
            destination.write(
                restored_encrypted_content
            )

        restored_version = DocumentVersion(
            document_id=document.id,
            version_number=new_version_number,
            stored_filename=restored_filename,
            file_size=len(decrypted_content),
            created_by=current_user.id,
        )

        db.add(restored_version)

        document.filename = restored_filename
        document.current_version = new_version_number

        db.commit()
        db.refresh(document)

        # Audit log
        create_audit_log(
            db=db,
            user_id=current_user.id,
            document_id=document.id,
            action="VERSION_RESTORED",
            details=(
                f"Restored version {version_number} "
                f"as new version {new_version_number}"
            ),
        )

        return document

    except Exception:
        db.rollback()

        if os.path.exists(restored_path):
            os.remove(restored_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore document version",
        )