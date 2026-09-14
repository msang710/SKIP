CREATE TABLE goals_next (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','completed','archived')),
  state_version INTEGER NOT NULL DEFAULT 1 CHECK(state_version>0),
  last_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  FOREIGN KEY (project_id,origin_request_id) REFERENCES requests (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,last_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,id,current_revision) REFERENCES goal_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;
INSERT INTO goals_next SELECT * FROM goals;
DROP TABLE goals;
ALTER TABLE goals_next RENAME TO goals;
CREATE TRIGGER goals_head_insert BEFORE INSERT ON goals WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM goal_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TRIGGER goals_head_update BEFORE UPDATE ON goals WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM goal_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TRIGGER goal_stable_identity BEFORE UPDATE ON goals WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;
CREATE TRIGGER goal_head_cas BEFORE UPDATE ON goals WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;
CREATE TRIGGER goal_head_monotonic BEFORE UPDATE ON goals WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;
