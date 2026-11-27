-- Complete fail-closed access, exact dose occurrences and transactional audit.
CREATE OR REPLACE FUNCTION msa.has_server_permission(permission text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT CASE WHEN msa.actor_id() IS NULL THEN false ELSE
  coalesce(nullif(current_setting('msa.authenticated_permissions',true),'')::jsonb ? permission,false) END
$$;
ALTER TABLE msa.review_outcomes ADD CONSTRAINT outcome_schedule_pair CHECK((schedule_id IS NULL)=(reviewed_content_digest IS NULL));
ALTER TABLE msa.reminder_settings DROP CONSTRAINT reminder_settings_notification_preferences_check;
ALTER TABLE msa.reminder_settings ADD CONSTRAINT notification_preferences_shape CHECK(
 msa.jtype(notification_preferences,'schema','string') AND notification_preferences->>'schema'='notification-preferences.v1'
 AND msa.jtype(notification_preferences,'channel','string') AND notification_preferences->>'channel' IN ('IN_APP','BROWSER'));

CREATE FUNCTION msa.schedule_copies_instructions(entry_id uuid, owner_id uuid, details jsonb) RETURNS boolean
 LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT FROM msa.medication_entry_versions v WHERE v.id=$1 AND v.user_id=$2 AND NOT EXISTS(
   SELECT FROM jsonb_array_elements_text($3->'times') timing WHERE NOT EXISTS(
    SELECT FROM jsonb_array_elements(v.medication_fields->'administrations') adm
    WHERE coalesce(adm->>'dose_raw',v.medication_fields->>'dose_raw')=$3->>'dose_raw'
     AND (adm->>'timing_raw') ~ ('(^|[^0-9])'||timing||'([^0-9]|$)'))))
$$;
CREATE OR REPLACE FUNCTION msa.can_access_case(case_id uuid, owner_id uuid) RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,msa AS $$
 SELECT coalesce(msa.actor_id()=$2,false) OR EXISTS (
  SELECT FROM msa.review_cases c JOIN msa.review_case_permissions p ON p.case_id=c.id AND p.user_id=c.user_id
  WHERE c.id=$1 AND c.user_id=$2 AND c.assigned_hcp_id=msa.actor_id()
   AND c.status IN ('OPEN','IN_REVIEW','CLOSED') AND p.hcp_id=msa.actor_id()
   AND p.granted_at<=statement_timestamp() AND p.revoked_at IS NULL
   AND (p.expires_at IS NULL OR p.expires_at>statement_timestamp())
   AND msa.has_server_permission('clinical.case_review'))
$$;
CREATE FUNCTION msa.domain_access_completion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actor uuid:=msa.actor_id(); ticket msa.support_tickets; schedule msa.medication_schedules;
BEGIN
 IF actor IS NULL THEN RAISE EXCEPTION 'Authenticated actor required'; END IF;
 IF TG_TABLE_NAME='support_messages' THEN
  SELECT * INTO STRICT ticket FROM msa.support_tickets WHERE id=NEW.ticket_id FOR UPDATE;
  IF NEW.author_user_id IS DISTINCT FROM actor OR NOT coalesce(actor=ticket.requester_user_id OR
    (actor=ticket.assigned_support_user_id AND msa.has_server_permission('operations.queue')),false)
   THEN RAISE EXCEPTION 'Ticket reply denied'; END IF;
 ELSIF TG_TABLE_NAME='support_tickets' AND TG_OP='UPDATE' THEN
  IF NOT coalesce(actor=OLD.requester_user_id OR msa.has_server_permission('operations.assign') OR
    (actor=OLD.assigned_support_user_id AND msa.has_server_permission('operations.queue')),false)
   THEN RAISE EXCEPTION 'Ticket access denied'; END IF;
 ELSIF TG_TABLE_NAME='dose_records' THEN
  SELECT * INTO STRICT schedule FROM msa.medication_schedules WHERE id=NEW.schedule_id AND user_id=NEW.user_id FOR UPDATE;
  IF NOT (schedule.schedule_details->'times' ? to_char(NEW.scheduled_for AT TIME ZONE schedule.timezone,'HH24:MI'))
   OR extract(second FROM NEW.scheduled_for)<>0 THEN RAISE EXCEPTION 'Dose occurrence is outside the exact schedule'; END IF;
 ELSIF TG_TABLE_NAME='medication_schedules' THEN
  IF NEW.verification_status='PATIENT_CONFIRMED' AND NOT msa.schedule_copies_instructions(NEW.entry_version_id,NEW.user_id,NEW.schedule_details)
   THEN RAISE EXCEPTION 'Patient may confirm copied instructions only; proposed timing needs HCP'; END IF;
 ELSIF TG_TABLE_NAME='reminder_settings' THEN
  IF NEW.enabled AND (TG_OP='INSERT' OR NOT OLD.enabled) THEN
   SELECT * INTO STRICT schedule FROM msa.medication_schedules WHERE id=NEW.schedule_id AND user_id=NEW.user_id FOR UPDATE;
   IF EXISTS(SELECT FROM msa.medication_entry_versions old JOIN msa.medication_entry_versions newer
     ON newer.item_id=old.item_id AND newer.version_no>old.version_no WHERE old.id=schedule.entry_version_id)
    THEN RAISE EXCEPTION 'New reminder targets stale medication version'; END IF;
   IF EXISTS(SELECT FROM msa.safety_assessments a JOIN msa.snapshot_entries se ON se.snapshot_id=a.snapshot_id
     JOIN msa.medication_entry_versions old ON old.id=se.entry_version_id
     JOIN msa.medication_entry_versions newer ON newer.item_id=old.item_id AND newer.version_no>old.version_no
     WHERE a.id=NEW.last_assessment_id AND a.user_id=NEW.user_id)
    THEN RAISE EXCEPTION 'Assessment medication list is stale'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER a_access_complete BEFORE INSERT OR UPDATE ON msa.support_tickets FOR EACH ROW EXECUTE FUNCTION msa.domain_access_completion();
