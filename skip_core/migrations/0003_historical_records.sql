-- One-time, user-requested migration. Imported claims confer no execution authority.
CREATE TABLE record_imports (
 id TEXT PRIMARY KEY, inventory_digest TEXT NOT NULL UNIQUE, file_count INTEGER NOT NULL,
 request_text TEXT NOT NULL, created_at TEXT NOT NULL
) STRICT;
CREATE TABLE imported_documents (
 project_id TEXT NOT NULL, id TEXT NOT NULL, import_id TEXT NOT NULL, goal_id TEXT,
 source_path TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
 content BLOB NOT NULL, content_sha256 TEXT NOT NULL, body_text TEXT, metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
 historical_status TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(project_id,id), UNIQUE(project_id,source_path),
 FOREIGN KEY(project_id) REFERENCES projects(id),
 FOREIGN KEY(import_id) REFERENCES record_imports(id),
 FOREIGN KEY(project_id,goal_id) REFERENCES goals(project_id,id)
) STRICT;
CREATE TABLE imported_sections (
 project_id TEXT NOT NULL, document_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 heading TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
 PRIMARY KEY(project_id,document_id,ordinal),
 FOREIGN KEY(project_id,document_id) REFERENCES imported_documents(project_id,id)
) STRICT;
CREATE TABLE imported_links (
 project_id TEXT NOT NULL, document_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 label TEXT NOT NULL, target_text TEXT NOT NULL, target_document_id TEXT,
 resolution TEXT NOT NULL CHECK(resolution IN ('resolved','external','unresolved')),
 PRIMARY KEY(project_id,document_id,ordinal),
 FOREIGN KEY(project_id,document_id) REFERENCES imported_documents(project_id,id),
 FOREIGN KEY(project_id,target_document_id) REFERENCES imported_documents(project_id,id)
) STRICT;
CREATE TABLE imported_record_refs (
 project_id TEXT NOT NULL, document_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 requirement_id TEXT, requirement_revision INTEGER,
 plan_id TEXT, plan_revision INTEGER, work_item_id TEXT, work_revision INTEGER,
 CHECK((requirement_id IS NOT NULL)+(plan_id IS NOT NULL)+(work_item_id IS NOT NULL)=1),
 CHECK((requirement_id IS NULL)=(requirement_revision IS NULL)),
 CHECK((plan_id IS NULL)=(plan_revision IS NULL)),
 CHECK((work_item_id IS NULL)=(work_revision IS NULL)),
 PRIMARY KEY(project_id,document_id,ordinal),
 FOREIGN KEY(project_id,document_id) REFERENCES imported_documents(project_id,id),
 FOREIGN KEY(project_id,requirement_id,requirement_revision) REFERENCES requirement_versions(project_id,id,revision),
 FOREIGN KEY(project_id,plan_id,plan_revision) REFERENCES plan_versions(project_id,id,revision),
 FOREIGN KEY(project_id,work_item_id,work_revision) REFERENCES work_item_versions(project_id,id,revision)
) STRICT;
CREATE TABLE project_identities (
 project_id TEXT NOT NULL, repository_identity TEXT NOT NULL, relative_root TEXT NOT NULL,
 PRIMARY KEY(project_id,repository_identity,relative_root),
 FOREIGN KEY(project_id) REFERENCES projects(id)
) STRICT;
CREATE INDEX imported_goal ON imported_documents(project_id,goal_id,kind,source_path);
CREATE INDEX imported_section_kind ON imported_sections(project_id,kind,document_id);
CREATE TRIGGER imported_documents_immutable_update BEFORE UPDATE ON imported_documents BEGIN SELECT RAISE(ABORT,'historical original is immutable'); END;
CREATE TRIGGER imported_documents_immutable_delete BEFORE DELETE ON imported_documents BEGIN SELECT RAISE(ABORT,'historical original deletion disabled'); END;
CREATE TRIGGER imported_sections_immutable_update BEFORE UPDATE ON imported_sections BEGIN SELECT RAISE(ABORT,'historical section is immutable'); END;
CREATE TRIGGER imported_sections_immutable_delete BEFORE DELETE ON imported_sections BEGIN SELECT RAISE(ABORT,'historical section deletion disabled'); END;
