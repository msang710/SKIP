-- Typed version registry: prose remains JSON text; identities and references are relational.
CREATE TABLE learning_records (
 project_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('failure','guideline','claim','boundary','environment','obligation','scenario')),
 id TEXT NOT NULL, current_revision INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(project_id,kind,id),
 FOREIGN KEY(project_id) REFERENCES projects(id)
) STRICT;
CREATE TABLE learning_versions (
 project_id TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
 goal_id TEXT, goal_revision INTEGER, body_json TEXT NOT NULL CHECK(json_valid(body_json)), digest TEXT NOT NULL,
 event_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,kind,id,revision),
 FOREIGN KEY(project_id,kind,id) REFERENCES learning_records(project_id,kind,id),
 FOREIGN KEY(project_id,goal_id,goal_revision) REFERENCES goal_versions(project_id,id,revision),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE learning_links (
 project_id TEXT NOT NULL, owner_kind TEXT NOT NULL, owner_id TEXT NOT NULL, owner_revision INTEGER NOT NULL,
 role TEXT NOT NULL, target_kind TEXT NOT NULL, target_id TEXT NOT NULL, target_revision INTEGER NOT NULL,
 PRIMARY KEY(project_id,owner_kind,owner_id,owner_revision,role,target_kind,target_id,target_revision),
 FOREIGN KEY(project_id,owner_kind,owner_id,owner_revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,target_kind,target_id,target_revision) REFERENCES learning_versions(project_id,kind,id,revision)
) STRICT;
CREATE TABLE learning_acceptances (
 project_id TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL, selection_id TEXT NOT NULL, contract_digest TEXT NOT NULL,
 event_id TEXT NOT NULL, PRIMARY KEY(project_id,kind,id,revision),
 FOREIGN KEY(project_id,kind,id,revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,selection_id) REFERENCES selections(project_id,id),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE failure_occurrences (
 project_id TEXT NOT NULL,id TEXT NOT NULL,case_kind TEXT NOT NULL DEFAULT 'failure' CHECK(case_kind='failure'),case_id TEXT NOT NULL,case_revision INTEGER NOT NULL,
 evidence_id TEXT NOT NULL, classification TEXT NOT NULL CHECK(classification IN ('product','tool','reported','injected','unclassified')),
 event_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(project_id,id),UNIQUE(project_id,evidence_id),
 FOREIGN KEY(project_id,case_kind,case_id,case_revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,evidence_id) REFERENCES evidence(project_id,id),FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE failure_attempts (
 project_id TEXT NOT NULL,id TEXT NOT NULL,case_kind TEXT NOT NULL DEFAULT 'failure' CHECK(case_kind='failure'),case_id TEXT NOT NULL,case_revision INTEGER NOT NULL,
 evidence_id TEXT NOT NULL,action_body TEXT NOT NULL, event_id TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(project_id,id),
 FOREIGN KEY(project_id,case_kind,case_id,case_revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,evidence_id) REFERENCES evidence(project_id,id),FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE guideline_assessments (
 project_id TEXT NOT NULL,id TEXT NOT NULL,guideline_kind TEXT NOT NULL DEFAULT 'guideline' CHECK(guideline_kind='guideline'),guideline_id TEXT NOT NULL,guideline_revision INTEGER NOT NULL,
 goal_id TEXT NOT NULL,goal_revision INTEGER NOT NULL,work_id TEXT,work_revision INTEGER,snapshot_id TEXT NOT NULL,
 applicability TEXT NOT NULL CHECK(applicability IN ('applies','not_applicable','unknown')),
 outcome TEXT NOT NULL CHECK(outcome IN ('not_tested','reproduced','not_reproduced','inconclusive')),
 rationale TEXT NOT NULL,evidence_id TEXT NOT NULL,basis_digest TEXT NOT NULL,event_id TEXT NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,id),FOREIGN KEY(project_id,guideline_kind,guideline_id,guideline_revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,goal_id,goal_revision) REFERENCES goal_versions(project_id,id,revision),
 FOREIGN KEY(project_id,work_id,work_revision) REFERENCES work_item_versions(project_id,id,revision),
 FOREIGN KEY(project_id,snapshot_id) REFERENCES snapshots(project_id,id),FOREIGN KEY(project_id,evidence_id) REFERENCES evidence(project_id,id),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE verification_runs (
 project_id TEXT NOT NULL,id TEXT NOT NULL,scenario_kind TEXT NOT NULL DEFAULT 'scenario' CHECK(scenario_kind='scenario'),scenario_id TEXT NOT NULL,scenario_revision INTEGER NOT NULL,
 snapshot_id TEXT NOT NULL,environment_evidence_id TEXT NOT NULL,environment_json TEXT NOT NULL CHECK(json_valid(environment_json)),
 execution_id TEXT, started_event_id TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(project_id,id),
 FOREIGN KEY(project_id,scenario_kind,scenario_id,scenario_revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,snapshot_id) REFERENCES snapshots(project_id,id),FOREIGN KEY(project_id,environment_evidence_id) REFERENCES evidence(project_id,id),
 FOREIGN KEY(project_id,execution_id) REFERENCES executions(project_id,id),FOREIGN KEY(project_id,started_event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE verification_results (
 project_id TEXT NOT NULL,run_id TEXT NOT NULL,injection TEXT NOT NULL CHECK(injection IN ('PASS','FAIL','NOT_RUN','INCONCLUSIVE')),
 behavior TEXT NOT NULL CHECK(behavior IN ('PASS','FAIL','NOT_RUN','INCONCLUSIVE')),recovery TEXT NOT NULL CHECK(recovery IN ('PASS','FAIL','NOT_RUN','INCONCLUSIVE')),
 evidence_id TEXT NOT NULL,trace_json TEXT NOT NULL CHECK(json_valid(trace_json)),event_id TEXT NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,run_id),FOREIGN KEY(project_id,run_id) REFERENCES verification_runs(project_id,id),
 FOREIGN KEY(project_id,evidence_id) REFERENCES evidence(project_id,id),FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE assurance_evaluations (
 project_id TEXT NOT NULL,id TEXT NOT NULL,claim_kind TEXT NOT NULL DEFAULT 'claim' CHECK(claim_kind='claim'),claim_id TEXT NOT NULL,claim_revision INTEGER NOT NULL,
 snapshot_id TEXT NOT NULL,body_json TEXT NOT NULL CHECK(json_valid(body_json)),basis_digest TEXT NOT NULL,event_id TEXT NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,id),FOREIGN KEY(project_id,claim_kind,claim_id,claim_revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,snapshot_id) REFERENCES snapshots(project_id,id),FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE INDEX learning_goal ON learning_versions(project_id,goal_id,kind,id,revision);
CREATE INDEX learning_target ON learning_links(project_id,target_kind,target_id,target_revision,role);
CREATE INDEX assessment_goal ON guideline_assessments(project_id,goal_id,guideline_id,created_at);
CREATE INDEX runs_scenario ON verification_runs(project_id,scenario_id,scenario_revision);
CREATE TRIGGER learning_head_exists BEFORE UPDATE OF current_revision ON learning_records WHEN NOT EXISTS(SELECT 1 FROM learning_versions v WHERE v.project_id=NEW.project_id AND v.kind=NEW.kind AND v.id=NEW.id AND v.revision=NEW.current_revision) BEGIN SELECT RAISE(ABORT,'learning head requires version'); END;
CREATE TRIGGER learning_versions_immutable_update BEFORE UPDATE ON learning_versions BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER learning_versions_immutable_delete BEFORE DELETE ON learning_versions BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER learning_links_immutable_update BEFORE UPDATE ON learning_links BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER learning_links_immutable_delete BEFORE DELETE ON learning_links BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER learning_acceptances_immutable_update BEFORE UPDATE ON learning_acceptances BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER learning_acceptances_immutable_delete BEFORE DELETE ON learning_acceptances BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER failure_occurrences_immutable_update BEFORE UPDATE ON failure_occurrences BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER failure_occurrences_immutable_delete BEFORE DELETE ON failure_occurrences BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER failure_attempts_immutable_update BEFORE UPDATE ON failure_attempts BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER failure_attempts_immutable_delete BEFORE DELETE ON failure_attempts BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER guideline_assessments_immutable_update BEFORE UPDATE ON guideline_assessments BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER guideline_assessments_immutable_delete BEFORE DELETE ON guideline_assessments BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER verification_runs_immutable_update BEFORE UPDATE ON verification_runs BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER verification_runs_immutable_delete BEFORE DELETE ON verification_runs BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER verification_results_immutable_update BEFORE UPDATE ON verification_results BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER verification_results_immutable_delete BEFORE DELETE ON verification_results BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER assurance_evaluations_immutable_update BEFORE UPDATE ON assurance_evaluations BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TRIGGER assurance_evaluations_immutable_delete BEFORE DELETE ON assurance_evaluations BEGIN SELECT RAISE(ABORT,'immutable learning record'); END;
CREATE TABLE learning_evidence (
 project_id TEXT NOT NULL,kind TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,evidence_id TEXT NOT NULL,role TEXT NOT NULL,
 PRIMARY KEY(project_id,kind,id,revision,evidence_id,role),
 FOREIGN KEY(project_id,kind,id,revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,evidence_id) REFERENCES evidence(project_id,id)
) STRICT;
CREATE TRIGGER learning_evidence_update BEFORE UPDATE ON learning_evidence BEGIN SELECT RAISE(ABORT,'immutable evidence link'); END;
CREATE TRIGGER learning_evidence_delete BEFORE DELETE ON learning_evidence BEGIN SELECT RAISE(ABORT,'immutable evidence link'); END;
CREATE TABLE learning_scopes (
 project_id TEXT NOT NULL,kind TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,scope_id TEXT NOT NULL,
 PRIMARY KEY(project_id,kind,id,revision),
 FOREIGN KEY(project_id,kind,id,revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,scope_id) REFERENCES scopes(project_id,id)
) STRICT;
CREATE TABLE obligation_work_checks (
 project_id TEXT NOT NULL,obligation_kind TEXT NOT NULL DEFAULT 'obligation' CHECK(obligation_kind='obligation'),obligation_id TEXT NOT NULL,obligation_revision INTEGER NOT NULL,
 work_id TEXT NOT NULL,work_revision INTEGER NOT NULL,check_id TEXT NOT NULL,
 PRIMARY KEY(project_id,obligation_id,obligation_revision,work_id,work_revision,check_id),
 FOREIGN KEY(project_id,obligation_kind,obligation_id,obligation_revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,work_id,work_revision,check_id) REFERENCES work_checks(project_id,work_item_id,work_revision,check_id)
) STRICT;
CREATE TABLE assurance_exceptions (
 project_id TEXT NOT NULL,id TEXT NOT NULL,obligation_kind TEXT NOT NULL DEFAULT 'obligation' CHECK(obligation_kind='obligation'),obligation_id TEXT NOT NULL,obligation_revision INTEGER NOT NULL,
 snapshot_id TEXT NOT NULL,selection_id TEXT NOT NULL,rationale TEXT NOT NULL,event_id TEXT NOT NULL,created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,id), FOREIGN KEY(project_id,obligation_kind,obligation_id,obligation_revision) REFERENCES learning_versions(project_id,kind,id,revision),
 FOREIGN KEY(project_id,snapshot_id) REFERENCES snapshots(project_id,id),FOREIGN KEY(project_id,selection_id) REFERENCES selections(project_id,id),FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TRIGGER learning_scopes_update BEFORE UPDATE ON learning_scopes BEGIN SELECT RAISE(ABORT,'immutable scope'); END;
CREATE TRIGGER learning_scopes_delete BEFORE DELETE ON learning_scopes BEGIN SELECT RAISE(ABORT,'immutable scope'); END;
CREATE TRIGGER obligation_work_checks_update BEFORE UPDATE ON obligation_work_checks BEGIN SELECT RAISE(ABORT,'immutable check'); END;
CREATE TRIGGER obligation_work_checks_delete BEFORE DELETE ON obligation_work_checks BEGIN SELECT RAISE(ABORT,'immutable check'); END;
CREATE TRIGGER assurance_exceptions_update BEFORE UPDATE ON assurance_exceptions BEGIN SELECT RAISE(ABORT,'immutable exception'); END;
CREATE TRIGGER assurance_exceptions_delete BEFORE DELETE ON assurance_exceptions BEGIN SELECT RAISE(ABORT,'immutable exception'); END;
CREATE TRIGGER learning_head_new BEFORE INSERT ON learning_records WHEN NEW.current_revision<>0 BEGIN SELECT RAISE(ABORT,'new learning aggregate starts empty'); END;
