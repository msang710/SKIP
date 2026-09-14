CREATE TABLE project_profile_versions (
 project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL CHECK(revision>0),
 base_revision INTEGER, tagline TEXT NOT NULL, body_markdown TEXT NOT NULL, content_digest TEXT NOT NULL,
 created_event_id TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,revision), FOREIGN KEY(project_id,created_event_id) REFERENCES events(project_id,id),
 FOREIGN KEY(project_id,base_revision) REFERENCES project_profile_versions(project_id,revision)
) STRICT;
CREATE TABLE project_profiles (
 project_id TEXT PRIMARY KEY REFERENCES projects(id), accepted_revision INTEGER,
 FOREIGN KEY(project_id,accepted_revision) REFERENCES project_profile_versions(project_id,revision)
) STRICT;
CREATE TABLE project_profile_reviews (
 project_id TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL, action TEXT NOT NULL CHECK(action IN ('accepted','rejected')),
 event_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(project_id,id),
 FOREIGN KEY(project_id,revision) REFERENCES project_profile_versions(project_id,revision),
 FOREIGN KEY(project_id,event_id) REFERENCES events(project_id,id)
) STRICT;
CREATE TABLE project_participations (
 project_id TEXT NOT NULL REFERENCES projects(id),id TEXT NOT NULL,identity_namespace TEXT NOT NULL,
 identity_key TEXT NOT NULL,agent_id TEXT,session_id TEXT NOT NULL,first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,
 PRIMARY KEY(project_id,id),UNIQUE(project_id,identity_namespace,identity_key)
) STRICT;
CREATE TABLE project_profile_reads (
 project_id TEXT NOT NULL,id TEXT NOT NULL,participation_id TEXT NOT NULL,profile_revision INTEGER NOT NULL,
 profile_digest TEXT NOT NULL,read_at TEXT NOT NULL,route TEXT NOT NULL,receipt_key TEXT NOT NULL,
 PRIMARY KEY(project_id,id),UNIQUE(project_id,participation_id,receipt_key),
 FOREIGN KEY(project_id,participation_id) REFERENCES project_participations(project_id,id),
 FOREIGN KEY(project_id,profile_revision) REFERENCES project_profile_versions(project_id,revision)
) STRICT;
CREATE TRIGGER profile_versions_no_update BEFORE UPDATE ON project_profile_versions BEGIN SELECT RAISE(ABORT,'immutable profile version'); END;
CREATE TRIGGER profile_versions_no_delete BEFORE DELETE ON project_profile_versions BEGIN SELECT RAISE(ABORT,'immutable profile version'); END;
CREATE TRIGGER profile_reviews_no_update BEFORE UPDATE ON project_profile_reviews BEGIN SELECT RAISE(ABORT,'immutable profile review'); END;
CREATE TRIGGER profile_reviews_no_delete BEFORE DELETE ON project_profile_reviews BEGIN SELECT RAISE(ABORT,'immutable profile review'); END;
CREATE INDEX profile_reads_participant ON project_profile_reads(project_id,participation_id,read_at);
