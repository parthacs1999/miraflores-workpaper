BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS hosted_schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hosted_session_bindings(
    token_hash TEXT PRIMARY KEY REFERENCES workflow_sessions(token_hash),
    subject_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS hosted_binding_no_update BEFORE UPDATE ON hosted_session_bindings
BEGIN SELECT RAISE(ABORT,'Session identity bindings are immutable'); END;
CREATE TRIGGER IF NOT EXISTS hosted_binding_no_delete BEFORE DELETE ON hosted_session_bindings
BEGIN SELECT RAISE(ABORT,'Session identity bindings are immutable'); END;
INSERT OR IGNORE INTO hosted_schema_migrations VALUES(7,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
COMMIT;
