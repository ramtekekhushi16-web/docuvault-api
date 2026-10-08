from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.sharing import router as sharing_router
from app.api.share_links import router as share_links_router
from app.api.share_access import router as share_access_router

app = FastAPI(
    title="DocuVault API",
    description=(
        "Secure Document Storage & Versioning Service "
        "with authentication, RBAC, sharing, versioning, "
        "encryption, and search."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(sharing_router)
app.include_router(share_links_router)
app.include_router(share_access_router)


@app.get("/")
def root():
    return {
        "message": "DocuVault API is running",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }