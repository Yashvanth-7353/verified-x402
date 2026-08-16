from fastapi import Request
from fastapi.responses import JSONResponse

class VerificationError(Exception):
    def __init__(self, message: str, reasons: list[str] = None):
        self.message = message
        self.reasons = reasons or []

async def verification_error_handler(request: Request, exc: VerificationError):
    return JSONResponse(
        status_code=400,
        content={
            "error": "verification_failed",
            "message": exc.message,
            "reasons": exc.reasons
        }
    )
