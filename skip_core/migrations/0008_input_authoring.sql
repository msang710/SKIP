-- Rebuild only the request discriminator. Existing rows and references retain IDs.
CREATE TABLE requests_next (
 project_id TEXT NOT NULL, id TEXT NOT NULL, interaction_id TEXT NOT NULL,
 operation TEXT NOT NULL CHECK(operation IN ('investigate','plan','implement','deploy','record')),
 intent TEXT NOT NULL, intent_digest TEXT NOT NULL CHECK(length(intent_digest)=64), created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,id), UNIQUE(project_id,interaction_id),
 FOREIGN KEY(project_id,interaction_id) REFERENCES verified_interactions(project_id,interaction_id) ON DELETE RESTRICT
) STRICT;
INSERT INTO requests_next SELECT * FROM requests;
DROP TABLE requests;
ALTER TABLE requests_next RENAME TO requests;
CREATE TABLE input_intent_versions (
 project_id TEXT NOT NULL, input_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
 body_json TEXT NOT NULL CHECK(json_valid(body_json)), digest TEXT NOT NULL, event_id TEXT NOT NULL,
 PRIMARY KEY(project_id,input_id,revision),
 FOREIGN KEY(project_id,input_id) REFERENCES input_envelopes(project_id,input_id),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE input_materializations (
 project_id TEXT NOT NULL, input_id TEXT NOT NULL, revision INTEGER NOT NULL,
 request_id TEXT NOT NULL, goal_id TEXT NOT NULL, payload_digest TEXT NOT NULL, receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 PRIMARY KEY(project_id,input_id),
 FOREIGN KEY(project_id,input_id,revision) REFERENCES input_intent_versions(project_id,input_id,revision),
 FOREIGN KEY(project_id,request_id) REFERENCES requests(project_id,id),
 FOREIGN KEY(project_id,goal_id) REFERENCES goals(project_id,id)
) STRICT;
CREATE TRIGGER input_intent_no_update BEFORE UPDATE ON input_intent_versions BEGIN SELECT RAISE(ABORT,'immutable input interpretation'); END;
CREATE TRIGGER input_intent_no_delete BEFORE DELETE ON input_intent_versions BEGIN SELECT RAISE(ABORT,'immutable input interpretation'); END;
CREATE TRIGGER input_materialization_no_update BEFORE UPDATE ON input_materializations BEGIN SELECT RAISE(ABORT,'immutable input materialization'); END;
CREATE TRIGGER input_materialization_no_delete BEFORE DELETE ON input_materializations BEGIN SELECT RAISE(ABORT,'immutable input materialization'); END;
