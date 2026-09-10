-- Settings are a single versioned DB value, never a JSON file fallback.
CREATE TABLE settings_sets (
 id TEXT PRIMARY KEY,
 scope_kind TEXT NOT NULL CHECK(scope_kind IN ('installation','project')),
 project_id TEXT REFERENCES projects(id) ON DELETE RESTRICT,
 current_revision INTEGER,
 state_version INTEGER NOT NULL DEFAULT 1,
 CHECK((scope_kind='installation' AND project_id IS NULL) OR (scope_kind='project' AND project_id IS NOT NULL)),
 FOREIGN KEY(id,current_revision) REFERENCES settings_versions(set_id,revision) ON DELETE RESTRICT
) STRICT;
CREATE UNIQUE INDEX one_installation_settings ON settings_sets(scope_kind) WHERE scope_kind='installation';
CREATE UNIQUE INDEX one_project_settings ON settings_sets(project_id) WHERE scope_kind='project';
CREATE TABLE settings_versions (
 set_id TEXT NOT NULL REFERENCES settings_sets(id) ON DELETE RESTRICT,
 revision INTEGER NOT NULL CHECK(revision>0),
 validated_body_json TEXT NOT NULL CHECK(json_valid(validated_body_json)),
 content_digest TEXT NOT NULL CHECK(length(content_digest)=64),
 provenance_digest TEXT NOT NULL CHECK(length(provenance_digest)=64),
 created_at TEXT NOT NULL,
 PRIMARY KEY(set_id,revision)
) STRICT;
CREATE TRIGGER settings_immutable_update BEFORE UPDATE ON settings_versions BEGIN SELECT RAISE(ABORT,'immutable settings'); END;
CREATE TRIGGER settings_immutable_delete BEFORE DELETE ON settings_versions BEGIN SELECT RAISE(ABORT,'immutable settings'); END;
CREATE TRIGGER settings_head_cas BEFORE UPDATE ON settings_sets WHEN NEW.id<>OLD.id OR NEW.scope_kind<>OLD.scope_kind OR NEW.project_id IS NOT OLD.project_id OR NEW.state_version<>OLD.state_version+1 OR NEW.current_revision<=COALESCE(OLD.current_revision,0) BEGIN SELECT RAISE(ABORT,'settings CAS required'); END;
CREATE TABLE command_receipts (
 project_id TEXT NOT NULL,
 principal_digest TEXT NOT NULL,
 command_key TEXT NOT NULL,
 command_digest TEXT NOT NULL CHECK(length(command_digest)=64),
 response_json TEXT NOT NULL CHECK(json_valid(response_json)),
 event_id TEXT NOT NULL,
 PRIMARY KEY(project_id,principal_digest,command_key),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id) ON DELETE RESTRICT
) STRICT;
CREATE TRIGGER receipt_immutable_update BEFORE UPDATE ON command_receipts BEGIN SELECT RAISE(ABORT,'immutable receipt'); END;
CREATE TRIGGER receipt_immutable_delete BEFORE DELETE ON command_receipts BEGIN SELECT RAISE(ABORT,'immutable receipt'); END;
CREATE TABLE request_goals (
 project_id TEXT NOT NULL,
 request_id TEXT NOT NULL,
 goal_id TEXT NOT NULL,
 PRIMARY KEY(project_id,request_id,goal_id),
 FOREIGN KEY(project_id,request_id) REFERENCES requests(project_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(project_id,goal_id) REFERENCES goals(project_id,id) ON DELETE RESTRICT
) STRICT;
CREATE TRIGGER request_goal_update BEFORE UPDATE ON request_goals BEGIN SELECT RAISE(ABORT,'immutable request goal'); END;
CREATE TRIGGER request_goal_delete BEFORE DELETE ON request_goals BEGIN SELECT RAISE(ABORT,'immutable request goal'); END;
