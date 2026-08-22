"""
Phase 9: Local Verification Record Store (SQLite or Postgres/Supabase backend).

Persists finalized verification records locally so that every verification
request produces a durable audit trail bridging the receipt system to
future Merkle anchoring.

Privacy invariant: raw payloads, private keys, X-PAYMENT data, and
recovery phrases are NEVER stored. Only identifiers, hashes, outcomes,
receipt metadata, payment references, and anchoring metadata are persisted.

Backend selection: if the DATABASE_URL environment variable is set (a
Postgres connection string, e.g. a Supabase project), records are persisted
there. Otherwise falls back to a local SQLite file — used for local
development so no external database is required to run the app.

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

import json
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


# ---------------------------------------------------------------------------
# LocalVerificationRecordStore
# ---------------------------------------------------------------------------

class LocalVerificationRecordStore:
    """
    Stores finalized verification records in SQLite (local dev) or Postgres
    (production, e.g. Supabase — set DATABASE_URL to enable).

    Thread-safe: uses a thread-local connection per thread.

    Lifecycle:
        1. save() — called after receipt generation (finalized state only)
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
            db_path: Path to the SQLite database file, used only when
                     DATABASE_URL is not set. If None, uses a default path
                     relative to the project backend directory.
        """
        self._database_url = os.environ.get("DATABASE_URL")

        if self._database_url:
            if psycopg2 is None:
                raise RuntimeError(
                    "DATABASE_URL is set but psycopg2 is not installed. "
                    "Add psycopg2-binary to requirements.txt."
                )
            self._dialect = "postgres"
            self._db_path = None
        else:
            self._dialect = "sqlite"
            if db_path is None:
                # Default: backend/data/verified.db
                backend_dir = Path(__file__).resolve().parent.parent.parent
                data_dir = backend_dir / "data"
                data_dir.mkdir(exist_ok=True)
                db_path = str(data_dir / "verified.db")
            self._db_path = db_path

        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            if self._dialect == "postgres":
                conn = psycopg2.connect(
                    self._database_url,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
            else:
                conn = sqlite3.connect(self._db_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _adapt_sql(self, sql: str) -> str:
        """Convert SQLite-style `?` placeholders to psycopg2-style `%s`."""
        if self._dialect == "postgres":
            return sql.replace("?", "%s")
        return sql

    def _execute(self, conn, sql: str, params=()):
        """Execute a statement, returning a cursor-like object with fetch*()."""
        sql = self._adapt_sql(sql)
        if self._dialect == "postgres":
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur
        return conn.execute(sql, params)

    def _init_db(self):
        """Initialize the database schema."""
        conn = self._get_conn()
        if self._dialect == "postgres":
            cur = conn.cursor()
            cur.execute(_SCHEMA_SQL)
        else:
            conn.executescript(_SCHEMA_SQL)
        conn.commit()
        if self._dialect == "postgres":
            host = urlparse(self._database_url).hostname
            logger.info("Local verification record store initialized (postgres @ %s)", host)
        else:
            logger.info("Local verification record store initialized at %s", self._db_path)

    def close(self):
        """Close the thread-local database connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    # -----------------------------------------------------------------------
    # Core operations
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
                receipt_id (integrity conflict).
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

        conn = self._get_conn()
        try:
            self._execute(
                conn,
                """
                INSERT INTO local_verification_records
                (record_id, request_id, receipt_id, outcome, receipt_hash,
                 output_hash, receipt_json, result_json, payment_metadata_json,
                 anchoring_status, merkle_inclusion_ref, anchor_tx_ref, merkle_root,
                 created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                ),
            )
            conn.commit()
            logger.info(
                "Record persisted: request_id=%s receipt_id=%s outcome=%s anchoring=%s",
                record.request_id,
                record.receipt_id,
                record.outcome,
                record.anchoring_status,
            )
            return record

        except (sqlite3.IntegrityError, *((psycopg2.IntegrityError,) if psycopg2 else ())) as e:
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

        conn = self._get_conn()

        existing = self.get_by_request_id(request_id)
        if existing is not None:
            # UPDATE the existing record with the final state
            self._execute(
                conn,
                """
                UPDATE local_verification_records
                SET outcome = ?,
                    receipt_id = ?,
                    receipt_hash = ?,
                    output_hash = ?,
                    receipt_json = ?,
                    result_json = ?,
                    payment_metadata_json = ?
                WHERE request_id = ?
                """,
                (
                    outcome,
                    str(receipt.receipt_id),
                    receipt.receipt_hash,
                    receipt.output_hash,
                    _serialize_model(receipt),
                    _serialize_model(result),
                    _serialize_model(payment_metadata) if payment_metadata else None,
                    request_id,
                ),
            )
            conn.commit()
            logger.info(
                "Record UPDATED: request_id=%s outcome=%s receipt_id=%s",
                request_id, outcome, str(receipt.receipt_id),
            )
            # Return the updated record
            updated = self.get_by_request_id(request_id)
            assert updated is not None
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
        self._execute(
            conn,
            """
            INSERT INTO local_verification_records
            (record_id, request_id, receipt_id, outcome, receipt_hash,
             output_hash, receipt_json, result_json, payment_metadata_json,
             anchoring_status, merkle_inclusion_ref, anchor_tx_ref, merkle_root,
             created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
            ),
        )
        conn.commit()
        logger.info(
            "Record CREATED: request_id=%s outcome=%s receipt_id=%s",
            request_id, outcome, record.receipt_id,
        )
        return record

    def get_by_request_id(self, request_id: str) -> Optional[LocalVerificationRecord]:
        """
        Retrieve a record by its request_id.

        Args:
            request_id: The VerificationRequest.request_id (as string).

        Returns:
            The LocalVerificationRecord if found, None otherwise.
        """
        conn = self._get_conn()
        row = self._execute(
            conn,
            "SELECT * FROM local_verification_records WHERE request_id = ?",
            (request_id,),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def get_by_receipt_id(self, receipt_id: str) -> Optional[LocalVerificationRecord]:
        """
        Retrieve a record by its receipt_id.

        Args:
            receipt_id: The VerificationReceipt.receipt_id (as string).

        Returns:
            The LocalVerificationRecord if found, None otherwise.
        """
        conn = self._get_conn()
        row = self._execute(
            conn,
            "SELECT * FROM local_verification_records WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def list_unanchored_records(self) -> list[LocalVerificationRecord]:
        """
        Return all records eligible for Merkle batching (Phase 10).

        Returns records with anchoring_status = 'unanchored', ordered by
        created_at ASC then record_id ASC for deterministic leaf ordering.

        IMPORTANT: Merkle roots depend on deterministic leaf ordering.
        This ordering is stable: created_at (ISO 8601) + record_id (UUID).

        Does NOT mutate anchoring status while reading.
        """
        conn = self._get_conn()
        rows = self._execute(
            conn,
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

        Args:
            record_ids: List of record_id strings to mark as anchored.
            merkle_root: The Merkle root that was anchored on Algorand.
            anchor_tx_ref: The Algorand transaction reference.
        """
        conn = self._get_conn()

        for record_id in record_ids:
            self._execute(
                conn,
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
    # Frontend API support (Phase 15)
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
        conn = self._get_conn()
        rows = self._execute(
            conn,
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
        conn = self._get_conn()
        row = self._execute(
            conn,
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
