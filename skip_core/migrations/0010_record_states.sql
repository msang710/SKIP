DROP TRIGGER requirement_decisions_same_goal;
DROP TRIGGER plan_requirements_same_goal;
DROP TRIGGER plan_decisions_same_goal;
DROP TRIGGER work_item_requirements_same_goal;
DROP TRIGGER requirement_decisions_goal_update;
DROP TRIGGER plan_requirements_goal_update;
DROP TRIGGER plan_decisions_goal_update;
DROP TRIGGER work_item_requirements_goal_update;
DROP TRIGGER work_item_plan_items_target_insert;
DROP TRIGGER work_item_plan_items_target_update;
DROP TRIGGER work_dependencies_target_insert;
DROP TRIGGER work_dependencies_target_update;
DROP TRIGGER requirement_selection_goal_insert;
DROP TRIGGER requirement_selection_goal_update;
DROP TRIGGER plan_selection_goal_insert;
DROP TRIGGER plan_selection_goal_update;
DROP TRIGGER authorization_requirement_goal_insert;
DROP TRIGGER authorization_requirement_goal_update;
DROP TRIGGER authorization_plan_goal_insert;
DROP TRIGGER authorization_plan_goal_update;
DROP TRIGGER authorization_work_item_goal_insert;
DROP TRIGGER authorization_work_item_goal_update;
-- Preserve all existing heads, references, triggers and indexes.

