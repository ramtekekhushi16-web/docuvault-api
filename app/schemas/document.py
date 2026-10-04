from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    owner_id: int
    filename: str
    original_filename: str
    content_type: str
    description: str | None
    current_version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    description: str | None = None