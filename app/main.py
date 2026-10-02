from fastapi import FastAPI

app = FastAPI(
    title="DocuVault API",
    description="Secure Document Storage & Versioning Service",
    version="1.0.0",
)


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