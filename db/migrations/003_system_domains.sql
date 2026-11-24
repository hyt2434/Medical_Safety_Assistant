-- SAD ERDs 01,05-09 and UC-19. Additive: released V4 facts/history are unchanged.
-- Auth remains in its own database. identity.users is the local UUID registry.
CREATE FUNCTION msa.actor_id() RETURNS uuid LANGUAGE sql STABLE AS $$
 SELECT nullif(current_setting('msa.authenticated_owner',true),'')::uuid
$$;
CREATE FUNCTION msa.has_server_permission(permission text) RETURNS boolean LANGUAGE sql STABLE AS $$
 SELECT coalesce(nullif(current_setting('msa.authenticated_permissions',true),'')::jsonb ? permission,false)
$$;
CREATE FUNCTION msa.domain_evidence(doc jsonb, tag text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
 SELECT coalesce(msa.jtype(doc,'schema','string') AND doc->>'schema'=tag
   AND msa.jtype(doc,'sources','array') AND jsonb_array_length(doc->'sources')>0
   AND NOT EXISTS (SELECT FROM jsonb_array_elements(CASE WHEN jsonb_typeof(doc->'sources')='array'
     THEN doc->'sources' ELSE '[]' END) e WHERE NOT msa.jtype(e,'locator','string')
       OR btrim(e->>'locator')='' OR NOT msa.is_hash(e->>'sha256')),false)
$$;
CREATE FUNCTION msa.valid_schedule(doc jsonb) RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE e jsonb;
BEGIN
 IF NOT msa.jtype(doc,'schema','string') OR doc->>'schema'<>'schedule.v1'
  OR NOT msa.jtype(doc,'times','array') OR jsonb_array_length(doc->'times')=0
  OR NOT msa.jtype(doc,'dose_raw','string') OR btrim(doc->>'dose_raw')='' THEN RETURN false; END IF;
 FOR e IN SELECT value FROM jsonb_array_elements(doc->'times') LOOP
  IF jsonb_typeof(e)<>'string' OR (e#>>'{}') !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$' THEN RETURN false; END IF;
 END LOOP;
 IF (SELECT count(*)<>count(DISTINCT value) FROM jsonb_array_elements(doc->'times')) THEN RETURN false; END IF;
 RETURN true;
END $$;
CREATE FUNCTION msa.schedule_digest(entry_id uuid, details jsonb, zone text, origin text)
 RETURNS text LANGUAGE sql IMMUTABLE AS $$
 SELECT msa.digest(jsonb_build_array(entry_id::text,details,zone,origin))
$$;

CREATE TABLE msa.dataset_review_decisions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 review_batch_id text NOT NULL CHECK(btrim(review_batch_id)<>''),
 subject_type text NOT NULL CHECK(subject_type IN ('MEDICATION','INGREDIENT','COMPONENT','DDINTER_MAPPING','INDICATION','PRIORITY')),
 source_record_id text NOT NULL CHECK(btrim(source_record_id)<>''),
 dataset_build text CHECK(dataset_build IS NULL OR msa.is_hash(dataset_build)),
 decision text NOT NULL CHECK(decision IN ('ACCEPT','REJECT','NEEDS_REVIEW','PROPOSE_CORRECTION')),
 reason text,
 evidence jsonb NOT NULL CHECK(msa.domain_evidence(evidence,'review-evidence.v1')),
 reviewer_user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 decided_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX dataset_review_subject ON msa.dataset_review_decisions(subject_type,source_record_id,decided_at);

CREATE TABLE msa.patient_health_facts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL,
 health_source_id uuid NOT NULL, source_fact_index integer NOT NULL CHECK(source_fact_index>=0),
 fact_type text NOT NULL CHECK(fact_type IN ('CONDITION','ALLERGY','ADR','MEASUREMENT','LIFESTYLE','MEDICATION_USE','OTHER')),
 field text NOT NULL CHECK(btrim(field)<>''), value_json jsonb NOT NULL,
 text_raw text, uncertainty_raw text,
 UNIQUE(id,user_id), UNIQUE(health_source_id,source_fact_index),
 FOREIGN KEY(health_source_id,user_id) REFERENCES msa.patient_health_sources(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
);
CREATE INDEX health_facts_owner_field ON msa.patient_health_facts(user_id,fact_type,field);
CREATE TABLE msa.patient_medication_uses (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL,
 health_fact_id uuid NOT NULL, entry_version_id uuid,
 medication_name_raw text NOT NULL CHECK(btrim(medication_name_raw)<>''),
 use_status text NOT NULL CHECK(use_status IN ('CURRENT','DISCONTINUED','UNKNOWN')),
 start_date date, end_date date,
 UNIQUE(id,user_id),
 FOREIGN KEY(health_fact_id,user_id) REFERENCES msa.patient_health_facts(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 FOREIGN KEY(entry_version_id,user_id) REFERENCES msa.medication_entry_versions(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK(end_date IS NULL OR start_date IS NULL OR end_date>=start_date),
 CHECK(use_status<>'CURRENT' OR end_date IS NULL)
);
CREATE INDEX medication_uses_owner_status ON msa.patient_medication_uses(user_id,use_status);

CREATE TABLE msa.medication_schedules (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL,
 entry_version_id uuid NOT NULL, supersedes_schedule_id uuid,
 schedule_details jsonb NOT NULL CHECK(msa.valid_schedule(schedule_details)),
 timezone text NOT NULL,
 schedule_origin text NOT NULL CHECK(schedule_origin IN ('PRESCRIPTION_TRANSCRIPTION','PROPOSED_CHANGE')),
 content_digest text NOT NULL GENERATED ALWAYS AS (msa.schedule_digest(entry_version_id,schedule_details,timezone,schedule_origin)) STORED,
 verification_status text NOT NULL DEFAULT 'UNVERIFIED' CHECK(verification_status IN ('UNVERIFIED','PATIENT_CONFIRMED','HCP_VERIFIED')),
 verification_evidence jsonb, verified_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(id,user_id), UNIQUE(id,entry_version_id,user_id), UNIQUE(supersedes_schedule_id),
 FOREIGN KEY(entry_version_id,user_id) REFERENCES msa.medication_entry_versions(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 FOREIGN KEY(supersedes_schedule_id,entry_version_id,user_id) REFERENCES msa.medication_schedules(id,entry_version_id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK(supersedes_schedule_id IS DISTINCT FROM id),
 CHECK((verification_status='UNVERIFIED')=(verification_evidence IS NULL AND verified_at IS NULL)),
 CHECK(verification_status='UNVERIFIED' OR (verification_evidence IS NOT NULL AND verified_at IS NOT NULL)),
 CHECK(verification_status<>'PATIENT_CONFIRMED' OR schedule_origin='PRESCRIPTION_TRANSCRIPTION')
);
CREATE UNIQUE INDEX one_schedule_root ON msa.medication_schedules(entry_version_id) WHERE supersedes_schedule_id IS NULL;
CREATE INDEX schedules_owner_entry ON msa.medication_schedules(user_id,entry_version_id);
CREATE TABLE msa.schedule_change_requests (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, schedule_id uuid NOT NULL,
 proposed_timing jsonb NOT NULL CHECK(msa.valid_schedule(proposed_timing)),
 status text NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','REJECTED','WITHDRAWN')),
 requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(id,user_id), UNIQUE(id,schedule_id,user_id),
 FOREIGN KEY(schedule_id,user_id) REFERENCES msa.medication_schedules(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
);
CREATE INDEX schedule_requests_owner_status ON msa.schedule_change_requests(user_id,status);
CREATE TABLE msa.review_cases (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 case_type text NOT NULL CHECK(case_type IN ('SAFETY','SCHEDULE')),
 safety_assessment_id uuid, schedule_id uuid, schedule_change_request_id uuid,
 assigned_hcp_id uuid REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 status text NOT NULL DEFAULT 'PENDING_CONSENT' CHECK(status IN ('PENDING_CONSENT','OPEN','IN_REVIEW','CLOSED','CANCELLED')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(), closed_at timestamptz,
 UNIQUE(id,user_id), UNIQUE(id,schedule_id,user_id),
 FOREIGN KEY(safety_assessment_id,user_id) REFERENCES msa.safety_assessments(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 FOREIGN KEY(schedule_id,user_id) REFERENCES msa.medication_schedules(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 FOREIGN KEY(schedule_change_request_id,schedule_id,user_id) REFERENCES msa.schedule_change_requests(id,schedule_id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK((case_type='SAFETY' AND safety_assessment_id IS NOT NULL AND schedule_id IS NULL AND schedule_change_request_id IS NULL)
  OR (case_type='SCHEDULE' AND schedule_id IS NOT NULL)),
 CHECK(schedule_change_request_id IS NULL OR schedule_id IS NOT NULL),
 CHECK((status IN ('CLOSED','CANCELLED'))=(closed_at IS NOT NULL)),
 CHECK(updated_at>=created_at AND (closed_at IS NULL OR closed_at>=created_at))
);
CREATE INDEX cases_owner_status ON msa.review_cases(user_id,status);
CREATE INDEX cases_assigned_hcp ON msa.review_cases(assigned_hcp_id,status);
CREATE TABLE msa.review_case_permissions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, case_id uuid NOT NULL,
 hcp_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 granted_at timestamptz NOT NULL DEFAULT clock_timestamp(), revoked_at timestamptz, expires_at timestamptz,
 consent_evidence jsonb NOT NULL CHECK(msa.domain_evidence(consent_evidence,'consent.v1')),
 FOREIGN KEY(case_id,user_id) REFERENCES msa.review_cases(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK(revoked_at IS NULL OR revoked_at>=granted_at), CHECK(expires_at IS NULL OR expires_at>granted_at), CHECK(hcp_id<>user_id)
);
CREATE INDEX case_permissions_access ON msa.review_case_permissions(case_id,hcp_id,granted_at);
CREATE FUNCTION msa.can_access_case(case_id uuid, owner_id uuid) RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,msa AS $$
 SELECT msa.actor_id()=owner_id OR EXISTS (
  SELECT FROM msa.review_cases c JOIN msa.review_case_permissions p ON p.case_id=c.id AND p.user_id=c.user_id
  WHERE c.id=case_id AND c.user_id=owner_id AND c.assigned_hcp_id=msa.actor_id()
   AND c.status IN ('OPEN','IN_REVIEW','CLOSED') AND p.hcp_id=msa.actor_id()
   AND p.granted_at<=statement_timestamp() AND p.revoked_at IS NULL
   AND (p.expires_at IS NULL OR p.expires_at>statement_timestamp())
   AND msa.has_server_permission('clinical.case_review'))
$$;
CREATE TABLE msa.review_case_messages (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, case_id uuid NOT NULL,
 sender_user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 content text NOT NULL CHECK(btrim(content)<>''), sent_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(case_id,user_id) REFERENCES msa.review_cases(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
);
CREATE INDEX case_messages_order ON msa.review_case_messages(case_id,sent_at,id);
CREATE TABLE msa.review_outcomes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, case_id uuid NOT NULL,
 reviewer_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 review_type text NOT NULL CHECK(review_type IN ('SAFETY','SCHEDULE')),
 decision text NOT NULL CHECK(decision IN ('APPROVED','CHANGES_REQUESTED','REJECTED','UNASSESSED')),
 notes text, evidence jsonb NOT NULL CHECK(msa.domain_evidence(evidence,'review-evidence.v1')),
 reviewed_at timestamptz NOT NULL DEFAULT clock_timestamp(), schedule_id uuid, reviewed_content_digest text,
 UNIQUE(id,user_id),
 FOREIGN KEY(case_id,user_id) REFERENCES msa.review_cases(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 FOREIGN KEY(case_id,schedule_id,user_id) REFERENCES msa.review_cases(id,schedule_id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK((review_type='SCHEDULE')=(schedule_id IS NOT NULL AND reviewed_content_digest IS NOT NULL)),
 CHECK(reviewed_content_digest IS NULL OR msa.is_hash(reviewed_content_digest))
);
CREATE INDEX outcomes_case ON msa.review_outcomes(case_id,reviewed_at);
CREATE TABLE msa.summary_shares (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, summary_id uuid NOT NULL,
 hcp_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 scope text NOT NULL CHECK(scope IN ('FULL','SECTIONS')),
 allowed_sections jsonb NOT NULL CHECK(msa.string_array(allowed_sections)),
 consent_evidence jsonb NOT NULL CHECK(msa.domain_evidence(consent_evidence,'consent.v1')),
 granted_at timestamptz NOT NULL DEFAULT clock_timestamp(), revoked_at timestamptz, expires_at timestamptz,
 FOREIGN KEY(summary_id,user_id) REFERENCES msa.patient_health_summaries(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK((scope='FULL' AND allowed_sections='[]') OR (scope='SECTIONS' AND jsonb_array_length(allowed_sections)>0)),
 CHECK(revoked_at IS NULL OR revoked_at>=granted_at), CHECK(expires_at IS NULL OR expires_at>granted_at), CHECK(hcp_id<>user_id)
);
CREATE INDEX summary_shares_access ON msa.summary_shares(summary_id,hcp_id,granted_at);
CREATE FUNCTION msa.can_access_summary(summary_id uuid, owner_id uuid) RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,msa AS $$
 SELECT msa.actor_id()=owner_id OR EXISTS(SELECT FROM msa.summary_shares p
  WHERE p.summary_id=can_access_summary.summary_id AND p.user_id=owner_id AND p.hcp_id=msa.actor_id()
   AND p.granted_at<=statement_timestamp() AND p.revoked_at IS NULL
   AND (p.expires_at IS NULL OR p.expires_at>statement_timestamp())
   AND msa.has_server_permission('clinical.case_review'))
$$;
-- Return only shared sections; an HCP must never receive the unrestricted JSONB.
CREATE FUNCTION msa.shared_summary(share_id uuid) RETURNS jsonb LANGUAGE plpgsql STABLE
 SECURITY DEFINER SET search_path=pg_catalog,msa AS $$
DECLARE p msa.summary_shares; doc jsonb;
BEGIN
 SELECT * INTO STRICT p FROM msa.summary_shares WHERE id=share_id;
 IF msa.actor_id()<>p.user_id AND (msa.actor_id() IS DISTINCT FROM p.hcp_id
  OR NOT msa.can_access_summary(p.summary_id,p.user_id) OR p.revoked_at IS NOT NULL
  OR p.granted_at>statement_timestamp() OR (p.expires_at IS NOT NULL AND p.expires_at<=statement_timestamp()))
  THEN RAISE EXCEPTION 'Summary sharing denied'; END IF;
 SELECT summary_content INTO STRICT doc FROM msa.patient_health_summaries WHERE id=p.summary_id AND user_id=p.user_id;
 IF p.scope='FULL' THEN RETURN doc; END IF;
 RETURN jsonb_build_object('schema','shared-summary.v1','sections',coalesce((
  SELECT jsonb_agg(e) FROM jsonb_array_elements(doc->'sections') e WHERE p.allowed_sections ? (e->>'key')),'[]'::jsonb));
END $$;

CREATE TABLE msa.reminder_settings (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, schedule_id uuid NOT NULL UNIQUE,
 enabled boolean NOT NULL DEFAULT false,
 notification_preferences jsonb NOT NULL CHECK(msa.jtype(notification_preferences,'schema','string')
  AND notification_preferences->>'schema'='notification-preferences.v1'
  AND msa.jtype(notification_preferences,'channel','string') AND notification_preferences->>'channel' IN ('IN_APP','EMAIL')),
 last_assessment_id uuid, eligibility_status text NOT NULL DEFAULT 'UNASSESSED'
  CHECK(eligibility_status IN ('UNASSESSED','ELIGIBLE','HELD','HCP_REVIEW_REQUIRED')),
 evaluated_at timestamptz,
 FOREIGN KEY(schedule_id,user_id) REFERENCES msa.medication_schedules(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 FOREIGN KEY(last_assessment_id,user_id) REFERENCES msa.safety_assessments(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK(NOT enabled OR (eligibility_status='ELIGIBLE' AND last_assessment_id IS NOT NULL AND evaluated_at IS NOT NULL))
);
CREATE INDEX reminders_owner ON msa.reminder_settings(user_id);
CREATE TABLE msa.dose_records (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, schedule_id uuid NOT NULL,
 scheduled_for timestamptz NOT NULL, dose_status text NOT NULL CHECK(dose_status IN ('TAKEN','MISSED','SKIPPED')),
 supersedes_record_id uuid UNIQUE, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(id,schedule_id,user_id),
 FOREIGN KEY(schedule_id,user_id) REFERENCES msa.medication_schedules(id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 FOREIGN KEY(supersedes_record_id,schedule_id,user_id) REFERENCES msa.dose_records(id,schedule_id,user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK(supersedes_record_id IS DISTINCT FROM id)
);
CREATE UNIQUE INDEX dose_occurrence_root ON msa.dose_records(schedule_id,scheduled_for) WHERE supersedes_record_id IS NULL;
CREATE INDEX doses_owner_time ON msa.dose_records(user_id,scheduled_for);
CREATE TABLE msa.medication_cabinet_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 medication_name_raw text NOT NULL CHECK(btrim(medication_name_raw)<>''),
 product_id uuid, reference_build text, expires_on date,
 FOREIGN KEY(product_id,reference_build) REFERENCES msa_ref.medications(id,dataset_build) ON DELETE RESTRICT ON UPDATE RESTRICT,
 CHECK((product_id IS NULL)=(reference_build IS NULL))
);
CREATE INDEX cabinet_owner_expiry ON msa.medication_cabinet_items(user_id,expires_on);
CREATE TABLE msa.support_tickets (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 requester_user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 assigned_support_user_id uuid REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 subject text NOT NULL CHECK(btrim(subject)<>''),
 status text NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','IN_PROGRESS','AWAITING_USER','RESOLVED','CLOSED')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK(updated_at>=created_at)
);
CREATE INDEX support_requester ON msa.support_tickets(requester_user_id,created_at);
CREATE INDEX support_assigned_status ON msa.support_tickets(assigned_support_user_id,status);
CREATE TABLE msa.support_messages (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), ticket_id uuid NOT NULL REFERENCES msa.support_tickets(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 author_user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
 content text NOT NULL CHECK(btrim(content)<>''), created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX support_message_order ON msa.support_messages(ticket_id,created_at,id);
CREATE TABLE msa.audit_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), actor_user_id uuid, subject_user_id uuid,
 action text NOT NULL CHECK(btrim(action)<>''), resource_type text NOT NULL CHECK(btrim(resource_type)<>''),
 resource_id text NOT NULL, outcome text NOT NULL CHECK(outcome IN ('SUCCESS','DENIED','FAILED')),
 details jsonb NOT NULL CHECK(msa.jtype(details,'schema','string') AND details->>'schema'='business-audit.v1'
  AND msa.jtype(details,'reason','string',true)),
 occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX business_audit_subject_time ON msa.audit_events(subject_user_id,occurred_at);
CREATE INDEX business_audit_resource ON msa.audit_events(resource_type,resource_id,occurred_at);

CREATE FUNCTION msa.system_domain_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE j jsonb:=to_jsonb(NEW); prev jsonb; actor uuid:=msa.actor_id(); source jsonb;
 s msa.medication_schedules; c msa.review_cases; p msa.support_tickets; a msa.safety_assessments;
 d text; entry_digest text;
BEGIN
 IF actor IS NULL THEN RAISE EXCEPTION 'Authenticated actor required'; END IF;
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Domain history cannot be deleted'; END IF;
 IF TG_TABLE_NAME IN ('review_case_messages','review_outcomes') THEN
  IF NOT msa.can_access_case(NEW.case_id,NEW.user_id) THEN RAISE EXCEPTION 'Case access denied'; END IF;
  SELECT * INTO STRICT c FROM msa.review_cases WHERE id=NEW.case_id AND user_id=NEW.user_id FOR UPDATE;
  IF TG_TABLE_NAME='review_case_messages' AND NEW.sender_user_id<>actor THEN RAISE EXCEPTION 'Sender mismatch'; END IF;
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
    IF TG_TABLE_NAME='reminder_settings' AND NEW.schedule_id<>OLD.schedule_id THEN RAISE EXCEPTION 'New schedule needs new reminder settings'; END IF;
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
  IF NEW.enabled AND (TG_OP='INSERT' OR NOT OLD.enabled) THEN
   SELECT * INTO STRICT s FROM msa.medication_schedules WHERE id=NEW.schedule_id AND user_id=NEW.user_id FOR UPDATE;
   IF s.verification_status='UNVERIFIED' OR EXISTS(SELECT FROM msa.medication_schedules WHERE supersedes_schedule_id=s.id)
    THEN RAISE EXCEPTION 'Reminder needs current verified schedule'; END IF;
   SELECT * INTO STRICT a FROM msa.safety_assessments WHERE id=NEW.last_assessment_id AND user_id=NEW.user_id;
   IF a.execution_status<>'COMPLETED' OR NOT EXISTS(SELECT FROM msa.snapshot_entries se
    WHERE se.snapshot_id=a.snapshot_id AND se.entry_version_id=s.entry_version_id AND se.user_id=NEW.user_id)
    THEN RAISE EXCEPTION 'Completed assessment for exact entry required'; END IF;
   IF a.check_results->'ddi'->>'coverage'<>'ASSESSED' OR a.check_results->'duplicate_ingredient'->>'coverage'<>'ASSESSED'
    THEN RAISE EXCEPTION 'Unsupported safety coverage requires review'; END IF;
   IF EXISTS(SELECT FROM msa.safety_findings f JOIN msa.finding_entries fe ON fe.finding_id=f.id AND fe.user_id=f.user_id
    WHERE f.assessment_id=a.id AND fe.entry_version_id=s.entry_version_id AND f.severity IN ('MAJOR','CONTRAINDICATED','SEVERE'))
    THEN RAISE EXCEPTION 'Severe finding holds affected new reminder'; END IF;
  END IF;
 ELSE NULL;
 END CASE;
 RETURN NEW;
END $$;

DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['dataset_review_decisions','patient_health_facts','patient_medication_uses','review_cases',
 'review_case_permissions','review_case_messages','review_outcomes','summary_shares','medication_schedules',
 'reminder_settings','schedule_change_requests','dose_records','medication_cabinet_items','support_tickets','support_messages','audit_events'] LOOP
  EXECUTE format('CREATE TRIGGER domain_guard BEFORE INSERT OR UPDATE OR DELETE ON msa.%I FOR EACH ROW EXECUTE FUNCTION msa.system_domain_guard()',tab);
  EXECUTE format('CREATE TRIGGER no_truncate BEFORE TRUNCATE ON msa.%I FOR EACH STATEMENT EXECUTE FUNCTION msa.reject_change()',tab);
  EXECUTE format('ALTER TABLE msa.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE msa.%I FORCE ROW LEVEL SECURITY',tab);
  IF tab IN ('review_cases','review_case_messages','review_outcomes') THEN
   EXECUTE format('CREATE POLICY domain_access ON msa.%I USING (msa.can_access_case(%s,user_id))',tab,CASE WHEN tab='review_cases' THEN 'id' ELSE 'case_id' END);
  ELSIF tab='dataset_review_decisions' THEN
   EXECUTE format('CREATE POLICY domain_access ON msa.%I USING (msa.has_server_permission(''catalog.review''))',tab);
  ELSIF tab='audit_events' THEN
   EXECUTE format('CREATE POLICY domain_access ON msa.%I USING (subject_user_id=msa.actor_id() OR msa.has_server_permission(''admin.audit''))',tab);
  ELSIF tab='support_tickets' THEN
   EXECUTE format('CREATE POLICY domain_access ON msa.%I USING (requester_user_id=msa.actor_id() OR (assigned_support_user_id=msa.actor_id() AND msa.has_server_permission(''operations.queue'')) OR msa.has_server_permission(''operations.assign''))',tab);
  ELSIF tab='support_messages' THEN
   EXECUTE format('CREATE POLICY domain_access ON msa.%I USING (EXISTS(SELECT FROM msa.support_tickets t WHERE t.id=ticket_id))',tab);
  ELSE EXECUTE format('CREATE POLICY domain_access ON msa.%I USING (user_id=msa.actor_id())',tab);
  END IF;
 END LOOP;
END $$;