CREATE TABLE decisions_next (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','rejected','superseded','archived')),
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
INSERT INTO decisions_next SELECT * FROM decisions;
DROP TABLE decisions;
ALTER TABLE decisions_next RENAME TO decisions;
CREATE TRIGGER decision_head_cas BEFORE UPDATE ON decisions WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;
CREATE TRIGGER decision_head_monotonic BEFORE UPDATE ON decisions WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;
CREATE TRIGGER decision_stable_identity BEFORE UPDATE ON decisions WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id OR NEW.goal_id<>OLD.goal_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;
CREATE TRIGGER decisions_head_insert BEFORE INSERT ON decisions WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TRIGGER decisions_head_update BEFORE UPDATE ON decisions WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE INDEX fk_decisions_10 ON decisions(project_id,origin_request_id);
CREATE INDEX fk_decisions_11 ON decisions(project_id,last_event_id);
CREATE INDEX fk_decisions_12 ON decisions(project_id,id,current_revision);
CREATE INDEX fk_decisions_13 ON decisions(project_id,goal_id);
CREATE TABLE requirements_next (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','rejected','superseded','archived')),
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
INSERT INTO requirements_next SELECT * FROM requirements;
DROP TABLE requirements;
ALTER TABLE requirements_next RENAME TO requirements;
CREATE INDEX fk_requirements_16 ON requirements(project_id,origin_request_id);
CREATE INDEX fk_requirements_17 ON requirements(project_id,last_event_id);
CREATE INDEX fk_requirements_18 ON requirements(project_id,id,current_revision);
CREATE INDEX fk_requirements_19 ON requirements(project_id,goal_id);
CREATE TRIGGER requirement_head_cas BEFORE UPDATE ON requirements WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;
CREATE TRIGGER requirement_head_monotonic BEFORE UPDATE ON requirements WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;
CREATE TRIGGER requirement_stable_identity BEFORE UPDATE ON requirements WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id OR NEW.goal_id<>OLD.goal_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;
CREATE TRIGGER requirements_head_insert BEFORE INSERT ON requirements WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TRIGGER requirements_head_update BEFORE UPDATE ON requirements WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TABLE plans_next (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','rejected','superseded','archived')),
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
INSERT INTO plans_next SELECT * FROM plans;
DROP TABLE plans;
ALTER TABLE plans_next RENAME TO plans;
CREATE INDEX fk_plans_22 ON plans(project_id,origin_request_id);
CREATE INDEX fk_plans_23 ON plans(project_id,last_event_id);
CREATE INDEX fk_plans_24 ON plans(project_id,id,current_revision);
CREATE INDEX fk_plans_25 ON plans(project_id,goal_id);
CREATE TRIGGER plan_head_cas BEFORE UPDATE ON plans WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;
CREATE TRIGGER plan_head_monotonic BEFORE UPDATE ON plans WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;
CREATE TRIGGER plan_stable_identity BEFORE UPDATE ON plans WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id OR NEW.goal_id<>OLD.goal_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;
CREATE TRIGGER plans_head_insert BEFORE INSERT ON plans WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TRIGGER plans_head_update BEFORE UPDATE ON plans WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TABLE work_items_next (
  project_id TEXT NOT NULL,
  id TEXT NOT NULL,
  goal_id TEXT NOT NULL,
  current_revision INTEGER,
  origin_request_id TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('active','held','rejected','superseded','archived')),
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
INSERT INTO work_items_next SELECT * FROM work_items;
DROP TABLE work_items;
ALTER TABLE work_items_next RENAME TO work_items;
CREATE INDEX fk_work_items_28 ON work_items(project_id,origin_request_id);
CREATE INDEX fk_work_items_29 ON work_items(project_id,last_event_id);
CREATE INDEX fk_work_items_30 ON work_items(project_id,id,current_revision);
CREATE INDEX fk_work_items_31 ON work_items(project_id,goal_id);
CREATE TRIGGER work_item_head_cas BEFORE UPDATE ON work_items WHEN NEW.state_version<>OLD.state_version+1 OR NEW.last_event_id=OLD.last_event_id BEGIN SELECT RAISE(ABORT,'CAS event required'); END;
CREATE TRIGGER work_item_head_monotonic BEFORE UPDATE ON work_items WHEN OLD.current_revision IS NOT NULL AND (NEW.current_revision IS NULL OR NEW.current_revision<OLD.current_revision) BEGIN SELECT RAISE(ABORT,'head cannot go backwards'); END;
CREATE TRIGGER work_item_stable_identity BEFORE UPDATE ON work_items WHEN NEW.project_id<>OLD.project_id OR NEW.id<>OLD.id OR NEW.origin_request_id<>OLD.origin_request_id OR NEW.goal_id<>OLD.goal_id BEGIN SELECT RAISE(ABORT,'stable identity'); END;
CREATE TRIGGER work_items_head_insert BEFORE INSERT ON work_items WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TRIGGER work_items_head_update BEFORE UPDATE ON work_items WHEN NEW.current_revision IS NOT NULL AND NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.id AND revision=NEW.current_revision AND sealed_at IS NOT NULL) BEGIN SELECT RAISE(ABORT,'head requires sealed version'); END;
CREATE TRIGGER requirement_decisions_same_goal BEFORE INSERT ON requirement_decisions WHEN (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) <> (SELECT goal_id FROM decisions WHERE project_id=NEW.project_id AND id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;
CREATE TRIGGER plan_requirements_same_goal BEFORE INSERT ON plan_requirements WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id) <> (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;
CREATE TRIGGER plan_decisions_same_goal BEFORE INSERT ON plan_decisions WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id) <> (SELECT goal_id FROM decisions WHERE project_id=NEW.project_id AND id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;
CREATE TRIGGER work_item_requirements_same_goal BEFORE INSERT ON work_item_requirements WHEN (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id) <> (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;
CREATE TRIGGER requirement_decisions_goal_update BEFORE UPDATE ON requirement_decisions WHEN (SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id)<>(SELECT goal_id FROM decisions WHERE project_id=NEW.project_id AND id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;
CREATE TRIGGER plan_requirements_goal_update BEFORE UPDATE ON plan_requirements WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id)<>(SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;
CREATE TRIGGER plan_decisions_goal_update BEFORE UPDATE ON plan_decisions WHEN (SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id)<>(SELECT goal_id FROM decisions WHERE project_id=NEW.project_id AND id=NEW.decision_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;
CREATE TRIGGER work_item_requirements_goal_update BEFORE UPDATE ON work_item_requirements WHEN (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM requirements WHERE project_id=NEW.project_id AND id=NEW.requirement_id) BEGIN SELECT RAISE(ABORT,'different goal'); END;
CREATE TRIGGER work_item_plan_items_target_insert BEFORE INSERT ON work_item_plan_items WHEN NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) OR (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id) BEGIN SELECT RAISE(ABORT,'target must be sealed in same goal'); END;
CREATE TRIGGER work_item_plan_items_target_update BEFORE UPDATE ON work_item_plan_items WHEN NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.plan_id AND revision=NEW.plan_revision AND sealed_at IS NOT NULL) OR (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM plans WHERE project_id=NEW.project_id AND id=NEW.plan_id) BEGIN SELECT RAISE(ABORT,'target must be sealed in same goal'); END;
CREATE TRIGGER work_dependencies_target_insert BEFORE INSERT ON work_dependencies WHEN NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.depends_on_id AND revision=NEW.depends_on_revision AND sealed_at IS NOT NULL) OR (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.depends_on_id) BEGIN SELECT RAISE(ABORT,'target must be sealed in same goal'); END;
CREATE TRIGGER work_dependencies_target_update BEFORE UPDATE ON work_dependencies WHEN NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.depends_on_id AND revision=NEW.depends_on_revision AND sealed_at IS NOT NULL) OR (SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.work_item_id)<>(SELECT goal_id FROM work_items WHERE project_id=NEW.project_id AND id=NEW.depends_on_id) BEGIN SELECT RAISE(ABORT,'target must be sealed in same goal'); END;
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
CREATE TABLE record_state_changes (
 project_id TEXT NOT NULL,
 id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('goal','decision','requirement','plan','work_item')),
 record_id TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>0),
 state_version INTEGER NOT NULL CHECK(state_version>0),
 from_state TEXT NOT NULL,
 to_state TEXT NOT NULL,
 reason TEXT NOT NULL,
 replacement_id TEXT,
 replacement_revision INTEGER,
 event_id TEXT NOT NULL,
 created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,id),
 UNIQUE(project_id,kind,record_id,state_version),
 CHECK((replacement_id IS NULL)=(replacement_revision IS NULL)),
 CHECK((to_state='superseded')=(replacement_id IS NOT NULL)),
 CHECK(to_state NOT IN ('rejected','superseded') OR length(trim(reason))>0),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id) ON DELETE RESTRICT
) STRICT;
CREATE TRIGGER record_state_changes_no_update BEFORE UPDATE ON record_state_changes BEGIN SELECT RAISE(ABORT,'immutable state history'); END;
CREATE TRIGGER record_state_changes_no_delete BEFORE DELETE ON record_state_changes BEGIN SELECT RAISE(ABORT,'immutable state history'); END;
CREATE TRIGGER record_state_changes_goal BEFORE INSERT ON record_state_changes WHEN NEW.kind='goal' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM goals h JOIN goal_versions v ON v.project_id=h.project_id AND v.id=h.id WHERE h.project_id=NEW.project_id AND h.id=NEW.record_id AND v.revision=NEW.revision AND v.sealed_at IS NOT NULL AND h.state_version=NEW.state_version AND h.lifecycle=NEW.to_state AND h.last_event_id=NEW.event_id) THEN RAISE(ABORT,'state history requires current record') END;
 END;
