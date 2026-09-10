CREATE TABLE input_envelopes (
 project_id TEXT NOT NULL, input_id TEXT NOT NULL, route TEXT NOT NULL, verification TEXT NOT NULL,
 body_json TEXT NOT NULL CHECK(json_valid(body_json)), digest TEXT NOT NULL, event_id TEXT NOT NULL,
 PRIMARY KEY(project_id,input_id), FOREIGN KEY(project_id,input_id) REFERENCES interactions(project_id,id),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE intent_interpretations (
 project_id TEXT NOT NULL, request_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0), input_id TEXT NOT NULL,
 body_json TEXT NOT NULL CHECK(json_valid(body_json)), digest TEXT NOT NULL, event_id TEXT NOT NULL,
 PRIMARY KEY(project_id,request_id,revision), FOREIGN KEY(project_id,request_id) REFERENCES requests(project_id,id),
 FOREIGN KEY(project_id,input_id) REFERENCES input_envelopes(project_id,input_id), FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE action_proposals (
 project_id TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),request_id TEXT NOT NULL,
 body_json TEXT NOT NULL CHECK(json_valid(body_json)),digest TEXT NOT NULL,event_id TEXT NOT NULL,
 PRIMARY KEY(project_id,id,revision), FOREIGN KEY(project_id,request_id) REFERENCES requests(project_id,id),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE response_bindings (
 project_id TEXT NOT NULL,input_id TEXT NOT NULL,proposal_id TEXT NOT NULL,proposal_revision INTEGER NOT NULL,
 basis_digest TEXT NOT NULL,event_id TEXT NOT NULL,
 PRIMARY KEY(project_id,input_id), FOREIGN KEY(project_id,input_id) REFERENCES input_envelopes(project_id,input_id),
 FOREIGN KEY(project_id,proposal_id,proposal_revision) REFERENCES action_proposals(project_id,id,revision),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE INDEX entry_request_input ON intent_interpretations(project_id,input_id);
CREATE TRIGGER input_envelopes_no_update BEFORE UPDATE ON input_envelopes BEGIN SELECT RAISE(ABORT,'immutable entry history'); END;
CREATE TRIGGER input_envelopes_no_delete BEFORE DELETE ON input_envelopes BEGIN SELECT RAISE(ABORT,'immutable entry history'); END;
CREATE TRIGGER intent_interpretations_no_update BEFORE UPDATE ON intent_interpretations BEGIN SELECT RAISE(ABORT,'immutable entry history'); END;
CREATE TRIGGER intent_interpretations_no_delete BEFORE DELETE ON intent_interpretations BEGIN SELECT RAISE(ABORT,'immutable entry history'); END;
CREATE TRIGGER action_proposals_no_update BEFORE UPDATE ON action_proposals BEGIN SELECT RAISE(ABORT,'immutable entry history'); END;
CREATE TRIGGER action_proposals_no_delete BEFORE DELETE ON action_proposals BEGIN SELECT RAISE(ABORT,'immutable entry history'); END;
CREATE TRIGGER response_bindings_no_update BEFORE UPDATE ON response_bindings BEGIN SELECT RAISE(ABORT,'immutable entry history'); END;
CREATE TRIGGER response_bindings_no_delete BEFORE DELETE ON response_bindings BEGIN SELECT RAISE(ABORT,'immutable entry history'); END;
