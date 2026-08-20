"""
Application entry point.

The x402 payment middleware is attached via FastAPI's add_middleware mechanism.
It intercepts every request to POST /api/v1/semantic-repair:
  - Missing X-PAYMENT  → HTTP 402 with the full GoPlausible challenge body
  - Malformed/invalid  → rejected by middleware / facilitator (never reaches handler)
  - Valid payment      → handler proceeds

All other routes (e.g. /api/v1/verify, /health) are not affected by the middleware
and remain completely free to use.
"""
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from x402.http import HTTPFacilitatorClient, RouteConfig, PaymentOption
from x402.schemas import FacilitatorConfig, AssetAmount
from x402.server import x402ResourceServer
from x402.mechanisms.avm.exact import register_exact_avm_server
from x402.http.middleware.fastapi import payment_middleware

from app.core.config import settings
from typing import Any
from app.core.errors import VerificationError, verification_error_handler
from app.api.router import api_router
from app.core.logging import logger, setup_logging
app = FastAPI()
# Initialize logging before any other code runs
setup_logging()
from x402.http import HTTPFacilitatorClient, RouteConfig, PaymentOption, FacilitatorConfig

# Initialize x402 resource server and register AVM scheme
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.FACILITATOR_URL))
_payment_server = x402ResourceServer(facilitator)
register_exact_avm_server(_payment_server)
# Register diagnostic hooks on the x402 resource server
def _verify_failure_hook(context: Any) -> Any:
    # Log verification failure details without exposing sensitive data
    # VerifyFailureContext has: payment_payload, requirements, error (Exception)
    try:
        error = getattr(context, "error", None)
        error_msg = str(error) if error is not None else "unknown"
        logger.error(f"x402 verification failure: error={error_msg}")
        try:
            import json, os
            log_path = os.path.join(os.path.dirname(__file__), "..", "payment_failure.log")
            log_path = os.path.abspath(log_path)
            with open(log_path, "a", encoding="utf-8") as f:
                json.dump({"hook": "verify", "error": error_msg}, f)
                f.write("\n")
        except Exception as log_exc:
            logger.exception(f"Failed to write verification failure log: {log_exc}")
    except Exception as e:
        logger.exception(f"Error in verification failure hook: {e}")
    return context

def _settle_failure_hook(context: Any) -> Any:
    # Log settlement failure details safely
    # SettleFailureContext has: payment_payload, requirements, error (Exception)
    try:
        error = getattr(context, "error", None)
        error_msg = str(error) if error is not None else "unknown"
        logger.error(f"x402 settlement failure: error={error_msg}")
    except Exception as e:
        logger.exception(f"Error in settlement failure hook: {e}")
    return context

# Attach the hooks to the server instance
_payment_server.on_verify_failure(_verify_failure_hook)
_payment_server.on_settle_failure(_settle_failure_hook)


_semantic_repair_route_key = f"POST {settings.API_V1_STR}/semantic-repair"

_payment_routes = {
    _semantic_repair_route_key: RouteConfig(
        accepts=PaymentOption(
            scheme="exact",
            pay_to="GAVMWAOT52HYGQOPZAVYXA2NZHZX7DXRJYZQ5YVG4NXPQ3UUWLCHUBWVW4",
            price=AssetAmount(amount=settings.SEMANTIC_REPAIR_PRICE, asset="10458941"),
            network=settings.ALGORAND_NETWORK,
        ),
        resource=f"{settings.API_V1_STR}/semantic-repair",
        description="Semantic repair of a structured agent output via GoPlausible AVM Facilitator",
    )
}

app.add_middleware(
    BaseHTTPMiddleware,
    dispatch=payment_middleware(
        routes=_payment_routes,
        server=_payment_server,
        sync_facilitator_on_start=True,
    ),
)

# ---------------------------------------------------------------------------
# Application-level error handling and routing
# ---------------------------------------------------------------------------

app.add_exception_handler(VerificationError, verification_error_handler)
app.include_router(api_router)