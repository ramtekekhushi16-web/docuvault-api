from fastapi import FastAPI

from app.api.auth import router as auth_router


app = FastAPI(
    title="DocuVault API",
    description=(
        "Secure Document Storage & Versioning Service "
        "with authentication, RBAC, sharing, versioning, "
        "encryption, and search."
    ),
    version="1.0.0",
)


app.include_router(auth_router)


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