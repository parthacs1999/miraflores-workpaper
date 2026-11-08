BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS product_schema_migrations(version INTEGER PRIMARY KEY,applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS product_files(
 id TEXT PRIMARY KEY,engagement_id TEXT NOT NULL,sha256 TEXT NOT NULL,media_type TEXT NOT NULL,
 size INTEGER NOT NULL CHECK(size BETWEEN 1 AND 5242880),content BLOB NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS product_commands(
 engagement_id TEXT NOT NULL,staff_id TEXT NOT NULL,command_key TEXT NOT NULL,request_hash TEXT NOT NULL,
 result_json TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(engagement_id,staff_id,command_key)
);
CREATE TABLE IF NOT EXISTS product_changes(
 id INTEGER PRIMARY KEY AUTOINCREMENT,engagement_id TEXT NOT NULL,area TEXT NOT NULL,category TEXT NOT NULL,
 resource_id TEXT NOT NULL,action TEXT NOT NULL,actor_id TEXT NOT NULL,created_at TEXT NOT NULL,
 source_table TEXT NOT NULL,source_id INTEGER NOT NULL,UNIQUE(source_table,source_id)
);
CREATE INDEX IF NOT EXISTS product_change_scope ON product_changes(engagement_id,id,area);
CREATE TABLE IF NOT EXISTS product_checkpoints(
 engagement_id TEXT NOT NULL,staff_id TEXT NOT NULL,scope_hash TEXT NOT NULL,cursor INTEGER NOT NULL,
 revision INTEGER NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(engagement_id,staff_id)
);
CREATE TRIGGER IF NOT EXISTS product_file_no_update BEFORE UPDATE ON product_files BEGIN SELECT RAISE(ABORT,'Original evidence is immutable'); END;
CREATE TRIGGER IF NOT EXISTS product_file_no_delete BEFORE DELETE ON product_files BEGIN SELECT RAISE(ABORT,'Original evidence cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS product_command_no_update BEFORE UPDATE ON product_commands BEGIN SELECT RAISE(ABORT,'Idempotency records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS product_command_no_delete BEFORE DELETE ON product_commands BEGIN SELECT RAISE(ABORT,'Idempotency history cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS product_change_no_update BEFORE UPDATE ON product_changes BEGIN SELECT RAISE(ABORT,'Changes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS product_change_no_delete BEFORE DELETE ON product_changes BEGIN SELECT RAISE(ABORT,'Changes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS product_workflow_change AFTER INSERT ON workflow_events WHEN NEW.kind NOT IN ('notification','p_checkpoint','p_bulk') BEGIN
 INSERT OR IGNORE INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id)
 VALUES(COALESCE(json_extract(NEW.payload_json,'$.after.engagement_id'),json_extract(NEW.payload_json,'$.before.engagement_id'),(SELECT engagement_id FROM workflow_entities WHERE id=NEW.entity_id),(SELECT engagement_id FROM workflow_signoffs WHERE id=NEW.entity_id),'CL-20417'),
 COALESCE(json_extract(NEW.payload_json,'$.after.area'),json_extract(NEW.payload_json,'$.before.area'),json_extract(NEW.payload_json,'$.area'),'engagement'),NEW.kind,NEW.entity_id,NEW.action,NEW.actor_id,NEW.created_at,'workflow_events',NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS product_review_change AFTER INSERT ON review_events BEGIN
 INSERT INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id)
 VALUES('CL-20417','finding','review',NEW.finding_id,NEW.new_status,NEW.actor_name,NEW.created_at,'review_events',NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS product_adjustment_change AFTER INSERT ON adjustment_events BEGIN
 INSERT INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id)
 VALUES('CL-20417','adjustment','adjustment',NEW.adjustment_id,NEW.action,NEW.actor_id,NEW.created_at,'adjustment_events',NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS product_verification_change AFTER INSERT ON field_verification_events BEGIN
 INSERT INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id)
 VALUES('CL-20417','document','verification',NEW.evidence_id,NEW.status,NEW.verifier_id,NEW.created_at,'field_verification_events',NEW.id);
END;
INSERT OR IGNORE INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id)
 SELECT COALESCE(json_extract(payload_json,'$.after.engagement_id'),json_extract(payload_json,'$.before.engagement_id'),(SELECT engagement_id FROM workflow_entities WHERE id=entity_id),(SELECT engagement_id FROM workflow_signoffs WHERE id=entity_id),'CL-20417'),COALESCE(json_extract(payload_json,'$.after.area'),json_extract(payload_json,'$.before.area'),json_extract(payload_json,'$.area'),'engagement'),kind,entity_id,action,actor_id,created_at,'workflow_events',id
 FROM workflow_events WHERE kind NOT IN ('notification','p_checkpoint','p_bulk') AND NOT EXISTS(SELECT 1 FROM product_schema_migrations WHERE version=6);
INSERT OR IGNORE INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id)
 SELECT 'CL-20417','adjustment','adjustment',adjustment_id,action,actor_id,created_at,'adjustment_events',id FROM adjustment_events WHERE NOT EXISTS(SELECT 1 FROM product_schema_migrations WHERE version=6);
INSERT OR IGNORE INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id)
 SELECT 'CL-20417','document','verification',evidence_id,status,verifier_id,created_at,'field_verification_events',id FROM field_verification_events WHERE NOT EXISTS(SELECT 1 FROM product_schema_migrations WHERE version=6);
INSERT OR IGNORE INTO product_schema_migrations VALUES(6,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
COMMIT;
