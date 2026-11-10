PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS schema_version(version TEXT PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES ('dav-import-v1');
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('synthetic','dav')),
 source_url TEXT NOT NULL, snapshot_at TEXT NOT NULL, artifact_sha256 TEXT NOT NULL,
 artifact_path TEXT NOT NULL, manifest_json TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
 config_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS batches (
 id TEXT PRIMARY KEY REFERENCES sources(id), last_row INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL CHECK(state IN ('RUNNING','PAUSED','COMPLETE','FAILED')),
 error TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS medications (
 id TEXT PRIMARY KEY, signature TEXT NOT NULL UNIQUE, brand_raw TEXT NOT NULL,
 manufacturer_raw TEXT NOT NULL, dosage_form_raw TEXT NOT NULL, dosage_form TEXT,
 route_raw TEXT, synthetic INTEGER NOT NULL CHECK(synthetic IN (0,1)),
 verification_status TEXT NOT NULL CHECK(verification_status IN
 ('REVIEW_REQUIRED','AMBIGUOUS','UNRESOLVED','VERIFIED','REJECTED'))
);
CREATE TABLE IF NOT EXISTS ingredients (
 id TEXT PRIMARY KEY, name_key TEXT NOT NULL, source_name TEXT NOT NULL,
 synthetic INTEGER NOT NULL CHECK(synthetic IN (0,1)), UNIQUE(name_key,synthetic)
);
CREATE TABLE IF NOT EXISTS components (
 medication_id TEXT NOT NULL REFERENCES medications(id), ordinal INTEGER NOT NULL,
 ingredient_id TEXT NOT NULL REFERENCES ingredients(id), name_raw TEXT NOT NULL,
 strength_raw TEXT NOT NULL, strength_json TEXT NOT NULL, basis_raw TEXT,
 verification_status TEXT NOT NULL DEFAULT 'REVIEW_REQUIRED' CHECK(verification_status IN
 ('REVIEW_REQUIRED','AMBIGUOUS','UNRESOLVED','VERIFIED','REJECTED')),
 PRIMARY KEY(medication_id,ordinal)
);
CREATE TABLE IF NOT EXISTS registrations (
 id TEXT PRIMARY KEY, identifier_raw TEXT NOT NULL, identifier_key TEXT NOT NULL,
 synthetic INTEGER NOT NULL CHECK(synthetic IN (0,1)),
 UNIQUE(identifier_key,synthetic)
);
CREATE TABLE IF NOT EXISTS observations (
 id TEXT PRIMARY KEY, raw_sha256 TEXT NOT NULL, raw_json TEXT NOT NULL,
 normalized_json TEXT NOT NULL, transform_sha256 TEXT NOT NULL, medication_id TEXT REFERENCES medications(id),
 registration_id TEXT REFERENCES registrations(id), synthetic INTEGER NOT NULL,
 validation_status TEXT NOT NULL CHECK(validation_status IN ('VALID','REVIEW_REQUIRED','QUARANTINED')),
 UNIQUE(raw_sha256,synthetic,transform_sha256)
);
CREATE TABLE IF NOT EXISTS raw_records (
 source_id TEXT NOT NULL REFERENCES sources(id), row_number INTEGER NOT NULL,
 locator_json TEXT NOT NULL, raw_json TEXT NOT NULL, raw_sha256 TEXT NOT NULL,
 observation_id TEXT NOT NULL REFERENCES observations(id),
 PRIMARY KEY(source_id,row_number)
);
CREATE TABLE IF NOT EXISTS issues (
 observation_id TEXT NOT NULL REFERENCES observations(id), code TEXT NOT NULL,
 severity TEXT NOT NULL CHECK(severity IN ('ERROR','WARNING')), detail TEXT NOT NULL,
 PRIMARY KEY(observation_id,code)
);
CREATE TABLE IF NOT EXISTS registration_events (
 id TEXT PRIMARY KEY, registration_id TEXT NOT NULL REFERENCES registrations(id),
 medication_id TEXT NOT NULL REFERENCES medications(id),
 observation_id TEXT NOT NULL UNIQUE REFERENCES observations(id), event_type TEXT NOT NULL,
 decision_raw TEXT, effective_date TEXT, valid_until TEXT, claimed_status_raw TEXT,
 current_authorization_status TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK(current_authorization_status='UNKNOWN')
);
CREATE TABLE IF NOT EXISTS registration_links (
 observation_id TEXT PRIMARY KEY REFERENCES observations(id),
 registration_id TEXT NOT NULL REFERENCES registrations(id), previous_identifier_raw TEXT NOT NULL,
 relation TEXT NOT NULL DEFAULT 'SOURCE_CLAIM_UNVERIFIED'
);
CREATE TABLE IF NOT EXISTS reviews (
 id INTEGER PRIMARY KEY, entity_type TEXT NOT NULL CHECK(entity_type IN ('medication','registration','mapping')),
 entity_id TEXT NOT NULL, scope TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN
 ('VERIFIED','REJECTED','REVIEW_REQUIRED','AMBIGUOUS','UNRESOLVED')),
 reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL, as_of_date TEXT,
 evidence_json TEXT NOT NULL, note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS terminology_mappings (
 id TEXT PRIMARY KEY, ingredient_id TEXT NOT NULL REFERENCES ingredients(id),
 namespace TEXT NOT NULL CHECK(namespace IN ('RxNorm','DDInter')),
 release TEXT NOT NULL, adapter_version TEXT NOT NULL, input_name TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('CANDIDATE','AMBIGUOUS','UNRESOLVED','REJECTED')),
 target_id TEXT, target_name TEXT, concept_type TEXT, evidence_json TEXT NOT NULL,
 candidates_json TEXT NOT NULL, UNIQUE(ingredient_id,namespace,release,adapter_version)
);
CREATE INDEX IF NOT EXISTS events_registration ON registration_events(registration_id);
CREATE INDEX IF NOT EXISTS events_medication ON registration_events(medication_id);
CREATE INDEX IF NOT EXISTS raw_observation ON raw_records(observation_id);
CREATE INDEX IF NOT EXISTS observation_medication ON observations(medication_id);
CREATE INDEX IF NOT EXISTS observation_registration ON observations(registration_id);
CREATE INDEX IF NOT EXISTS issue_code ON issues(code);
CREATE INDEX IF NOT EXISTS component_ingredient ON components(ingredient_id);
CREATE INDEX IF NOT EXISTS review_entity ON reviews(entity_type,entity_id,scope,id);
CREATE VIEW IF NOT EXISTS medication_reference AS
 SELECT m.*, 'UNKNOWN' AS current_authorization_status,
 (SELECT r.status FROM reviews r WHERE r.entity_type='medication' AND r.entity_id=m.id
  AND r.scope='historical_identity' ORDER BY r.id DESC LIMIT 1) AS independent_review_status
 FROM medications m;
