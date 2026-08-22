"""
Phase 10: Deterministic Merkle Tree.

Algorithm (explicitly defined):
    - Leaf: receipt_hash (64-char hex string = SHA-256 digest of receipt)
            The leaf value is the raw 32-byte hex-decoded digest.
    - Parent: SHA-256(left_32_bytes || right_32_bytes)
    - Odd node rule: duplicate the last node (pad with itself)
    - Empty tree: no root (returns None)
    - Ordering: caller provides pre-ordered leaves; this module does not sort.

Properties:
    - Same ordered leaves → same root (deterministic)
    - Changing any leaf → different root (collision-resistant)
    - Changing leaf order → different root (order-dependent)
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Leaf size in bytes (SHA-256 digest)
LEAF_BYTES = 32

# Canonical receipt_hash: exactly 64 lowercase hex characters (SHA-256 hexdigest)
_HEX64_RE = re.compile(r'^[0-9a-f]{64}$')


def is_valid_receipt_hash(receipt_hash: Optional[str]) -> bool:
    """
    Validate that a receipt_hash is a canonical 64-character hex string.

    The canonical format is produced by hashlib.sha256(...).hexdigest()
    which returns exactly 64 lowercase hex characters.
    """
    return bool(receipt_hash and _HEX64_RE.match(receipt_hash))


def _sha256(data: bytes) -> bytes:
    """SHA-256 hash of raw bytes, returning the 32-byte digest."""
    return hashlib.sha256(data).digest()


def hash_leaf(receipt_hash_hex: str) -> bytes:
    """
    Convert a receipt_hash hex string to a 32-byte leaf value.

    The receipt_hash is already a SHA-256 hex digest. We decode it to raw bytes.
    This is the value committed into the Merkle tree.
    """
    return bytes.fromhex(receipt_hash_hex)


def compute_root(leaves: list[str]) -> Optional[str]:
    """
    Compute the Merkle root from an ordered list of receipt_hash hex strings.

    Args:
        leaves: Ordered list of 64-char hex strings (receipt_hash values).

    Returns:
        The Merkle root as a 64-char hex string, or None if leaves is empty.
    """
    if not leaves:
        return None

    # Convert hex strings to 32-byte digests
    nodes = [hash_leaf(h) for h in leaves]

    # Build tree level by level
    while len(nodes) > 1:
        next_level = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            if i + 1 < len(nodes):
                right = nodes[i + 1]
            else:
                # Odd node: duplicate the last node
                right = nodes[i]
            next_level.append(_sha256(left + right))
        nodes = next_level

    return nodes[0].hex()


def build_merkle_tree(leaves: list[str]) -> Optional[MerkleTree]:
    """
    Build a full Merkle tree from ordered receipt_hash hex strings.

    Returns a MerkleTree object with the root and the ability to generate
    inclusion proofs for individual leaves.
    """
    if not leaves:
        return MerkleTree(root=None, leaves=leaves, levels=[])

    # Convert to bytes
    nodes = [hash_leaf(h) for h in leaves]

    levels = [nodes[:]]  # Level 0 = leaves

    while len(nodes) > 1:
        next_level = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            right = nodes[i + 1] if i + 1 < len(nodes) else nodes[i]
            next_level.append(_sha256(left + right))
        nodes = next_level
        levels.append(nodes[:])

    root = nodes[0].hex()
    return MerkleTree(root=root, leaves=leaves, levels=levels)


def generate_proof(tree: MerkleTree, leaf_index: int) -> list[str]:
    """
    Generate a Merkle inclusion proof for a leaf at the given index.

    The proof is a list of sibling hashes (hex-encoded) from leaf to root.
    An independent verifier can reconstruct the root from the leaf + proof.
    """
    if tree.root is None or leaf_index < 0 or leaf_index >= len(tree.leaves):
        return []

    proof = []
    idx = leaf_index

    for level in tree.levels[:-1]:  # Skip root level
        if idx % 2 == 0:
            # Left node: sibling is to the right
            sibling_idx = idx + 1
        else:
            # Right node: sibling is to the left
            sibling_idx = idx - 1

        if sibling_idx < len(level):
            proof.append(level[sibling_idx].hex())
        else:
            # No sibling (odd node, was duplicated) — use self
            proof.append(level[idx].hex())

        idx = idx // 2

    return proof


def verify_proof(leaf_hash_hex: str, proof: list[str], root_hex: str, leaf_index: int) -> bool:
    """
    Verify a Merkle inclusion proof.

    Args:
        leaf_hash_hex: The receipt_hash hex string (leaf value).
        proof: List of sibling hashes from leaf to root.
        root_hex: The expected Merkle root hex string.
        leaf_index: The position of the leaf in the original ordered list.

    Returns:
        True if the proof is valid.
    """
    current = hash_leaf(leaf_hash_hex)
    idx = leaf_index

    for sibling_hex in proof:
        sibling = bytes.fromhex(sibling_hex)
        if idx % 2 == 0:
            # We were on the left: hash(current || sibling)
            current = _sha256(current + sibling)
        else:
            # We were on the right: hash(sibling || current)
            current = _sha256(sibling + current)
        idx = idx // 2

    return current.hex() == root_hex


class MerkleTree:
    """Immutable Merkle tree with root and levels."""

    def __init__(
        self,
        root: Optional[str],
        leaves: list[str],
        levels: list[list[bytes]],
    ):
        self.root = root
        self.leaves = leaves
        self.levels = levels

    @property
    def leaf_count(self) -> int:
        return len(self.leaves)

    def __repr__(self) -> str:
        if self.root is None:
            return "MerkleTree(empty)"
        return f"MerkleTree(root={self.root[:16]}..., leaves={self.leaf_count})"
