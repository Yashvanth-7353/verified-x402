"""
Application entry point.

Phase 8: Custom x402 payment middleware that verifies AND settles payment
BEFORE calling the route handler.  This ensures PaymentMetadata with
payment_status="settled" is available to the semantic-repair handler,
satisfying the DATA_MODEL.md invariant that verified_repaired outcomes
require a non-null, settled PaymentMetadata reference.

Flow:
  Request → verify payment → settle payment → store on request.state → handler

All other routes (e.g. /api/v1/verify, /health) are not affected by the middleware
and remain completely free to use.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from x402.http import HTTPFacilitatorClient, RouteConfig, PaymentOption, FacilitatorConfig
from x402.http.types import HTTPRequestContext, RouteConfig as RouteConfigType
from x402.http.x402_http_server import x402HTTPResourceServer
from x402.schemas import FacilitatorConfig as FacilitatorConfigSchema, AssetAmount
from x402.server import x402ResourceServer
from x402.mechanisms.avm.exact import register_exact_avm_server

from app.core.config import settings
from app.core.errors import VerificationError, verification_error_handler
from app.api.router import api_router
from app.core.logging import logger, setup_logging

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI()
setup_logging()

# ---------------------------------------------------------------------------
# x402 resource server setup
# ---------------------------------------------------------------------------
facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.FACILITATOR_URL))
_payment_server = x402ResourceServer(facilitator)
register_exact_avm_server(_payment_server)


# ---------------------------------------------------------------------------
# Diagnostic hooks (safe — no secrets logged)
# ---------------------------------------------------------------------------
def _verify_failure_hook(context: Any) -> Any:
    try:
        error = getattr(context, "error", None)
        error_msg = str(error) if error is not None else "unknown"
        logger.error(f"x402 verification failure: error={error_msg}")
        try:
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
    try:
        error = getattr(context, "error", None)
        error_msg = str(error) if error is not None else "unknown"
        logger.error(f"x402 settlement failure: error={error_msg}")
    except Exception as e:
        logger.exception(f"Error in settlement failure hook: {e}")
    return context


_payment_server.on_verify_failure(_verify_failure_hook)
_payment_server.on_settle_failure(_settle_failure_hook)


# ---------------------------------------------------------------------------
# Payment route configuration
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Phase 8 Custom Middleware — verify → settle → handler
# ---------------------------------------------------------------------------
def _verified_payment_middleware(
    routes: dict[str, Any],
    x402_server: x402ResourceServer,
):
    """
    Custom x402 middleware that settles payment BEFORE calling the handler.

    This ensures that when the semantic-repair handler runs, settlement has
    already been confirmed by the GoPlausible AVM facilitator on Algorand.
    The handler can then create PaymentMetadata with payment_status="settled"
    and reference the actual Algorand transaction.

    The standard x402 middleware calls the handler THEN settles, which means
    settlement information is not available inside the handler.  Phase 8
    requires settlement info to be available for PaymentMetadata creation.
    """
    http_server = x402HTTPResourceServer(x402_server, routes)
    init_done = False

    async def middleware(request: Request, call_next) -> Response:
        nonlocal init_done

        # Build the framework-agnostic adapter and request context
        from x402.http.middleware.fastapi import FastAPIAdapter  # local to avoid top-level import issues

        adapter = FastAPIAdapter(request)
        context = HTTPRequestContext(
            adapter=adapter,
            path=request.url.path,
            method=request.method,
            payment_header=(
                adapter.get_header("payment-signature")
                or adapter.get_header("x-payment")
            ),
        )

        # If the route doesn't require payment, pass through immediately
        if not http_server.requires_payment(context):
            return await call_next(request)

        # Lazy-initialize on first protected request
        if not init_done:
            http_server.initialize()
            init_done = True

        # ---- Verify payment ----
        result = await http_server.process_http_request(context)

        if result.type == "no-payment-required":
            return await call_next(request)

        if result.type == "payment-error":
            response_instructions = result.response
            if response_instructions is None:
                return JSONResponse(
                    content={"error": "Payment required"},
                    status_code=402,
                )
            if getattr(response_instructions, "is_html", False):
                from starlette.responses import HTMLResponse
                return HTMLResponse(
                    content=response_instructions.body,
                    status_code=response_instructions.status,
                    headers=response_instructions.headers,
                )
            return JSONResponse(
                content=response_instructions.body or {},
                status_code=response_instructions.status,
                headers=response_instructions.headers,
            )

        if result.type == "payment-verified":
            # ---- Settle IMMEDIATELY (before handler) ----
            settle_result = await http_server.process_settlement(
                result.payment_payload,
                result.payment_requirements,
            )

            if not settle_result.success:
                logger.warning(
                    "x402 settlement failed after verification: %s",
                    settle_result.error_reason,
                )
                return JSONResponse(
                    content={
                        "error": "Settlement failed",
                        "details": settle_result.error_reason,
                    },
                    status_code=402,
                )

            # Store payment + settlement info on request.state so the
            # handler can create accurate PaymentMetadata.
            request.state.payment_payload = result.payment_payload
            request.state.payment_requirements = result.payment_requirements
            request.state.settlement_result = settle_result

            logger.info(
                "x402 payment verified and settled: network=%s tx=%s",
                settle_result.network,
                settle_result.transaction,
            )

            # ---- Call the route handler ----
            response = await call_next(request)

            # Read the response body so we can append settlement headers
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Merge settlement headers into the response
            headers = dict(response.headers)
            headers.update(settle_result.headers)

            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

        # Fallback — should not happen
        return await call_next(request)

    return middleware


# ---------------------------------------------------------------------------
# Attach the custom middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    BaseHTTPMiddleware,
    dispatch=_verified_payment_middleware(
        routes=_payment_routes,
        x402_server=_payment_server,
    ),
)

# ---------------------------------------------------------------------------
# Application-level error handling and routing
# ---------------------------------------------------------------------------
app.add_exception_handler(VerificationError, verification_error_handler)
app.include_router(api_router)
