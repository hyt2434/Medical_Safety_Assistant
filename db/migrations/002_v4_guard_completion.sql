-- Preserve existing V4 data/history and apply the completed local guard improvements.

-- Compatible with the audited earlier V4 baseline; no tables or stored digests change.

CREATE OR REPLACE FUNCTION msa.ref_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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

CREATE OR REPLACE FUNCTION msa.assert_ref_build(build text) RETURNS void LANGUAGE plpgsql AS $$
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

CREATE OR REPLACE FUNCTION msa.finding_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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

CREATE OR REPLACE FUNCTION msa.finding_complete() RETURNS trigger LANGUAGE plpgsql AS $$
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

CREATE OR REPLACE FUNCTION msa.validate_checks(a msa.safety_assessments) RETURNS void LANGUAGE plpgsql AS $$
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
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(c->'pair_results') AS pair_result(value) WHERE pair_result.value->>'status' IN ('UNASSESSED','SOURCE_CONFLICT','NO_RECORD_IN_LOADED_SUBSET')) THEN RAISE EXCEPTION 'Coverage exceeds supported results'; END IF;
   IF k='ddi' AND EXISTS(SELECT 1 FROM msa.snapshot_entries se CROSS JOIN LATERAL jsonb_array_elements(se.component_context->'components') comp
    WHERE se.snapshot_id=a.snapshot_id AND (SELECT count(DISTINCT dm.target_id) FROM jsonb_array_elements(se.component_context->'mapping_refs') ref JOIN msa_ref.ddinter_mappings dm ON dm.id=(ref->>'mapping_id')::uuid
     WHERE ref->>'component_id'=comp->>'component_id' AND dm.target_id IS NOT NULL)<>1) THEN RAISE EXCEPTION 'Complete DDI coverage needs reliable component targets'; END IF;
  END IF;
  SELECT EXISTS(SELECT 1 FROM msa.safety_findings WHERE assessment_id=a.id AND finding_type=CASE WHEN k='ddi' THEN 'DDI' ELSE 'DUPLICATE_INGREDIENT' END) INTO has_result;
  IF has_result AND c->>'coverage' NOT IN ('ASSESSED','PARTIAL') THEN RAISE EXCEPTION 'Retained positive finding requires at least partial coverage'; END IF;
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION msa.workflow_refs_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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

CREATE OR REPLACE TRIGGER c_workflow_refs BEFORE INSERT OR UPDATE ON msa.workflow_instances FOR EACH ROW EXECUTE FUNCTION msa.workflow_refs_guard();
