-- Provenance belongs to native records; it does not confer execution authority.
CREATE TABLE record_origins (
 project_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('goal','decision','requirement','plan','work_item','evidence')),
 record_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0), document_id TEXT NOT NULL,
 source_key TEXT NOT NULL, source_status TEXT NOT NULL, source_date TEXT,
 classification TEXT, source_excerpt TEXT NOT NULL, unresolved_json TEXT NOT NULL CHECK(json_valid(unresolved_json)),
 PRIMARY KEY(project_id,kind,record_id,revision),
 FOREIGN KEY(project_id,document_id) REFERENCES imported_documents(project_id,id)
) STRICT;
CREATE TABLE document_dispositions (
 project_id TEXT NOT NULL, document_id TEXT NOT NULL,
 disposition TEXT NOT NULL CHECK(disposition IN ('converted','supplement','excluded')),
 reason TEXT NOT NULL, event_id TEXT NOT NULL,
 PRIMARY KEY(project_id,document_id),
 FOREIGN KEY(project_id,document_id) REFERENCES imported_documents(project_id,id),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TRIGGER origin_update BEFORE UPDATE ON record_origins BEGIN SELECT RAISE(ABORT,'immutable origin'); END;
CREATE TRIGGER origin_delete BEFORE DELETE ON record_origins BEGIN SELECT RAISE(ABORT,'immutable origin'); END;
CREATE TRIGGER origin_goal_target BEFORE INSERT ON record_origins WHEN NEW.kind='goal' AND NOT EXISTS(SELECT 1 FROM goal_versions WHERE project_id=NEW.project_id AND id=NEW.record_id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'origin target must be sealed'); END;
CREATE TRIGGER origin_decision_target BEFORE INSERT ON record_origins WHEN NEW.kind='decision' AND NOT EXISTS(SELECT 1 FROM decision_versions WHERE project_id=NEW.project_id AND id=NEW.record_id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'origin target must be sealed'); END;
CREATE TRIGGER origin_requirement_target BEFORE INSERT ON record_origins WHEN NEW.kind='requirement' AND NOT EXISTS(SELECT 1 FROM requirement_versions WHERE project_id=NEW.project_id AND id=NEW.record_id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'origin target must be sealed'); END;
CREATE TRIGGER origin_plan_target BEFORE INSERT ON record_origins WHEN NEW.kind='plan' AND NOT EXISTS(SELECT 1 FROM plan_versions WHERE project_id=NEW.project_id AND id=NEW.record_id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'origin target must be sealed'); END;
CREATE TRIGGER origin_work_item_target BEFORE INSERT ON record_origins WHEN NEW.kind='work_item' AND NOT EXISTS(SELECT 1 FROM work_item_versions WHERE project_id=NEW.project_id AND id=NEW.record_id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'origin target must be sealed'); END;
CREATE TRIGGER origin_evidence_target BEFORE INSERT ON record_origins WHEN NEW.kind='evidence' AND NOT EXISTS(SELECT 1 FROM evidence WHERE project_id=NEW.project_id AND id=NEW.record_id) BEGIN SELECT RAISE(ABORT,'origin target must be sealed'); END;

DROP TRIGGER decision_seal_children;
CREATE TRIGGER decision_seal_children BEFORE UPDATE ON decision_versions WHEN NEW.sealed_at IS NOT NULL AND (SELECT count(*) FROM decision_options WHERE project_id=NEW.project_id AND decision_id=NEW.id AND decision_revision=NEW.revision)<2 AND NOT EXISTS(SELECT 1 FROM record_origins WHERE project_id=NEW.project_id AND kind='decision' AND record_id=NEW.id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'aggregate needs children'); END;

DROP TRIGGER requirement_seal_children;
CREATE TRIGGER requirement_seal_children BEFORE UPDATE ON requirement_versions WHEN NEW.sealed_at IS NOT NULL AND (SELECT count(*) FROM acceptance_criteria WHERE project_id=NEW.project_id AND requirement_id=NEW.id AND requirement_revision=NEW.revision)<1 AND NOT EXISTS(SELECT 1 FROM record_origins WHERE project_id=NEW.project_id AND kind='requirement' AND record_id=NEW.id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'aggregate needs children'); END;

DROP TRIGGER work_item_seal_children;
CREATE TRIGGER work_item_seal_children BEFORE UPDATE ON work_item_versions WHEN NEW.sealed_at IS NOT NULL AND (SELECT count(*) FROM work_checks WHERE project_id=NEW.project_id AND work_item_id=NEW.id AND work_revision=NEW.revision)<1 AND NOT EXISTS(SELECT 1 FROM record_origins WHERE project_id=NEW.project_id AND kind='work_item' AND record_id=NEW.id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'aggregate needs children'); END;

DROP TRIGGER work_full_plan;
CREATE TRIGGER work_full_plan BEFORE UPDATE ON work_item_versions WHEN NEW.sealed_at IS NOT NULL AND NEW.workflow_depth='full' AND (NOT EXISTS(SELECT 1 FROM work_item_plan_items WHERE project_id=NEW.project_id AND work_item_id=NEW.id AND work_revision=NEW.revision) OR NOT EXISTS(SELECT 1 FROM work_item_requirements WHERE project_id=NEW.project_id AND work_item_id=NEW.id AND work_item_revision=NEW.revision)) AND NOT EXISTS(SELECT 1 FROM record_origins WHERE project_id=NEW.project_id AND kind='work_item' AND record_id=NEW.id AND revision=NEW.revision) BEGIN SELECT RAISE(ABORT,'full work needs plan and requirement'); END;
