"""
Phase 10 tests: Merkle tree implementation.

Tests cover:
- Empty tree
- Single leaf
- Two leaves
- Three leaves (odd count)
- Four leaves
- Deterministic root
- Changed leaf changes root
- Changed ordering changes root
- Proof generation and verification
"""
import hashlib
import pytest

from app.anchoring.merkle import (
    compute_root,
    build_merkle_tree,
    generate_proof,
    verify_proof,
    hash_leaf,
    LEAF_BYTES,
)


# ---------------------------------------------------------------------------
# Helper: create a deterministic receipt_hash from a seed
# ---------------------------------------------------------------------------

def _receipt_hash(seed: str) -> str:
    """Create a deterministic 64-char hex receipt_hash from a seed string."""
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Test vectors
# ---------------------------------------------------------------------------

LEAF_A = _receipt_hash("record_a")
LEAF_B = _receipt_hash("record_b")
LEAF_C = _receipt_hash("record_c")
LEAF_D = _receipt_hash("record_d")


class TestEmptyTree:
    def test_empty_leaves_returns_none(self):
        """Empty leaves list returns None root."""
        assert compute_root([]) is None

    def test_build_empty_tree(self):
        """Building empty tree returns tree with None root."""
        tree = build_merkle_tree([])
        assert tree.root is None
        assert tree.leaf_count == 0


class TestSingleLeaf:
    def test_single_leaf_root_is_leaf(self):
        """Single leaf: root equals the leaf hash."""
        root = compute_root([LEAF_A])
        assert root == LEAF_A

    def test_single_leaf_tree(self):
        """Single leaf tree has root = leaf."""
        tree = build_merkle_tree([LEAF_A])
        assert tree.root == LEAF_A
        assert tree.leaf_count == 1
        # Single leaf: only the leaf level exists (no parent level needed)


class TestTwoLeaves:
    def test_two_leaves_deterministic(self):
        """Two leaves produce a deterministic root."""
        root1 = compute_root([LEAF_A, LEAF_B])
        root2 = compute_root([LEAF_A, LEAF_B])
        assert root1 == root2

    def test_two_leaves_root_is_sha256(self):
        """Two leaves: root = SHA256(leaf_a_bytes || leaf_b_bytes)."""
        root = compute_root([LEAF_A, LEAF_B])
        expected = hashlib.sha256(hash_leaf(LEAF_A) + hash_leaf(LEAF_B)).hexdigest()
        assert root == expected


class TestThreeLeaves:
    def test_three_leaves_odd_doubling(self):
        """Three leaves: odd node is doubled (leaf_c paired with itself)."""
        root = compute_root([LEAF_A, LEAF_B, LEAF_C])

        # Level 0: [A, B, C]
        # Level 1: [SHA256(A||B), SHA256(C||C)]  (C doubled)
        # Level 2: SHA256(SHA256(A||B) || SHA256(C||C))
        ab = hashlib.sha256(hash_leaf(LEAF_A) + hash_leaf(LEAF_B)).digest()
        cc = hashlib.sha256(hash_leaf(LEAF_C) + hash_leaf(LEAF_C)).digest()
        expected = hashlib.sha256(ab + cc).hexdigest()
        assert root == expected

    def test_three_leaves_deterministic(self):
        """Three leaves produce a deterministic root."""
        root1 = compute_root([LEAF_A, LEAF_B, LEAF_C])
        root2 = compute_root([LEAF_A, LEAF_B, LEAF_C])
        assert root1 == root2


class TestFourLeaves:
    def test_four_leaves_balanced(self):
        """Four leaves form a balanced tree."""
        root = compute_root([LEAF_A, LEAF_B, LEAF_C, LEAF_D])

        ab = hashlib.sha256(hash_leaf(LEAF_A) + hash_leaf(LEAF_B)).digest()
        cd = hashlib.sha256(hash_leaf(LEAF_C) + hash_leaf(LEAF_D)).digest()
        expected = hashlib.sha256(ab + cd).hexdigest()
        assert root == expected


class TestDeterminism:
    def test_same_inputs_same_root(self):
        """Same ordered leaves always produce the same root."""
        leaves = [LEAF_A, LEAF_B, LEAF_C, LEAF_D]
        roots = [compute_root(leaves) for _ in range(10)]
        assert len(set(roots)) == 1

    def test_changed_leaf_changes_root(self):
        """Changing one leaf changes the root."""
        root_original = compute_root([LEAF_A, LEAF_B, LEAF_C])
        root_tampered = compute_root([LEAF_A, LEAF_B, _receipt_hash("record_c_tampered")])
        assert root_original != root_tampered

    def test_changed_order_changes_root(self):
        """Changing leaf order changes the root."""
        root_ab = compute_root([LEAF_A, LEAF_B])
        root_ba = compute_root([LEAF_B, LEAF_A])
        assert root_ab != root_ba


class TestProofs:
    def test_proof_generation_and_verification(self):
        """Generate proof for each leaf and verify it."""
        leaves = [LEAF_A, LEAF_B, LEAF_C, LEAF_D]
        tree = build_merkle_tree(leaves)
        assert tree.root is not None

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            assert verify_proof(leaf, proof, tree.root, i), f"Proof failed for leaf {i}"

    def test_proof_fails_with_wrong_root(self):
        """Proof verification fails with wrong root."""
        leaves = [LEAF_A, LEAF_B]
        tree = build_merkle_tree(leaves)
        proof = generate_proof(tree, 0)
        assert not verify_proof(LEAF_A, proof, "0" * 64, 0)

    def test_proof_fails_with_wrong_leaf(self):
        """Proof verification fails with wrong leaf."""
        leaves = [LEAF_A, LEAF_B]
        tree = build_merkle_tree(leaves)
        proof = generate_proof(tree, 0)
        assert not verify_proof(LEAF_B, proof, tree.root, 0)

    def test_proof_fails_with_wrong_index(self):
        """Proof verification fails with wrong leaf index."""
        leaves = [LEAF_A, LEAF_B]
        tree = build_merkle_tree(leaves)
        proof = generate_proof(tree, 0)
        assert not verify_proof(LEAF_A, proof, tree.root, 1)

    def test_single_leaf_proof(self):
        """Single leaf has empty proof."""
        tree = build_merkle_tree([LEAF_A])
        proof = generate_proof(tree, 0)
        assert proof == []
        assert verify_proof(LEAF_A, proof, tree.root, 0)

    def test_three_leaf_proof(self):
        """Proof works for odd-count trees."""
        leaves = [LEAF_A, LEAF_B, LEAF_C]
        tree = build_merkle_tree(leaves)
        for i in range(3):
            proof = generate_proof(tree, i)
            assert verify_proof(leaves[i], proof, tree.root, i)
