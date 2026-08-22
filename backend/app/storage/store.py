"""
Phase 9: Local Verification Record Store (SQLite + Postgres/Supabase, dual-write).

Persists finalized verification records so that every verification request
produces a durable audit trail bridging the receipt system to future Merkle
anchoring.

Privacy invariant: raw payloads, private keys, X-PAYMENT data, and
recovery phrases are NEVER stored. Only identifiers, hashes, outcomes,
receipt metadata, payment references, and anchoring metadata are persisted.

Backend selection:
    - DATABASE_URL unset (typical local dev): SQLite only, at db_path.
    - DATABASE_URL set (a Postgres connection string, e.g. a Supabase
      project — always set in production): Postgres is PRIMARY (all reads
      and the authoritative write), and every write is also mirrored,
      best-effort, to the local SQLite file. A mirror write failure is
      logged and does not fail the request — Postgres is the source of
      truth. The mirror is self-healing: each mirror write checks whether
      the row already exists there and inserts or updates accordingly, so
      a previously-failed or missed mirror write is caught up automatically
      on the next write for that request_id.

Architecture:
    VerificationRequest
          ↓
    VerificationResult
          ↓
    VerificationReceipt
          ↓
    LocalVerificationRecord  ← THIS MODULE
          ↓
    future Merkle anchoring (Phase 10)
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pydantic import BaseModel

from app.models.enums import AnchoringStatus
from app.models.verification import VerificationResult, VerificationReceipt
from app.models.payments import PaymentMetadata

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # psycopg2 is only required when DATABASE_URL is set
    psycopg2 = None

logger = logging.getLogger(__name__)

_INTEGRITY_ERRORS = (sqlite3.IntegrityError, *((psycopg2.IntegrityError,) if psycopg2 else ()))


# ---------------------------------------------------------------------------
# LocalVerificationRecord — the persisted entity
# ---------------------------------------------------------------------------

class LocalVerificationRecord(BaseModel):
    """
    The full local, on-device record — a superset of VerificationResult
    plus VerificationReceipt plus anchoring status.

    Per DATA_MODEL.md §3.8, this is persisted in the Local Verification
    Record Store and is never transmitted off-device in raw form.
    """
    record_id: UUID
    request_id: str          # Reference to VerificationRequest.request_id
    receipt_id: str          # Reference to VerificationReceipt.receipt_id
    outcome: str             # verified | verified_repaired | rejected
    receipt_hash: str        # The receipt hash (Merkle leaf value)
    output_hash: str         # Hash of the final validated output
    receipt_json: str        # Serialized VerificationReceipt (deterministic JSON)
    result_json: str         # Serialized VerificationResult (deterministic JSON)
    payment_metadata_json: Optional[str] = None  # Serialized PaymentMetadata (if any)
    anchoring_status: AnchoringStatus = AnchoringStatus.unanchored
    merkle_inclusion_ref: Optional[str] = None
    anchor_tx_ref: Optional[str] = None
    merkle_root: Optional[str] = None
    created_at: str          # ISO 8601 UTC timestamp


# ---------------------------------------------------------------------------
# Schema (compatible with both SQLite and Postgres)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS local_verification_records (
    record_id       TEXT PRIMARY KEY,
    request_id      TEXT NOT NULL UNIQUE,
    receipt_id      TEXT NOT NULL UNIQUE,
    outcome         TEXT NOT NULL,
    receipt_hash    TEXT NOT NULL,
    output_hash     TEXT NOT NULL,
    receipt_json    TEXT NOT NULL,
    result_json     TEXT NOT NULL,
    payment_metadata_json TEXT,
    anchoring_status TEXT NOT NULL DEFAULT 'unanchored',
    merkle_inclusion_ref TEXT,
    anchor_tx_ref   TEXT,
    merkle_root     TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lvr_receipt_id
    ON local_verification_records(receipt_id);

CREATE INDEX IF NOT EXISTS idx_lvr_anchoring_status
    ON local_verification_records(anchoring_status);

CREATE INDEX IF NOT EXISTS idx_lvr_created_at
    ON local_verification_records(created_at);
"""

