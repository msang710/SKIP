-- SKIP Core generation 1. Immutable once released.
PRAGMA foreign_keys=ON;
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('active','archived')),
  created_at TEXT NOT NULL
) STRICT;

CREATE TABLE sources (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('git','directory','runtime')),
  logical_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,name),
  FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE interactions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  origin_context_digest TEXT NOT NULL CHECK(length(origin_context_digest)=64),
  external_event_key TEXT NOT NULL,
  actor_kind TEXT NOT NULL CHECK(actor_kind IN ('human','agent','system')),
  body TEXT NOT NULL,
  body_digest TEXT NOT NULL CHECK(length(body_digest)=64),
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,origin_context_digest,external_event_key),
  FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE verified_interactions (
  project_id TEXT NOT NULL,
  interaction_id TEXT NOT NULL,
  method TEXT NOT NULL CHECK(method IN ('native_user_action','host_user_turn','interactive_tty')),
  verifier TEXT NOT NULL,
  proof_digest TEXT NOT NULL CHECK(length(proof_digest)=64),
  verified_at TEXT NOT NULL,
  PRIMARY KEY(project_id,interaction_id),
  FOREIGN KEY (project_id,interaction_id) REFERENCES interactions (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER verified_actor BEFORE INSERT ON verified_interactions WHEN (SELECT actor_kind FROM interactions WHERE project_id=NEW.project_id AND id=NEW.interaction_id) <> 'human' BEGIN SELECT RAISE(ABORT,'human interaction required'); END;

CREATE TABLE requests (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  interaction_id TEXT NOT NULL,
  operation TEXT NOT NULL CHECK(operation IN ('investigate','plan','implement','deploy')),
  intent TEXT NOT NULL,
  intent_digest TEXT NOT NULL CHECK(length(intent_digest)=64),
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,interaction_id),
  FOREIGN KEY (project_id,interaction_id) REFERENCES verified_interactions (project_id,interaction_id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE events (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  sequence INTEGER NOT NULL CHECK(sequence>0),
  interaction_id TEXT NOT NULL,
  command_key TEXT NOT NULL,
  command_digest TEXT NOT NULL CHECK(length(command_digest)=64),
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,sequence),
  UNIQUE(project_id,command_key),
  FOREIGN KEY (project_id,interaction_id) REFERENCES interactions (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE goals (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','archived')),
  state_version INTEGER NOT NULL DEFAULT 1 CHECK(state_version>0),
  last_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  FOREIGN KEY (project_id,origin_request_id) REFERENCES requests (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,last_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,id,current_revision) REFERENCES goal_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TABLE goal_versions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision>0),
  title TEXT NOT NULL,
  intent TEXT NOT NULL,
  success_definition TEXT NOT NULL,
  content_digest TEXT CHECK(content_digest IS NULL OR length(content_digest)=64),
  sealed_at TEXT,
  created_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,id,revision),
  FOREIGN KEY (project_id,id) REFERENCES goals (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,created_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  CHECK (sealed_at IS NULL OR content_digest IS NOT NULL)
) STRICT;

CREATE TRIGGER goal_versions_new_unsealed BEFORE INSERT ON goal_versions WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER goal_versions_immutable_update BEFORE UPDATE ON goal_versions WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed version'); END;

CREATE TRIGGER goal_versions_immutable_delete BEFORE DELETE ON goal_versions BEGIN SELECT RAISE(ABORT,'version deletion disabled'); END;

CREATE TRIGGER goals_head_insert BEFORE INSERT ON goals WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM goal_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TRIGGER goals_head_update BEFORE UPDATE ON goals WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM goal_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TABLE decisions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','archived')),
  state_version INTEGER NOT NULL DEFAULT 1 CHECK(state_version>0),
  last_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,id,goal_id),
  FOREIGN KEY (project_id,origin_request_id) REFERENCES requests (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,last_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,id,current_revision) REFERENCES decision_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,goal_id) REFERENCES goals (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE decision_versions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision>0),
  question TEXT NOT NULL,
  rationale TEXT NOT NULL,
  risk_summary TEXT NOT NULL,
  content_digest TEXT CHECK(content_digest IS NULL OR length(content_digest)=64),
  sealed_at TEXT,
  created_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,id,revision),
  FOREIGN KEY (project_id,id) REFERENCES decisions (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,created_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  CHECK (sealed_at IS NULL OR content_digest IS NOT NULL)
) STRICT;

CREATE TRIGGER decision_versions_new_unsealed BEFORE INSERT ON decision_versions WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER decision_versions_immutable_update BEFORE UPDATE ON decision_versions WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed version'); END;

CREATE TRIGGER decision_versions_immutable_delete BEFORE DELETE ON decision_versions BEGIN SELECT RAISE(ABORT,'version deletion disabled'); END;

CREATE TRIGGER decisions_head_insert BEFORE INSERT ON decisions WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TRIGGER decisions_head_update BEFORE UPDATE ON decisions WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TABLE requirements (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','archived')),
  state_version INTEGER NOT NULL DEFAULT 1 CHECK(state_version>0),
  last_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,id,goal_id),
  FOREIGN KEY (project_id,origin_request_id) REFERENCES requests (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,last_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,id,current_revision) REFERENCES requirement_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,goal_id) REFERENCES goals (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE requirement_versions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision>0),
  title TEXT NOT NULL,
  statement TEXT NOT NULL,
  rationale TEXT NOT NULL,
  content_digest TEXT CHECK(content_digest IS NULL OR length(content_digest)=64),
  sealed_at TEXT,
  created_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,id,revision),
  FOREIGN KEY (project_id,id) REFERENCES requirements (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,created_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  CHECK (sealed_at IS NULL OR content_digest IS NOT NULL)
) STRICT;

CREATE TRIGGER requirement_versions_new_unsealed BEFORE INSERT ON requirement_versions WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER requirement_versions_immutable_update BEFORE UPDATE ON requirement_versions WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed version'); END;

CREATE TRIGGER requirement_versions_immutable_delete BEFORE DELETE ON requirement_versions BEGIN SELECT RAISE(ABORT,'version deletion disabled'); END;

CREATE TRIGGER requirements_head_insert BEFORE INSERT ON requirements WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TRIGGER requirements_head_update BEFORE UPDATE ON requirements WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TABLE plans (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','archived')),
  state_version INTEGER NOT NULL DEFAULT 1 CHECK(state_version>0),
  last_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,id,goal_id),
  FOREIGN KEY (project_id,origin_request_id) REFERENCES requests (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,last_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,id,current_revision) REFERENCES plan_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,goal_id) REFERENCES goals (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE plan_versions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision>0),
  title TEXT NOT NULL,
  design_body TEXT NOT NULL,
  scope_description TEXT NOT NULL,
  alternatives_body TEXT NOT NULL,
  rollback_body TEXT NOT NULL,
  content_digest TEXT CHECK(content_digest IS NULL OR length(content_digest)=64),
  sealed_at TEXT,
  created_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,id,revision),
  FOREIGN KEY (project_id,id) REFERENCES plans (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,created_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  CHECK (sealed_at IS NULL OR content_digest IS NOT NULL)
) STRICT;

CREATE TRIGGER plan_versions_new_unsealed BEFORE INSERT ON plan_versions WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER plan_versions_immutable_update BEFORE UPDATE ON plan_versions WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed version'); END;

CREATE TRIGGER plan_versions_immutable_delete BEFORE DELETE ON plan_versions BEGIN SELECT RAISE(ABORT,'version deletion disabled'); END;

CREATE TRIGGER plans_head_insert BEFORE INSERT ON plans WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TRIGGER plans_head_update BEFORE UPDATE ON plans WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TABLE work_items (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','archived')),
  state_version INTEGER NOT NULL DEFAULT 1 CHECK(state_version>0),
  last_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,id,goal_id),
  FOREIGN KEY (project_id,origin_request_id) REFERENCES requests (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,last_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,id,current_revision) REFERENCES work_item_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,goal_id) REFERENCES goals (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE work_item_versions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision>0),
  operation TEXT NOT NULL CHECK(operation IN ('investigate','requirements','design','tasks','implement','validate','deploy')),
  title TEXT NOT NULL,
  instruction_body TEXT NOT NULL,
  completion_definition TEXT NOT NULL,
  workflow_depth TEXT NOT NULL CHECK(workflow_depth IN ('compact','full')),
  request_id TEXT NOT NULL,
  content_digest TEXT CHECK(content_digest IS NULL OR length(content_digest)=64),
  sealed_at TEXT,
  created_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,id,revision),
  FOREIGN KEY (project_id,id) REFERENCES work_items (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,created_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,request_id) REFERENCES requests (project_id,id) ON DELETE RESTRICT,
  CHECK (sealed_at IS NULL OR content_digest IS NOT NULL)
) STRICT;

CREATE TRIGGER work_item_versions_new_unsealed BEFORE INSERT ON work_item_versions WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER work_item_versions_immutable_update BEFORE UPDATE ON work_item_versions WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed version'); END;

CREATE TRIGGER work_item_versions_immutable_delete BEFORE DELETE ON work_item_versions BEGIN SELECT RAISE(ABORT,'version deletion disabled'); END;

CREATE TRIGGER work_items_head_insert BEFORE INSERT ON work_items WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TRIGGER work_items_head_update BEFORE UPDATE ON work_items WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;

