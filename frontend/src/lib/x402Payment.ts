/**
 * x402 browser payment utility.
 *
 * Creates signed payment payloads using the browser wallet's ClientAvmSigner.
 * The payment is signed by the wallet, then sent to the backend as PAYMENT-SIGNATURE.
 * The backend's GoPlausible facilitator settles the actual Algorand transaction.
 *
 * NO private keys are ever handled here.
 * The wallet handles all signing via its native interface.
 */
import { x402Client } from '@x402/core/client';
import { ExactAvmScheme } from '@x402/avm/exact/client';

import type { ClientAvmSigner } from '@x402/avm/exact/client';
import type { PaymentRequired } from '@x402/core';

/**
 * Create a ClientAvmSigner from the useWallet hook's signTransactions function.
 * This adapts @txnlab/use-wallet's interface to x402's ClientAvmSigner interface.
 */
export function createWalletAvmSigner(
  address: string,
  walletSignTransactions: (
    txnGroup: Uint8Array[] | Uint8Array[],
    indexesToSign?: number[],
  ) => Promise<(Uint8Array | null)[]>,
): ClientAvmSigner {
  return {
    address,
    signTransactions: walletSignTransactions,
  };
}

/**
 * Parse a 402 response's PAYMENT-REQUIRED header into a PaymentRequired object.
 * The header contains base64-encoded JSON per the x402 v2 spec.
 */
export function parsePaymentRequired(
  paymentRequiredHeader: string,
): PaymentRequired {
  const decoded = JSON.parse(atob(paymentRequiredHeader));
  return decoded as PaymentRequired;
}

/**
 * Create a signed x402 payment payload using the wallet signer.
 * Returns the base64-encoded PAYMENT-SIGNATURE header value.
 *
 * IMPORTANT: We register the ExactAvmScheme using the ACTUAL network string
 * from the payment requirements (not ALGORAND_TESTNET_CAIP2 from the library,
 * which may be truncated in @x402/avm v2.23.0).
 */
export async function createSignedPayment(
  paymentRequired: PaymentRequired,
  walletSigner: ClientAvmSigner,
): Promise<string> {
  const client = new x402Client();

  // Get the actual network from the payment requirements — NOT from the
  // library constant ALGORAND_TESTNET_CAIP2 which may be truncated.
  const network = paymentRequired.accepts?.[0]?.network;
  if (!network) {
    throw new Error('No network found in payment requirements');
  }

  const scheme = new ExactAvmScheme(walletSigner);
  client.register(network, scheme);

  const payload = await client.createPaymentPayload(paymentRequired);

  const encoded = btoa(
    JSON.stringify({
      x402Version: payload.x402Version,
      payload: payload.payload,
      accepted: paymentRequired.accepts?.[0] ?? paymentRequired,
      resource: paymentRequired.resource,
      extensions: payload.extensions,
    }),
  );

  return encoded;
}
