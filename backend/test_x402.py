import x402
from x402.http import HTTPFacilitatorClient, RouteConfig, PaymentOption
from x402.server import x402ResourceServer
from x402.schemas import FacilitatorConfig
from x402.mechanisms.avm.exact import register_exact_avm_server
from x402.http.middleware.fastapi import payment_middleware

client = HTTPFacilitatorClient(FacilitatorConfig(url="https://facilitator.goplausible.xyz"))
server = x402ResourceServer(facilitator_clients=client)
register_exact_avm_server(server)

routes = {
    "/api/v1/semantic-repair": RouteConfig(
        accepts=PaymentOption(
            scheme="avm.exact.v2",
            pay_to="SOME_ADDRESS",
            price="1000000",
            network="algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI="
        )
    )
}

# payment_middleware signature: (routes, server, paywall_config=None, paywall_provider=None, sync_facilitator_on_start=True)
middleware_fn = payment_middleware(routes=routes, server=server, sync_facilitator_on_start=False)

print("Middleware created:", middleware_fn)
