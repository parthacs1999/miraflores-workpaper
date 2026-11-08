BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS adjustment_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS adjustments (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    packet_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('draft','submitted','approved','rejected','reversed','superseded')),
    revision INTEGER NOT NULL CHECK(revision > 0),
    sequence INTEGER NOT NULL CHECK(sequence > 0),
    prepared_by TEXT NOT NULL,
    supersedes_id TEXT REFERENCES adjustments(id),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS adjustments_version_state ON adjustments(version, state);
CREATE TABLE IF NOT EXISTS adjustment_revisions (
    adjustment_id TEXT NOT NULL REFERENCES adjustments(id),
    revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(adjustment_id, revision)
);
CREATE TABLE IF NOT EXISTS adjustment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adjustment_id TEXT NOT NULL REFERENCES adjustments(id),
    revision INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT NOT NULL,
    note TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(adjustment_id, sequence)
);
CREATE TRIGGER IF NOT EXISTS adjustment_revisions_no_update BEFORE UPDATE ON adjustment_revisions
BEGIN SELECT RAISE(ABORT, 'Adjustment revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS adjustment_revisions_no_delete BEFORE DELETE ON adjustment_revisions
BEGIN SELECT RAISE(ABORT, 'Adjustment revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS adjustment_events_no_update BEFORE UPDATE ON adjustment_events
BEGIN SELECT RAISE(ABORT, 'Adjustment events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS adjustment_events_no_delete BEFORE DELETE ON adjustment_events
BEGIN SELECT RAISE(ABORT, 'Adjustment events are append-only'); END;
INSERT OR IGNORE INTO adjustment_schema_migrations(version, applied_at)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
COMMIT;
