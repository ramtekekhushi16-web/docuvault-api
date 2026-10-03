from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.session import Base


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)

    document_id = Column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )

    token_hash = Column(String(128), unique=True, nullable=False, index=True)

    expires_at = Column(DateTime(timezone=True), nullable=True)

    password_hash = Column(String(255), nullable=True)

    is_one_time = Column(Boolean, default=False, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )