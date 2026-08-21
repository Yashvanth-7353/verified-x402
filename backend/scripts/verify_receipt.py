#!/usr/bin/env python3
"""
Standalone CLI receipt verifier.

Verifies a signed VerificationReceipt using ONLY:
- The receipt JSON
- The public signing key

Does NOT require:
- The Verified backend
- SQLite
- Private signing key
- Algorand access
- GoPlausible

Usage:
    # From a JSON file:
    python scripts/verify_receipt.py receipt.json --public-key <base64-key>

    # From stdin:
    echo '{"receipt_id": ...}' | python scripts/verify_receipt.py - --public-key <base64-key>

    # Using environment variable for public key:
    python scripts/verify_receipt.py receipt.json

    (reads RECEIPT_SIGNING_PUBLIC_KEY from environment or .env)

Example output for a valid receipt:
    Receipt Verification
    ====================
    Signature:          VALID
    Receipt integrity:  VALID
    Algorithm:          Ed25519
    Signing Key ID:     acaf712941c19df2
    Overall:            VALID

Example output for a tampered receipt:
    Receipt Verification
    ====================
    Signature:          INVALID
    Receipt integrity:  INVALID
    Overall:            INVALID
"""
import sys
import os
import json
import argparse

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.crypto.verify import ReceiptVerifier


def load_receipt(source: str) -> dict:
    """Load receipt JSON from file path or stdin ('-')."""
    if source == "-":
        return json.load(sys.stdin)
    else:
        with open(source, "r") as f:
            return json.load(f)


def load_public_key(cli_key: str | None = None) -> str | None:
    """Load public key from CLI arg, environment, or .env file."""
    if cli_key:
        return cli_key

    # Try environment variable
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.client"))

    return os.environ.get("RECEIPT_SIGNING_PUBLIC_KEY") or None


def print_result(result, receipt: dict):
    """Print verification result in a human-readable format."""
    print()
    print("Receipt Verification")
    print("=" * 40)
    print(f"  Signature:          {'VALID' if result.signature_valid else 'INVALID'}")
    print(f"  Receipt integrity:  {'VALID' if result.receipt_integrity_valid else 'INVALID'}")
    if result.algorithm:
        print(f"  Algorithm:          {result.algorithm}")
    if result.signing_key_id:
        print(f"  Signing Key ID:     {result.signing_key_id}")
    print(f"  Receipt ID:         {str(receipt.get('receipt_id', 'N/A'))[:16]}...")
    print(f"  Outcome:            {receipt.get('outcome', 'N/A')}")
    print()
    print(f"  Overall:            {'VALID' if result.valid else 'INVALID'}")
    if result.details:
        print(f"  Details:            {result.details}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Independently verify a signed VerificationReceipt"
    )
    parser.add_argument(
        "receipt_file",
        help="Path to receipt JSON file, or '-' for stdin",
    )
    parser.add_argument(
        "--public-key",
        help="Base64-encoded Ed25519 public key (or set RECEIPT_SIGNING_PUBLIC_KEY env var)",
    )
    args = parser.parse_args()

    # Load receipt
    try:
        receipt = load_receipt(args.receipt_file)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading receipt: {e}", file=sys.stderr)
        sys.exit(1)

    # Load public key
    public_key = load_public_key(args.public_key)
    if not public_key:
        print(
            "Error: No public key provided. Use --public-key or set RECEIPT_SIGNING_PUBLIC_KEY.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Verify
    try:
        verifier = ReceiptVerifier(public_key_b64=public_key)
    except ValueError as e:
        print(f"Error: Invalid public key: {e}", file=sys.stderr)
        sys.exit(1)

    result = verifier.verify(receipt)
    print_result(result, receipt)

    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
