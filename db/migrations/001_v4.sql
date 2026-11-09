-- Core Database V4. Exactly 20 owned tables / 193 attributes.
-- Requires existing identity.users(id uuid PRIMARY KEY/UNIQUE); never alters identity.
-- New baseline, not an upgrade of the retired prototype. Applied transactionally by manage.py.
CREATE SCHEMA msa_ref;
CREATE SCHEMA msa;

CREATE FUNCTION msa.is_hash(value text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT coalesce(value ~ '^[0-9a-f]{64}$',false)
$$;
CREATE FUNCTION msa.is_uuid(value text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT coalesce(value ~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',false)
$$;
-- Canonical contract pg-jsonb-text-v4: SHA256(UTF8 PostgreSQL JSONB::text).
-- All application hashes go through this function, not a client JSON serializer.
CREATE FUNCTION msa.digest(doc jsonb) RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
 SELECT encode(sha256(convert_to(doc::text,'UTF8')),'hex')
$$;
CREATE FUNCTION msa.summary_digest(content jsonb, manifest jsonb) RETURNS text
 LANGUAGE sql IMMUTABLE STRICT AS $$ SELECT msa.digest(jsonb_build_array(content,manifest)) $$;
CREATE FUNCTION msa.health_digest(origin text, content jsonb, source_date date, verification text, locator jsonb)
 RETURNS text LANGUAGE sql IMMUTABLE SET DateStyle='ISO, YMD' AS $$
 SELECT msa.digest(jsonb_build_array(origin,content,source_date,verification,locator))
$$;
CREATE FUNCTION msa.jtype(doc jsonb, key text, expected text, nullable boolean DEFAULT false)
 RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT coalesce(jsonb_typeof(doc)='object' AND doc ? key
  AND (jsonb_typeof(doc->key)=expected OR (nullable AND doc->key='null'::jsonb)),false)
$$;
CREATE FUNCTION msa.keys(doc jsonb, required text[]) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT coalesce(jsonb_typeof(doc)='object' AND doc ?& required,false)
$$;
CREATE FUNCTION msa.string_array(doc jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT coalesce(jsonb_typeof(doc)='array' AND NOT EXISTS(
  SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof(doc)='array' THEN doc ELSE '[]' END) a
  WHERE jsonb_typeof(a)<>'string'),false)
$$;
CREATE FUNCTION msa.valid_document(doc jsonb, tag text) RETURNS boolean
 LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE e jsonb; k text; t jsonb; seen text[] := '{}';
BEGIN
 IF NOT msa.keys(doc,ARRAY['schema']) OR doc->>'schema' IS DISTINCT FROM tag THEN RETURN false; END IF;
 CASE tag
 WHEN 'csv-source.v4' THEN
  IF NOT msa.keys(doc,ARRAY['csv','artifact_sha256','source_id','source_record_id','source_ref','rule_version','manifest_locator'])
   OR NOT msa.jtype(doc,'csv','string') OR NOT msa.is_hash(doc->>'artifact_sha256')
   OR NOT msa.jtype(doc,'source_id','string') OR btrim(doc->>'source_id')=''
   OR NOT msa.jtype(doc,'source_record_id','string',true) OR NOT msa.jtype(doc,'rule_version','string',true)
   OR NOT msa.jtype(doc,'source_ref','object') OR doc->'source_ref'->>'id' IS DISTINCT FROM doc->>'source_id'
   OR NOT msa.jtype(doc,'manifest_locator','object') THEN RETURN false; END IF;
  t:=doc->'manifest_locator';
  IF NOT msa.jtype(t,'uri','string') OR btrim(t->>'uri')='' OR NOT msa.is_hash(t->>'artifact_sha256') THEN RETURN false; END IF;
  IF doc ? 'source_attributes' AND NOT msa.jtype(doc,'source_attributes','object') THEN RETURN false; END IF;
  IF doc ? 'legacy_review' AND NOT msa.jtype(doc,'legacy_review','object') THEN RETURN false; END IF;
 WHEN 'product-details.v4' THEN
  FOREACH k IN ARRAY ARRAY['registration_token','registration_number_source','packaging','release_characteristic','route_status','release_status','dosage_form_status'] LOOP
   IF NOT msa.jtype(doc,k,'string',true) THEN RETURN false; END IF;
  END LOOP;
  IF NOT msa.jtype(doc,'source_identity_definition','object') THEN RETURN false; END IF;
 WHEN 'strength-basis.v4' THEN
  FOREACH k IN ARRAY ARRAY['expression_raw','primary_strength_assertion_id','strength_source_status','strength_transform_status'] LOOP
   IF NOT msa.jtype(doc,k,'string',true) THEN RETURN false; END IF;
  END LOOP;
  IF NOT doc ? 'strength_basis_verified' OR NOT msa.jtype(doc,'numeric_assertions','array') THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'numeric_assertions') LOOP
   IF NOT msa.keys(e,ARRAY['source_assertion_id','numerator_value','numerator_unit','denominator_value','denominator_unit','basis_raw','source_locator'])
    OR NOT msa.jtype(e,'source_assertion_id','string')
    OR NOT msa.jtype(e,'numerator_value','number',true) OR NOT msa.jtype(e,'numerator_unit','string',true)
    OR NOT msa.jtype(e,'denominator_value','number',true) OR NOT msa.jtype(e,'denominator_unit','string',true)
    OR NOT msa.jtype(e,'basis_raw','string',true)
    OR NOT msa.valid_document(e->'source_locator','csv-source.v4') THEN RETURN false; END IF;
   IF ((e->>'numerator_value') IS NULL) <> ((e->>'numerator_unit') IS NULL)
    OR ((e->>'denominator_value') IS NULL) <> ((e->>'denominator_unit') IS NULL)
    OR (e->>'denominator_value' IS NOT NULL AND e->>'numerator_value' IS NULL) THEN RETURN false; END IF;
   IF (e->>'numerator_value')::numeric<=0 OR (e->>'denominator_value')::numeric<=0 THEN RETURN false; END IF;
  END LOOP;
 WHEN 'message.v4' THEN
  IF NOT msa.jtype(doc,'content_refs','array') THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'content_refs') LOOP
   IF NOT msa.jtype(e,'kind','string') OR NOT msa.jtype(e,'locator','object') OR NOT msa.is_hash(e->>'artifact_sha256') THEN RETURN false; END IF;
  END LOOP;
  IF doc ? 'grounding' AND NOT msa.jtype(doc,'grounding','array') THEN RETURN false; END IF;
  IF doc ? 'intent_candidates' AND NOT msa.jtype(doc,'intent_candidates','array') THEN RETURN false; END IF;
 WHEN 'workflow.v4' THEN
  IF NOT msa.jtype(doc,'pending_questions','array') OR NOT msa.jtype(doc,'draft','object',true)
   OR NOT msa.jtype(doc,'pending_confirmation','object',true) THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'pending_questions') LOOP
   IF NOT msa.jtype(e,'field_key','string') OR NOT msa.jtype(e,'question','string') THEN RETURN false; END IF;
   IF e ? 'target_id' AND e->>'target_id' IS NOT NULL AND NOT msa.is_uuid(e->>'target_id') THEN RETURN false; END IF;
  END LOOP;
  IF doc->'pending_confirmation'<>'null'::jsonb THEN
   t:=doc->'pending_confirmation';
   IF NOT msa.jtype(t,'draft_revision','number') OR (t->>'draft_revision')::numeric<1
    OR NOT msa.is_hash(t->>'payload_digest') OR NOT msa.is_uuid(t->>'display_message_id') THEN RETURN false; END IF;
  END IF;
 WHEN 'input.v4' THEN
  IF NOT coalesce(doc->>'digest_basis' IN ('ORIGINAL_BYTES','CANONICAL_JSON'),false) THEN RETURN false; END IF;
  IF NOT (coalesce(msa.jtype(doc,'text','string') AND btrim(doc->>'text')<>'',false)
   OR msa.jtype(doc,'manual_fields','object') OR msa.jtype(doc,'object_locator','object')) THEN RETURN false; END IF;
  IF doc ? 'object_locator' AND (NOT msa.jtype(doc->'object_locator','uri','string')
   OR btrim(doc->'object_locator'->>'uri')='') THEN RETURN false; END IF;
 WHEN 'extraction.v4' THEN
  IF NOT msa.jtype(doc,'medications','array') OR NOT msa.string_array(doc->'warnings')
   OR NOT msa.string_array(doc->'document_instructions_raw') THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'medications') LOOP
   IF NOT msa.valid_document(e || '{"schema":"medication-entry.v4"}','medication-entry.v4') THEN RETURN false; END IF;
  END LOOP;
 WHEN 'medication-entry.v4' THEN
  FOREACH k IN ARRAY ARRAY['name_raw','strength_raw','dose_raw','route_raw','frequency_raw','duration_raw','quantity_raw','instructions_raw','evidence_text'] LOOP
   IF NOT msa.jtype(doc,k,'string',true) THEN RETURN false; END IF;
  END LOOP;
  IF NOT msa.string_array(doc->'uncertain_fields') OR NOT msa.jtype(doc,'administrations','array') THEN RETURN false; END IF;
  IF doc ? 'product_id' OR doc ? 'ddinter_id' THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'administrations') LOOP
   IF NOT msa.jtype(e,'timing_raw','string',true) OR NOT msa.jtype(e,'dose_raw','string',true) THEN RETURN false; END IF;
  END LOOP;
 WHEN 'item-origin.v4' THEN
  IF NOT msa.is_uuid(doc->>'input_id') OR NOT msa.is_uuid(doc->>'extraction_id')
   OR NOT msa.jtype(doc,'item_ordinal','number') OR (doc->>'item_ordinal')::numeric<1
   OR NOT msa.jtype(doc,'locator','object') OR NOT msa.jtype(doc,'text_raw','string',true) THEN RETURN false; END IF;
 WHEN 'match-evidence.v4' THEN
  IF NOT msa.jtype(doc,'method','string') OR NOT msa.jtype(doc,'qualifiers','object')
   OR NOT msa.jtype(doc,'external_candidates','array') OR NOT msa.jtype(doc,'candidate_evidence','array')
   OR NOT msa.jtype(doc,'outcome_reason','string',true) OR NOT msa.string_array(doc->'limitations') THEN RETURN false; END IF;
 WHEN 'snapshot-entry.v4' THEN
  IF NOT msa.is_hash(doc->>'input_content_digest')
   OR NOT coalesce(doc->>'identification_status' IN ('SELECTED','AMBIGUOUS','NO_MATCH','FAILED','NOT_ATTEMPTED'),false)
   OR NOT msa.jtype(doc,'product_id','string',true) OR NOT msa.jtype(doc,'reference_build','string',true)
   OR NOT coalesce(doc->>'component_coverage' IN ('COMPLETE','PARTIAL','UNKNOWN'),false)
   OR NOT msa.jtype(doc,'components','array') OR NOT msa.jtype(doc,'mapping_refs','array')
   OR NOT msa.string_array(doc->'limitations') THEN RETURN false; END IF;
  IF doc->>'product_id' IS NOT NULL AND NOT msa.is_uuid(doc->>'product_id') THEN RETURN false; END IF;
  IF doc->>'reference_build' IS NOT NULL AND NOT msa.is_hash(doc->>'reference_build') THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'mapping_refs') LOOP
   IF NOT msa.is_uuid(e->>'mapping_id') OR NOT msa.is_uuid(e->>'component_id')
    OR e->>'mapping_id'=ANY(seen) THEN RETURN false; END IF;
   seen:=array_append(seen,e->>'mapping_id');
  END LOOP;
 WHEN 'knowledge-builds.v4' THEN
  IF NOT msa.is_hash(doc->>'snapshot_digest') OR NOT msa.jtype(doc,'reference_builds','array')
   OR NOT msa.jtype(doc,'ddinter','object') OR NOT msa.string_array(doc->'limitations') THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'reference_builds') LOOP
   IF jsonb_typeof(e)<>'string' OR NOT msa.is_hash(e#>>'{}') THEN RETURN false; END IF;
  END LOOP;
  IF NOT (msa.jtype(doc,'engine_config','object') OR msa.is_hash(doc->>'engine_config_digest')) THEN RETURN false; END IF;
 WHEN 'checks.v4' THEN
  FOREACH k IN ARRAY ARRAY['ddi','duplicate_ingredient'] LOOP
   t:=doc->k;
   IF NOT msa.keys(t,ARRAY['execution','coverage','scope','pair_results','limitations','error'])
    OR NOT coalesce(t->>'execution' IN ('NOT_STARTED','RUNNING','COMPLETED','FAILED'),false)
    OR NOT coalesce(t->>'coverage' IN ('PENDING','ASSESSED','PARTIAL','UNASSESSED','NOT_APPLICABLE'),false)
    OR NOT msa.jtype(t,'scope','object') OR NOT msa.jtype(t,'pair_results','array') OR NOT msa.string_array(t->'limitations')
    OR NOT msa.jtype(t,'error','object',true) THEN RETURN false; END IF;
   IF t->>'execution'='FAILED' AND (t->>'coverage' NOT IN ('PARTIAL','UNASSESSED') OR t->'error'='null'::jsonb) THEN RETURN false; END IF;
   FOR e IN SELECT value FROM jsonb_array_elements(t->'pair_results') LOOP
    IF NOT msa.jtype(e,'entry_version_ids','array') OR jsonb_array_length(e->'entry_version_ids')<>2
     OR NOT msa.jtype(e,'component_refs','array') OR NOT msa.jtype(e,'source_record_refs','array')
     OR NOT coalesce(e->>'status' IN ('INTERACTION_DETECTED','NO_RECORD_IN_LOADED_SUBSET','SOURCE_CONFLICT','UNASSESSED','DUPLICATE_DETECTED','NO_DUPLICATE_IN_ASSESSED_SCOPE'),false)
     OR NOT msa.jtype(e,'reason','string',true) THEN RETURN false; END IF;
   END LOOP;
  END LOOP;
 WHEN 'error.v4' THEN
  IF NOT msa.jtype(doc,'code','string') OR NOT msa.jtype(doc,'message','string') OR NOT msa.jtype(doc,'details','object',true) THEN RETURN false; END IF;
 WHEN 'finding-evidence.v4' THEN
  IF NOT msa.jtype(doc,'rule_id','string') OR btrim(doc->>'rule_id')=''
   OR NOT msa.jtype(doc,'rule_version','string',true) OR NOT msa.jtype(doc,'sources','array')
   OR NOT msa.jtype(doc,'component_refs','array') OR NOT msa.string_array(doc->'limitations') THEN RETURN false; END IF;
 WHEN 'health-source.v4' THEN
  IF NOT msa.jtype(doc,'facts','array') OR NOT msa.string_array(doc->'limitations') THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'facts') LOOP
   IF NOT msa.jtype(e,'field','string') OR NOT e ? 'value' OR NOT msa.jtype(e,'text_raw','string',true)
    OR NOT msa.jtype(e,'uncertainty','string',true) THEN RETURN false; END IF;
  END LOOP;
 WHEN 'health-source-locator.v4' THEN
  IF NOT (msa.is_uuid(doc->>'message_id') OR (msa.jtype(doc,'uri','string') AND msa.is_hash(doc->>'artifact_sha256'))) THEN RETURN false; END IF;
 WHEN 'patient-summary.v4' THEN
  IF NOT msa.jtype(doc,'as_of','string') OR NOT msa.jtype(doc,'patient_context','object') THEN RETURN false; END IF;
  FOREACH k IN ARRAY ARRAY['conditions','allergies'] LOOP
   IF NOT coalesce(doc->k->>'state' IN ('KNOWN','NONE_REPORTED','UNKNOWN'),false)
    OR NOT msa.jtype(doc->k,'items','array') THEN RETURN false; END IF;
  END LOOP;
  FOREACH k IN ARRAY ARRAY['medications','safety_findings','limitations','sections'] LOOP
   IF NOT msa.jtype(doc,k,'array') THEN RETURN false; END IF;
  END LOOP;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'sections') LOOP
   IF NOT msa.jtype(e,'key','string') OR NOT msa.jtype(e,'title','string') OR NOT msa.jtype(e,'text','string')
    OR NOT msa.string_array(e->'source_keys') THEN RETURN false; END IF;
  END LOOP;
 WHEN 'summary-manifest.v4' THEN
  IF NOT msa.jtype(doc,'sources','array') OR jsonb_array_length(doc->'sources')=0 THEN RETURN false; END IF;
  FOR e IN SELECT value FROM jsonb_array_elements(doc->'sources') LOOP
   IF NOT msa.jtype(e,'key','string') OR e->>'key'=ANY(seen) OR NOT msa.is_hash(e->>'digest')
    OR NOT msa.jtype(e,'scope','string')
    OR NOT coalesce(e->>'kind' IN ('HEALTH_SOURCE','ENTRY_VERSION','SNAPSHOT','ASSESSMENT','FINDING','REF_MEDICATION','EXTERNAL_DOCUMENT'),false) THEN RETURN false; END IF;
   seen:=array_append(seen,e->>'key');
   IF e->>'kind'='EXTERNAL_DOCUMENT' THEN
    IF NOT msa.jtype(e,'locator','object') THEN RETURN false; END IF;
   ELSIF NOT msa.is_uuid(e->>'id') THEN RETURN false;
   END IF;
   IF e->>'kind'='REF_MEDICATION' AND NOT msa.is_hash(e->>'dataset_build') THEN RETURN false; END IF;
  END LOOP;
 WHEN 'summary-generation.v4' THEN
  IF NOT msa.jtype(doc,'generator_version','string',true) OR NOT msa.jtype(doc,'template_version','string',true)
   OR NOT msa.jtype(doc,'model_ref','string',true) OR NOT msa.string_array(doc->'limitations') THEN RETURN false; END IF;
 ELSE RETURN false;
 END CASE;
 RETURN true;
