#!/usr/bin/env python3
"""
Generate an Ed25519 keypair for receipt signing.

This script generates a fresh Ed25519 keypair and prints the
configuration needed for Verified's receipt signing (Phase 12).

Add the PRIVATE KEY to your backend/.env file:
    RECEIPT_SIGNING_PRIVATE_KEY=<private-key-b64>

The PUBLIC KEY can optionally be shared with verifiers:
    RECEIPT_SIGNING_PUBLIC_KEY=<public-key-b64>

SECURITY:
- NEVER commit the private key to source control.
- NEVER share the private key publicly.
- NEVER print the private key in application logs.
- The private key signs receipts; the public key verifies them.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.crypto.signing import ReceiptSigner


def main():
    private_b64, public_b64 = ReceiptSigner.generate_keypair()

    print("=" * 60)
    print("  Ed25519 Receipt Signing Key Generation")
    print("=" * 60)
    print()
    print("Add to backend/.env:")
    print()
    print(f"  RECEIPT_SIGNING_PRIVATE_KEY={private_b64}")
    print()
    print(f"  RECEIPT_SIGNING_PUBLIC_KEY={public_b64}")
    print()
    print("=" * 60)
    print("  SECURITY REMINDERS")
    print("=" * 60)
    print()
    print("  - NEVER commit the private key to git")
    print("  - NEVER share the private key publicly")
    print("  - NEVER log the private key")
    print("  - The public key is safe to share with verifiers")
    print()
    print("  Key ID (for reference):", end=" ")

    # Compute key ID
    import hashlib
    import base64
    key_id = hashlib.sha256(base64.b64decode(public_b64)).hexdigest()[:16]
    print(key_id)
    print()


if __name__ == "__main__":
    main()