CREATE TRIGGER a_access_complete BEFORE INSERT ON msa.support_messages FOR EACH ROW EXECUTE FUNCTION msa.domain_access_completion();
CREATE TRIGGER a_access_complete BEFORE INSERT ON msa.dose_records FOR EACH ROW EXECUTE FUNCTION msa.domain_access_completion();
CREATE TRIGGER a_access_complete BEFORE INSERT OR UPDATE ON msa.reminder_settings FOR EACH ROW EXECUTE FUNCTION msa.domain_access_completion();
CREATE TRIGGER a_access_complete BEFORE INSERT OR UPDATE ON msa.medication_schedules FOR EACH ROW EXECUTE FUNCTION msa.domain_access_completion();

-- Existing Core reads now set a transaction-local server identity as writes do.
-- Raw history, sources and summaries are owner-only. Case consent grants only
-- the exact medication/snapshot/assessment context, never the whole profile.
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['conversation_sessions','conversation_messages','workflow_instances','intake_sessions',
  'intake_inputs','intake_extractions','intake_items','medication_entry_versions','entry_matches',
  'medication_list_snapshots','snapshot_entries','safety_assessments','safety_findings','finding_entries',
  'patient_health_sources','patient_health_summaries'] LOOP
  EXECUTE format('ALTER TABLE msa.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE msa.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY owner_access ON msa.%I USING (user_id=msa.actor_id()) WITH CHECK (user_id=msa.actor_id())',tab);
 END LOOP;
END $$;
CREATE POLICY case_assessment_read ON msa.safety_assessments FOR SELECT USING(EXISTS(
 SELECT FROM msa.review_cases c WHERE c.safety_assessment_id=safety_assessments.id AND msa.can_access_case(c.id,c.user_id)));
CREATE POLICY case_findings_read ON msa.safety_findings FOR SELECT USING(EXISTS(
 SELECT FROM msa.review_cases c WHERE c.safety_assessment_id=safety_findings.assessment_id AND msa.can_access_case(c.id,c.user_id)));
CREATE POLICY case_snapshot_read ON msa.medication_list_snapshots FOR SELECT USING(EXISTS(
 SELECT FROM msa.review_cases c JOIN msa.safety_assessments a ON a.id=c.safety_assessment_id
 WHERE a.snapshot_id=medication_list_snapshots.id AND msa.can_access_case(c.id,c.user_id)));
CREATE POLICY case_snapshot_entries_read ON msa.snapshot_entries FOR SELECT USING(EXISTS(
 SELECT FROM msa.review_cases c JOIN msa.safety_assessments a ON a.id=c.safety_assessment_id
 WHERE a.snapshot_id=snapshot_entries.snapshot_id AND msa.can_access_case(c.id,c.user_id)));