_INSERT_SQL = """
INSERT INTO local_verification_records
(record_id, request_id, receipt_id, outcome, receipt_hash,
 output_hash, receipt_json, result_json, payment_metadata_json,
 anchoring_status, merkle_inclusion_ref, anchor_tx_ref, merkle_root,
 created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_SQL = """
UPDATE local_verification_records
SET outcome = ?,
    receipt_id = ?,
    receipt_hash = ?,
    output_hash = ?,
    receipt_json = ?,
    result_json = ?,
    payment_metadata_json = ?
WHERE request_id = ?
"""


# ---------------------------------------------------------------------------
# Serialization helpers — deterministic JSON
# ---------------------------------------------------------------------------

def _serialize_model(model) -> str:
    """Deterministic JSON serialization of a Pydantic model."""
    return model.model_dump_json()


def _deserialize_receipt(json_str: str) -> VerificationReceipt:
    return VerificationReceipt.model_validate_json(json_str)


def _deserialize_result(json_str: str) -> VerificationResult:
    return VerificationResult.model_validate_json(json_str)


def _deserialize_payment_metadata(json_str: Optional[str]) -> Optional[PaymentMetadata]:
    if json_str is None:
        return None
    return PaymentMetadata.model_validate_json(json_str)


def _insert_params(record: LocalVerificationRecord) -> tuple:
    return (
        str(record.record_id),
        record.request_id,
        record.receipt_id,
        record.outcome,
        record.receipt_hash,
        record.output_hash,
        record.receipt_json,
        record.result_json,
        record.payment_metadata_json,
        record.anchoring_status.value,
        record.merkle_inclusion_ref,
        record.anchor_tx_ref,
        record.merkle_root,
        record.created_at,
    )


def _update_params(record: LocalVerificationRecord) -> tuple:
    return (
        record.outcome,
        record.receipt_id,
        record.receipt_hash,
        record.output_hash,
        record.receipt_json,
        record.result_json,
        record.payment_metadata_json,
        record.request_id,
    )


# ---------------------------------------------------------------------------
# LocalVerificationRecordStore
# ---------------------------------------------------------------------------

class LocalVerificationRecordStore:
    """
    Stores finalized verification records. Postgres (Supabase) is primary
    whenever DATABASE_URL is set — including always in production — with
    SQLite kept as a live mirror. Without DATABASE_URL (typical local dev),
    SQLite alone is used, unchanged from before.

    Thread-safe: uses thread-local connections per dialect.

    Lifecycle:
        1. save() / upsert() — called after receipt generation
        2. get_by_request_id() / get_by_receipt_id() — retrieval
        3. list_unanchored_records() — consumed by Phase 10 Merkle batching
        4. mark_anchored() — called by Phase 10 after successful anchoring

    Idempotency:
        save() with the same request_id will raise IntegrityError if the
        receipt_id differs (conflict). If the same record is saved twice
        (same request_id + receipt_id), the second save is a no-op.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the store.

        Args:
            db_path: Path to the SQLite database file (used as either the
                     sole backend or the mirror, depending on DATABASE_URL).
                     If None, uses a default path relative to the project
                     backend directory.
        """
        self._database_url = os.environ.get("DATABASE_URL")
        if self._database_url and psycopg2 is None:
            raise RuntimeError(
                "DATABASE_URL is set but psycopg2 is not installed. "
                "Add psycopg2-binary to requirements.txt."
            )

        if db_path is None:
            # Default: backend/data/verified.db
            backend_dir = Path(__file__).resolve().parent.parent.parent
            data_dir = backend_dir / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "verified.db")
        self._sqlite_path = db_path

        self._primary = "postgres" if self._database_url else "sqlite"
        self._mirror = "sqlite" if self._primary == "postgres" else None

        self._local = threading.local()

        self._init_schema(self._primary)
        if self._mirror:
            self._init_schema(self._mirror)

        if self._primary == "postgres":
            host = urlparse(self._database_url).hostname
            logger.info(
                "Local verification record store initialized: primary=postgres@%s mirror=%s",
                host,
                self._sqlite_path if self._mirror else "none",
            )
        else:
            logger.info("Local verification record store initialized at %s (sqlite only)", self._sqlite_path)

    # -----------------------------------------------------------------------
    # Connection / dialect plumbing
    # -----------------------------------------------------------------------

    def _conn(self, dialect: str):
        """Get (or open) the thread-local connection for a dialect."""
        conns = getattr(self._local, "conns", None)
        if conns is None:
            conns = {}
            self._local.conns = conns
        if conns.get(dialect) is None:
            if dialect == "postgres":
                conns[dialect] = psycopg2.connect(
                    self._database_url,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                    connect_timeout=5,
                )
            else:
                conn = sqlite3.connect(self._sqlite_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                conns[dialect] = conn
        return conns[dialect]

    @staticmethod
    def _adapt_sql(dialect: str, sql: str) -> str:
        """Convert SQLite-style `?` placeholders to psycopg2-style `%s`."""
        if dialect == "postgres":
            return sql.replace("?", "%s")
        return sql

    def _execute(self, dialect: str, conn, sql: str, params=()):
        """Execute a statement, returning a cursor-like object with fetch*()."""
        sql = self._adapt_sql(dialect, sql)
        if dialect == "postgres":
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur
        return conn.execute(sql, params)

    def _init_schema(self, dialect: str):
        conn = self._conn(dialect)
        if dialect == "postgres":
            cur = conn.cursor()
            cur.execute(_SCHEMA_SQL)
        else:
            conn.executescript(_SCHEMA_SQL)
        conn.commit()

    def close(self):
        """Close all thread-local database connections."""
        conns = getattr(self._local, "conns", None)
        if not conns:
            return
        for conn in conns.values():
            if conn is not None:
                conn.close()
        self._local.conns = {}

    # -----------------------------------------------------------------------
    # Internal dialect-scoped read/write helpers (used for both primary and mirror)
    # -----------------------------------------------------------------------

    def _get_by_request_id_on(self, dialect: str, conn, request_id: str) -> Optional[LocalVerificationRecord]:
        row = self._execute(
            dialect, conn,
            "SELECT * FROM local_verification_records WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def _insert_on(self, dialect: str, conn, record: LocalVerificationRecord):
        self._execute(dialect, conn, _INSERT_SQL, _insert_params(record))

    def _update_on(self, dialect: str, conn, record: LocalVerificationRecord):
        self._execute(dialect, conn, _UPDATE_SQL, _update_params(record))

    def _mirror_upsert(self, record: LocalVerificationRecord):
        """Best-effort self-healing upsert of `record` into the mirror dialect."""
        if not self._mirror:
            return
        conn = self._conn(self._mirror)
        try:
            existing = self._get_by_request_id_on(self._mirror, conn, record.request_id)
            if existing is not None:
                self._update_on(self._mirror, conn, record)
            else:
                self._insert_on(self._mirror, conn, record)
            conn.commit()
        except Exception:
            logger.warning(
                "Mirror write to %s failed for request_id=%s (primary write succeeded; "
                "will self-heal on next write for this request)",
                self._mirror, record.request_id, exc_info=True,
            )
            try:
                conn.rollback()
            except Exception:
                pass

    def _mirror_mark_anchored(self, record_ids: list[str], merkle_root: str, anchor_tx_ref: str):
        if not self._mirror:
            return
        conn = self._conn(self._mirror)
        try:
            for record_id in record_ids:
                self._execute(
                    self._mirror, conn,
                    """
                    UPDATE local_verification_records
                    SET anchoring_status = 'anchored',
                        merkle_root = ?,
                        anchor_tx_ref = ?
                    WHERE record_id = ? AND anchoring_status != 'anchored'
                    """,
                    (merkle_root, anchor_tx_ref, record_id),
                )
            conn.commit()
        except Exception:
            logger.warning(
                "Mirror mark_anchored to %s failed for %d record(s) (primary write succeeded)",
                self._mirror, len(record_ids), exc_info=True,
            )
            try:
                conn.rollback()
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Core operations (operate on primary; mirror best-effort)
    # -----------------------------------------------------------------------

    def save(
        self,
        result: VerificationResult,
        receipt: VerificationReceipt,
        payment_metadata: Optional[PaymentMetadata] = None,
    ) -> LocalVerificationRecord:
        """
        Persist a finalized verification record.

        Called AFTER receipt generation — the result and receipt are final.
        Only finalized state is stored; intermediate candidates are never persisted.

        Args:
            result: The finalized VerificationResult.
            receipt: The finalized VerificationReceipt.
            payment_metadata: Optional PaymentMetadata (for semantic repair).

        Returns:
            The created LocalVerificationRecord.

        Raises:
            sqlite3.IntegrityError / psycopg2.IntegrityError: If request_id
                conflicts with an existing record that has a different
                receipt_id (integrity conflict). Only the primary backend's
                integrity is authoritative for this check.
        """
        record = LocalVerificationRecord(
            record_id=uuid4(),
            request_id=str(receipt.request_id_ref),
            receipt_id=str(receipt.receipt_id),
            outcome=receipt.outcome.value,
            receipt_hash=receipt.receipt_hash,
            output_hash=receipt.output_hash,
            receipt_json=_serialize_model(receipt),
            result_json=_serialize_model(result),
            payment_metadata_json=_serialize_model(payment_metadata) if payment_metadata else None,
            anchoring_status=AnchoringStatus.unanchored,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        conn = self._conn(self._primary)
        try:
            self._insert_on(self._primary, conn, record)
            conn.commit()
            logger.info(
                "Record persisted: request_id=%s receipt_id=%s outcome=%s anchoring=%s",
                record.request_id,
                record.receipt_id,
                record.outcome,
                record.anchoring_status,
            )
            self._mirror_upsert(record)
            return record

        except _INTEGRITY_ERRORS as e:
            # A Postgres transaction is aborted after an error — roll back
            # before issuing any further query on this connection.
            conn.rollback()

            # Check if it's a duplicate save (same request_id + same receipt_id)
            # or a conflict (same request_id, different receipt_id)
            existing = self.get_by_request_id(record.request_id)
            if existing is not None and existing.receipt_id == record.receipt_id:
                # Idempotent: same record already saved
                logger.info(
                    "Idempotent save: request_id=%s already persisted with same receipt_id",
                    record.request_id,
                )
                return existing

            # Conflict: same request_id, different receipt_id
            logger.error(
                "INTEGRITY CONFLICT: request_id=%s already has receipt_id=%s, "
                "cannot save with receipt_id=%s",
                record.request_id,
                existing.receipt_id if existing else "unknown",
                record.receipt_id,
            )
            raise sqlite3.IntegrityError(
                f"request_id={record.request_id} already exists with a different receipt_id"
            ) from e

    def upsert(
        self,
        result: VerificationResult,
        receipt: VerificationReceipt,
        payment_metadata: Optional[PaymentMetadata] = None,
    ) -> LocalVerificationRecord:
        """
        Insert or update a verification record.

        If a record with the same request_id already exists (e.g., from
        an initial /verify call), UPDATE it with the final result (e.g.,
        from a successful /semantic-repair call). This ensures the
        database always reflects the final verification lifecycle state.

        If no record exists, INSERT a new one.
        """
        request_id = str(receipt.request_id_ref)
        outcome = receipt.outcome.value

        conn = self._conn(self._primary)
        existing = self._get_by_request_id_on(self._primary, conn, request_id)

        if existing is not None:
            updated = existing.model_copy(update={
                "outcome": outcome,
                "receipt_id": str(receipt.receipt_id),
                "receipt_hash": receipt.receipt_hash,
                "output_hash": receipt.output_hash,
                "receipt_json": _serialize_model(receipt),
                "result_json": _serialize_model(result),
                "payment_metadata_json": _serialize_model(payment_metadata) if payment_metadata else None,
            })
            self._update_on(self._primary, conn, updated)
            conn.commit()
            logger.info(
                "Record UPDATED: request_id=%s outcome=%s receipt_id=%s",
                request_id, outcome, str(receipt.receipt_id),
            )
            self._mirror_upsert(updated)
            return updated

        # No existing record — INSERT new
        record = LocalVerificationRecord(
            record_id=uuid4(),
            request_id=request_id,
            receipt_id=str(receipt.receipt_id),
            outcome=outcome,
            receipt_hash=receipt.receipt_hash,
            output_hash=receipt.output_hash,
            receipt_json=_serialize_model(receipt),
            result_json=_serialize_model(result),
            payment_metadata_json=_serialize_model(payment_metadata) if payment_metadata else None,
            anchoring_status=AnchoringStatus.unanchored,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._insert_on(self._primary, conn, record)
        conn.commit()
        logger.info(
            "Record CREATED: request_id=%s outcome=%s receipt_id=%s",
            request_id, outcome, record.receipt_id,
        )
        self._mirror_upsert(record)
        return record

    def get_by_request_id(self, request_id: str) -> Optional[LocalVerificationRecord]:
        """Retrieve a record by its request_id (reads from the primary backend)."""
        return self._get_by_request_id_on(self._primary, self._conn(self._primary), request_id)

    def get_by_receipt_id(self, receipt_id: str) -> Optional[LocalVerificationRecord]:
        """Retrieve a record by its receipt_id (reads from the primary backend)."""
        conn = self._conn(self._primary)
        row = self._execute(
            self._primary, conn,
            "SELECT * FROM local_verification_records WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def list_unanchored_records(self) -> list[LocalVerificationRecord]:
        """
        Return all records eligible for Merkle batching (Phase 10), read
        from the primary backend.

        Returns records with anchoring_status = 'unanchored', ordered by
        created_at ASC then record_id ASC for deterministic leaf ordering.

        IMPORTANT: Merkle roots depend on deterministic leaf ordering.
        This ordering is stable: created_at (ISO 8601) + record_id (UUID).

        Does NOT mutate anchoring status while reading.
        """
        conn = self._conn(self._primary)
        rows = self._execute(
            self._primary, conn,
            """
            SELECT * FROM local_verification_records
            WHERE anchoring_status = 'unanchored'
            ORDER BY created_at ASC, record_id ASC
            """,
        ).fetchall()

        return [self._row_to_record(row) for row in rows]

    def mark_anchored(
        self,
        record_ids: list[str],
        merkle_root: str,
        anchor_tx_ref: str,
    ):
        """
        Mark records as anchored after successful Merkle anchoring (Phase 10).

        Called by the Merkle Anchoring Service after a batch is anchored.
        Applied to the primary backend; mirrored best-effort.

        Args:
            record_ids: List of record_id strings to mark as anchored.
            merkle_root: The Merkle root that was anchored on Algorand.
            anchor_tx_ref: The Algorand transaction reference.
        """
        conn = self._conn(self._primary)

        for record_id in record_ids:
            self._execute(
                self._primary, conn,
                """
                UPDATE local_verification_records
                SET anchoring_status = 'anchored',
                    merkle_root = ?,
                    anchor_tx_ref = ?
                WHERE record_id = ? AND anchoring_status != 'anchored'
                """,
                (merkle_root, anchor_tx_ref, record_id),
            )

        conn.commit()
        logger.info(
            "Marked %d records as anchored (merkle_root=%s...)",
            len(record_ids),
            merkle_root[:16],
        )
        self._mirror_mark_anchored(record_ids, merkle_root, anchor_tx_ref)

    # -----------------------------------------------------------------------
    # Deserialization
    # -----------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row) -> LocalVerificationRecord:
        """Convert a database row (sqlite3.Row or psycopg2 RealDictRow) to a LocalVerificationRecord."""
        return LocalVerificationRecord(
            record_id=UUID(row["record_id"]),
            request_id=row["request_id"],
            receipt_id=row["receipt_id"],
            outcome=row["outcome"],
            receipt_hash=row["receipt_hash"],
            output_hash=row["output_hash"],
            receipt_json=row["receipt_json"],
            result_json=row["result_json"],
            payment_metadata_json=row["payment_metadata_json"],
            anchoring_status=AnchoringStatus(row["anchoring_status"]),
            merkle_inclusion_ref=row["merkle_inclusion_ref"],
            anchor_tx_ref=row["anchor_tx_ref"],
            merkle_root=row["merkle_root"],
            created_at=row["created_at"],
        )

    def get_receipt(self, record: LocalVerificationRecord) -> VerificationReceipt:
        """Deserialize the receipt from a record."""
        return _deserialize_receipt(record.receipt_json)

    def get_result(self, record: LocalVerificationRecord) -> VerificationResult:
        """Deserialize the result from a record."""
        return _deserialize_result(record.result_json)

    # -----------------------------------------------------------------------
    # Frontend API support (Phase 15) — reads from the primary backend
    # -----------------------------------------------------------------------

    def list_records(self, offset: int = 0, limit: int = 50) -> list[dict]:
        """
        Return a page of records as plain dicts for the frontend API.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            List of dicts with safe metadata fields.
        """
        conn = self._conn(self._primary)
        rows = self._execute(
            self._primary, conn,
            """
            SELECT record_id, request_id, receipt_id, outcome, receipt_hash,
                   output_hash, anchoring_status, merkle_root, anchor_tx_ref,
                   created_at, receipt_json, result_json, payment_metadata_json
            FROM local_verification_records
            ORDER BY created_at DESC, record_id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            # Extract safe metadata from serialized JSON
            try:
                receipt = _deserialize_receipt(row["receipt_json"])
                d["schema_ref_and_version"] = receipt.schema_ref_and_version
                d["signing_key_id"] = receipt.signing_key_id
                d["signature_algorithm"] = receipt.signature_algorithm
            except Exception:
                d["schema_ref_and_version"] = None
                d["signing_key_id"] = None
                d["signature_algorithm"] = None

            try:
                result = _deserialize_result(row["result_json"])
                d["validator_version"] = result.validator_version
                if result.repair_info:
                    d["repair_type"] = result.repair_info.repair_type.value
                else:
                    d["repair_type"] = None
            except Exception:
                d["validator_version"] = None
                d["repair_type"] = None

            try:
                pm = _deserialize_payment_metadata(row["payment_metadata_json"])
                if pm:
                    d["payment_status"] = pm.payment_status.value
                    d["payment_facilitator"] = pm.facilitator
                    d["settlement_network"] = pm.settlement_network
                else:
                    d["payment_status"] = None
                    d["payment_facilitator"] = None
                    d["settlement_network"] = None
            except Exception:
                d["payment_status"] = None
                d["payment_facilitator"] = None
                d["settlement_network"] = None

            results.append(d)

        return results

    def get_by_record_id(self, record_id: str) -> Optional[dict]:
        """
        Retrieve a record by its record_id as a plain dict.

        Args:
            record_id: The LocalVerificationRecord.record_id (as string).

        Returns:
            Dict with safe metadata fields, or None if not found.
        """
        conn = self._conn(self._primary)
        row = self._execute(
            self._primary, conn,
            "SELECT * FROM local_verification_records WHERE record_id = ?",
            (record_id,),
        ).fetchone()

        if row is None:
            return None

        d = dict(row)
        try:
            receipt = _deserialize_receipt(row["receipt_json"])
            d["schema_ref_and_version"] = receipt.schema_ref_and_version
            d["signing_key_id"] = receipt.signing_key_id
            d["signature_algorithm"] = receipt.signature_algorithm
        except Exception:
            d["schema_ref_and_version"] = None
            d["signing_key_id"] = None
            d["signature_algorithm"] = None

        try:
            result = _deserialize_result(row["result_json"])
            d["validator_version"] = result.validator_version
            d["agent_identifier"] = None  # Not stored, derive from result
            if result.repair_info:
                d["repair_type"] = result.repair_info.repair_type.value
            else:
                d["repair_type"] = None
        except Exception:
            d["validator_version"] = None
            d["repair_type"] = None

        try:
            pm = _deserialize_payment_metadata(row["payment_metadata_json"])
            if pm:
                d["payment_status"] = pm.payment_status.value
                d["payment_facilitator"] = pm.facilitator
                d["settlement_network"] = pm.settlement_network
            else:
                d["payment_status"] = None
                d["payment_facilitator"] = None
                d["settlement_network"] = None
        except Exception:
            d["payment_status"] = None
            d["payment_facilitator"] = None
            d["settlement_network"] = None

        return d

    def get_payment_metadata(
        self, record: LocalVerificationRecord
    ) -> Optional[PaymentMetadata]:
        """Deserialize payment metadata from a record (if present)."""
        return _deserialize_payment_metadata(record.payment_metadata_json)
