BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS reconciliation_schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
-- Bootstrap the identical legacy schema only on fresh databases. Existing tables/rows stay intact.
CREATE TABLE IF NOT EXISTS reviews (
 version TEXT NOT NULL, finding_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
 note TEXT NOT NULL DEFAULT '', updated_by TEXT, updated_at TEXT, PRIMARY KEY(version,finding_id)
);
CREATE TABLE IF NOT EXISTS review_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT NOT NULL, finding_id TEXT NOT NULL,
 previous_status TEXT NOT NULL, new_status TEXT NOT NULL, note TEXT NOT NULL,
 actor_role TEXT NOT NULL, actor_name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reconciliation_decisions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT NOT NULL, finding_id TEXT NOT NULL,
 review_event_id INTEGER NOT NULL UNIQUE, actor_id TEXT NOT NULL, disposition TEXT NOT NULL,
 authority TEXT NOT NULL, evidence_refs_json TEXT NOT NULL, adjustment_id TEXT,
 packet_hash TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS finding_adjustment_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT NOT NULL, finding_id TEXT NOT NULL,
 adjustment_id TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('link','unlink')),
 actor_id TEXT NOT NULL, note TEXT NOT NULL, packet_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reconciliation_decision_lookup ON reconciliation_decisions(version,finding_id,id);
CREATE INDEX IF NOT EXISTS finding_adjustment_lookup ON finding_adjustment_events(version,finding_id,id);
CREATE TRIGGER IF NOT EXISTS review_history_no_update BEFORE UPDATE ON review_events BEGIN SELECT RAISE(ABORT,'Review history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS review_history_no_delete BEFORE DELETE ON review_events BEGIN SELECT RAISE(ABORT,'Review history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS reconciliation_decision_no_update BEFORE UPDATE ON reconciliation_decisions BEGIN SELECT RAISE(ABORT,'Decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS reconciliation_decision_no_delete BEFORE DELETE ON reconciliation_decisions BEGIN SELECT RAISE(ABORT,'Decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS finding_adjustment_no_update BEFORE UPDATE ON finding_adjustment_events BEGIN SELECT RAISE(ABORT,'Finding links are append-only'); END;
CREATE TRIGGER IF NOT EXISTS finding_adjustment_no_delete BEFORE DELETE ON finding_adjustment_events BEGIN SELECT RAISE(ABORT,'Finding links are append-only'); END;
INSERT OR IGNORE INTO reconciliation_schema_migrations VALUES (3,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
COMMIT;
