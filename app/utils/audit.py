from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    user_id: int | None,
    document_id: int | None,
    action: str,
    details: str | None = None,
    ip_address: str | None = None,
):
    audit_log = AuditLog(
        user_id=user_id,
        document_id=document_id,
        action=action,
        details=details,
        ip_address=ip_address,
    )

    db.add(audit_log)