CREATE TABLE decision_options (
  project_id TEXT NOT NULL,
  decision_id TEXT NOT NULL,
  decision_revision INTEGER NOT NULL,
  option_id TEXT NOT NULL,
  label TEXT NOT NULL,
  description TEXT NOT NULL,
  consequences TEXT NOT NULL,
  recommended INTEGER NOT NULL CHECK(recommended IN (0,1)),
  position INTEGER NOT NULL CHECK(position>=0),
  PRIMARY KEY(project_id,decision_id,decision_revision,option_id),
  UNIQUE(project_id,decision_id,decision_revision,position),
  FOREIGN KEY (project_id,decision_id,decision_revision) REFERENCES decision_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE UNIQUE INDEX one_recommendation ON decision_options(project_id,decision_id,decision_revision) WHERE recommended=1;

CREATE TRIGGER decision_options_sealed_insert BEFORE INSERT ON decision_options WHEN EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER decision_options_sealed_update BEFORE UPDATE ON decision_options WHEN EXISTS(SELECT 1 FROM decision_versions WHERE project_id=OLD.project_id AND id=OLD.decision_id AND revision=OLD.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER decision_options_sealed_delete BEFORE DELETE ON decision_options WHEN EXISTS(SELECT 1 FROM decision_versions WHERE project_id=OLD.project_id AND id=OLD.decision_id AND revision=OLD.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER decision_options_sealed_move BEFORE UPDATE ON decision_options WHEN EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE acceptance_criteria (
  project_id TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  requirement_revision INTEGER NOT NULL,
  criterion_id TEXT NOT NULL,
  description TEXT NOT NULL,
  given_text TEXT NOT NULL,
  when_text TEXT NOT NULL,
  then_text TEXT NOT NULL,
  required INTEGER NOT NULL CHECK(required IN (0,1)),
  PRIMARY KEY(project_id,requirement_id,requirement_revision,criterion_id),
  FOREIGN KEY (project_id,requirement_id,requirement_revision) REFERENCES requirement_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER acceptance_criteria_sealed_insert BEFORE INSERT ON acceptance_criteria WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER acceptance_criteria_sealed_update BEFORE UPDATE ON acceptance_criteria WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=OLD.project_id AND id=OLD.requirement_id AND revision=OLD.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER acceptance_criteria_sealed_delete BEFORE DELETE ON acceptance_criteria WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=OLD.project_id AND id=OLD.requirement_id AND revision=OLD.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER acceptance_criteria_sealed_move BEFORE UPDATE ON acceptance_criteria WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE plan_items (
  project_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  plan_revision INTEGER NOT NULL,
  item_id TEXT NOT NULL,
  title TEXT NOT NULL,
  design_body TEXT NOT NULL,
  verification_body TEXT NOT NULL,
  position INTEGER NOT NULL CHECK(position>=0),
  PRIMARY KEY(project_id,plan_id,plan_revision,item_id),
  UNIQUE(project_id,plan_id,plan_revision,position),
  FOREIGN KEY (project_id,plan_id,plan_revision) REFERENCES plan_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER plan_items_sealed_insert BEFORE INSERT ON plan_items WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_items_sealed_update BEFORE UPDATE ON plan_items WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_items_sealed_delete BEFORE DELETE ON plan_items WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_items_sealed_move BEFORE UPDATE ON plan_items WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE work_checks (
  project_id TEXT NOT NULL,
  work_item_id TEXT NOT NULL,
  work_revision INTEGER NOT NULL,
  check_id TEXT NOT NULL,
  description TEXT NOT NULL,
  surface TEXT NOT NULL,
  required INTEGER NOT NULL CHECK(required IN (0,1)),
  PRIMARY KEY(project_id,work_item_id,work_revision,check_id),
  FOREIGN KEY (project_id,work_item_id,work_revision) REFERENCES work_item_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER work_checks_sealed_insert BEFORE INSERT ON work_checks WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_checks_sealed_update BEFORE UPDATE ON work_checks WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=OLD.project_id AND id=OLD.work_item_id AND revision=OLD.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_checks_sealed_delete BEFORE DELETE ON work_checks WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=OLD.project_id AND id=OLD.work_item_id AND revision=OLD.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_checks_sealed_move BEFORE UPDATE ON work_checks WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE requirement_decisions (
  project_id TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  requirement_revision INTEGER NOT NULL,
  decision_id TEXT NOT NULL,
  decision_revision INTEGER NOT NULL,
  rationale TEXT NOT NULL,
  PRIMARY KEY(project_id,requirement_id,requirement_revision,decision_id,decision_revision),
  FOREIGN KEY (project_id,requirement_id,requirement_revision) REFERENCES requirement_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,decision_id,decision_revision) REFERENCES decision_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER requirement_decisions_sealed_insert BEFORE INSERT ON requirement_decisions WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER requirement_decisions_sealed_update BEFORE UPDATE ON requirement_decisions WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=OLD.project_id AND id=OLD.requirement_id AND revision=OLD.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER requirement_decisions_sealed_delete BEFORE DELETE ON requirement_decisions WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=OLD.project_id AND id=OLD.requirement_id AND revision=OLD.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER requirement_decisions_sealed_move BEFORE UPDATE ON requirement_decisions WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER requirement_decisions_same_goal BEFORE INSERT ON requirement_decisions WHEN (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) <> (SELECT goal_id FROM decisions WHERE project_id=NEW.project_id AND id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;

CREATE TABLE plan_requirements (
  project_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  plan_revision INTEGER NOT NULL,
  requirement_id TEXT NOT NULL,
  requirement_revision INTEGER NOT NULL,
  rationale TEXT NOT NULL,
  PRIMARY KEY(project_id,plan_id,plan_revision,requirement_id,requirement_revision),
  FOREIGN KEY (project_id,plan_id,plan_revision) REFERENCES plan_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,requirement_id,requirement_revision) REFERENCES requirement_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER plan_requirements_sealed_insert BEFORE INSERT ON plan_requirements WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_requirements_sealed_update BEFORE UPDATE ON plan_requirements WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_requirements_sealed_delete BEFORE DELETE ON plan_requirements WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_requirements_sealed_move BEFORE UPDATE ON plan_requirements WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_requirements_same_goal BEFORE INSERT ON plan_requirements WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id) <> (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;

CREATE TABLE plan_decisions (
  project_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  plan_revision INTEGER NOT NULL,
  decision_id TEXT NOT NULL,
  decision_revision INTEGER NOT NULL,
  rationale TEXT NOT NULL,
  PRIMARY KEY(project_id,plan_id,plan_revision,decision_id,decision_revision),
  FOREIGN KEY (project_id,plan_id,plan_revision) REFERENCES plan_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,decision_id,decision_revision) REFERENCES decision_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER plan_decisions_sealed_insert BEFORE INSERT ON plan_decisions WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_decisions_sealed_update BEFORE UPDATE ON plan_decisions WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_decisions_sealed_delete BEFORE DELETE ON plan_decisions WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_decisions_sealed_move BEFORE UPDATE ON plan_decisions WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_decisions_same_goal BEFORE INSERT ON plan_decisions WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id) <> (SELECT goal_id FROM decisions WHERE project_id=NEW.project_id AND id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;

CREATE TABLE work_item_requirements (
  project_id TEXT NOT NULL,
  work_item_id TEXT NOT NULL,
  work_item_revision INTEGER NOT NULL,
  requirement_id TEXT NOT NULL,
  requirement_revision INTEGER NOT NULL,
  rationale TEXT NOT NULL,
  PRIMARY KEY(project_id,work_item_id,work_item_revision,requirement_id,requirement_revision),
  FOREIGN KEY (project_id,work_item_id,work_item_revision) REFERENCES work_item_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,requirement_id,requirement_revision) REFERENCES requirement_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER work_item_requirements_sealed_insert BEFORE INSERT ON work_item_requirements WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_item_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_item_requirements_sealed_update BEFORE UPDATE ON work_item_requirements WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=OLD.project_id AND id=OLD.work_item_id AND revision=OLD.work_item_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_item_requirements_sealed_delete BEFORE DELETE ON work_item_requirements WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=OLD.project_id AND id=OLD.work_item_id AND revision=OLD.work_item_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_item_requirements_sealed_move BEFORE UPDATE ON work_item_requirements WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_item_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_item_requirements_same_goal BEFORE INSERT ON work_item_requirements WHEN (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id) <> (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;

CREATE TABLE work_item_plan_items (
  project_id TEXT NOT NULL,
  work_item_id TEXT NOT NULL,
  work_revision INTEGER NOT NULL,
  plan_id TEXT NOT NULL,
  plan_revision INTEGER NOT NULL,
  plan_item_id TEXT NOT NULL,
  rationale TEXT NOT NULL,
  PRIMARY KEY(project_id,work_item_id,work_revision,plan_id,plan_revision,plan_item_id),
  FOREIGN KEY (project_id,work_item_id,work_revision) REFERENCES work_item_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,plan_id,plan_revision,plan_item_id) REFERENCES plan_items (project_id,plan_id,plan_revision,item_id) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER work_item_plan_items_sealed_insert BEFORE INSERT ON work_item_plan_items WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_item_plan_items_sealed_update BEFORE UPDATE ON work_item_plan_items WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=OLD.project_id AND id=OLD.work_item_id AND revision=OLD.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_item_plan_items_sealed_delete BEFORE DELETE ON work_item_plan_items WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=OLD.project_id AND id=OLD.work_item_id AND revision=OLD.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_item_plan_items_sealed_move BEFORE UPDATE ON work_item_plan_items WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE work_dependencies (
  project_id TEXT NOT NULL,
  work_item_id TEXT NOT NULL,
  work_revision INTEGER NOT NULL,
  depends_on_id TEXT NOT NULL,
  depends_on_revision INTEGER NOT NULL,
  reason TEXT NOT NULL,
  PRIMARY KEY(project_id,work_item_id,work_revision,depends_on_id,depends_on_revision),
  FOREIGN KEY (project_id,work_item_id,work_revision) REFERENCES work_item_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,depends_on_id,depends_on_revision) REFERENCES work_item_versions (project_id,id,revision) ON DELETE RESTRICT,
  CHECK (work_item_id <> depends_on_id)
) STRICT;

CREATE TRIGGER work_dependencies_sealed_insert BEFORE INSERT ON work_dependencies WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_dependencies_sealed_update BEFORE UPDATE ON work_dependencies WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=OLD.project_id AND id=OLD.work_item_id AND revision=OLD.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_dependencies_sealed_delete BEFORE DELETE ON work_dependencies WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=OLD.project_id AND id=OLD.work_item_id AND revision=OLD.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_dependencies_sealed_move BEFORE UPDATE ON work_dependencies WHEN EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE selections (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  decision_id TEXT NOT NULL,
  decision_revision INTEGER NOT NULL,
  option_id TEXT NOT NULL,
  interaction_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  supersedes_id TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,interaction_id,decision_id),
  UNIQUE(project_id,supersedes_id),
  FOREIGN KEY (project_id,decision_id,decision_revision,option_id) REFERENCES decision_options (project_id,decision_id,decision_revision,option_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,interaction_id) REFERENCES verified_interactions (project_id,interaction_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,supersedes_id) REFERENCES selections (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE requirement_selections (
  project_id TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  requirement_revision INTEGER NOT NULL,
  selection_id TEXT NOT NULL,
  rationale TEXT NOT NULL,
  PRIMARY KEY(project_id,requirement_id,requirement_revision,selection_id),
  FOREIGN KEY (project_id,requirement_id,requirement_revision) REFERENCES requirement_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,selection_id) REFERENCES selections (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER requirement_selections_sealed_insert BEFORE INSERT ON requirement_selections WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER requirement_selections_sealed_update BEFORE UPDATE ON requirement_selections WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=OLD.project_id AND id=OLD.requirement_id AND revision=OLD.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER requirement_selections_sealed_delete BEFORE DELETE ON requirement_selections WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=OLD.project_id AND id=OLD.requirement_id AND revision=OLD.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER requirement_selections_sealed_move BEFORE UPDATE ON requirement_selections WHEN EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE plan_selections (
  project_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  plan_revision INTEGER NOT NULL,
  selection_id TEXT NOT NULL,
  rationale TEXT NOT NULL,
  PRIMARY KEY(project_id,plan_id,plan_revision,selection_id),
  FOREIGN KEY (project_id,plan_id,plan_revision) REFERENCES plan_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,selection_id) REFERENCES selections (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER plan_selections_sealed_insert BEFORE INSERT ON plan_selections WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_selections_sealed_update BEFORE UPDATE ON plan_selections WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_selections_sealed_delete BEFORE DELETE ON plan_selections WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_selections_sealed_move BEFORE UPDATE ON plan_selections WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE selection_revocations (
  project_id TEXT NOT NULL,
  selection_id TEXT NOT NULL,
  interaction_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,selection_id),
  FOREIGN KEY (project_id,selection_id) REFERENCES selections (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,interaction_id) REFERENCES verified_interactions (project_id,interaction_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE scopes (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT,
  summary TEXT NOT NULL,
  digest TEXT NOT NULL CHECK(length(digest)=64),
  sealed_at TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,id,goal_id),
  FOREIGN KEY (project_id,goal_id) REFERENCES goals (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE scope_paths (
  project_id TEXT NOT NULL,
  scope_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  access TEXT NOT NULL CHECK(access IN ('read','modify','create','delete')),
  PRIMARY KEY(project_id,scope_id,source_id,relative_path),
  FOREIGN KEY (project_id,scope_id) REFERENCES scopes (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,source_id) REFERENCES sources (project_id,id) ON DELETE RESTRICT,
  CHECK (length(relative_path)>0)
) STRICT;

CREATE TABLE snapshots (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  scope_id TEXT NOT NULL,
  digest TEXT NOT NULL CHECK(length(digest)=64),
  sealed_at TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,id,scope_id),
  FOREIGN KEY (project_id,scope_id) REFERENCES scopes (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE snapshot_entries (
  project_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  file_state TEXT NOT NULL CHECK(file_state IN ('present','absent')),
  source_revision TEXT,
  content_digest TEXT CHECK(content_digest IS NULL OR length(content_digest)=64),
  PRIMARY KEY(project_id,snapshot_id,source_id,relative_path),
  FOREIGN KEY (project_id,snapshot_id) REFERENCES snapshots (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,source_id) REFERENCES sources (project_id,id) ON DELETE RESTRICT,
  CHECK ((file_state='present' AND content_digest IS NOT NULL) OR (file_state='absent' AND content_digest IS NULL))
) STRICT;

CREATE TABLE risk_assessments (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  goal_revision INTEGER NOT NULL,
  scope_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('goal','change')),
  policy_version TEXT NOT NULL,
  level TEXT NOT NULL CHECK(level IN ('low','medium','high','unknown')),
  rationale TEXT NOT NULL,
  assessor_interaction_id TEXT NOT NULL,
  digest TEXT NOT NULL CHECK(length(digest)=64),
  sealed_at TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,id,kind),
  UNIQUE(project_id,id,scope_id,snapshot_id),
  FOREIGN KEY (project_id,goal_id,goal_revision) REFERENCES goal_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,scope_id,goal_id) REFERENCES scopes (project_id,id,goal_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,snapshot_id,scope_id) REFERENCES snapshots (project_id,id,scope_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,assessor_interaction_id) REFERENCES interactions (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE risk_factors (
  project_id TEXT NOT NULL,
  assessment_id TEXT NOT NULL,
  dimension TEXT NOT NULL,
  impact TEXT NOT NULL CHECK(impact IN ('none','material','unknown')),
  explanation TEXT NOT NULL,
  PRIMARY KEY(project_id,assessment_id,dimension),
  FOREIGN KEY (project_id,assessment_id) REFERENCES risk_assessments (project_id,id) ON DELETE RESTRICT,
  CHECK (dimension IN ('business_rules','inventory','money','permissions','sensitive_data','persisted_data','external_state','boot_recovery'))
) STRICT;

CREATE TABLE authorizations (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  request_id TEXT NOT NULL,
  interaction_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('investigate','requirements','design','tasks','implement','validate','deploy')),
  scope_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  goal_risk_id TEXT NOT NULL,
  change_risk_id TEXT NOT NULL,
  basis_digest TEXT NOT NULL CHECK(length(basis_digest)=64),
  expires_at TEXT,
  sealed_at TEXT,
  event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,id,request_id),
  FOREIGN KEY (project_id,request_id) REFERENCES requests (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,interaction_id) REFERENCES verified_interactions (project_id,interaction_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,snapshot_id,scope_id) REFERENCES snapshots (project_id,id,scope_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,goal_risk_id,scope_id,snapshot_id) REFERENCES risk_assessments (project_id,id,scope_id,snapshot_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,change_risk_id,scope_id,snapshot_id) REFERENCES risk_assessments (project_id,id,scope_id,snapshot_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE authorization_selections (
  project_id TEXT NOT NULL,
  authorization_id TEXT NOT NULL,
  selection_id TEXT NOT NULL,
  PRIMARY KEY(project_id,authorization_id,selection_id),
  FOREIGN KEY (project_id,authorization_id) REFERENCES authorizations (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,selection_id) REFERENCES selections (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE authorization_requirements (
  project_id TEXT NOT NULL,
  authorization_id TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  requirement_revision INTEGER NOT NULL,
  PRIMARY KEY(project_id,authorization_id,requirement_id,requirement_revision),
  FOREIGN KEY (project_id,authorization_id) REFERENCES authorizations (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,requirement_id,requirement_revision) REFERENCES requirement_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TABLE authorization_plans (
  project_id TEXT NOT NULL,
  authorization_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  plan_revision INTEGER NOT NULL,
  PRIMARY KEY(project_id,authorization_id,plan_id,plan_revision),
  FOREIGN KEY (project_id,authorization_id) REFERENCES authorizations (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,plan_id,plan_revision) REFERENCES plan_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TABLE authorization_work_items (
  project_id TEXT NOT NULL,
  authorization_id TEXT NOT NULL,
  work_item_id TEXT NOT NULL,
  work_revision INTEGER NOT NULL,
  PRIMARY KEY(project_id,authorization_id,work_item_id,work_revision),
  FOREIGN KEY (project_id,authorization_id) REFERENCES authorizations (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,work_item_id,work_revision) REFERENCES work_item_versions (project_id,id,revision) ON DELETE RESTRICT
) STRICT;

CREATE TABLE authorization_revocations (
  project_id TEXT NOT NULL,
  authorization_id TEXT NOT NULL,
  interaction_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,authorization_id),
  FOREIGN KEY (project_id,authorization_id) REFERENCES authorizations (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,interaction_id) REFERENCES verified_interactions (project_id,interaction_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE executions (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  request_id TEXT NOT NULL,
  authorization_id TEXT NOT NULL,
  work_item_id TEXT NOT NULL,
  work_revision INTEGER NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('prepared','accepted','running','finished','failed','cancel_requested','cancelled','cancellation_unknown')),
  attempt_no INTEGER NOT NULL CHECK(attempt_no>0),
  state_version INTEGER NOT NULL CHECK(state_version>0),
  last_event_id TEXT NOT NULL,
  dispatch_context_digest TEXT NOT NULL CHECK(length(dispatch_context_digest)=64),
  result_receipt_digest TEXT CHECK(result_receipt_digest IS NULL OR length(result_receipt_digest)=64),
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,work_item_id,work_revision,attempt_no),
  FOREIGN KEY (project_id,authorization_id,request_id) REFERENCES authorizations (project_id,id,request_id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,authorization_id,work_item_id,work_revision) REFERENCES authorization_work_items (project_id,authorization_id,work_item_id,work_revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,last_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE deliveries (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  execution_id TEXT NOT NULL,
  message_key TEXT NOT NULL,
  payload TEXT NOT NULL,
  payload_digest TEXT NOT NULL CHECK(length(payload_digest)=64),
  state TEXT NOT NULL CHECK(state IN ('pending','dispatching','accepted','delivery_unknown','failed','cancelled')),
  state_version INTEGER NOT NULL CHECK(state_version>0),
  lease_owner TEXT,
  lease_until TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
  last_error TEXT,
  last_event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,execution_id),
  UNIQUE(project_id,message_key),
  FOREIGN KEY (project_id,execution_id) REFERENCES executions (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,last_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  CHECK ((lease_owner IS NULL)=(lease_until IS NULL))
) STRICT;

CREATE TABLE delivery_attempts (
  project_id TEXT NOT NULL,
  delivery_id TEXT NOT NULL,
  attempt_no INTEGER NOT NULL CHECK(attempt_no>0),
  started_event_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  outcome TEXT CHECK(outcome IN ('accepted','rejected','unknown')),
  host_message_key TEXT,
  error_text TEXT,
  PRIMARY KEY(project_id,delivery_id,attempt_no),
  FOREIGN KEY (project_id,delivery_id) REFERENCES deliveries (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,started_event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  CHECK ((finished_at IS NULL)=(outcome IS NULL))
) STRICT;

CREATE TABLE evidence (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  execution_id TEXT,
  reporter_interaction_id TEXT NOT NULL,
  surface TEXT NOT NULL CHECK(surface IN ('source','unit','integration','typecheck','build','package','install','runtime','ui','device','production')),
  result TEXT NOT NULL CHECK(result IN ('PASS','FAIL','NOT_RUN','INCONCLUSIVE')),
  provenance TEXT NOT NULL CHECK(provenance IN ('agent_report','host_observation','user_observation')),
  summary TEXT NOT NULL,
  method TEXT NOT NULL,
  observed_at TEXT,
  event_id TEXT NOT NULL,
  sealed_at TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  FOREIGN KEY (project_id,snapshot_id) REFERENCES snapshots (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,execution_id) REFERENCES executions (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,reporter_interaction_id) REFERENCES interactions (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT,
  CHECK (result='NOT_RUN' OR observed_at IS NOT NULL)
) STRICT;

CREATE TABLE evidence_payloads (
  project_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  part_id TEXT NOT NULL,
  media_type TEXT NOT NULL,
  content BLOB NOT NULL,
  content_digest TEXT NOT NULL CHECK(length(content_digest)=64),
  byte_length INTEGER NOT NULL CHECK(byte_length>=0),
  PRIMARY KEY(project_id,evidence_id,part_id),
  FOREIGN KEY (project_id,evidence_id) REFERENCES evidence (project_id,id) ON DELETE RESTRICT,
  CHECK (length(content)=byte_length)
) STRICT;

CREATE TABLE decision_evidence (
  project_id TEXT NOT NULL,
  decision_id TEXT NOT NULL,
  decision_revision INTEGER NOT NULL,
  evidence_id TEXT NOT NULL,
  explanation TEXT NOT NULL,
  PRIMARY KEY(project_id,decision_id,decision_revision,evidence_id),
  FOREIGN KEY (project_id,decision_id,decision_revision) REFERENCES decision_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,evidence_id) REFERENCES evidence (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER decision_evidence_sealed_insert BEFORE INSERT ON decision_evidence WHEN EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER decision_evidence_sealed_update BEFORE UPDATE ON decision_evidence WHEN EXISTS(SELECT 1 FROM decision_versions WHERE project_id=OLD.project_id AND id=OLD.decision_id AND revision=OLD.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER decision_evidence_sealed_delete BEFORE DELETE ON decision_evidence WHEN EXISTS(SELECT 1 FROM decision_versions WHERE project_id=OLD.project_id AND id=OLD.decision_id AND revision=OLD.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER decision_evidence_sealed_move BEFORE UPDATE ON decision_evidence WHEN EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE plan_evidence (
  project_id TEXT NOT NULL,
  plan_id TEXT NOT NULL,
  plan_revision INTEGER NOT NULL,
  evidence_id TEXT NOT NULL,
  explanation TEXT NOT NULL,
  PRIMARY KEY(project_id,plan_id,plan_revision,evidence_id),
  FOREIGN KEY (project_id,plan_id,plan_revision) REFERENCES plan_versions (project_id,id,revision) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,evidence_id) REFERENCES evidence (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TRIGGER plan_evidence_sealed_insert BEFORE INSERT ON plan_evidence WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_evidence_sealed_update BEFORE UPDATE ON plan_evidence WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_evidence_sealed_delete BEFORE DELETE ON plan_evidence WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=OLD.project_id AND id=OLD.plan_id AND revision=OLD.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER plan_evidence_sealed_move BEFORE UPDATE ON plan_evidence WHEN EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TABLE criterion_results (
  project_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  requirement_id TEXT NOT NULL,
  requirement_revision INTEGER NOT NULL,
  criterion_id TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('PASS','FAIL','NOT_RUN','INCONCLUSIVE')),
  explanation TEXT NOT NULL,
  PRIMARY KEY(project_id,evidence_id,requirement_id,requirement_revision,criterion_id),
  FOREIGN KEY (project_id,evidence_id) REFERENCES evidence (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,requirement_id,requirement_revision,criterion_id) REFERENCES acceptance_criteria (project_id,requirement_id,requirement_revision,criterion_id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE work_check_results (
  project_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  work_item_id TEXT NOT NULL,
  work_revision INTEGER NOT NULL,
  check_id TEXT NOT NULL,
  verdict TEXT NOT NULL CHECK(verdict IN ('PASS','FAIL','NOT_RUN','INCONCLUSIVE')),
  explanation TEXT NOT NULL,
  PRIMARY KEY(project_id,evidence_id,work_item_id,work_revision,check_id),
  FOREIGN KEY (project_id,evidence_id) REFERENCES evidence (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,work_item_id,work_revision,check_id) REFERENCES work_checks (project_id,work_item_id,work_revision,check_id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE risk_evidence (
  project_id TEXT NOT NULL,
  assessment_id TEXT NOT NULL,
  dimension TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  explanation TEXT NOT NULL,
  PRIMARY KEY(project_id,assessment_id,dimension,evidence_id),
  FOREIGN KEY (project_id,assessment_id,dimension) REFERENCES risk_factors (project_id,assessment_id,dimension) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,evidence_id) REFERENCES evidence (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE current_facts (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT,
  statement TEXT NOT NULL,
  source_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  supersedes_id TEXT,
  event_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id,id),
  UNIQUE(project_id,supersedes_id),
  FOREIGN KEY (project_id,goal_id) REFERENCES goals (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,source_id) REFERENCES sources (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,snapshot_id) REFERENCES snapshots (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,evidence_id) REFERENCES evidence (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,supersedes_id) REFERENCES current_facts (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE fact_retractions (
  project_id TEXT NOT NULL,
  fact_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(project_id,fact_id),
  FOREIGN KEY (project_id,fact_id) REFERENCES current_facts (project_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (project_id,event_id) REFERENCES events (project_id,id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY CHECK(version>0),
  checksum TEXT NOT NULL CHECK(length(checksum)=64),
  applied_at TEXT NOT NULL
) STRICT;

CREATE TRIGGER scopes_insert_unsealed BEFORE INSERT ON scopes WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER scopes_sealed_update BEFORE UPDATE ON scopes WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER scopes_no_delete BEFORE DELETE ON scopes BEGIN SELECT RAISE(ABORT,'aggregate deletion disabled'); END;

CREATE TRIGGER scope_paths_aggregate_insert BEFORE INSERT ON scope_paths WHEN EXISTS(SELECT 1 FROM scopes WHERE project_id=NEW.project_id AND id=NEW.scope_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER scope_paths_aggregate_update BEFORE UPDATE ON scope_paths WHEN EXISTS(SELECT 1 FROM scopes WHERE project_id=OLD.project_id AND id=OLD.scope_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER scope_paths_aggregate_delete BEFORE DELETE ON scope_paths WHEN EXISTS(SELECT 1 FROM scopes WHERE project_id=OLD.project_id AND id=OLD.scope_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER scope_paths_aggregate_move BEFORE UPDATE ON scope_paths WHEN EXISTS(SELECT 1 FROM scopes WHERE project_id=NEW.project_id AND id=NEW.scope_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER snapshots_insert_unsealed BEFORE INSERT ON snapshots WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER snapshots_sealed_update BEFORE UPDATE ON snapshots WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER snapshots_no_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'aggregate deletion disabled'); END;

CREATE TRIGGER snapshot_entries_aggregate_insert BEFORE INSERT ON snapshot_entries WHEN EXISTS(SELECT 1 FROM snapshots WHERE project_id=NEW.project_id AND id=NEW.snapshot_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER snapshot_entries_aggregate_update BEFORE UPDATE ON snapshot_entries WHEN EXISTS(SELECT 1 FROM snapshots WHERE project_id=OLD.project_id AND id=OLD.snapshot_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER snapshot_entries_aggregate_delete BEFORE DELETE ON snapshot_entries WHEN EXISTS(SELECT 1 FROM snapshots WHERE project_id=OLD.project_id AND id=OLD.snapshot_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER snapshot_entries_aggregate_move BEFORE UPDATE ON snapshot_entries WHEN EXISTS(SELECT 1 FROM snapshots WHERE project_id=NEW.project_id AND id=NEW.snapshot_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_assessments_insert_unsealed BEFORE INSERT ON risk_assessments WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER risk_assessments_sealed_update BEFORE UPDATE ON risk_assessments WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_assessments_no_delete BEFORE DELETE ON risk_assessments BEGIN SELECT RAISE(ABORT,'aggregate deletion disabled'); END;

CREATE TRIGGER risk_factors_aggregate_insert BEFORE INSERT ON risk_factors WHEN EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=NEW.project_id AND id=NEW.assessment_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_factors_aggregate_update BEFORE UPDATE ON risk_factors WHEN EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=OLD.project_id AND id=OLD.assessment_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_factors_aggregate_delete BEFORE DELETE ON risk_factors WHEN EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=OLD.project_id AND id=OLD.assessment_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_factors_aggregate_move BEFORE UPDATE ON risk_factors WHEN EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=NEW.project_id AND id=NEW.assessment_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_evidence_aggregate_insert BEFORE INSERT ON risk_evidence WHEN EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=NEW.project_id AND id=NEW.assessment_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_evidence_aggregate_update BEFORE UPDATE ON risk_evidence WHEN EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=OLD.project_id AND id=OLD.assessment_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_evidence_aggregate_delete BEFORE DELETE ON risk_evidence WHEN EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=OLD.project_id AND id=OLD.assessment_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER risk_evidence_aggregate_move BEFORE UPDATE ON risk_evidence WHEN EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=NEW.project_id AND id=NEW.assessment_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER evidence_insert_unsealed BEFORE INSERT ON evidence WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER evidence_sealed_update BEFORE UPDATE ON evidence WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT,'aggregate deletion disabled'); END;

CREATE TRIGGER evidence_payloads_aggregate_insert BEFORE INSERT ON evidence_payloads WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER evidence_payloads_aggregate_update BEFORE UPDATE ON evidence_payloads WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=OLD.project_id AND id=OLD.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER evidence_payloads_aggregate_delete BEFORE DELETE ON evidence_payloads WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=OLD.project_id AND id=OLD.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER evidence_payloads_aggregate_move BEFORE UPDATE ON evidence_payloads WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER criterion_results_aggregate_insert BEFORE INSERT ON criterion_results WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER criterion_results_aggregate_update BEFORE UPDATE ON criterion_results WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=OLD.project_id AND id=OLD.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER criterion_results_aggregate_delete BEFORE DELETE ON criterion_results WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=OLD.project_id AND id=OLD.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER criterion_results_aggregate_move BEFORE UPDATE ON criterion_results WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_check_results_aggregate_insert BEFORE INSERT ON work_check_results WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_check_results_aggregate_update BEFORE UPDATE ON work_check_results WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=OLD.project_id AND id=OLD.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_check_results_aggregate_delete BEFORE DELETE ON work_check_results WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=OLD.project_id AND id=OLD.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER work_check_results_aggregate_move BEFORE UPDATE ON work_check_results WHEN EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorizations_insert_unsealed BEFORE INSERT ON authorizations WHEN NEW.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'build before sealing'); END;

CREATE TRIGGER authorizations_sealed_update BEFORE UPDATE ON authorizations WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorizations_no_delete BEFORE DELETE ON authorizations BEGIN SELECT RAISE(ABORT,'aggregate deletion disabled'); END;

CREATE TRIGGER authorization_selections_aggregate_insert BEFORE INSERT ON authorization_selections WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=NEW.project_id AND id=NEW.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_selections_aggregate_update BEFORE UPDATE ON authorization_selections WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=OLD.project_id AND id=OLD.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_selections_aggregate_delete BEFORE DELETE ON authorization_selections WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=OLD.project_id AND id=OLD.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_selections_aggregate_move BEFORE UPDATE ON authorization_selections WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=NEW.project_id AND id=NEW.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_requirements_aggregate_insert BEFORE INSERT ON authorization_requirements WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=NEW.project_id AND id=NEW.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_requirements_aggregate_update BEFORE UPDATE ON authorization_requirements WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=OLD.project_id AND id=OLD.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_requirements_aggregate_delete BEFORE DELETE ON authorization_requirements WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=OLD.project_id AND id=OLD.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_requirements_aggregate_move BEFORE UPDATE ON authorization_requirements WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=NEW.project_id AND id=NEW.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_plans_aggregate_insert BEFORE INSERT ON authorization_plans WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=NEW.project_id AND id=NEW.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_plans_aggregate_update BEFORE UPDATE ON authorization_plans WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=OLD.project_id AND id=OLD.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_plans_aggregate_delete BEFORE DELETE ON authorization_plans WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=OLD.project_id AND id=OLD.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_plans_aggregate_move BEFORE UPDATE ON authorization_plans WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=NEW.project_id AND id=NEW.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_work_items_aggregate_insert BEFORE INSERT ON authorization_work_items WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=NEW.project_id AND id=NEW.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_work_items_aggregate_update BEFORE UPDATE ON authorization_work_items WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=OLD.project_id AND id=OLD.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_work_items_aggregate_delete BEFORE DELETE ON authorization_work_items WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=OLD.project_id AND id=OLD.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER authorization_work_items_aggregate_move BEFORE UPDATE ON authorization_work_items WHEN EXISTS(SELECT 1 FROM authorizations WHERE project_id=NEW.project_id AND id=NEW.authorization_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'sealed aggregate'); END;

CREATE TRIGGER sources_immutable_update BEFORE UPDATE ON sources BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER sources_immutable_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER interactions_immutable_update BEFORE UPDATE ON interactions BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER interactions_immutable_delete BEFORE DELETE ON interactions BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER verified_interactions_immutable_update BEFORE UPDATE ON verified_interactions BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER verified_interactions_immutable_delete BEFORE DELETE ON verified_interactions BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER requests_immutable_update BEFORE UPDATE ON requests BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER requests_immutable_delete BEFORE DELETE ON requests BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER events_immutable_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER events_immutable_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER selections_immutable_update BEFORE UPDATE ON selections BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER selections_immutable_delete BEFORE DELETE ON selections BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER selection_revocations_immutable_update BEFORE UPDATE ON selection_revocations BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER selection_revocations_immutable_delete BEFORE DELETE ON selection_revocations BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER authorization_revocations_immutable_update BEFORE UPDATE ON authorization_revocations BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER authorization_revocations_immutable_delete BEFORE DELETE ON authorization_revocations BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER current_facts_immutable_update BEFORE UPDATE ON current_facts BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER current_facts_immutable_delete BEFORE DELETE ON current_facts BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER fact_retractions_immutable_update BEFORE UPDATE ON fact_retractions BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER fact_retractions_immutable_delete BEFORE DELETE ON fact_retractions BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER schema_migrations_immutable_update BEFORE UPDATE ON schema_migrations BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE TRIGGER schema_migrations_immutable_delete BEFORE DELETE ON schema_migrations BEGIN SELECT RAISE(ABORT,'immutable record'); END;

CREATE INDEX fk_events_4 ON events(project_id,interaction_id);

CREATE INDEX fk_goals_5 ON goals(project_id,origin_request_id);

CREATE INDEX fk_goals_6 ON goals(project_id,last_event_id);

CREATE INDEX fk_goals_7 ON goals(project_id,id,current_revision);

CREATE INDEX fk_goal_versions_9 ON goal_versions(project_id,created_event_id);

CREATE INDEX fk_decisions_10 ON decisions(project_id,origin_request_id);

CREATE INDEX fk_decisions_11 ON decisions(project_id,last_event_id);

CREATE INDEX fk_decisions_12 ON decisions(project_id,id,current_revision);

CREATE INDEX fk_decisions_13 ON decisions(project_id,goal_id);

CREATE INDEX fk_decision_versions_15 ON decision_versions(project_id,created_event_id);

CREATE INDEX fk_requirements_16 ON requirements(project_id,origin_request_id);

CREATE INDEX fk_requirements_17 ON requirements(project_id,last_event_id);

CREATE INDEX fk_requirements_18 ON requirements(project_id,id,current_revision);

CREATE INDEX fk_requirements_19 ON requirements(project_id,goal_id);

CREATE INDEX fk_requirement_versions_21 ON requirement_versions(project_id,created_event_id);

CREATE INDEX fk_plans_22 ON plans(project_id,origin_request_id);

CREATE INDEX fk_plans_23 ON plans(project_id,last_event_id);

CREATE INDEX fk_plans_24 ON plans(project_id,id,current_revision);

CREATE INDEX fk_plans_25 ON plans(project_id,goal_id);

CREATE INDEX fk_plan_versions_27 ON plan_versions(project_id,created_event_id);

CREATE INDEX fk_work_items_28 ON work_items(project_id,origin_request_id);

CREATE INDEX fk_work_items_29 ON work_items(project_id,last_event_id);

CREATE INDEX fk_work_items_30 ON work_items(project_id,id,current_revision);

CREATE INDEX fk_work_items_31 ON work_items(project_id,goal_id);

CREATE INDEX fk_work_item_versions_33 ON work_item_versions(project_id,created_event_id);

CREATE INDEX fk_work_item_versions_34 ON work_item_versions(project_id,request_id);

CREATE INDEX fk_requirement_decisions_40 ON requirement_decisions(project_id,decision_id,decision_revision);

CREATE INDEX fk_plan_requirements_42 ON plan_requirements(project_id,requirement_id,requirement_revision);

CREATE INDEX fk_plan_decisions_44 ON plan_decisions(project_id,decision_id,decision_revision);

CREATE INDEX fk_work_item_requirements_46 ON work_item_requirements(project_id,requirement_id,requirement_revision);

CREATE INDEX fk_work_item_plan_items_48 ON work_item_plan_items(project_id,plan_id,plan_revision,plan_item_id);

CREATE INDEX fk_work_dependencies_50 ON work_dependencies(project_id,depends_on_id,depends_on_revision);

CREATE INDEX fk_selections_51 ON selections(project_id,decision_id,decision_revision,option_id);

CREATE INDEX fk_selections_53 ON selections(project_id,event_id);

CREATE INDEX fk_requirement_selections_56 ON requirement_selections(project_id,selection_id);

CREATE INDEX fk_plan_selections_58 ON plan_selections(project_id,selection_id);

CREATE INDEX fk_selection_revocations_60 ON selection_revocations(project_id,interaction_id);

CREATE INDEX fk_selection_revocations_61 ON selection_revocations(project_id,event_id);

CREATE INDEX fk_scopes_62 ON scopes(project_id,goal_id);

CREATE INDEX fk_scope_paths_64 ON scope_paths(project_id,source_id);

CREATE INDEX fk_snapshots_65 ON snapshots(project_id,scope_id);

CREATE INDEX fk_snapshot_entries_67 ON snapshot_entries(project_id,source_id);

CREATE INDEX fk_risk_assessments_68 ON risk_assessments(project_id,goal_id,goal_revision);

CREATE INDEX fk_risk_assessments_69 ON risk_assessments(project_id,scope_id,goal_id);

CREATE INDEX fk_risk_assessments_70 ON risk_assessments(project_id,snapshot_id,scope_id);

CREATE INDEX fk_risk_assessments_71 ON risk_assessments(project_id,assessor_interaction_id);

CREATE INDEX fk_authorizations_73 ON authorizations(project_id,request_id);

CREATE INDEX fk_authorizations_74 ON authorizations(project_id,interaction_id);

CREATE INDEX fk_authorizations_75 ON authorizations(project_id,snapshot_id,scope_id);

CREATE INDEX fk_authorizations_76 ON authorizations(project_id,goal_risk_id,scope_id,snapshot_id);

CREATE INDEX fk_authorizations_77 ON authorizations(project_id,change_risk_id,scope_id,snapshot_id);

CREATE INDEX fk_authorizations_78 ON authorizations(project_id,event_id);

CREATE INDEX fk_authorization_selections_80 ON authorization_selections(project_id,selection_id);

CREATE INDEX fk_authorization_requirements_82 ON authorization_requirements(project_id,requirement_id,requirement_revision);

CREATE INDEX fk_authorization_plans_84 ON authorization_plans(project_id,plan_id,plan_revision);

CREATE INDEX fk_authorization_work_items_86 ON authorization_work_items(project_id,work_item_id,work_revision);

CREATE INDEX fk_authorization_revocations_88 ON authorization_revocations(project_id,interaction_id);

CREATE INDEX fk_authorization_revocations_89 ON authorization_revocations(project_id,event_id);

CREATE INDEX fk_executions_90 ON executions(project_id,authorization_id,request_id);

CREATE INDEX fk_executions_91 ON executions(project_id,authorization_id,work_item_id,work_revision);

CREATE INDEX fk_executions_92 ON executions(project_id,last_event_id);

CREATE INDEX fk_deliveries_94 ON deliveries(project_id,last_event_id);

CREATE INDEX fk_delivery_attempts_96 ON delivery_attempts(project_id,started_event_id);

CREATE INDEX fk_evidence_97 ON evidence(project_id,snapshot_id);

CREATE INDEX fk_evidence_98 ON evidence(project_id,execution_id);

CREATE INDEX fk_evidence_99 ON evidence(project_id,reporter_interaction_id);

CREATE INDEX fk_evidence_100 ON evidence(project_id,event_id);

CREATE INDEX fk_decision_evidence_103 ON decision_evidence(project_id,evidence_id);

CREATE INDEX fk_plan_evidence_105 ON plan_evidence(project_id,evidence_id);

CREATE INDEX fk_criterion_results_107 ON criterion_results(project_id,requirement_id,requirement_revision,criterion_id);

CREATE INDEX fk_work_check_results_109 ON work_check_results(project_id,work_item_id,work_revision,check_id);

CREATE INDEX fk_risk_evidence_111 ON risk_evidence(project_id,evidence_id);

CREATE INDEX fk_current_facts_112 ON current_facts(project_id,goal_id);

CREATE INDEX fk_current_facts_113 ON current_facts(project_id,source_id);

CREATE INDEX fk_current_facts_114 ON current_facts(project_id,snapshot_id);

CREATE INDEX fk_current_facts_115 ON current_facts(project_id,evidence_id);

CREATE INDEX fk_current_facts_117 ON current_facts(project_id,event_id);

CREATE INDEX fk_fact_retractions_119 ON fact_retractions(project_id,event_id);

CREATE INDEX deliveries_pending ON deliveries(state,lease_until,created_at);
CREATE INDEX evidence_snapshot ON evidence(project_id,snapshot_id,surface,result);
CREATE VIEW now_facts AS SELECT f.* FROM current_facts f
WHERE NOT EXISTS(SELECT 1 FROM current_facts newer WHERE newer.project_id=f.project_id AND newer.supersedes_id=f.id)
AND NOT EXISTS(SELECT 1 FROM fact_retractions r WHERE r.project_id=f.project_id AND r.fact_id=f.id);

-- Additional integrity rules
CREATE TRIGGER goal_stable_identity BEFORE UPDATE ON goals WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;

CREATE TRIGGER goal_stable_version BEFORE UPDATE ON goal_versions WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.revision<>OLD.revision BEGIN SELECT RAISE(ABORT,'stable version key'); END;

CREATE TRIGGER goal_head_cas BEFORE UPDATE ON goals WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;

CREATE TRIGGER goal_head_monotonic BEFORE UPDATE ON goals WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;

CREATE TRIGGER decision_stable_identity BEFORE UPDATE ON decisions WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id OR NEW.goal_id<>OLD.goal_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;

CREATE TRIGGER decision_stable_version BEFORE UPDATE ON decision_versions WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.revision<>OLD.revision BEGIN SELECT RAISE(ABORT,'stable version key'); END;

CREATE TRIGGER decision_head_cas BEFORE UPDATE ON decisions WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;

CREATE TRIGGER decision_head_monotonic BEFORE UPDATE ON decisions WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;

CREATE TRIGGER requirement_stable_identity BEFORE UPDATE ON requirements WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id OR NEW.goal_id<>OLD.goal_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;

CREATE TRIGGER requirement_stable_version BEFORE UPDATE ON requirement_versions WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.revision<>OLD.revision BEGIN SELECT RAISE(ABORT,'stable version key'); END;

CREATE TRIGGER requirement_head_cas BEFORE UPDATE ON requirements WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;

CREATE TRIGGER requirement_head_monotonic BEFORE UPDATE ON requirements WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;

CREATE TRIGGER plan_stable_identity BEFORE UPDATE ON plans WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id OR NEW.goal_id<>OLD.goal_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;

CREATE TRIGGER plan_stable_version BEFORE UPDATE ON plan_versions WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.revision<>OLD.revision BEGIN SELECT RAISE(ABORT,'stable version key'); END;

CREATE TRIGGER plan_head_cas BEFORE UPDATE ON plans WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;

CREATE TRIGGER plan_head_monotonic BEFORE UPDATE ON plans WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;

CREATE TRIGGER work_item_stable_identity BEFORE UPDATE ON work_items WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id OR NEW.goal_id<>OLD.goal_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;

CREATE TRIGGER work_item_stable_version BEFORE UPDATE ON work_item_versions WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.revision<>OLD.revision BEGIN SELECT RAISE(ABORT,'stable version key'); END;

CREATE TRIGGER work_item_head_cas BEFORE UPDATE ON work_items WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;

CREATE TRIGGER work_item_head_monotonic BEFORE UPDATE ON work_items WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;

CREATE TRIGGER requirement_decisions_target_insert BEFORE INSERT ON requirement_decisions WHEN NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'target must be sealed'); END;

CREATE TRIGGER requirement_decisions_target_update BEFORE UPDATE ON requirement_decisions WHEN NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'target must be sealed'); END;

CREATE TRIGGER requirement_decisions_goal_update BEFORE UPDATE ON requirement_decisions WHEN (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id)<>(SELECT goal_id FROM decisions WHERE project_id=NEW.project_id AND id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;

CREATE TRIGGER plan_requirements_target_insert BEFORE INSERT ON plan_requirements WHEN NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'target must be sealed'); END;

CREATE TRIGGER plan_requirements_target_update BEFORE UPDATE ON plan_requirements WHEN NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'target must be sealed'); END;

CREATE TRIGGER plan_requirements_goal_update BEFORE UPDATE ON plan_requirements WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id)<>(SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;

CREATE TRIGGER plan_decisions_target_insert BEFORE INSERT ON plan_decisions WHEN NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'target must be sealed'); END;

CREATE TRIGGER plan_decisions_target_update BEFORE UPDATE ON plan_decisions WHEN NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'target must be sealed'); END;

CREATE TRIGGER plan_decisions_goal_update BEFORE UPDATE ON plan_decisions WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id)<>(SELECT goal_id FROM decisions WHERE project_id=NEW.project_id AND id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;

CREATE TRIGGER work_item_requirements_target_insert BEFORE INSERT ON work_item_requirements WHEN NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'target must be sealed'); END;

CREATE TRIGGER work_item_requirements_target_update BEFORE UPDATE ON work_item_requirements WHEN NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'target must be sealed'); END;

CREATE TRIGGER work_item_requirements_goal_update BEFORE UPDATE ON work_item_requirements WHEN (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;

CREATE TRIGGER work_item_plan_items_target_insert BEFORE INSERT ON work_item_plan_items WHEN NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) OR (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id) BEGIN SELECT RAISE(ABORT,'target must be sealed in same goal'); END;

CREATE TRIGGER work_item_plan_items_target_update BEFORE UPDATE ON work_item_plan_items WHEN NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) OR (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id) BEGIN SELECT RAISE(ABORT,'target must be sealed in same goal'); END;

CREATE TRIGGER work_dependencies_target_insert BEFORE INSERT ON work_dependencies WHEN NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.depends_on_id AND revision=NEW.depends_on_revision AND sealed_at IS NOT NULL) OR (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.depends_on_id) BEGIN SELECT RAISE(ABORT,'target must be sealed in same goal'); END;

CREATE TRIGGER work_dependencies_target_update BEFORE UPDATE ON work_dependencies WHEN NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.depends_on_id AND revision=NEW.depends_on_revision AND sealed_at IS NOT NULL) OR (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.depends_on_id) BEGIN SELECT RAISE(ABORT,'target must be sealed in same goal'); END;

CREATE TRIGGER decision_seal_children BEFORE UPDATE ON decision_versions WHEN NEW.sealed_at IS NOT NULL AND (SELECT count(*) FROM decision_options WHERE project_id=NEW.project_id AND decision_id=NEW.id AND decision_revision=NEW.revision)<2 BEGIN SELECT RAISE(ABORT,'aggregate needs children'); END;

CREATE TRIGGER requirement_seal_children BEFORE UPDATE ON requirement_versions WHEN NEW.sealed_at IS NOT NULL AND (SELECT count(*) FROM acceptance_criteria WHERE project_id=NEW.project_id AND requirement_id=NEW.id AND requirement_revision=NEW.revision)<1 BEGIN SELECT RAISE(ABORT,'aggregate needs children'); END;

CREATE TRIGGER plan_seal_children BEFORE UPDATE ON plan_versions WHEN NEW.sealed_at IS NOT NULL AND (SELECT count(*) FROM plan_items WHERE project_id=NEW.project_id AND plan_id=NEW.id AND plan_revision=NEW.revision)<1 BEGIN SELECT RAISE(ABORT,'aggregate needs children'); END;

CREATE TRIGGER work_item_seal_children BEFORE UPDATE ON work_item_versions WHEN NEW.sealed_at IS NOT NULL AND (SELECT count(*) FROM work_checks WHERE project_id=NEW.project_id AND work_item_id=NEW.id AND work_revision=NEW.revision)<1 BEGIN SELECT RAISE(ABORT,'aggregate needs children'); END;

CREATE TRIGGER work_full_plan BEFORE UPDATE ON work_item_versions WHEN NEW.sealed_at IS NOT NULL AND NEW.workflow_depth='full' AND (NOT EXISTS(SELECT 1 FROM work_item_plan_items WHERE project_id=NEW.project_id AND work_item_id=NEW.id AND work_revision=NEW.revision) OR NOT EXISTS(SELECT 1 FROM work_item_requirements WHERE project_id=NEW.project_id AND work_item_id=NEW.id AND work_item_revision=NEW.revision)) BEGIN SELECT RAISE(ABORT,'full work needs plan and requirement'); END;

CREATE TRIGGER selection_sealed BEFORE INSERT ON selections WHEN NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.decision_id AND revision=NEW.decision_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'selection needs sealed decision'); END;

CREATE TRIGGER selection_replacement BEFORE INSERT ON selections WHEN NEW.supersedes_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM selections WHERE project_id=NEW.project_id AND id=NEW.supersedes_id AND decision_id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'cannot replace another decision'); END;

CREATE TRIGGER risk_assessments_sealed_snapshot BEFORE UPDATE ON risk_assessments WHEN NEW.sealed_at IS NOT NULL AND NOT EXISTS(SELECT 1 FROM snapshots WHERE project_id=NEW.project_id AND id=NEW.snapshot_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'snapshot must be sealed'); END;

CREATE TRIGGER evidence_sealed_snapshot BEFORE UPDATE ON evidence WHEN NEW.sealed_at IS NOT NULL AND NOT EXISTS(SELECT 1 FROM snapshots WHERE project_id=NEW.project_id AND id=NEW.snapshot_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'snapshot must be sealed'); END;

CREATE TRIGGER snapshot_sealed_scope BEFORE UPDATE ON snapshots WHEN NEW.sealed_at IS NOT NULL AND NOT EXISTS(SELECT 1 FROM scopes WHERE project_id=NEW.project_id AND id=NEW.scope_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'scope must be sealed'); END;

CREATE TRIGGER risk_dimensions BEFORE UPDATE ON risk_assessments WHEN NEW.sealed_at IS NOT NULL AND (SELECT count(*) FROM risk_factors WHERE project_id=NEW.project_id AND assessment_id=NEW.id)<>8 BEGIN SELECT RAISE(ABORT,'all risk dimensions required'); END;

CREATE TRIGGER decision_evidence_ready_insert BEFORE INSERT ON decision_evidence WHEN NOT EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'evidence must be sealed'); END;

CREATE TRIGGER decision_evidence_ready_update BEFORE UPDATE ON decision_evidence WHEN NOT EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'evidence must be sealed'); END;

CREATE TRIGGER plan_evidence_ready_insert BEFORE INSERT ON plan_evidence WHEN NOT EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'evidence must be sealed'); END;

CREATE TRIGGER plan_evidence_ready_update BEFORE UPDATE ON plan_evidence WHEN NOT EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'evidence must be sealed'); END;

CREATE TRIGGER work_evidence_execution BEFORE INSERT ON work_check_results WHEN (SELECT execution_id FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id) IS NOT NULL AND NOT EXISTS(SELECT 1 FROM evidence e JOIN executions x ON x.project_id=e.project_id AND x.id=e.execution_id WHERE e.project_id=NEW.project_id AND e.id=NEW.evidence_id AND x.work_item_id=NEW.work_item_id AND x.work_revision=NEW.work_revision) BEGIN SELECT RAISE(ABORT,'evidence belongs to another work revision'); END;

CREATE TRIGGER authorization_requirement_target_insert BEFORE INSERT ON authorization_requirements WHEN NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'authorization target must be sealed'); END;

CREATE TRIGGER authorization_requirement_target_update BEFORE UPDATE ON authorization_requirements WHEN NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.requirement_id AND revision=NEW.requirement_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'authorization target must be sealed'); END;

CREATE TRIGGER authorization_plan_target_insert BEFORE INSERT ON authorization_plans WHEN NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'authorization target must be sealed'); END;

CREATE TRIGGER authorization_plan_target_update BEFORE UPDATE ON authorization_plans WHEN NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'authorization target must be sealed'); END;

CREATE TRIGGER authorization_work_item_target_insert BEFORE INSERT ON authorization_work_items WHEN NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'authorization target must be sealed'); END;

CREATE TRIGGER authorization_work_item_target_update BEFORE UPDATE ON authorization_work_items WHEN NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.work_item_id AND revision=NEW.work_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'authorization target must be sealed'); END;

CREATE TRIGGER authorization_risks BEFORE UPDATE ON authorizations WHEN NEW.sealed_at IS NOT NULL AND (NOT EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=NEW.project_id AND id=NEW.goal_risk_id AND kind='goal' AND sealed_at IS NOT NULL) OR NOT EXISTS(SELECT 1 FROM risk_assessments WHERE project_id=NEW.project_id AND id=NEW.change_risk_id AND kind='change' AND sealed_at IS NOT NULL)) BEGIN SELECT RAISE(ABORT,'both risk kinds required'); END;

CREATE TRIGGER execution_authority BEFORE INSERT ON executions WHEN NOT EXISTS(SELECT 1 FROM authorizations a JOIN work_item_versions w ON w.project_id=a.project_id AND w.id=NEW.work_item_id AND w.revision=NEW.work_revision WHERE a.project_id=NEW.project_id AND a.id=NEW.authorization_id AND a.sealed_at IS NOT NULL AND w.operation=a.action) OR EXISTS(SELECT 1 FROM authorization_revocations WHERE project_id=NEW.project_id AND authorization_id=NEW.authorization_id) BEGIN SELECT RAISE(ABORT,'execution needs matching sealed authority'); END;

CREATE TRIGGER fact_evidence BEFORE INSERT ON current_facts WHEN NOT EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id AND snapshot_id=NEW.snapshot_id AND sealed_at IS NOT NULL AND result<>'NOT_RUN') BEGIN SELECT RAISE(ABORT,'fact needs matching observed evidence'); END;

CREATE TRIGGER fact_supersedes BEFORE INSERT ON current_facts WHEN NEW.supersedes_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM current_facts WHERE project_id=NEW.project_id AND id=NEW.supersedes_id AND source_id=NEW.source_id AND goal_id IS NEW.goal_id) BEGIN SELECT RAISE(ABORT,'fact lineage mismatch'); END;

CREATE TRIGGER delivery_attempt_complete BEFORE UPDATE ON delivery_attempts WHEN OLD.finished_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'attempt already finished'); END;

CREATE TRIGGER executions_cas BEFORE UPDATE ON executions WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;

CREATE TRIGGER executions_identity BEFORE UPDATE ON executions WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.request_id<>OLD.request_id OR NEW.authorization_id<>OLD.authorization_id OR NEW.work_item_id<>OLD.work_item_id OR NEW.work_revision<>OLD.work_revision OR NEW.dispatch_context_digest<>OLD.dispatch_context_digest OR NEW.attempt_no<>OLD.attempt_no BEGIN SELECT RAISE(ABORT,'execution identity is immutable'); END;

CREATE TRIGGER executions_delete BEFORE DELETE ON executions WHEN 1 BEGIN SELECT RAISE(ABORT,'operational history deletion disabled'); END;

CREATE TRIGGER deliveries_cas BEFORE UPDATE ON deliveries WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;

CREATE TRIGGER deliveries_identity BEFORE UPDATE ON deliveries WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.execution_id<>OLD.execution_id OR NEW.message_key<>OLD.message_key OR NEW.payload<>OLD.payload OR NEW.payload_digest<>OLD.payload_digest BEGIN SELECT RAISE(ABORT,'execution identity is immutable'); END;

CREATE TRIGGER deliveries_delete BEFORE DELETE ON deliveries WHEN 1 BEGIN SELECT RAISE(ABORT,'operational history deletion disabled'); END;

CREATE TRIGGER requirement_selection_goal_insert BEFORE INSERT ON requirement_selections WHEN (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id)<>(SELECT d.goal_id FROM selections s JOIN decisions d ON d.project_id=s.project_id AND d.id=s.decision_id WHERE s.project_id=NEW.project_id AND s.id=NEW.selection_id) BEGIN SELECT RAISE(ABORT,'selection from another goal'); END;

CREATE TRIGGER requirement_selection_goal_update BEFORE UPDATE ON requirement_selections WHEN (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id)<>(SELECT d.goal_id FROM selections s JOIN decisions d ON d.project_id=s.project_id AND d.id=s.decision_id WHERE s.project_id=NEW.project_id AND s.id=NEW.selection_id) BEGIN SELECT RAISE(ABORT,'selection from another goal'); END;

CREATE TRIGGER plan_selection_goal_insert BEFORE INSERT ON plan_selections WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id)<>(SELECT d.goal_id FROM selections s JOIN decisions d ON d.project_id=s.project_id AND d.id=s.decision_id WHERE s.project_id=NEW.project_id AND s.id=NEW.selection_id) BEGIN SELECT RAISE(ABORT,'selection from another goal'); END;

CREATE TRIGGER plan_selection_goal_update BEFORE UPDATE ON plan_selections WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id)<>(SELECT d.goal_id FROM selections s JOIN decisions d ON d.project_id=s.project_id AND d.id=s.decision_id WHERE s.project_id=NEW.project_id AND s.id=NEW.selection_id) BEGIN SELECT RAISE(ABORT,'selection from another goal'); END;

CREATE TRIGGER authorization_requirement_goal_insert BEFORE INSERT ON authorization_requirements WHEN (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id)<>(SELECT s.goal_id FROM authorizations a JOIN scopes s ON s.project_id=a.project_id AND s.id=a.scope_id WHERE a.project_id=NEW.project_id AND a.id=NEW.authorization_id) BEGIN SELECT RAISE(ABORT,'authorization scope goal mismatch'); END;

CREATE TRIGGER authorization_requirement_goal_update BEFORE UPDATE ON authorization_requirements WHEN (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id)<>(SELECT s.goal_id FROM authorizations a JOIN scopes s ON s.project_id=a.project_id AND s.id=a.scope_id WHERE a.project_id=NEW.project_id AND a.id=NEW.authorization_id) BEGIN SELECT RAISE(ABORT,'authorization scope goal mismatch'); END;

CREATE TRIGGER authorization_plan_goal_insert BEFORE INSERT ON authorization_plans WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id)<>(SELECT s.goal_id FROM authorizations a JOIN scopes s ON s.project_id=a.project_id AND s.id=a.scope_id WHERE a.project_id=NEW.project_id AND a.id=NEW.authorization_id) BEGIN SELECT RAISE(ABORT,'authorization scope goal mismatch'); END;

CREATE TRIGGER authorization_plan_goal_update BEFORE UPDATE ON authorization_plans WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id)<>(SELECT s.goal_id FROM authorizations a JOIN scopes s ON s.project_id=a.project_id AND s.id=a.scope_id WHERE a.project_id=NEW.project_id AND a.id=NEW.authorization_id) BEGIN SELECT RAISE(ABORT,'authorization scope goal mismatch'); END;

CREATE TRIGGER authorization_work_item_goal_insert BEFORE INSERT ON authorization_work_items WHEN (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT s.goal_id FROM authorizations a JOIN scopes s ON s.project_id=a.project_id AND s.id=a.scope_id WHERE a.project_id=NEW.project_id AND a.id=NEW.authorization_id) BEGIN SELECT RAISE(ABORT,'authorization scope goal mismatch'); END;

CREATE TRIGGER authorization_work_item_goal_update BEFORE UPDATE ON authorization_work_items WHEN (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT s.goal_id FROM authorizations a JOIN scopes s ON s.project_id=a.project_id AND s.id=a.scope_id WHERE a.project_id=NEW.project_id AND a.id=NEW.authorization_id) BEGIN SELECT RAISE(ABORT,'authorization scope goal mismatch'); END;

CREATE TRIGGER criterion_execution_insert BEFORE INSERT ON criterion_results WHEN (SELECT execution_id FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id) IS NOT NULL AND NOT EXISTS(SELECT 1 FROM evidence e JOIN executions x ON x.project_id=e.project_id AND x.id=e.execution_id JOIN work_item_requirements wr ON wr.project_id=x.project_id AND wr.work_item_id=x.work_item_id AND wr.work_item_revision=x.work_revision WHERE e.project_id=NEW.project_id AND e.id=NEW.evidence_id AND wr.requirement_id=NEW.requirement_id AND wr.requirement_revision=NEW.requirement_revision) BEGIN SELECT RAISE(ABORT,'criterion not linked to executed work'); END;

CREATE TRIGGER criterion_execution_update BEFORE UPDATE ON criterion_results WHEN (SELECT execution_id FROM evidence WHERE project_id=NEW.project_id AND id=NEW.evidence_id) IS NOT NULL AND NOT EXISTS(SELECT 1 FROM evidence e JOIN executions x ON x.project_id=e.project_id AND x.id=e.execution_id JOIN work_item_requirements wr ON wr.project_id=x.project_id AND wr.work_item_id=x.work_item_id AND wr.work_item_revision=x.work_revision WHERE e.project_id=NEW.project_id AND e.id=NEW.evidence_id AND wr.requirement_id=NEW.requirement_id AND wr.requirement_revision=NEW.requirement_revision) BEGIN SELECT RAISE(ABORT,'criterion not linked to executed work'); END;

CREATE UNIQUE INDEX one_selection_lineage ON selections(project_id,decision_id) WHERE supersedes_id IS NULL;

CREATE UNIQUE INDEX one_active_work_execution ON executions(project_id,work_item_id) WHERE state IN ('prepared','accepted','running','cancel_requested','cancellation_unknown');