CREATE POLICY case_finding_entries_read ON msa.finding_entries FOR SELECT USING(EXISTS(
 SELECT FROM msa.review_cases c JOIN msa.safety_findings f ON f.assessment_id=c.safety_assessment_id
 WHERE f.id=finding_entries.finding_id AND msa.can_access_case(c.id,c.user_id)));
CREATE POLICY case_medication_read ON msa.medication_entry_versions FOR SELECT USING(EXISTS(
 SELECT FROM msa.review_cases c LEFT JOIN msa.medication_schedules s ON s.id=c.schedule_id
 LEFT JOIN msa.safety_assessments a ON a.id=c.safety_assessment_id
 WHERE c.user_id=medication_entry_versions.user_id AND msa.can_access_case(c.id,c.user_id)
  AND (s.entry_version_id=medication_entry_versions.id OR EXISTS(SELECT FROM msa.snapshot_entries se
   WHERE se.snapshot_id=a.snapshot_id AND se.entry_version_id=medication_entry_versions.id))));
CREATE POLICY case_match_read ON msa.entry_matches FOR SELECT USING(EXISTS(
 SELECT FROM msa.medication_entry_versions e WHERE e.id=entry_matches.entry_version_id AND e.user_id=entry_matches.user_id));
DROP POLICY domain_access ON msa.medication_schedules;
CREATE POLICY domain_access ON msa.medication_schedules USING(user_id=msa.actor_id() OR EXISTS(
 SELECT FROM msa.review_cases c WHERE c.schedule_id=medication_schedules.id AND msa.can_access_case(c.id,c.user_id)))
 WITH CHECK(user_id=msa.actor_id());
DROP POLICY domain_access ON msa.support_messages;
CREATE POLICY domain_access ON msa.support_messages USING(EXISTS(SELECT FROM msa.support_tickets t
 WHERE t.id=support_messages.ticket_id AND (t.requester_user_id=msa.actor_id()
  OR (t.assigned_support_user_id=msa.actor_id() AND msa.has_server_permission('operations.queue')))));
DROP POLICY domain_access ON msa.audit_events;
CREATE POLICY domain_access ON msa.audit_events USING(actor_user_id=msa.actor_id() OR subject_user_id=msa.actor_id()
 OR msa.has_server_permission('admin.audit')) WITH CHECK(actor_user_id=msa.actor_id());

CREATE FUNCTION msa.audit_business_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_row jsonb:=to_jsonb(NEW); actor uuid:=msa.actor_id(); resource text;
BEGIN
 IF actor IS NULL THEN RAISE EXCEPTION 'Business writes require authenticated actor'; END IF;
 resource:=coalesce(current_row->>'id',concat_ws(':',current_row->>'finding_id',current_row->>'entry_version_id'));
 INSERT INTO msa.audit_events(actor_user_id,subject_user_id,action,resource_type,resource_id,outcome,details)
 VALUES(actor,coalesce(current_row->>'user_id',current_row->>'requester_user_id')::uuid,
  TG_TABLE_NAME||'.'||lower(TG_OP),TG_TABLE_SCHEMA||'.'||TG_TABLE_NAME,resource,'SUCCESS',
  jsonb_build_object('schema','business-audit.v1','reason',null,
   'previous_digest',CASE WHEN TG_OP='UPDATE' THEN msa.digest(to_jsonb(OLD)) ELSE NULL END,
   'current_digest',msa.digest(current_row)));
 RETURN NEW;
END $$;
DO $$ DECLARE tab text; BEGIN
 FOR tab IN SELECT tablename FROM pg_tables WHERE schemaname='msa' AND tablename<>'audit_events' LOOP
  EXECUTE format('CREATE TRIGGER z_business_audit AFTER INSERT OR UPDATE ON msa.%I FOR EACH ROW EXECUTE FUNCTION msa.audit_business_change()',tab);
 END LOOP;
END $$;

CREATE OR REPLACE FUNCTION msa.system_domain_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE j jsonb:=to_jsonb(NEW); prev jsonb; actor uuid:=msa.actor_id(); source jsonb;
 s msa.medication_schedules; c msa.review_cases; p msa.support_tickets; a msa.safety_assessments;
 d text; entry_digest text;
