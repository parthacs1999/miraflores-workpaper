BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS lifecycle_schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lifecycle_snapshots(
 id TEXT PRIMARY KEY,content_hash TEXT NOT NULL,version TEXT NOT NULL,
 purpose TEXT NOT NULL CHECK(purpose IN ('return','amendment')),
 mode TEXT NOT NULL CHECK(mode IN ('demonstration','authoritative')),
 parent_id TEXT REFERENCES lifecycle_snapshots(id),content_json TEXT NOT NULL,
 dependency_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lifecycle_snapshot_content ON lifecycle_snapshots(content_hash);
CREATE TABLE IF NOT EXISTS lifecycle_packages(
 id TEXT PRIMARY KEY,kind TEXT NOT NULL CHECK(kind IN ('client_copy','examination_response','handoff')),
 snapshot_id TEXT NOT NULL REFERENCES lifecycle_snapshots(id),resource_id TEXT NOT NULL,
 content_hash TEXT NOT NULL,content_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS lifecycle_package_resource ON lifecycle_packages(resource_id,kind);
CREATE TRIGGER IF NOT EXISTS lifecycle_snapshot_no_update BEFORE UPDATE ON lifecycle_snapshots BEGIN SELECT RAISE(ABORT,'Finalized snapshot content is immutable'); END;
CREATE TRIGGER IF NOT EXISTS lifecycle_snapshot_no_delete BEFORE DELETE ON lifecycle_snapshots BEGIN SELECT RAISE(ABORT,'Historical snapshots cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS lifecycle_package_no_update BEFORE UPDATE ON lifecycle_packages BEGIN SELECT RAISE(ABORT,'Generated packages are immutable'); END;
CREATE TRIGGER IF NOT EXISTS lifecycle_package_no_delete BEFORE DELETE ON lifecycle_packages BEGIN SELECT RAISE(ABORT,'Generated package history cannot be deleted'); END;
INSERT OR IGNORE INTO lifecycle_schema_migrations VALUES(5,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
COMMIT;