END $$;

CREATE TABLE msa_ref.medications (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  source_medication_id text NOT NULL,
  dataset_build text NOT NULL CHECK (dataset_build IS NULL OR msa.is_hash(dataset_build)),
  brand_name text NOT NULL,
  manufacturer text,
  dosage_form text,
  route text,
  component_count integer,
  product_details jsonb NOT NULL CHECK (product_details IS NULL OR msa.valid_document(product_details,'product-details.v4')),
  indications jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(indications)='array'),
  priorities jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(priorities)='array'),
  source_locator jsonb NOT NULL CHECK (source_locator IS NULL OR msa.valid_document(source_locator,'csv-source.v4')),
  UNIQUE(dataset_build,source_medication_id),
  UNIQUE(id,dataset_build),
  CHECK(btrim(source_medication_id)<>'' AND btrim(brand_name)<>''),
  CHECK(component_count IS NULL OR component_count>=0)
);

CREATE TABLE msa_ref.ingredients (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  source_ingredient_id text NOT NULL,
  dataset_build text NOT NULL CHECK (dataset_build IS NULL OR msa.is_hash(dataset_build)),
  name_original text NOT NULL,
  name_normalized text,
  acceptance_scope text NOT NULL,
  source_locator jsonb NOT NULL CHECK (source_locator IS NULL OR msa.valid_document(source_locator,'csv-source.v4')),
  UNIQUE(dataset_build,source_ingredient_id),
  UNIQUE(id,dataset_build),
  CHECK(btrim(source_ingredient_id)<>'' AND btrim(name_original)<>'' AND btrim(acceptance_scope)<>'')
);

CREATE TABLE msa_ref.medication_ingredients (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  medication_id uuid NOT NULL,
  ingredient_id uuid,
  dataset_build text NOT NULL CHECK (dataset_build IS NULL OR msa.is_hash(dataset_build)),
  source_component_id text NOT NULL,
  ordinal integer NOT NULL,
  ingredient_name_raw text,
  ingredient_text_raw text NOT NULL,
  chemical_form_raw text,
  equivalence_raw text,
  strength_basis jsonb NOT NULL CHECK (strength_basis IS NULL OR msa.valid_document(strength_basis,'strength-basis.v4')),
  source_locator jsonb NOT NULL CHECK (source_locator IS NULL OR msa.valid_document(source_locator,'csv-source.v4')),
  UNIQUE(dataset_build,source_component_id),
  UNIQUE(medication_id,ordinal),
  UNIQUE(id,dataset_build),
  CHECK(ordinal>=1 AND btrim(source_component_id)<>'')
);

CREATE TABLE msa_ref.ddinter_mappings (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  source_mapping_id text NOT NULL,
  component_id uuid NOT NULL,
  dataset_build text NOT NULL CHECK (dataset_build IS NULL OR msa.is_hash(dataset_build)),
  target_id text,
  mapping_set_id text,
  target_catalog_sha256 text CHECK (target_catalog_sha256 IS NULL OR msa.is_hash(target_catalog_sha256)),
  retrieval_evidence jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(retrieval_evidence)='array'),
  source_locator jsonb NOT NULL CHECK (source_locator IS NULL OR msa.valid_document(source_locator,'csv-source.v4')),
  UNIQUE(dataset_build,source_mapping_id),
  CHECK(btrim(source_mapping_id)<>''),
  CHECK(target_id IS NULL OR btrim(target_id)<>''),
  CHECK(mapping_set_id IS NULL OR btrim(mapping_set_id)<>'')
);

CREATE TABLE msa.conversation_sessions (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'OPEN',
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  closed_at timestamptz,
  UNIQUE(id,user_id),
  CHECK(status IN ('OPEN','CLOSED')),
  CHECK((status='CLOSED')=(closed_at IS NOT NULL)),
  CHECK(closed_at IS NULL OR closed_at>=created_at)
);

