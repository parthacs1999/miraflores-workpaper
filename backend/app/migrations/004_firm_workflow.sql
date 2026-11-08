BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS workflow_schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workflow_entities(
 id TEXT PRIMARY KEY,kind TEXT NOT NULL,engagement_id TEXT NOT NULL,area TEXT NOT NULL,
 revision INTEGER NOT NULL,state TEXT NOT NULL,data_json TEXT NOT NULL,authors_json TEXT NOT NULL,
 created_by TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS workflow_entity_scope ON workflow_entities(engagement_id,kind,area);
CREATE TABLE IF NOT EXISTS workflow_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,entity_id TEXT NOT NULL,kind TEXT NOT NULL,action TEXT NOT NULL,
 actor_id TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,event_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS workflow_policies(
 id TEXT PRIMARY KEY,revision INTEGER NOT NULL UNIQUE,policy_json TEXT NOT NULL,
 created_by TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_sessions(
 token_hash TEXT PRIMARY KEY,staff_id TEXT,csrf_hash TEXT NOT NULL,assurance TEXT NOT NULL,
 expires_at TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,credential_epoch TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_signoffs(
 id TEXT PRIMARY KEY,engagement_id TEXT NOT NULL,area TEXT NOT NULL,level TEXT NOT NULL,staff_id TEXT NOT NULL,
 assurance TEXT NOT NULL,legal_signature INTEGER NOT NULL CHECK(legal_signature=0),
 manifest_json TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('valid','invalidated','revoked')),
 reason TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_access_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,staff_id TEXT,action TEXT NOT NULL,resource_json TEXT NOT NULL,
 purpose TEXT NOT NULL,outcome TEXT NOT NULL,request_id TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_readiness_evaluations(
 id TEXT PRIMARY KEY,engagement_id TEXT NOT NULL,staff_id TEXT NOT NULL,
 result_json TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS wf_events_update BEFORE UPDATE ON workflow_events BEGIN SELECT RAISE(ABORT,'Workflow events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS wf_events_delete BEFORE DELETE ON workflow_events BEGIN SELECT RAISE(ABORT,'Workflow events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS wf_policy_update BEFORE UPDATE ON workflow_policies BEGIN SELECT RAISE(ABORT,'Policy revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS wf_policy_delete BEFORE DELETE ON workflow_policies BEGIN SELECT RAISE(ABORT,'Policy revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS wf_access_update BEFORE UPDATE ON workflow_access_events BEGIN SELECT RAISE(ABORT,'Access events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS wf_access_delete BEFORE DELETE ON workflow_access_events BEGIN SELECT RAISE(ABORT,'Access events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS wf_readiness_update BEFORE UPDATE ON workflow_readiness_evaluations BEGIN SELECT RAISE(ABORT,'Readiness events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS wf_readiness_delete BEFORE DELETE ON workflow_readiness_evaluations BEGIN SELECT RAISE(ABORT,'Readiness events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS wf_signoff_delete BEFORE DELETE ON workflow_signoffs BEGIN SELECT RAISE(ABORT,'Sign-offs cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS wf_signoff_update BEFORE UPDATE ON workflow_signoffs
WHEN OLD.state!='valid' OR NEW.state NOT IN ('invalidated','revoked') OR NEW.id!=OLD.id
 OR NEW.engagement_id!=OLD.engagement_id OR NEW.area!=OLD.area OR NEW.level!=OLD.level
 OR NEW.staff_id!=OLD.staff_id OR NEW.assurance!=OLD.assurance OR NEW.legal_signature!=OLD.legal_signature
 OR NEW.manifest_json!=OLD.manifest_json OR NEW.created_at!=OLD.created_at
BEGIN SELECT RAISE(ABORT,'Signed content is immutable and invalidation is permanent'); END;
INSERT OR IGNORE INTO workflow_schema_migrations VALUES(4,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
COMMIT;
