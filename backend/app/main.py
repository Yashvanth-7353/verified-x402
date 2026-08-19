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
from app.core.logging import setup_logging
from app.core.errors import VerificationError, verification_error_handler
from app.api.router import api_router

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Local-first verification layer for AI agents",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# x402 payment middleware — protects POST /api/v1/semantic-repair only
# ---------------------------------------------------------------------------

_facilitator_client = HTTPFacilitatorClient(
    FacilitatorConfig(url=settings.FACILITATOR_URL)
)

_payment_server = x402ResourceServer(facilitator_clients=_facilitator_client)
register_exact_avm_server(_payment_server)

_semantic_repair_route_key = f"POST {settings.API_V1_STR}/semantic-repair"

_payment_routes = {
    _semantic_repair_route_key: RouteConfig(
        accepts=PaymentOption(
            scheme="exact",
            pay_to=settings.AVM_ADDRESS,
            price=AssetAmount(amount=settings.SEMANTIC_REPAIR_PRICE, asset="0"),
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