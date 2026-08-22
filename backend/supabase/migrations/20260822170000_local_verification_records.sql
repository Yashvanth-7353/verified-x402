-- Mirrors app/storage/store.py's SQLite schema for local_verification_records.
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