BEGIN
 IF actor IS NULL THEN RAISE EXCEPTION 'Authenticated actor required'; END IF;
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Domain history cannot be deleted'; END IF;
 IF TG_TABLE_NAME IN ('review_case_messages','review_outcomes') THEN
  IF NOT msa.can_access_case(NEW.case_id,NEW.user_id) THEN RAISE EXCEPTION 'Case access denied'; END IF;
  SELECT * INTO STRICT c FROM msa.review_cases WHERE id=NEW.case_id AND user_id=NEW.user_id FOR UPDATE;
  IF TG_TABLE_NAME='review_case_messages' THEN
   IF NEW.sender_user_id<>actor THEN RAISE EXCEPTION 'Sender mismatch'; END IF;
  END IF;
  IF TG_TABLE_NAME='review_outcomes' THEN
   IF actor=NEW.user_id OR NEW.reviewer_id<>actor OR c.assigned_hcp_id<>actor
    OR c.status NOT IN ('OPEN','IN_REVIEW') OR NEW.review_type<>c.case_type THEN RAISE EXCEPTION 'Assigned HCP review required'; END IF;
   IF NEW.schedule_id IS NOT NULL THEN
    SELECT * INTO STRICT s FROM msa.medication_schedules WHERE id=NEW.schedule_id AND user_id=NEW.user_id;
    IF NEW.reviewed_content_digest<>s.content_digest OR EXISTS(SELECT FROM msa.medication_schedules WHERE supersedes_schedule_id=s.id)
     THEN RAISE EXCEPTION 'Review targets stale schedule'; END IF;
   END IF;
  END IF;
 ELSIF TG_TABLE_NAME='dataset_review_decisions' THEN
  IF NEW.reviewer_user_id<>actor OR NOT msa.has_server_permission('catalog.review') THEN RAISE EXCEPTION 'Dataset reviewer required'; END IF;
 ELSIF TG_TABLE_NAME='audit_events' THEN
  IF NEW.actor_user_id IS DISTINCT FROM actor THEN RAISE EXCEPTION 'Audit actor mismatch'; END IF;
 ELSIF TG_TABLE_NAME='support_tickets' THEN
  IF TG_OP='INSERT' AND NEW.requester_user_id<>actor THEN RAISE EXCEPTION 'Ticket requester mismatch'; END IF;
  IF TG_OP='UPDATE' AND actor<>OLD.requester_user_id AND NOT (msa.has_server_permission('operations.queue')
   AND (actor=OLD.assigned_support_user_id OR msa.has_server_permission('operations.assign'))) THEN RAISE EXCEPTION 'Ticket access denied'; END IF;
  IF TG_OP='INSERT' AND NEW.assigned_support_user_id IS NOT NULL THEN RAISE EXCEPTION 'Assignment requires separate staff action'; END IF;
  IF TG_OP='UPDATE' AND NEW.assigned_support_user_id IS DISTINCT FROM OLD.assigned_support_user_id
   AND NOT msa.has_server_permission('operations.assign') THEN RAISE EXCEPTION 'Ticket assignment denied'; END IF;
 ELSIF TG_TABLE_NAME='support_messages' THEN
  SELECT * INTO STRICT p FROM msa.support_tickets WHERE id=NEW.ticket_id FOR UPDATE;
  IF NEW.author_user_id<>actor OR NOT(actor=p.requester_user_id OR
   (actor=p.assigned_support_user_id AND msa.has_server_permission('operations.queue'))) THEN RAISE EXCEPTION 'Ticket reply denied'; END IF;
 ELSE
  PERFORM msa.require_owner(NEW.user_id);
 END IF;
 IF TG_OP='UPDATE' THEN
  prev:=to_jsonb(OLD);
  CASE TG_TABLE_NAME
   WHEN 'review_case_permissions','summary_shares' THEN
    IF (j-'revoked_at')<>(prev-'revoked_at') OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
     THEN RAISE EXCEPTION 'Permission history is immutable except first revocation'; END IF;
   WHEN 'medication_schedules' THEN
    IF (j-ARRAY['verification_status','verification_evidence','verified_at','content_digest'])<>(prev-ARRAY['verification_status','verification_evidence','verified_at','content_digest'])
     OR OLD.verification_status<>'UNVERIFIED' THEN RAISE EXCEPTION 'Append a new schedule revision'; END IF;
   WHEN 'review_cases' THEN
    IF (j-ARRAY['assigned_hcp_id','status','updated_at','closed_at'])<>(prev-ARRAY['assigned_hcp_id','status','updated_at','closed_at'])
     OR OLD.status IN ('CLOSED','CANCELLED') THEN RAISE EXCEPTION 'Closed case or immutable context'; END IF;
   WHEN 'schedule_change_requests' THEN
    IF (j-'status')<>(prev-'status') OR OLD.status<>'PENDING' OR NEW.status NOT IN ('WITHDRAWN')
     THEN RAISE EXCEPTION 'Request outcomes require an HCP review, not owner approval'; END IF;
   WHEN 'support_tickets' THEN
    IF (j-ARRAY['assigned_support_user_id','status','updated_at'])<>(prev-ARRAY['assigned_support_user_id','status','updated_at'])
     THEN RAISE EXCEPTION 'Immutable ticket source'; END IF;
   WHEN 'reminder_settings','medication_cabinet_items' THEN
    IF NEW.id<>OLD.id OR NEW.user_id<>OLD.user_id THEN RAISE EXCEPTION 'Immutable ownership'; END IF;
    IF TG_TABLE_NAME='reminder_settings' THEN
     IF NEW.schedule_id<>OLD.schedule_id THEN RAISE EXCEPTION 'New schedule needs new reminder settings'; END IF;
    END IF;
   ELSE RAISE EXCEPTION 'Append-only domain history';
  END CASE;
 END IF;
 CASE TG_TABLE_NAME
 WHEN 'patient_health_facts' THEN
  SELECT source_content->'facts'->NEW.source_fact_index INTO STRICT source FROM msa.patient_health_sources
    WHERE id=NEW.health_source_id AND user_id=NEW.user_id;
  IF source IS NULL OR source->>'field' IS DISTINCT FROM NEW.field OR source->'value' IS DISTINCT FROM NEW.value_json
   OR source->>'text_raw' IS DISTINCT FROM NEW.text_raw OR source->>'uncertainty' IS DISTINCT FROM NEW.uncertainty_raw
   THEN RAISE EXCEPTION 'Health projection differs from original source'; END IF;
 WHEN 'patient_medication_uses' THEN
  IF NOT EXISTS(SELECT FROM msa.patient_health_facts WHERE id=NEW.health_fact_id AND user_id=NEW.user_id AND fact_type='MEDICATION_USE')
   THEN RAISE EXCEPTION 'Medication use requires a medication-use fact'; END IF;
 WHEN 'medication_schedules' THEN
  IF NOT EXISTS(SELECT FROM pg_timezone_names WHERE name=NEW.timezone) THEN RAISE EXCEPTION 'Unknown IANA timezone'; END IF;
  SELECT content_digest INTO STRICT entry_digest FROM msa.medication_entry_versions
    WHERE id=NEW.entry_version_id AND user_id=NEW.user_id AND confirmed_at IS NOT NULL;
  IF EXISTS(SELECT FROM msa.medication_entry_versions v JOIN msa.medication_entry_versions base ON base.id=NEW.entry_version_id
    WHERE v.item_id=base.item_id AND v.version_no>base.version_no) THEN RAISE EXCEPTION 'Schedule uses a stale medication version'; END IF;
  d:=msa.schedule_digest(NEW.entry_version_id,NEW.schedule_details,NEW.timezone,NEW.schedule_origin);
  IF TG_OP='INSERT' AND NEW.verification_status<>'UNVERIFIED' THEN RAISE EXCEPTION 'Create draft before confirmation'; END IF;
  IF NEW.verification_status<>'UNVERIFIED' THEN
   source:=NEW.verification_evidence;
   IF source->>'schema' IS DISTINCT FROM 'schedule-verification.v1' OR source->>'schedule_digest' IS DISTINCT FROM d
    OR source->>'entry_digest' IS DISTINCT FROM entry_digest OR source->'explicit' IS DISTINCT FROM 'true'::jsonb
    OR NOT msa.is_uuid(source->>'confirmation_key') THEN RAISE EXCEPTION 'Schedule confirmation does not match displayed content'; END IF;
   IF EXISTS(SELECT FROM msa.medication_schedules WHERE supersedes_schedule_id=NEW.id) THEN RAISE EXCEPTION 'Stale schedule confirmation'; END IF;
   IF NEW.verification_status='HCP_VERIFIED' AND NOT EXISTS(SELECT FROM msa.review_outcomes o
    JOIN msa.review_cases rc ON rc.id=o.case_id WHERE o.id=(source->>'review_outcome_id')::uuid
     AND o.user_id=NEW.user_id AND o.schedule_id=NEW.id AND o.reviewed_content_digest=d AND o.decision='APPROVED'
     AND o.review_type='SCHEDULE') THEN RAISE EXCEPTION 'Exact schedule needs HCP approval'; END IF;
  END IF;
 WHEN 'review_cases' THEN
  IF NEW.status IN ('OPEN','IN_REVIEW') AND (NEW.assigned_hcp_id IS NULL OR NOT EXISTS(
   SELECT FROM msa.review_case_permissions cp WHERE cp.case_id=NEW.id AND cp.hcp_id=NEW.assigned_hcp_id
    AND cp.revoked_at IS NULL AND cp.granted_at<=statement_timestamp() AND (cp.expires_at IS NULL OR cp.expires_at>statement_timestamp())))
   THEN RAISE EXCEPTION 'Patient consent required before assignment/access'; END IF;
 WHEN 'summary_shares' THEN
  IF EXISTS(SELECT FROM jsonb_array_elements_text(NEW.allowed_sections) k WHERE NOT EXISTS(
   SELECT FROM msa.patient_health_summaries sh,jsonb_array_elements(sh.summary_content->'sections') sec
    WHERE sh.id=NEW.summary_id AND sh.user_id=NEW.user_id AND sec->>'key'=k)) THEN RAISE EXCEPTION 'Unknown shared section'; END IF;
 WHEN 'dose_records' THEN
  SELECT * INTO STRICT s FROM msa.medication_schedules WHERE id=NEW.schedule_id AND user_id=NEW.user_id FOR UPDATE;
  IF s.verification_status='UNVERIFIED' THEN RAISE EXCEPTION 'Dose requires verified schedule'; END IF;
  IF NEW.supersedes_record_id IS NOT NULL AND NOT EXISTS(SELECT FROM msa.dose_records r WHERE r.id=NEW.supersedes_record_id
    AND r.schedule_id=NEW.schedule_id AND r.user_id=NEW.user_id AND r.scheduled_for=NEW.scheduled_for)
   THEN RAISE EXCEPTION 'Dose correction targets a different occurrence'; END IF;
 WHEN 'reminder_settings' THEN
  IF NEW.enabled AND (TG_OP='INSERT' OR NOT OLD.enabled OR NEW.last_assessment_id IS DISTINCT FROM OLD.last_assessment_id OR NEW.eligibility_status IS DISTINCT FROM OLD.eligibility_status) THEN
   SELECT * INTO STRICT s FROM msa.medication_schedules WHERE id=NEW.schedule_id AND user_id=NEW.user_id FOR UPDATE;
   IF s.verification_status='UNVERIFIED' OR EXISTS(SELECT FROM msa.medication_schedules WHERE supersedes_schedule_id=s.id)
    THEN RAISE EXCEPTION 'Reminder needs current verified schedule'; END IF;
   SELECT * INTO STRICT a FROM msa.safety_assessments WHERE id=NEW.last_assessment_id AND user_id=NEW.user_id;
   IF a.execution_status<>'COMPLETED' OR NOT EXISTS(SELECT FROM msa.snapshot_entries se
    WHERE se.snapshot_id=a.snapshot_id AND se.entry_version_id=s.entry_version_id AND se.user_id=NEW.user_id)
    THEN RAISE EXCEPTION 'Completed assessment for exact entry required'; END IF;
   IF (a.check_results->'ddi'->>'coverage'<>'ASSESSED' OR a.check_results->'duplicate_ingredient'->>'coverage'<>'ASSESSED'
    OR EXISTS(SELECT FROM msa.safety_findings f JOIN msa.finding_entries fe ON fe.finding_id=f.id AND fe.user_id=f.user_id
    WHERE f.assessment_id=a.id AND fe.entry_version_id=s.entry_version_id AND f.severity IN ('MAJOR','CONTRAINDICATED','SEVERE'))
    OR EXISTS(SELECT FROM msa.safety_findings f JOIN msa.finding_entries fe ON fe.finding_id=f.id AND fe.user_id=f.user_id
      WHERE f.assessment_id=a.id AND fe.entry_version_id=s.entry_version_id AND f.evidence->'reminder_hold'->>'required'='true'))
    AND NOT (s.verification_status='HCP_VERIFIED' AND EXISTS(SELECT FROM msa.review_outcomes o JOIN msa.review_cases rc ON rc.id=o.case_id
      WHERE o.id=(s.verification_evidence->>'review_outcome_id')::uuid AND o.schedule_id=s.id AND o.user_id=s.user_id
       AND o.decision='APPROVED' AND o.reviewed_content_digest=s.content_digest AND rc.safety_assessment_id=a.id))
    THEN RAISE EXCEPTION 'Risk or unsupported coverage needs HCP approval of this schedule and assessment'; END IF;
  END IF;
 ELSE NULL;
 END CASE;
 RETURN NEW;
END $$;
