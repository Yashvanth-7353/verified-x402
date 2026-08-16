from fastapi import FastAPI

app = FastAPI(
    title="Verified",
    description="Local-first verification layer for AI agents",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "verified",
        "version": "0.1.0",
    }