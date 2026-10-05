from datetime import datetime

from pydantic import BaseModel, Field


class PermissionCreate(BaseModel):
    user_id: int
    role: str = Field(pattern="^(Viewer|Editor)$")


class PermissionResponse(BaseModel):
    id: int
    document_id: int
    user_id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class ShareLinkCreate(BaseModel):
    expires_at: datetime | None = None
    password: str | None = Field(default=None, min_length=4)
    is_one_time: bool = False


class ShareLinkResponse(BaseModel):
    id: int
    document_id: int
    expires_at: datetime | None
    is_one_time: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ShareLinkCreateResponse(BaseModel):
    id: int
    document_id: int
    token: str
    expires_at: datetime | None
    is_one_time: bool
    created_at: datetime