CREATE TABLE msa.conversation_messages (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  conversation_id uuid NOT NULL,
  sequence_no bigint NOT NULL,
  role text NOT NULL,
  text_content text,
  metadata jsonb NOT NULL DEFAULT '{"schema":"message.v4","content_refs":[]}'::jsonb CHECK (metadata IS NULL OR msa.valid_document(metadata,'message.v4')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(conversation_id,sequence_no),
  UNIQUE(id,user_id),
  UNIQUE(id,conversation_id,user_id),
  CHECK(sequence_no>=1),
  CHECK(role IN ('USER','ASSISTANT','SYSTEM','TOOL')),
  CHECK(nullif(btrim(text_content),'') IS NOT NULL OR coalesce(jsonb_array_length(metadata->'content_refs'),0)>0)
);

CREATE TABLE msa.workflow_instances (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  conversation_id uuid NOT NULL,
  origin_message_id uuid,
  intake_session_id uuid,
  workflow_type text NOT NULL,
  fsm_version text NOT NULL,
  state text NOT NULL DEFAULT 'COLLECTING',
  revision integer NOT NULL DEFAULT 1,
  context jsonb NOT NULL DEFAULT '{"schema":"workflow.v4","pending_questions":[],"draft":null,"pending_confirmation":null}'::jsonb CHECK (context IS NULL OR msa.valid_document(context,'workflow.v4')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(id,user_id),
  CHECK(workflow_type IN ('MEDICATION_INTAKE','SAFETY_REQUEST','PATIENT_SUMMARY','Q_AND_A')),
  CHECK(btrim(fsm_version)<>''),
  CHECK(state IN ('COLLECTING','CLARIFYING','AWAITING_CONFIRMATION','SUSPENDED','COMPLETED','CANCELLED','FAILED')),
  CHECK(revision>=1 AND updated_at>=created_at)
);

CREATE TABLE msa.intake_sessions (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  conversation_id uuid,
  purpose text NOT NULL,
  status text NOT NULL DEFAULT 'OPEN',
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(id,user_id),
  UNIQUE(id,conversation_id,user_id),
  CHECK(purpose IN ('MEDICATION_COLLECTION','SAFETY_CHECK','MEDICATION_INFORMATION')),
  CHECK(status IN ('OPEN','CLOSED','CANCELLED')),
  CHECK(updated_at>=created_at)
);

CREATE TABLE msa.intake_inputs (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  session_id uuid NOT NULL,
  message_id uuid,
  modality text NOT NULL,
  content_type text,
  payload_or_locator jsonb NOT NULL CHECK (payload_or_locator IS NULL OR msa.valid_document(payload_or_locator,'input.v4')),
  input_digest text NOT NULL CHECK (input_digest IS NULL OR msa.is_hash(input_digest)),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(id,user_id),
  CHECK(modality IN ('IMAGE','AUDIO','TEXT','MANUAL'))
);

CREATE TABLE msa.intake_extractions (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  input_id uuid NOT NULL,
  attempt_no integer NOT NULL,
  extractor_name text NOT NULL,
  extractor_version text NOT NULL,
  status text NOT NULL,
  result jsonb NOT NULL CHECK (result IS NULL OR msa.valid_document(result,'extraction.v4')),
  errors jsonb CHECK (errors IS NULL OR msa.valid_document(errors,'error.v4')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(input_id,attempt_no),
  UNIQUE(id,user_id),
  CHECK(attempt_no>=1 AND btrim(extractor_name)<>'' AND btrim(extractor_version)<>''),
  CHECK(status IN ('SUCCEEDED','PARTIAL','FAILED')),
  CHECK(status<>'FAILED' OR errors IS NOT NULL)
);

CREATE TABLE msa.intake_items (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  extraction_id uuid NOT NULL,
  item_ordinal integer NOT NULL,
  origin_evidence jsonb NOT NULL CHECK (origin_evidence IS NULL OR msa.valid_document(origin_evidence,'item-origin.v4')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(extraction_id,item_ordinal),
  UNIQUE(id,user_id),
  CHECK(item_ordinal>=1)
);

CREATE TABLE msa.medication_entry_versions (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  item_id uuid NOT NULL,
  version_no integer NOT NULL,
  supersedes_version_id uuid,
  source_extraction_id uuid,
  medication_fields jsonb NOT NULL CHECK (medication_fields IS NULL OR msa.valid_document(medication_fields,'medication-entry.v4')),
  content_digest text NOT NULL GENERATED ALWAYS AS (msa.digest(medication_fields)) STORED CHECK (content_digest IS NULL OR msa.is_hash(content_digest)),
  confirmed_at timestamptz,
  confirmation_key uuid,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(item_id,version_no),
  UNIQUE(supersedes_version_id),
  UNIQUE(user_id,confirmation_key),
  UNIQUE(id,user_id),
  UNIQUE(id,item_id,user_id),
  CHECK(version_no>=1),
  CHECK((version_no=1 AND supersedes_version_id IS NULL) OR (version_no>1 AND supersedes_version_id IS NOT NULL AND supersedes_version_id<>id)),
  CHECK((confirmed_at IS NULL)=(confirmation_key IS NULL)),
  CHECK(confirmed_at IS NULL OR confirmed_at>=created_at)
);

CREATE TABLE msa.entry_matches (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  entry_version_id uuid NOT NULL,
  attempt_no integer NOT NULL,
  match_status text NOT NULL,
  candidate_rank integer,
  product_id uuid,
  reference_build text CHECK (reference_build IS NULL OR msa.is_hash(reference_build)),
  matcher_version text NOT NULL,
  confidence numeric,
  match_evidence jsonb NOT NULL CHECK (match_evidence IS NULL OR msa.valid_document(match_evidence,'match-evidence.v4')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(id,entry_version_id,user_id),
  CHECK(attempt_no>=1 AND btrim(matcher_version)<>''),
  CHECK(match_status IN ('CANDIDATE','SELECTED','AMBIGUOUS','NO_MATCH','FAILED')),
  CHECK((match_status='CANDIDATE' AND candidate_rank IS NOT NULL AND candidate_rank>=1) OR (match_status<>'CANDIDATE' AND candidate_rank IS NULL)),
  CHECK(product_id IS NULL OR reference_build IS NOT NULL),
  CHECK(match_status<>'SELECTED' OR (product_id IS NOT NULL AND reference_build IS NOT NULL)),
  CHECK(match_status NOT IN ('AMBIGUOUS','NO_MATCH','FAILED') OR product_id IS NULL),
  CHECK(confidence IS NULL OR confidence BETWEEN 0 AND 1)
);

CREATE TABLE msa.medication_list_snapshots (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  supersedes_snapshot_id uuid,
  context_key text NOT NULL,
  data_context text NOT NULL DEFAULT 'PATIENT',
  status text NOT NULL DEFAULT 'DRAFT',
  as_of_at timestamptz NOT NULL,
  snapshot_digest text CHECK (snapshot_digest IS NULL OR msa.is_hash(snapshot_digest)),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  sealed_at timestamptz,
  UNIQUE(id,user_id),
  CHECK(supersedes_snapshot_id IS DISTINCT FROM id),
  CHECK(btrim(context_key)<>''),
  CHECK(data_context IN ('PATIENT','DEIDENTIFIED','SYNTHETIC_TEST')),
  CHECK((status='DRAFT' AND snapshot_digest IS NULL AND sealed_at IS NULL) OR (status='SEALED' AND snapshot_digest IS NOT NULL AND sealed_at IS NOT NULL AND sealed_at>=created_at))
);

CREATE TABLE msa.snapshot_entries (
  snapshot_id uuid NOT NULL,
  entry_version_id uuid NOT NULL,
  user_id uuid NOT NULL,
  entry_match_id uuid,
  component_context jsonb NOT NULL CHECK (component_context IS NULL OR msa.valid_document(component_context,'snapshot-entry.v4')),
  PRIMARY KEY(snapshot_id,entry_version_id),
  UNIQUE(snapshot_id,entry_version_id,user_id)
);

CREATE TABLE msa.safety_assessments (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  snapshot_id uuid NOT NULL,
  retry_of_assessment_id uuid,
  request_key uuid NOT NULL,
  engine_version text NOT NULL,
  knowledge_builds jsonb NOT NULL CHECK (knowledge_builds IS NULL OR msa.valid_document(knowledge_builds,'knowledge-builds.v4')),
  check_results jsonb NOT NULL CHECK (check_results IS NULL OR msa.valid_document(check_results,'checks.v4')),
  execution_status text NOT NULL DEFAULT 'RUNNING',
  error_details jsonb CHECK (error_details IS NULL OR msa.valid_document(error_details,'error.v4')),
  result_digest text CHECK (result_digest IS NULL OR msa.is_hash(result_digest)),
  started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at timestamptz,
  UNIQUE(user_id,request_key),
  UNIQUE(id,user_id),
  UNIQUE(id,snapshot_id,user_id),
  CHECK(retry_of_assessment_id IS DISTINCT FROM id),
  CHECK(btrim(engine_version)<>''),
  CHECK(execution_status IN ('RUNNING','COMPLETED','FAILED')),
  CHECK((execution_status='RUNNING' AND result_digest IS NULL AND finished_at IS NULL) OR (execution_status IN ('COMPLETED','FAILED') AND result_digest IS NOT NULL AND finished_at IS NOT NULL AND finished_at>=started_at)),
  CHECK((execution_status='FAILED' AND error_details IS NOT NULL) OR (execution_status<>'FAILED' AND error_details IS NULL))
);

CREATE TABLE msa.safety_findings (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  assessment_id uuid NOT NULL,
  snapshot_id uuid NOT NULL,
  prior_finding_id uuid,
  finding_key text NOT NULL,
  finding_type text NOT NULL,
  severity text NOT NULL,
  source_severity text,
  explanation text NOT NULL,
  recommended_next_step text,
  evidence jsonb NOT NULL CHECK (evidence IS NULL OR msa.valid_document(evidence,'finding-evidence.v4')),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(assessment_id,finding_key),
  UNIQUE(id,user_id),
  UNIQUE(id,snapshot_id,user_id),
  CHECK(prior_finding_id IS DISTINCT FROM id),
  CHECK(btrim(finding_key)<>'' AND btrim(explanation)<>''),
  CHECK(finding_type IN ('DDI','DUPLICATE_INGREDIENT','UNRESOLVED','SOURCE_CONFLICT','COVERAGE_LIMITATION','SYSTEM_ISSUE')),
  CHECK(severity IN ('UNKNOWN','MINOR','MODERATE','MAJOR','CONTRAINDICATED'))
);

CREATE TABLE msa.finding_entries (
  finding_id uuid NOT NULL,
  entry_version_id uuid NOT NULL,
  snapshot_id uuid NOT NULL,
  user_id uuid NOT NULL,
  PRIMARY KEY(finding_id,entry_version_id)
);

CREATE TABLE msa.patient_health_sources (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  message_id uuid,
  supersedes_source_id uuid,
  corrects_source_id uuid,
  origin text NOT NULL,
  source_content jsonb NOT NULL CHECK (source_content IS NULL OR msa.valid_document(source_content,'health-source.v4')),
  verification_status text NOT NULL DEFAULT 'REPORTED',
  source_date date,
  source_locator jsonb NOT NULL CHECK (source_locator IS NULL OR msa.valid_document(source_locator,'health-source-locator.v4')),
  content_digest text NOT NULL GENERATED ALWAYS AS (msa.health_digest(origin,source_content,source_date,verification_status,source_locator)) STORED CHECK (content_digest IS NULL OR msa.is_hash(content_digest)),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(id,user_id),
  UNIQUE(supersedes_source_id),
  CHECK(supersedes_source_id IS DISTINCT FROM id AND corrects_source_id IS DISTINCT FROM id),
  CHECK(supersedes_source_id IS NULL OR corrects_source_id IS NULL),
  CHECK(corrects_source_id IS NULL OR origin='PATIENT_REPORTED'),
  CHECK(origin IN ('PATIENT_REPORTED','PHYSICIAN_PROVIDED','OTHER_DOCUMENT')),
  CHECK(verification_status IN ('REPORTED','PATIENT_CONFIRMED','SOURCE_VERIFIED'))
);

CREATE TABLE msa.patient_health_summaries (
  id uuid PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  series_root_id uuid NOT NULL,
  supersedes_summary_id uuid,
  version_no integer NOT NULL,
  workflow_id uuid,
  draft_revision integer,
  medication_snapshot_id uuid,
  primary_assessment_id uuid,
  summary_content jsonb NOT NULL CHECK (summary_content IS NULL OR msa.valid_document(summary_content,'patient-summary.v4')),
  source_manifest jsonb NOT NULL CHECK (source_manifest IS NULL OR msa.valid_document(source_manifest,'summary-manifest.v4')),
  confirmation_digest text NOT NULL GENERATED ALWAYS AS (msa.summary_digest(summary_content,source_manifest)) STORED CHECK (confirmation_digest IS NULL OR msa.is_hash(confirmation_digest)),
  confirmation_key uuid NOT NULL,
  generation_context jsonb NOT NULL CHECK (generation_context IS NULL OR msa.valid_document(generation_context,'summary-generation.v4')),
  generated_at timestamptz NOT NULL,
  confirmed_at timestamptz NOT NULL,
  UNIQUE(id,user_id),
  UNIQUE(id,series_root_id,user_id),
  UNIQUE(series_root_id,version_no),
  UNIQUE(supersedes_summary_id),
  UNIQUE(user_id,confirmation_key),
  CHECK((version_no=1 AND series_root_id=id AND supersedes_summary_id IS NULL) OR (version_no>1 AND series_root_id<>id AND supersedes_summary_id IS NOT NULL AND supersedes_summary_id<>id)),
  CHECK((workflow_id IS NULL)=(draft_revision IS NULL)),
  CHECK(draft_revision IS NULL OR draft_revision>=1),
  CHECK(primary_assessment_id IS NULL OR medication_snapshot_id IS NOT NULL),
  CHECK(generated_at<=confirmed_at)
);

ALTER TABLE msa_ref.medication_ingredients ADD FOREIGN KEY (medication_id,dataset_build) REFERENCES msa_ref.medications(id,dataset_build) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa_ref.medication_ingredients ADD FOREIGN KEY (ingredient_id,dataset_build) REFERENCES msa_ref.ingredients(id,dataset_build) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa_ref.ddinter_mappings ADD FOREIGN KEY (component_id,dataset_build) REFERENCES msa_ref.medication_ingredients(id,dataset_build) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.conversation_sessions ADD FOREIGN KEY (user_id) REFERENCES identity.users(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.conversation_messages ADD FOREIGN KEY (conversation_id,user_id) REFERENCES msa.conversation_sessions(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.workflow_instances ADD FOREIGN KEY (conversation_id,user_id) REFERENCES msa.conversation_sessions(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.workflow_instances ADD FOREIGN KEY (origin_message_id,conversation_id,user_id) REFERENCES msa.conversation_messages(id,conversation_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.workflow_instances ADD FOREIGN KEY (intake_session_id,conversation_id,user_id) REFERENCES msa.intake_sessions(id,conversation_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.intake_sessions ADD FOREIGN KEY (user_id) REFERENCES identity.users(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.intake_sessions ADD FOREIGN KEY (conversation_id,user_id) REFERENCES msa.conversation_sessions(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.intake_inputs ADD FOREIGN KEY (session_id,user_id) REFERENCES msa.intake_sessions(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.intake_inputs ADD FOREIGN KEY (message_id,user_id) REFERENCES msa.conversation_messages(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.intake_extractions ADD FOREIGN KEY (input_id,user_id) REFERENCES msa.intake_inputs(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.intake_items ADD FOREIGN KEY (extraction_id,user_id) REFERENCES msa.intake_extractions(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.medication_entry_versions ADD FOREIGN KEY (item_id,user_id) REFERENCES msa.intake_items(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.medication_entry_versions ADD FOREIGN KEY (source_extraction_id,user_id) REFERENCES msa.intake_extractions(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.medication_entry_versions ADD FOREIGN KEY (supersedes_version_id,item_id,user_id) REFERENCES msa.medication_entry_versions(id,item_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.entry_matches ADD FOREIGN KEY (entry_version_id,user_id) REFERENCES msa.medication_entry_versions(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.entry_matches ADD FOREIGN KEY (product_id,reference_build) REFERENCES msa_ref.medications(id,dataset_build) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.medication_list_snapshots ADD FOREIGN KEY (user_id) REFERENCES identity.users(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.medication_list_snapshots ADD FOREIGN KEY (supersedes_snapshot_id,user_id) REFERENCES msa.medication_list_snapshots(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.snapshot_entries ADD FOREIGN KEY (snapshot_id,user_id) REFERENCES msa.medication_list_snapshots(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.snapshot_entries ADD FOREIGN KEY (entry_version_id,user_id) REFERENCES msa.medication_entry_versions(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.snapshot_entries ADD FOREIGN KEY (entry_match_id,entry_version_id,user_id) REFERENCES msa.entry_matches(id,entry_version_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.safety_assessments ADD FOREIGN KEY (snapshot_id,user_id) REFERENCES msa.medication_list_snapshots(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.safety_assessments ADD FOREIGN KEY (retry_of_assessment_id,snapshot_id,user_id) REFERENCES msa.safety_assessments(id,snapshot_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.safety_findings ADD FOREIGN KEY (assessment_id,snapshot_id,user_id) REFERENCES msa.safety_assessments(id,snapshot_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.safety_findings ADD FOREIGN KEY (prior_finding_id,user_id) REFERENCES msa.safety_findings(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.finding_entries ADD FOREIGN KEY (finding_id,snapshot_id,user_id) REFERENCES msa.safety_findings(id,snapshot_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.finding_entries ADD FOREIGN KEY (snapshot_id,entry_version_id,user_id) REFERENCES msa.snapshot_entries(snapshot_id,entry_version_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_sources ADD FOREIGN KEY (user_id) REFERENCES identity.users(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_sources ADD FOREIGN KEY (message_id,user_id) REFERENCES msa.conversation_messages(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_sources ADD FOREIGN KEY (supersedes_source_id,user_id) REFERENCES msa.patient_health_sources(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_sources ADD FOREIGN KEY (corrects_source_id,user_id) REFERENCES msa.patient_health_sources(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_summaries ADD FOREIGN KEY (user_id) REFERENCES identity.users(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_summaries ADD FOREIGN KEY (series_root_id,user_id) REFERENCES msa.patient_health_summaries(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_summaries ADD FOREIGN KEY (supersedes_summary_id,series_root_id,user_id) REFERENCES msa.patient_health_summaries(id,series_root_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_summaries ADD FOREIGN KEY (workflow_id,user_id) REFERENCES msa.workflow_instances(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_summaries ADD FOREIGN KEY (medication_snapshot_id,user_id) REFERENCES msa.medication_list_snapshots(id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;
ALTER TABLE msa.patient_health_summaries ADD FOREIGN KEY (primary_assessment_id,medication_snapshot_id,user_id) REFERENCES msa.safety_assessments(id,snapshot_id,user_id) ON UPDATE RESTRICT ON DELETE RESTRICT;

-- Essential indexes; PK/UNIQUE indexes are not repeated.
CREATE INDEX medications_name_idx ON msa_ref.medications(dataset_build,lower(brand_name));
CREATE INDEX medications_registration_idx ON msa_ref.medications(dataset_build,(product_details->>'registration_token')) WHERE product_details->>'registration_token' IS NOT NULL;
CREATE INDEX ingredients_name_idx ON msa_ref.ingredients(dataset_build,lower(name_original));
CREATE INDEX components_ingredient_idx ON msa_ref.medication_ingredients(ingredient_id,dataset_build) WHERE ingredient_id IS NOT NULL;
CREATE INDEX mappings_component_idx ON msa_ref.ddinter_mappings(component_id,dataset_build);
CREATE INDEX mappings_target_idx ON msa_ref.ddinter_mappings(dataset_build,target_id) WHERE target_id IS NOT NULL;
CREATE INDEX conversations_owner_idx ON msa.conversation_sessions(user_id,created_at DESC);
CREATE INDEX workflows_thread_idx ON msa.workflow_instances(conversation_id,state);
CREATE INDEX workflows_intake_idx ON msa.workflow_instances(intake_session_id) WHERE intake_session_id IS NOT NULL;
CREATE INDEX workflows_origin_idx ON msa.workflow_instances(origin_message_id) WHERE origin_message_id IS NOT NULL;
CREATE INDEX intakes_owner_idx ON msa.intake_sessions(user_id,created_at DESC);
CREATE INDEX intakes_thread_idx ON msa.intake_sessions(conversation_id) WHERE conversation_id IS NOT NULL;
CREATE INDEX inputs_session_idx ON msa.intake_inputs(session_id,created_at);
CREATE INDEX inputs_message_idx ON msa.intake_inputs(message_id) WHERE message_id IS NOT NULL;
CREATE INDEX versions_extraction_idx ON msa.medication_entry_versions(source_extraction_id) WHERE source_extraction_id IS NOT NULL;
CREATE UNIQUE INDEX matches_outcome_uq ON msa.entry_matches(entry_version_id,attempt_no) WHERE match_status<>'CANDIDATE';
CREATE UNIQUE INDEX matches_rank_uq ON msa.entry_matches(entry_version_id,attempt_no,candidate_rank) WHERE match_status='CANDIDATE';
CREATE INDEX matches_product_idx ON msa.entry_matches(product_id,reference_build) WHERE product_id IS NOT NULL;
CREATE INDEX snapshots_owner_idx ON msa.medication_list_snapshots(user_id,context_key,as_of_at DESC);
CREATE INDEX snapshots_prior_idx ON msa.medication_list_snapshots(supersedes_snapshot_id) WHERE supersedes_snapshot_id IS NOT NULL;
CREATE INDEX snapshot_entries_version_idx ON msa.snapshot_entries(entry_version_id);
CREATE INDEX snapshot_entries_match_idx ON msa.snapshot_entries(entry_match_id) WHERE entry_match_id IS NOT NULL;
CREATE INDEX assessments_snapshot_idx ON msa.safety_assessments(snapshot_id,started_at DESC);
CREATE INDEX assessments_retry_idx ON msa.safety_assessments(retry_of_assessment_id) WHERE retry_of_assessment_id IS NOT NULL;
CREATE INDEX findings_severe_idx ON msa.safety_findings(user_id,recorded_at DESC) WHERE severity IN ('MAJOR','CONTRAINDICATED');
CREATE INDEX findings_prior_idx ON msa.safety_findings(prior_finding_id) WHERE prior_finding_id IS NOT NULL;
CREATE INDEX finding_entries_member_idx ON msa.finding_entries(snapshot_id,entry_version_id,user_id);
CREATE INDEX health_sources_owner_idx ON msa.patient_health_sources(user_id,created_at DESC);
CREATE INDEX health_sources_message_idx ON msa.patient_health_sources(message_id) WHERE message_id IS NOT NULL;
CREATE INDEX health_sources_corrects_idx ON msa.patient_health_sources(corrects_source_id) WHERE corrects_source_id IS NOT NULL;
CREATE UNIQUE INDEX summaries_workflow_uq ON msa.patient_health_summaries(workflow_id,draft_revision) WHERE workflow_id IS NOT NULL;
CREATE INDEX summaries_owner_idx ON msa.patient_health_summaries(user_id,confirmed_at DESC);
CREATE INDEX summaries_snapshot_idx ON msa.patient_health_summaries(medication_snapshot_id) WHERE medication_snapshot_id IS NOT NULL;
CREATE INDEX summaries_assessment_idx ON msa.patient_health_summaries(primary_assessment_id,medication_snapshot_id,user_id) WHERE primary_assessment_id IS NOT NULL;

COMMENT ON SCHEMA msa_ref IS '{"schema":"ref-build-ledger.v4","builds":{}}';
CREATE FUNCTION msa.build_info(build text) RETURNS jsonb LANGUAGE sql STABLE AS $$
 SELECT coalesce(obj_description(oid,'pg_namespace')::jsonb->'builds'->build,'null'::jsonb)
 FROM pg_namespace WHERE nspname='msa_ref'
$$;
CREATE FUNCTION msa.published(build text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT coalesce(msa.build_info(build)->>'published'='true',false)
$$;
CREATE FUNCTION msa.valid_related(items jsonb, kind text, parent_id text) RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE e jsonb; k text; seen text[]:='{}';
BEGIN
 IF jsonb_typeof(items) IS DISTINCT FROM 'array' THEN RETURN false; END IF;
 FOR e IN SELECT value FROM jsonb_array_elements(items) LOOP
  IF NOT msa.jtype(e,'id','string') OR btrim(e->>'id')='' OR e->>'id'=ANY(seen)
   OR e->>'medication_id' IS DISTINCT FROM parent_id OR NOT msa.valid_document(e->'source_locator','csv-source.v4')
   OR e->'source_locator'->>'source_id' IS DISTINCT FROM e->>'id' THEN RETURN false; END IF;
  seen:=array_append(seen,e->>'id');
  IF kind='indications' THEN
   FOREACH k IN ARRAY ARRAY['assertion_kind','polarity','text_raw','expression_state'] LOOP
    IF NOT msa.jtype(e,k,'string') THEN RETURN false; END IF;
   END LOOP;
   IF NOT msa.jtype(e,'condition_expression','object') OR NOT msa.jtype(e,'source_qualifications','object')
    OR NOT msa.jtype(e,'literal_operators','array') THEN RETURN false; END IF;
  ELSE
   FOREACH k IN ARRAY ARRAY['purpose','policy_status'] LOOP
    IF NOT msa.jtype(e,k,'string') THEN RETURN false; END IF;
   END LOOP;
   IF NOT msa.string_array(e->'condition_groups') OR NOT msa.string_array(e->'selected_condition_groups')
    OR NOT msa.jtype(e,'selected_for_hdsd_collection','boolean') OR NOT msa.jtype(e,'clinical_recommendation','boolean')
    OR NOT msa.keys(e,ARRAY['collection_priority_tier','source_clinical_priority']) THEN RETURN false; END IF;
  END IF;
 END LOOP;
 RETURN true;
END $$;
CREATE FUNCTION msa.ref_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE source_key text; c msa_ref.medication_ingredients%ROWTYPE; p msa_ref.medications%ROWTYPE;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Published reference facts are immutable'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.dataset_build,4));
 IF msa.published(NEW.dataset_build) THEN RAISE EXCEPTION 'Cannot append to published build'; END IF;
 source_key:=to_jsonb(NEW)->>('source_'||CASE TG_TABLE_NAME WHEN 'medications' THEN 'medication' WHEN 'ingredients' THEN 'ingredient' WHEN 'medication_ingredients' THEN 'component' ELSE 'mapping' END||'_id');
 IF NEW.source_locator->>'csv' IS DISTINCT FROM TG_TABLE_NAME||'.csv' OR NEW.source_locator->>'source_id' IS DISTINCT FROM source_key THEN RAISE EXCEPTION 'Source ID mismatch'; END IF;
 IF TG_TABLE_NAME='medications' THEN
  IF NOT msa.valid_related(NEW.indications,'indications',NEW.source_medication_id)
   OR NOT msa.valid_related(NEW.priorities,'priorities',NEW.source_medication_id) THEN RAISE EXCEPTION 'Invalid related source records'; END IF;
 ELSIF TG_TABLE_NAME='ddinter_mappings' THEN
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.retrieval_evidence) e WHERE jsonb_typeof(e)<>'object') THEN RAISE EXCEPTION 'Mapping retrieval evidence must retain source objects'; END IF;
  SELECT * INTO c FROM msa_ref.medication_ingredients WHERE id=NEW.component_id AND dataset_build=NEW.dataset_build;
  SELECT * INTO p FROM msa_ref.medications WHERE id=c.medication_id;
  IF NEW.source_locator->'source_attributes'->>'component_id' IS DISTINCT FROM c.source_component_id
   OR NEW.source_locator->'source_attributes'->>'medication_id' IS DISTINCT FROM p.source_medication_id THEN RAISE EXCEPTION 'Mapping source parent mismatch'; END IF;
 END IF;
 RETURN NEW;
END $$;
-- One publication check per build, under the loader's advisory lock. Structural checks only.
CREATE FUNCTION msa.assert_ref_build(build text) RETURNS void LANGUAGE plpgsql AS $$
DECLARE table_name text; bad boolean; info jsonb;
BEGIN
 info:=msa.build_info(build);
 IF NOT msa.is_hash(info->>'manifest_sha256') OR NOT msa.jtype(info,'files','object') THEN RAISE EXCEPTION 'Pinned build manifest is required before publication'; END IF;
 FOREACH table_name IN ARRAY ARRAY['medications','ingredients','medication_ingredients','ddinter_mappings'] LOOP
  EXECUTE format('SELECT EXISTS(SELECT 1 FROM msa_ref.%I WHERE dataset_build=$1 AND (source_locator->>''artifact_sha256'' IS DISTINCT FROM $2 OR source_locator->''manifest_locator''->>''artifact_sha256'' IS DISTINCT FROM $3))',table_name)
    INTO bad USING build,info->'files'->>table_name,info->>'manifest_sha256';
  IF bad THEN RAISE EXCEPTION 'Source or manifest hash mismatch for %',table_name; END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM msa_ref.medications m CROSS JOIN LATERAL jsonb_array_elements(m.indications) e
  WHERE m.dataset_build=build AND (e->'source_locator'->>'csv'<>'medication_indications.csv' OR e->'source_locator'->>'artifact_sha256' IS DISTINCT FROM info->'files'->>'medication_indications'))
 OR EXISTS(SELECT 1 FROM msa_ref.medications m CROSS JOIN LATERAL jsonb_array_elements(m.priorities) e
  WHERE m.dataset_build=build AND (e->'source_locator'->>'csv'<>'medication_priorities.csv' OR e->'source_locator'->>'artifact_sha256' IS DISTINCT FROM info->'files'->>'medication_priorities')) THEN RAISE EXCEPTION 'Related-source artifact mismatch'; END IF;
 IF EXISTS(SELECT 1 FROM msa_ref.medications m WHERE m.dataset_build=build AND m.component_count IS NOT NULL
  AND m.component_count<>(SELECT count(*) FROM msa_ref.medication_ingredients c WHERE c.medication_id=m.id)) THEN
  RAISE EXCEPTION 'Source-declared component inventory differs from retained rows';
 END IF;
 IF EXISTS(SELECT e->>'id' FROM msa_ref.medications m CROSS JOIN LATERAL jsonb_array_elements(m.indications) e
  WHERE m.dataset_build=build GROUP BY e->>'id' HAVING count(*)>1)
 OR EXISTS(SELECT e->>'id' FROM msa_ref.medications m CROSS JOIN LATERAL jsonb_array_elements(m.priorities) e
  WHERE m.dataset_build=build GROUP BY e->>'id' HAVING count(*)>1) THEN RAISE EXCEPTION 'Repeated related source ID within build'; END IF;
END $$;
CREATE FUNCTION msa.require_owner(owner_id uuid) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
 IF nullif(current_setting('msa.authenticated_owner',true),'') IS DISTINCT FROM owner_id::text THEN
  RAISE EXCEPTION 'Trusted authenticated-owner context required' USING ERRCODE='42501';
 END IF;
END $$;
CREATE FUNCTION msa.reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION '% on immutable Core history is forbidden',TG_OP; END $$;
CREATE FUNCTION msa.owner_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN PERFORM msa.require_owner(OLD.user_id); RAISE EXCEPTION 'Core history cannot be deleted'; END IF;
 PERFORM msa.require_owner(NEW.user_id);
 IF TG_OP='UPDATE' AND NEW.user_id<>OLD.user_id THEN RAISE EXCEPTION 'Owner is immutable'; END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION msa.context_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_no integer; last_id uuid; context_id uuid; expected_id uuid; s text; w msa.workflow_instances%ROWTYPE;
BEGIN
 IF TG_TABLE_NAME='conversation_sessions' AND TG_OP='UPDATE' THEN
  IF OLD.status<>'OPEN' OR NEW.status<>'CLOSED'
   OR (to_jsonb(OLD)-ARRAY['status','closed_at']) IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['status','closed_at']) THEN RAISE EXCEPTION 'Only conversation close is allowed'; END IF;
  NEW.closed_at:=clock_timestamp();
 ELSIF TG_TABLE_NAME='intake_sessions' AND TG_OP='UPDATE' THEN
  IF OLD.status<>'OPEN' OR NEW.status NOT IN ('CLOSED','CANCELLED')
   OR (to_jsonb(OLD)-ARRAY['status','updated_at']) IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['status','updated_at']) THEN RAISE EXCEPTION 'Invalid intake transition'; END IF;
  NEW.updated_at:=clock_timestamp();
 ELSIF TG_TABLE_NAME='workflow_instances' THEN
  IF NEW.intake_session_id IS NOT NULL THEN
   SELECT conversation_id INTO context_id FROM msa.intake_sessions WHERE id=NEW.intake_session_id;
   IF context_id IS DISTINCT FROM NEW.conversation_id THEN RAISE EXCEPTION 'Workflow intake has a different conversation'; END IF;
  END IF;
  IF TG_OP='INSERT' THEN
   IF NEW.state<>'COLLECTING' OR NEW.revision<>1 THEN RAISE EXCEPTION 'Workflow starts COLLECTING revision 1'; END IF;
  ELSE
   IF OLD.state IN ('COMPLETED','CANCELLED','FAILED') OR NEW.revision<>OLD.revision+1
    OR (to_jsonb(OLD)-ARRAY['state','revision','context','updated_at']) IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['state','revision','context','updated_at']) THEN RAISE EXCEPTION 'Invalid workflow revision'; END IF;
   IF NOT (NEW.state=OLD.state OR NEW.state IN ('CANCELLED','FAILED','SUSPENDED')
    OR (OLD.state IN ('COLLECTING','CLARIFYING') AND NEW.state IN ('COLLECTING','CLARIFYING','AWAITING_CONFIRMATION'))
    OR (OLD.state='AWAITING_CONFIRMATION' AND NEW.state IN ('COLLECTING','CLARIFYING','COMPLETED'))
    OR (OLD.state='SUSPENDED' AND NEW.state IN ('COLLECTING','CLARIFYING','AWAITING_CONFIRMATION'))) THEN RAISE EXCEPTION 'Invalid FSM edge'; END IF;
   NEW.updated_at:=clock_timestamp();
  END IF;
  IF NEW.context->'pending_confirmation'<>'null'::jsonb THEN
   IF NEW.state<>'AWAITING_CONFIRMATION'
    OR NEW.context->'draft'->>'draft_revision' IS DISTINCT FROM NEW.context->'pending_confirmation'->>'draft_revision'
    OR NEW.context->'draft'->>'display_message_id' IS DISTINCT FROM NEW.context->'pending_confirmation'->>'display_message_id'
    OR NOT EXISTS(SELECT 1 FROM msa.conversation_messages WHERE id=(NEW.context->'pending_confirmation'->>'display_message_id')::uuid AND conversation_id=NEW.conversation_id AND user_id=NEW.user_id AND role='ASSISTANT') THEN RAISE EXCEPTION 'Invalid displayed draft context'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='conversation_messages' THEN
  PERFORM 1 FROM msa.conversation_sessions WHERE id=NEW.conversation_id AND status='OPEN' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Conversation is closed'; END IF;
 ELSIF TG_TABLE_NAME='intake_inputs' THEN
  SELECT conversation_id,status INTO context_id,s FROM msa.intake_sessions WHERE id=NEW.session_id FOR UPDATE;
  IF s IS DISTINCT FROM 'OPEN' THEN RAISE EXCEPTION 'Input requires OPEN intake'; END IF;
  IF NEW.message_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM msa.conversation_messages WHERE id=NEW.message_id AND conversation_id=context_id AND user_id=NEW.user_id AND role='USER') THEN RAISE EXCEPTION 'Input message is outside intake'; END IF;
  IF NEW.modality IN ('IMAGE','AUDIO') AND NOT msa.jtype(NEW.payload_or_locator,'object_locator','object') THEN RAISE EXCEPTION 'Binary input needs retained object'; END IF;
 ELSIF TG_TABLE_NAME='intake_items' THEN
  SELECT status,input_id INTO s,context_id FROM msa.intake_extractions WHERE id=NEW.extraction_id;
  IF s='FAILED' OR NEW.origin_evidence->>'input_id' IS DISTINCT FROM context_id::text
   OR NEW.origin_evidence->>'extraction_id' IS DISTINCT FROM NEW.extraction_id::text
   OR NEW.origin_evidence->>'item_ordinal' IS DISTINCT FROM NEW.item_ordinal::text THEN RAISE EXCEPTION 'Invalid item origin'; END IF;
 ELSIF TG_TABLE_NAME='medication_entry_versions' THEN
  PERFORM 1 FROM msa.intake_items WHERE id=NEW.item_id FOR UPDATE;
  IF TG_OP='INSERT' THEN
   SELECT version_no,id INTO old_no,last_id FROM msa.medication_entry_versions WHERE item_id=NEW.item_id ORDER BY version_no DESC LIMIT 1;
   IF NEW.version_no<>coalesce(old_no,0)+1 OR NEW.supersedes_version_id IS DISTINCT FROM last_id
    OR NEW.confirmed_at IS NOT NULL OR NEW.confirmation_key IS NOT NULL THEN RAISE EXCEPTION 'Insert a consecutive unconfirmed version'; END IF;
  ELSE
   IF OLD.confirmed_at IS NOT NULL OR NEW.confirmed_at IS NULL OR NEW.confirmation_key IS NULL
    OR (to_jsonb(OLD)-ARRAY['confirmed_at','confirmation_key','content_digest']) IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['confirmed_at','confirmation_key','content_digest'])
    OR EXISTS(SELECT 1 FROM msa.medication_entry_versions WHERE item_id=OLD.item_id AND version_no>OLD.version_no)
    OR nullif(current_setting('msa.displayed_digest',true),'') IS DISTINCT FROM OLD.content_digest THEN RAISE EXCEPTION 'Invalid/stale exact confirmation'; END IF;
   NEW.confirmed_at:=clock_timestamp();
  END IF;
  IF NEW.source_extraction_id IS NOT NULL THEN
   SELECT p.session_id INTO context_id FROM msa.intake_items i JOIN msa.intake_extractions x ON x.id=i.extraction_id JOIN msa.intake_inputs p ON p.id=x.input_id WHERE i.id=NEW.item_id;
   SELECT p.session_id INTO expected_id FROM msa.intake_extractions x JOIN msa.intake_inputs p ON p.id=x.input_id WHERE x.id=NEW.source_extraction_id;
   IF context_id IS DISTINCT FROM expected_id THEN RAISE EXCEPTION 'Correction extraction belongs to another intake'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='entry_matches' THEN
  PERFORM 1 FROM msa.medication_entry_versions WHERE id=NEW.entry_version_id AND confirmed_at IS NOT NULL FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Identification requires confirmed input'; END IF;
  IF NEW.reference_build IS NOT NULL AND NOT msa.published(NEW.reference_build) THEN RAISE EXCEPTION 'Reference build is not published'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION msa.match_complete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (SELECT count(*) FROM msa.entry_matches WHERE entry_version_id=NEW.entry_version_id AND attempt_no=NEW.attempt_no AND match_status<>'CANDIDATE')<>1
 OR EXISTS(SELECT 1 FROM msa.entry_matches WHERE entry_version_id=NEW.entry_version_id AND attempt_no=NEW.attempt_no
 AND (matcher_version<>NEW.matcher_version OR reference_build IS DISTINCT FROM NEW.reference_build)) THEN RAISE EXCEPTION 'Attempt requires one consistent outcome'; END IF;
 RETURN NULL;
END $$;
CREATE FUNCTION msa.component_document(c msa_ref.medication_ingredients) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
 SELECT jsonb_build_object('component_id',c.id::text,'source_component_id',c.source_component_id,
 'ingredient_id',c.ingredient_id::text,'name_raw',c.ingredient_name_raw,'ingredient_text_raw',c.ingredient_text_raw,
 'chemical_form_raw',c.chemical_form_raw,'equivalence_raw',c.equivalence_raw,'strength_basis',c.strength_basis,'source_locator',c.source_locator)
$$;
CREATE FUNCTION msa.snapshot_document(sid uuid) RETURNS jsonb LANGUAGE sql STABLE SET TimeZone='UTC' AS $$
 SELECT jsonb_build_object('id',s.id,'user_id',s.user_id,'context_key',s.context_key,'data_context',s.data_context,
 'as_of_epoch',extract(epoch FROM s.as_of_at),'supersedes_snapshot_id',s.supersedes_snapshot_id,
 'entries',(SELECT jsonb_agg(jsonb_build_object('entry_version_id',e.entry_version_id,'content_digest',v.content_digest,
  'entry_match_id',e.entry_match_id,'component_context',e.component_context,
  'mappings',(SELECT coalesce(jsonb_agg(to_jsonb(m) ORDER BY m.id),'[]') FROM jsonb_array_elements(e.component_context->'mapping_refs') r JOIN msa_ref.ddinter_mappings m ON m.id=(r->>'mapping_id')::uuid)) ORDER BY e.entry_version_id)
 FROM msa.snapshot_entries e JOIN msa.medication_entry_versions v ON v.id=e.entry_version_id WHERE e.snapshot_id=s.id))
 FROM msa.medication_list_snapshots s WHERE s.id=sid
$$;
CREATE FUNCTION msa.snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p msa.medication_list_snapshots%ROWTYPE; v msa.medication_entry_versions%ROWTYPE; m msa.entry_matches%ROWTYPE;
 comps jsonb; refs jsonb; wanted text;
BEGIN
 IF TG_TABLE_NAME='medication_list_snapshots' THEN
  IF TG_OP='INSERT' THEN
   IF NEW.status<>'DRAFT' THEN RAISE EXCEPTION 'Assemble DRAFT snapshot first'; END IF;
   IF NEW.supersedes_snapshot_id IS NOT NULL THEN
    SELECT * INTO p FROM msa.medication_list_snapshots WHERE id=NEW.supersedes_snapshot_id FOR UPDATE;
    IF p.status<>'SEALED' OR p.user_id<>NEW.user_id OR p.context_key<>NEW.context_key OR p.data_context<>NEW.data_context OR p.as_of_at>NEW.as_of_at THEN RAISE EXCEPTION 'Invalid snapshot predecessor'; END IF;
   END IF;
  ELSE
   IF OLD.status<>'DRAFT' OR NEW.status<>'SEALED'
    OR (to_jsonb(OLD)-ARRAY['status','snapshot_digest','sealed_at']) IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['status','snapshot_digest','sealed_at'])
    OR NOT EXISTS(SELECT 1 FROM msa.snapshot_entries WHERE snapshot_id=OLD.id) THEN RAISE EXCEPTION 'Invalid snapshot seal'; END IF;
   NEW.snapshot_digest:=msa.digest(msa.snapshot_document(OLD.id)); NEW.sealed_at:=clock_timestamp();
  END IF;
  RETURN NEW;
 END IF;
 SELECT * INTO p FROM msa.medication_list_snapshots WHERE id=NEW.snapshot_id FOR UPDATE;
 SELECT * INTO v FROM msa.medication_entry_versions WHERE id=NEW.entry_version_id;
 IF p.status IS DISTINCT FROM 'DRAFT' OR v.confirmed_at IS NULL
  OR NEW.component_context->>'input_content_digest' IS DISTINCT FROM v.content_digest THEN RAISE EXCEPTION 'Snapshot requires exact confirmed version'; END IF;
 IF EXISTS(SELECT 1 FROM msa.snapshot_entries e JOIN msa.medication_entry_versions x ON x.id=e.entry_version_id WHERE e.snapshot_id=NEW.snapshot_id AND x.item_id=v.item_id) THEN RAISE EXCEPTION 'One version per occurrence in snapshot'; END IF;
 IF NEW.entry_match_id IS NOT NULL THEN
  SELECT * INTO m FROM msa.entry_matches WHERE id=NEW.entry_match_id;
  IF m.match_status='CANDIDATE' OR m.entry_version_id<>NEW.entry_version_id OR m.user_id<>NEW.user_id THEN RAISE EXCEPTION 'Snapshot must pin its own outcome'; END IF;
  wanted:=m.match_status;
 ELSE wanted:='NOT_ATTEMPTED'; END IF;
 IF NEW.component_context->>'identification_status' IS DISTINCT FROM wanted THEN RAISE EXCEPTION 'Frozen identification mismatch'; END IF;
 IF wanted='SELECTED' THEN
  IF NEW.component_context->>'product_id' IS DISTINCT FROM m.product_id::text OR NEW.component_context->>'reference_build' IS DISTINCT FROM m.reference_build THEN RAISE EXCEPTION 'Frozen product/build mismatch'; END IF;
  SELECT coalesce(jsonb_agg(msa.component_document(c) ORDER BY ordinal),'[]') INTO comps FROM msa_ref.medication_ingredients c WHERE medication_id=m.product_id;
  SELECT coalesce(jsonb_agg(jsonb_build_object('mapping_id',d.id::text,'component_id',d.component_id::text) ORDER BY d.id),'[]') INTO refs
   FROM msa_ref.ddinter_mappings d JOIN msa_ref.medication_ingredients c ON c.id=d.component_id WHERE c.medication_id=m.product_id AND d.dataset_build=m.reference_build;
  IF NEW.component_context->'components' IS DISTINCT FROM comps OR NEW.component_context->'mapping_refs' IS DISTINCT FROM refs THEN RAISE EXCEPTION 'Frozen component/mapping membership or evidence differs from immutable REF'; END IF;
  IF p.data_context<>'SYNTHETIC_TEST' AND coalesce((msa.build_info(m.reference_build)->>'synthetic')::boolean,false) THEN RAISE EXCEPTION 'Synthetic REF cannot enter real context'; END IF;
  IF NEW.component_context->>'component_coverage'='COMPLETE' AND (jsonb_array_length(comps)=0 OR EXISTS(SELECT 1 FROM msa_ref.medications WHERE id=m.product_id AND component_count IS NULL)) THEN RAISE EXCEPTION 'Cannot claim complete unknown inventory'; END IF;
 ELSE
  IF NEW.component_context->>'product_id' IS NOT NULL OR jsonb_array_length(NEW.component_context->'components')<>0 OR jsonb_array_length(NEW.component_context->'mapping_refs')<>0
   OR (wanted='NOT_ATTEMPTED' AND NEW.component_context->>'reference_build' IS NOT NULL)
   OR (wanted<>'NOT_ATTEMPTED' AND NEW.component_context->>'reference_build' IS DISTINCT FROM m.reference_build) THEN RAISE EXCEPTION 'Unresolved input cannot acquire product/mappings'; END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION msa.finding_document(fid uuid) RETURNS jsonb LANGUAGE sql STABLE SET TimeZone='UTC' AS $$
 SELECT jsonb_build_object('finding',to_jsonb(f),'entries',
  (SELECT coalesce(jsonb_agg(to_jsonb(e) ORDER BY entry_version_id),'[]') FROM msa.finding_entries e WHERE e.finding_id=f.id))
 FROM msa.safety_findings f WHERE f.id=fid
$$;
CREATE FUNCTION msa.validate_component_refs(refs jsonb,sid uuid, finding uuid DEFAULT NULL) RETURNS void LANGUAGE plpgsql AS $$
DECLARE r jsonb;
BEGIN
 FOR r IN SELECT value FROM jsonb_array_elements(refs) LOOP
  IF NOT msa.is_uuid(r->>'entry_version_id') OR NOT msa.is_uuid(r->>'component_id')
   OR NOT EXISTS(SELECT 1 FROM msa.snapshot_entries e CROSS JOIN LATERAL jsonb_array_elements(e.component_context->'components') c
    WHERE e.snapshot_id=sid AND e.entry_version_id=(r->>'entry_version_id')::uuid AND c->>'component_id'=r->>'component_id') THEN RAISE EXCEPTION 'Component reference outside frozen entry'; END IF;
  IF finding IS NOT NULL AND NOT EXISTS(SELECT 1 FROM msa.finding_entries WHERE finding_id=finding AND entry_version_id=(r->>'entry_version_id')::uuid) THEN RAISE EXCEPTION 'Component reference is not affected by finding'; END IF;
 END LOOP;
END $$;
CREATE FUNCTION msa.finding_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a msa.safety_assessments%ROWTYPE; parent uuid; f msa.safety_findings%ROWTYPE; n integer; src jsonb; pair jsonb; targets text[];
BEGIN
 IF TG_TABLE_NAME='finding_entries' THEN
  SELECT assessment_id INTO parent FROM msa.safety_findings WHERE id=NEW.finding_id;
 ELSE parent:=NEW.assessment_id; END IF;
 SELECT * INTO a FROM msa.safety_assessments WHERE id=parent FOR UPDATE;
 IF a.execution_status IS DISTINCT FROM 'RUNNING' THEN RAISE EXCEPTION 'Finding publication requires open assessment'; END IF;
 IF TG_TABLE_NAME='safety_findings' THEN
  IF NEW.prior_finding_id IS NOT NULL THEN
   IF NOT EXISTS(SELECT 1 FROM msa.safety_findings WHERE id=NEW.prior_finding_id AND user_id=NEW.user_id AND recorded_at<=NEW.recorded_at) THEN RAISE EXCEPTION 'Invalid prior finding'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION msa.finding_complete() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE f msa.safety_findings%ROWTYPE; n integer; src jsonb; target text; targets text[];
BEGIN
 IF TG_TABLE_NAME='safety_findings' THEN SELECT * INTO f FROM msa.safety_findings WHERE id=NEW.id;
 ELSE SELECT * INTO f FROM msa.safety_findings WHERE id=NEW.finding_id; END IF;
 SELECT count(*) INTO n FROM msa.finding_entries WHERE finding_id=f.id;
 IF (f.finding_type='DDI' AND n<>2) OR (f.finding_type='DUPLICATE_INGREDIENT' AND n<2)
  OR (f.finding_type='UNRESOLVED' AND n<>1) OR (f.finding_type='SOURCE_CONFLICT' AND n<1)
  OR (f.finding_type='SYSTEM_ISSUE' AND n<>0) THEN RAISE EXCEPTION 'Invalid finding cardinality'; END IF;
 PERFORM msa.validate_component_refs(f.evidence->'component_refs',f.snapshot_id,f.id);
 IF f.finding_type='DDI' THEN
  IF jsonb_array_length(f.evidence->'sources')=0 OR jsonb_array_length(f.evidence->'component_refs')<2 THEN RAISE EXCEPTION 'DDI needs target pair source evidence'; END IF;
  FOR src IN SELECT value FROM jsonb_array_elements(f.evidence->'sources') LOOP
   IF NOT msa.is_hash(src->>'artifact_sha256') OR NOT msa.jtype(src,'locator','object')
    OR NOT msa.jtype(src,'target_ids','array') OR jsonb_array_length(src->'target_ids')<>2
    OR NOT msa.jtype(src,'source_severity','string') OR NOT msa.jtype(src,'record','object') THEN RAISE EXCEPTION 'DDI needs a retained interaction record, not mapping evidence alone'; END IF;
   IF src->'record'->'drug_id_pair' IS DISTINCT FROM src->'target_ids'
    OR src->'record'->>'original_level' IS DISTINCT FROM src->>'source_severity'
    OR src->'record'->'evidence'->>'csv_sha256' IS DISTINCT FROM src->>'artifact_sha256' THEN RAISE EXCEPTION 'DDI source fields differ from retained record'; END IF;
   SELECT array_agg(value) INTO targets FROM jsonb_array_elements_text(src->'target_ids');
   IF targets[1]=targets[2] THEN RAISE EXCEPTION 'Self target pair belongs to duplicate rule'; END IF;
   FOREACH target IN ARRAY targets LOOP
    IF NOT EXISTS(SELECT 1 FROM msa.finding_entries fe JOIN msa.snapshot_entries se ON (se.snapshot_id,se.entry_version_id)=(fe.snapshot_id,fe.entry_version_id)
     CROSS JOIN LATERAL jsonb_array_elements(se.component_context->'mapping_refs') mr
     JOIN msa_ref.ddinter_mappings dm ON dm.id=(mr->>'mapping_id')::uuid
     WHERE fe.finding_id=f.id AND dm.target_id=target) THEN RAISE EXCEPTION 'Interaction target absent from affected frozen mappings'; END IF;
   END LOOP;
   IF NOT EXISTS(SELECT 1 FROM msa.finding_entries left_fe JOIN msa.snapshot_entries left_se ON (left_se.snapshot_id,left_se.entry_version_id)=(left_fe.snapshot_id,left_fe.entry_version_id)
     CROSS JOIN LATERAL jsonb_array_elements(left_se.component_context->'mapping_refs') lm
     JOIN msa_ref.ddinter_mappings ld ON ld.id=(lm->>'mapping_id')::uuid,
     msa.finding_entries right_fe JOIN msa.snapshot_entries right_se ON (right_se.snapshot_id,right_se.entry_version_id)=(right_fe.snapshot_id,right_fe.entry_version_id)
     CROSS JOIN LATERAL jsonb_array_elements(right_se.component_context->'mapping_refs') rm
     JOIN msa_ref.ddinter_mappings rd ON rd.id=(rm->>'mapping_id')::uuid
     WHERE left_fe.finding_id=f.id AND right_fe.finding_id=f.id AND left_fe.entry_version_id<>right_fe.entry_version_id
      AND ld.target_id=targets[1] AND rd.target_id=targets[2]) THEN RAISE EXCEPTION 'Source target pair is not supported across two occurrences'; END IF;
  END LOOP;
 END IF;
 RETURN NULL;
END $$;
CREATE FUNCTION msa.coverage(checks jsonb) RETURNS text LANGUAGE sql IMMUTABLE AS $$
 SELECT CASE WHEN checks->'ddi'->>'coverage'='PENDING' OR checks->'duplicate_ingredient'->>'coverage'='PENDING' THEN 'PENDING'
 WHEN checks->'ddi'->>'coverage'='NOT_APPLICABLE' AND checks->'duplicate_ingredient'->>'coverage'='NOT_APPLICABLE' THEN 'NOT_APPLICABLE'
 WHEN checks->'ddi'->>'coverage' IN ('ASSESSED','NOT_APPLICABLE') AND checks->'duplicate_ingredient'->>'coverage' IN ('ASSESSED','NOT_APPLICABLE') THEN 'ASSESSED'
 WHEN checks->'ddi'->>'coverage' IN ('ASSESSED','PARTIAL') OR checks->'duplicate_ingredient'->>'coverage' IN ('ASSESSED','PARTIAL') THEN 'PARTIAL' ELSE 'UNASSESSED' END
$$;
CREATE FUNCTION msa.validate_checks(a msa.safety_assessments) RETURNS void LANGUAGE plpgsql AS $$
DECLARE k text; c jsonb; p jsonb; r jsonb; ids uuid[]; seen text[]; pair_key text; size integer; has_result boolean; n integer;
BEGIN
 SELECT count(*) INTO size FROM msa.snapshot_entries WHERE snapshot_id=a.snapshot_id;
 FOREACH k IN ARRAY ARRAY['ddi','duplicate_ingredient'] LOOP
  c:=a.check_results->k; seen:='{}';
  IF c->>'execution' IN ('NOT_STARTED','RUNNING') OR c->>'coverage'='PENDING' THEN RAISE EXCEPTION 'Terminal assessment contains pending check'; END IF;
  IF a.execution_status='COMPLETED' AND c->>'execution'='FAILED' THEN RAISE EXCEPTION 'Completed attempt contains failed check'; END IF;
  IF size=1 AND c->>'execution'='COMPLETED' AND c->>'coverage'<>'NOT_APPLICABLE' THEN RAISE EXCEPTION 'One occurrence has no inter-medication pair'; END IF;
  IF size>1 AND c->>'coverage'='NOT_APPLICABLE' THEN RAISE EXCEPTION 'Unresolved entries must not vanish from pair coverage'; END IF;
  FOR p IN SELECT value FROM jsonb_array_elements(c->'pair_results') LOOP
   SELECT array_agg(value::uuid ORDER BY value::uuid) INTO ids FROM jsonb_array_elements_text(p->'entry_version_ids');
   pair_key:=ids[1]::text||':'||ids[2]::text;
   IF ids[1]=ids[2] OR pair_key=ANY(seen) OR (SELECT count(*) FROM msa.snapshot_entries WHERE snapshot_id=a.snapshot_id AND entry_version_id=ANY(ids))<>2 THEN RAISE EXCEPTION 'Invalid/repeated occurrence pair'; END IF;
   seen:=array_append(seen,pair_key);
   PERFORM msa.validate_component_refs(p->'component_refs',a.snapshot_id);
   FOR r IN SELECT value FROM jsonb_array_elements(p->'source_record_refs') LOOP
    IF r ? 'finding_id' THEN
     IF NOT EXISTS(SELECT 1 FROM msa.safety_findings WHERE id=(r->>'finding_id')::uuid AND assessment_id=a.id
      AND (r->>'source_index')::integer>=0 AND (r->>'source_index')::integer<jsonb_array_length(evidence->'sources')) THEN RAISE EXCEPTION 'Pair refers to invalid source finding'; END IF;
    ELSIF NOT (msa.is_hash(r->>'artifact_sha256') AND msa.jtype(r,'locator','object')) THEN RAISE EXCEPTION 'Invalid source record reference'; END IF;
   END LOOP;
  END LOOP;
  IF coalesce(array_length(seen,1),0)<>size*(size-1)/2 THEN RAISE EXCEPTION 'All supplied occurrence pairs must remain represented'; END IF;
  IF c->>'coverage'='ASSESSED' THEN
   IF k='ddi' AND NOT coalesce((a.knowledge_builds->'ddinter'->'loaded_scope'->>'interaction_coverage_complete')::boolean,false) THEN RAISE EXCEPTION 'DDI coverage cannot exceed pinned knowledge scope'; END IF;
   IF EXISTS(SELECT 1 FROM msa.snapshot_entries WHERE snapshot_id=a.snapshot_id AND component_context->>'component_coverage'<>'COMPLETE')
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(c->'pair_results') p WHERE p->>'status' IN ('UNASSESSED','SOURCE_CONFLICT','NO_RECORD_IN_LOADED_SUBSET')) THEN RAISE EXCEPTION 'Coverage exceeds supported results'; END IF;
   IF k='ddi' AND EXISTS(SELECT 1 FROM msa.snapshot_entries se CROSS JOIN LATERAL jsonb_array_elements(se.component_context->'components') comp
    WHERE se.snapshot_id=a.snapshot_id AND (SELECT count(DISTINCT dm.target_id) FROM jsonb_array_elements(se.component_context->'mapping_refs') ref JOIN msa_ref.ddinter_mappings dm ON dm.id=(ref->>'mapping_id')::uuid
     WHERE ref->>'component_id'=comp->>'component_id' AND dm.target_id IS NOT NULL)<>1) THEN RAISE EXCEPTION 'Complete DDI coverage needs reliable component targets'; END IF;
  END IF;
  SELECT EXISTS(SELECT 1 FROM msa.safety_findings WHERE assessment_id=a.id AND finding_type=CASE WHEN k='ddi' THEN 'DDI' ELSE 'DUPLICATE_INGREDIENT' END) INTO has_result;
  IF has_result AND c->>'coverage' NOT IN ('ASSESSED','PARTIAL') THEN RAISE EXCEPTION 'Retained positive finding requires at least partial coverage'; END IF;
 END LOOP;
END $$;
CREATE FUNCTION msa.assessment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE snap msa.medication_list_snapshots%ROWTYPE; refs jsonb;
BEGIN
 IF TG_OP='INSERT' THEN
  SELECT * INTO snap FROM msa.medication_list_snapshots WHERE id=NEW.snapshot_id;
  IF snap.status IS DISTINCT FROM 'SEALED' OR NEW.execution_status<>'RUNNING' OR NEW.knowledge_builds->>'snapshot_digest' IS DISTINCT FROM snap.snapshot_digest THEN RAISE EXCEPTION 'Assessment requires sealed exact snapshot'; END IF;
  IF NEW.retry_of_assessment_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM msa.safety_assessments WHERE id=NEW.retry_of_assessment_id AND execution_status<>'RUNNING') THEN RAISE EXCEPTION 'Retry requires terminal predecessor'; END IF;
  SELECT coalesce(jsonb_agg(DISTINCT e.component_context->>'reference_build' ORDER BY e.component_context->>'reference_build') FILTER(WHERE e.component_context->>'reference_build' IS NOT NULL),'[]')
   INTO refs FROM msa.snapshot_entries e WHERE snapshot_id=NEW.snapshot_id;
  IF NEW.knowledge_builds->'reference_builds' IS DISTINCT FROM refs THEN RAISE EXCEPTION 'Reference dependencies differ from frozen snapshot'; END IF;
  IF snap.data_context<>'SYNTHETIC_TEST' AND coalesce((NEW.knowledge_builds->'ddinter'->>'synthetic')::boolean,false) THEN RAISE EXCEPTION 'Synthetic knowledge requires synthetic context'; END IF;
 ELSE
  IF OLD.execution_status<>'RUNNING' OR NEW.execution_status NOT IN ('COMPLETED','FAILED')
   OR (to_jsonb(OLD)-ARRAY['execution_status','check_results','error_details','result_digest','finished_at'])
    IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['execution_status','check_results','error_details','result_digest','finished_at']) THEN RAISE EXCEPTION 'Assessment dependency/history is immutable'; END IF;
  PERFORM msa.validate_checks(NEW);
  NEW.finished_at:=clock_timestamp();
  NEW.result_digest:=msa.digest(jsonb_build_object('snapshot_id',OLD.snapshot_id,'knowledge_builds',OLD.knowledge_builds,'engine_version',OLD.engine_version,
   'execution_status',NEW.execution_status,'checks',NEW.check_results,'error',NEW.error_details,
   'findings',(SELECT coalesce(jsonb_agg(msa.finding_document(id) ORDER BY id),'[]') FROM msa.safety_findings WHERE assessment_id=OLD.id)));
 END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION msa.validate_manifest(doc jsonb, owner_id uuid) RETURNS void LANGUAGE plpgsql AS $$
DECLARE r jsonb; actual text;
BEGIN
 IF NOT msa.valid_document(doc,'summary-manifest.v4') THEN RAISE EXCEPTION 'Invalid summary manifest'; END IF;
 FOR r IN SELECT value FROM jsonb_array_elements(doc->'sources') LOOP
  actual:=NULL;
  CASE r->>'kind'
   WHEN 'HEALTH_SOURCE' THEN SELECT content_digest INTO actual FROM msa.patient_health_sources WHERE id=(r->>'id')::uuid AND user_id=owner_id;
   WHEN 'ENTRY_VERSION' THEN SELECT content_digest INTO actual FROM msa.medication_entry_versions WHERE id=(r->>'id')::uuid AND user_id=owner_id AND confirmed_at IS NOT NULL;
   WHEN 'SNAPSHOT' THEN SELECT snapshot_digest INTO actual FROM msa.medication_list_snapshots WHERE id=(r->>'id')::uuid AND user_id=owner_id AND status='SEALED';
   WHEN 'ASSESSMENT' THEN SELECT result_digest INTO actual FROM msa.safety_assessments WHERE id=(r->>'id')::uuid AND user_id=owner_id AND execution_status<>'RUNNING';
   WHEN 'FINDING' THEN SELECT msa.digest(msa.finding_document(id)) INTO actual FROM msa.safety_findings WHERE id=(r->>'id')::uuid AND user_id=owner_id;
   WHEN 'REF_MEDICATION' THEN SELECT msa.digest(to_jsonb(m)) INTO actual FROM msa_ref.medications m WHERE id=(r->>'id')::uuid AND dataset_build=r->>'dataset_build' AND msa.published(dataset_build);
   WHEN 'EXTERNAL_DOCUMENT' THEN
    IF NOT msa.jtype(r->'locator','uri','string') THEN RAISE EXCEPTION 'External document needs retained locator'; END IF;
    actual:=r->'locator'->>'artifact_sha256';
  END CASE;
  IF actual IS NULL OR actual IS DISTINCT FROM r->>'digest' THEN RAISE EXCEPTION 'Missing/cross-owner/changed/unconfirmed summary source'; END IF;
 END LOOP;
END $$;
CREATE FUNCTION msa.health_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous msa.patient_health_sources%ROWTYPE;
BEGIN
 IF NEW.source_locator ? 'message_id' AND (NEW.message_id IS NULL OR NEW.source_locator->>'message_id' IS DISTINCT FROM NEW.message_id::text) THEN RAISE EXCEPTION 'Health source message mismatch'; END IF;
 IF NEW.supersedes_source_id IS NOT NULL THEN
  SELECT * INTO previous FROM msa.patient_health_sources WHERE id=NEW.supersedes_source_id;
  IF previous.origin IS DISTINCT FROM NEW.origin THEN RAISE EXCEPTION 'Replacement cannot change origin'; END IF;
 END IF;
 IF NEW.verification_status='PATIENT_CONFIRMED' AND (NEW.source_locator->>'actor_id' IS DISTINCT FROM NEW.user_id::text OR NOT msa.jtype(NEW.source_locator,'confirmed_at','string')) THEN RAISE EXCEPTION 'Patient source confirmation needs actual owner evidence'; END IF;
 IF NEW.verification_status='SOURCE_VERIFIED' AND NOT msa.jtype(NEW.source_locator,'evidence_locator','object') THEN RAISE EXCEPTION 'Source verification needs evidence'; END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION msa.summary_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prior msa.patient_health_summaries%ROWTYPE; w msa.workflow_instances%ROWTYPE; digest text; r jsonb; key text;
BEGIN
 PERFORM msa.validate_manifest(NEW.source_manifest,NEW.user_id);
 digest:=msa.summary_digest(NEW.summary_content,NEW.source_manifest);
 IF nullif(current_setting('msa.displayed_digest',true),'') IS DISTINCT FROM digest THEN RAISE EXCEPTION 'Summary is not the exact displayed content and manifest'; END IF;
 IF NEW.version_no>1 THEN
  PERFORM 1 FROM msa.patient_health_summaries WHERE id=NEW.series_root_id FOR UPDATE;
  SELECT * INTO prior FROM msa.patient_health_summaries WHERE series_root_id=NEW.series_root_id ORDER BY version_no DESC LIMIT 1;
  IF NEW.version_no<>prior.version_no+1 OR NEW.supersedes_summary_id IS DISTINCT FROM prior.id OR NEW.confirmed_at<prior.confirmed_at THEN RAISE EXCEPTION 'Summary must extend latest version'; END IF;
 END IF;
 IF NEW.workflow_id IS NOT NULL THEN
  SELECT * INTO w FROM msa.workflow_instances WHERE id=NEW.workflow_id FOR UPDATE;
  IF w.workflow_type<>'PATIENT_SUMMARY' OR w.state<>'AWAITING_CONFIRMATION' OR w.revision<>NEW.draft_revision
   OR w.context->'pending_confirmation'->>'payload_digest' IS DISTINCT FROM digest
   OR w.context->'pending_confirmation'->>'draft_revision' IS DISTINCT FROM NEW.draft_revision::text
   OR w.context->'draft'->'content' IS DISTINCT FROM NEW.summary_content OR w.context->'draft'->'source_manifest' IS DISTINCT FROM NEW.source_manifest THEN RAISE EXCEPTION 'Summary does not match pending workflow draft'; END IF;
 END IF;
 IF NEW.medication_snapshot_id IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM msa.medication_list_snapshots WHERE id=NEW.medication_snapshot_id AND status='SEALED') OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.source_manifest->'sources') s WHERE s->>'kind'='SNAPSHOT' AND s->>'id'=NEW.medication_snapshot_id::text) THEN RAISE EXCEPTION 'Manifest must include selected sealed snapshot'; END IF;
 END IF;
 IF NEW.primary_assessment_id IS NOT NULL AND (NOT EXISTS(SELECT 1 FROM msa.safety_assessments WHERE id=NEW.primary_assessment_id AND execution_status<>'RUNNING') OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.source_manifest->'sources') s WHERE s->>'kind'='ASSESSMENT' AND s->>'id'=NEW.primary_assessment_id::text)) THEN RAISE EXCEPTION 'Manifest must include terminal primary assessment'; END IF;
 FOR r IN SELECT value FROM jsonb_array_elements(NEW.summary_content->'sections')
  UNION ALL SELECT value FROM jsonb_array_elements(NEW.summary_content->'medications')
  UNION ALL SELECT value FROM jsonb_array_elements(NEW.summary_content->'safety_findings') LOOP
  FOR key IN SELECT value FROM jsonb_array_elements_text(coalesce(r->'source_keys','[]')) LOOP
   IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(NEW.source_manifest->'sources') s WHERE s->>'key'=key) THEN RAISE EXCEPTION 'Summary claim has unknown source key'; END IF;
  END LOOP;
 END LOOP;
 RETURN NEW;
END $$;
CREATE FUNCTION msa.workflow_refs_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r jsonb; target uuid;
BEGIN
 FOR r IN SELECT value FROM jsonb_array_elements(NEW.context->'pending_questions') LOOP
  IF r->>'target_id' IS NOT NULL THEN
   target:=(r->>'target_id')::uuid;
   IF NOT EXISTS(
    SELECT 1 FROM msa.medication_entry_versions WHERE id=target AND user_id=NEW.user_id
    UNION ALL SELECT 1 FROM msa.intake_items WHERE id=target AND user_id=NEW.user_id
    UNION ALL SELECT 1 FROM msa.intake_sessions WHERE id=target AND user_id=NEW.user_id
    UNION ALL SELECT 1 FROM msa.patient_health_sources WHERE id=target AND user_id=NEW.user_id
    UNION ALL SELECT 1 FROM msa.medication_list_snapshots WHERE id=target AND user_id=NEW.user_id
    UNION ALL SELECT 1 FROM msa.safety_findings WHERE id=target AND user_id=NEW.user_id) THEN RAISE EXCEPTION 'Question target is missing or belongs to another owner'; END IF;
  END IF;
 END LOOP;
 IF NEW.context->'draft' ? 'source_manifest' THEN PERFORM msa.validate_manifest(NEW.context->'draft'->'source_manifest',NEW.user_id); END IF;
 IF NEW.state='AWAITING_CONFIRMATION' AND NEW.workflow_type='PATIENT_SUMMARY' THEN
  IF NOT msa.valid_document(NEW.context->'draft'->'content','patient-summary.v4')
   OR NOT msa.valid_document(NEW.context->'draft'->'generation_context','summary-generation.v4')
   OR NEW.context->'pending_confirmation'->>'payload_digest' IS DISTINCT FROM msa.summary_digest(NEW.context->'draft'->'content',NEW.context->'draft'->'source_manifest')
   OR NEW.context->'draft'->>'draft_revision' IS DISTINCT FROM NEW.revision::text THEN RAISE EXCEPTION 'Invalid displayed summary draft/revision/digest'; END IF;
 END IF;
 IF NEW.context->'pending_confirmation' ? 'entry_version_ids' THEN
  FOR r IN SELECT value FROM jsonb_array_elements(NEW.context->'pending_confirmation'->'entry_version_ids') LOOP
   IF NOT EXISTS(SELECT 1 FROM msa.medication_entry_versions WHERE id=(r#>>'{}')::uuid AND user_id=NEW.user_id) THEN RAISE EXCEPTION 'Confirmation contains foreign/missing entry'; END IF;
  END LOOP;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER c_workflow_refs BEFORE INSERT OR UPDATE ON msa.workflow_instances FOR EACH ROW EXECUTE FUNCTION msa.workflow_refs_guard();
CREATE TRIGGER reference_guard BEFORE INSERT OR UPDATE OR DELETE ON msa_ref.medications FOR EACH ROW EXECUTE FUNCTION msa.ref_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa_ref.medications FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER reference_guard BEFORE INSERT OR UPDATE OR DELETE ON msa_ref.ingredients FOR EACH ROW EXECUTE FUNCTION msa.ref_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa_ref.ingredients FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER reference_guard BEFORE INSERT OR UPDATE OR DELETE ON msa_ref.medication_ingredients FOR EACH ROW EXECUTE FUNCTION msa.ref_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa_ref.medication_ingredients FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER reference_guard BEFORE INSERT OR UPDATE OR DELETE ON msa_ref.ddinter_mappings FOR EACH ROW EXECUTE FUNCTION msa.ref_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa_ref.ddinter_mappings FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.conversation_sessions FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.conversation_sessions FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.conversation_messages FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.conversation_messages FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.workflow_instances FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.workflow_instances FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.intake_sessions FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.intake_sessions FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.intake_inputs FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.intake_inputs FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.intake_extractions FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.intake_extractions FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.intake_items FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.intake_items FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.medication_entry_versions FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.medication_entry_versions FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.entry_matches FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.entry_matches FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.medication_list_snapshots FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.medication_list_snapshots FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.snapshot_entries FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.snapshot_entries FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.safety_assessments FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.safety_assessments FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.safety_findings FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.safety_findings FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.finding_entries FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.finding_entries FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.patient_health_sources FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.patient_health_sources FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER a_owner_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.patient_health_summaries FOR EACH ROW EXECUTE FUNCTION msa.owner_guard();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.patient_health_summaries FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER b_context_guard BEFORE INSERT OR UPDATE ON msa.conversation_sessions FOR EACH ROW EXECUTE FUNCTION msa.context_guard();
CREATE TRIGGER b_context_guard BEFORE INSERT ON msa.conversation_messages FOR EACH ROW EXECUTE FUNCTION msa.context_guard();
CREATE TRIGGER b_context_guard BEFORE INSERT OR UPDATE ON msa.workflow_instances FOR EACH ROW EXECUTE FUNCTION msa.context_guard();
CREATE TRIGGER b_context_guard BEFORE INSERT OR UPDATE ON msa.intake_sessions FOR EACH ROW EXECUTE FUNCTION msa.context_guard();
CREATE TRIGGER b_context_guard BEFORE INSERT ON msa.intake_inputs FOR EACH ROW EXECUTE FUNCTION msa.context_guard();
CREATE TRIGGER b_context_guard BEFORE INSERT ON msa.intake_items FOR EACH ROW EXECUTE FUNCTION msa.context_guard();
CREATE TRIGGER b_context_guard BEFORE INSERT OR UPDATE ON msa.medication_entry_versions FOR EACH ROW EXECUTE FUNCTION msa.context_guard();
CREATE TRIGGER b_context_guard BEFORE INSERT ON msa.entry_matches FOR EACH ROW EXECUTE FUNCTION msa.context_guard();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.conversation_messages FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.intake_inputs FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.intake_extractions FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.intake_items FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.entry_matches FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.snapshot_entries FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.safety_findings FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.finding_entries FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.patient_health_sources FOR EACH ROW EXECUTE FUNCTION msa.reject_change();
CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON msa.patient_health_summaries FOR EACH ROW EXECUTE FUNCTION msa.reject_change();

CREATE CONSTRAINT TRIGGER match_attempt_complete AFTER INSERT ON msa.entry_matches DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION msa.match_complete();
CREATE TRIGGER b_snapshot_guard BEFORE INSERT OR UPDATE ON msa.medication_list_snapshots FOR EACH ROW EXECUTE FUNCTION msa.snapshot_guard();
CREATE TRIGGER b_snapshot_entry_guard BEFORE INSERT ON msa.snapshot_entries FOR EACH ROW EXECUTE FUNCTION msa.snapshot_guard();
CREATE TRIGGER b_assessment_guard BEFORE INSERT OR UPDATE ON msa.safety_assessments FOR EACH ROW EXECUTE FUNCTION msa.assessment_guard();
CREATE TRIGGER b_finding_guard BEFORE INSERT ON msa.safety_findings FOR EACH ROW EXECUTE FUNCTION msa.finding_guard();
CREATE TRIGGER b_finding_entry_guard BEFORE INSERT ON msa.finding_entries FOR EACH ROW EXECUTE FUNCTION msa.finding_guard();
CREATE CONSTRAINT TRIGGER finding_complete AFTER INSERT ON msa.safety_findings DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION msa.finding_complete();
CREATE CONSTRAINT TRIGGER finding_members_complete AFTER INSERT ON msa.finding_entries DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION msa.finding_complete();
CREATE TRIGGER b_health_guard BEFORE INSERT ON msa.patient_health_sources FOR EACH ROW EXECUTE FUNCTION msa.health_guard();
CREATE TRIGGER b_summary_guard BEFORE INSERT ON msa.patient_health_summaries FOR EACH ROW EXECUTE FUNCTION msa.summary_guard();
