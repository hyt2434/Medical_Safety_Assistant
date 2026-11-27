-- Keep applied 003/004 bytes intact. Avoid PL/pgSQL OLD record alias capture.
CREATE UNIQUE INDEX schedule_confirmation_once ON msa.medication_schedules(user_id,(verification_evidence->>'confirmation_key'))
 WHERE verification_status<>'UNVERIFIED';
CREATE OR REPLACE FUNCTION msa.can_access_summary(summary_id uuid, owner_id uuid) RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,msa AS $$
 SELECT coalesce(msa.actor_id()=$2,false) OR EXISTS(SELECT FROM msa.summary_shares p
  WHERE p.summary_id=$1 AND p.user_id=$2 AND p.hcp_id=msa.actor_id()
   AND p.granted_at<=statement_timestamp() AND p.revoked_at IS NULL
   AND (p.expires_at IS NULL OR p.expires_at>statement_timestamp())
   AND msa.has_server_permission('clinical.case_review'))
$$;
CREATE OR REPLACE FUNCTION msa.shared_summary(share_id uuid) RETURNS jsonb LANGUAGE plpgsql STABLE
 SECURITY DEFINER SET search_path=pg_catalog,msa AS $$
DECLARE p msa.summary_shares; doc jsonb;
BEGIN
 IF msa.actor_id() IS NULL THEN RAISE EXCEPTION 'Summary sharing denied: missing authenticated context'; END IF;
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
CREATE OR REPLACE FUNCTION msa.domain_access_completion() RETURNS trigger LANGUAGE plpgsql AS $$
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
   IF EXISTS(SELECT FROM msa.medication_entry_versions prior_entry JOIN msa.medication_entry_versions newer
     ON newer.item_id=prior_entry.item_id AND newer.version_no>prior_entry.version_no WHERE prior_entry.id=schedule.entry_version_id)
    THEN RAISE EXCEPTION 'New reminder targets stale medication version'; END IF;
   IF EXISTS(SELECT FROM msa.safety_assessments a JOIN msa.snapshot_entries se ON se.snapshot_id=a.snapshot_id
     JOIN msa.medication_entry_versions prior_entry ON prior_entry.id=se.entry_version_id
     JOIN msa.medication_entry_versions newer ON newer.item_id=prior_entry.item_id AND newer.version_no>prior_entry.version_no
     WHERE a.id=NEW.last_assessment_id AND a.user_id=NEW.user_id)
    THEN RAISE EXCEPTION 'Assessment medication list is stale'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END $$;