CREATE TRIGGER record_state_changes_decision BEFORE INSERT ON record_state_changes WHEN NEW.kind='decision' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM decisions h JOIN decision_versions v ON v.project_id=h.project_id AND v.id=h.id WHERE h.project_id=NEW.project_id AND h.id=NEW.record_id AND v.revision=NEW.revision AND v.sealed_at IS NOT NULL AND h.state_version=NEW.state_version AND h.lifecycle=NEW.to_state AND h.last_event_id=NEW.event_id) THEN RAISE(ABORT,'state history requires current record') END;
 END;
CREATE TRIGGER record_state_changes_requirement BEFORE INSERT ON record_state_changes WHEN NEW.kind='requirement' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM requirements h JOIN requirement_versions v ON v.project_id=h.project_id AND v.id=h.id WHERE h.project_id=NEW.project_id AND h.id=NEW.record_id AND v.revision=NEW.revision AND v.sealed_at IS NOT NULL AND h.state_version=NEW.state_version AND h.lifecycle=NEW.to_state AND h.last_event_id=NEW.event_id) THEN RAISE(ABORT,'state history requires current record') END;
 END;
CREATE TRIGGER record_state_changes_plan BEFORE INSERT ON record_state_changes WHEN NEW.kind='plan' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM plans h JOIN plan_versions v ON v.project_id=h.project_id AND v.id=h.id WHERE h.project_id=NEW.project_id AND h.id=NEW.record_id AND v.revision=NEW.revision AND v.sealed_at IS NOT NULL AND h.state_version=NEW.state_version AND h.lifecycle=NEW.to_state AND h.last_event_id=NEW.event_id) THEN RAISE(ABORT,'state history requires current record') END;
 END;
CREATE TRIGGER record_state_changes_work_item BEFORE INSERT ON record_state_changes WHEN NEW.kind='work_item' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM work_items h JOIN work_item_versions v ON v.project_id=h.project_id AND v.id=h.id WHERE h.project_id=NEW.project_id AND h.id=NEW.record_id AND v.revision=NEW.revision AND v.sealed_at IS NOT NULL AND h.state_version=NEW.state_version AND h.lifecycle=NEW.to_state AND h.last_event_id=NEW.event_id) THEN RAISE(ABORT,'state history requires current record') END;
 END;
