BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS evidence_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS field_verification_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK(sequence > 0),
    verifier_id TEXT NOT NULL,
    verifier_name TEXT NOT NULL,
    verifier_role TEXT NOT NULL,
    credential TEXT,
    assurance TEXT NOT NULL CHECK(assurance IN ('staff_attestation','cpa_attestation')),
    method TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('confirmed','needs_review','revoked')),
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    packet_hash TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    UNIQUE(version, evidence_id, sequence)
);
CREATE INDEX IF NOT EXISTS field_verification_lookup ON field_verification_events(version, evidence_id, sequence);
CREATE TRIGGER IF NOT EXISTS field_verification_no_update BEFORE UPDATE ON field_verification_events
BEGIN SELECT RAISE(ABORT, 'Field verification history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS field_verification_no_delete BEFORE DELETE ON field_verification_events
BEGIN SELECT RAISE(ABORT, 'Field verification history is append-only'); END;
INSERT OR IGNORE INTO evidence_schema_migrations(version, applied_at)
VALUES (2, strftime('%Y-%m-%dT%H:%M:%fZ','now'));
COMMIT;
