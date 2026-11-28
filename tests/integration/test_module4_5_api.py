"""Real PostgreSQL domain API flow; only server session and provider directory are injected.

Requires an existing marked MODULE2_TEST_DSN with the current migrations. No reference
CSV or inference services are needed: the assessment is explicitly synthetic.
"""
from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from apps.backend.api.app import app
from apps.backend.api import deps
from apps.backend.api.routes.domains import domain_repository
from module4_hcp.service import HcpService
from shared.db import DomainRepository
from shared.db.repository import empty_checks
from shared.db.intake_adapter import persist_module1
from tests.integration.test_module2_core import postgres_repo
from tests.db_cleanup import isolated_core_owner


def test_review_activation_doses_access_and_atomic_rollback(postgres_repo, monkeypatch):
    core = postgres_repo
    with ExitStack() as stack:
        hcp = stack.enter_context(isolated_core_owner(core.db))
        other = stack.enter_context(isolated_core_owner(core.db))
        actor = {'id': core.owner, 'permissions': ['patient.workspace']}
        def session(msa_session=None):
            return {'account': {'id': str(actor['id'])}, 'contextPermissions': actor['permissions']}
        app.dependency_overrides[deps.current_session] = session
        monkeypatch.setattr(deps, 'current_session', session)
        monkeypatch.setenv('AUTH_ALLOWED_ORIGINS', 'http://127.0.0.1:5173')
        monkeypatch.setenv('CORE_DB_DSN', __import__('os').environ['MODULE2_TEST_DSN'])
        monkeypatch.setattr(HcpService, 'providers', lambda self: [{'id': str(hcp), 'full_name': 'Synthetic HCP'}])
        client = TestClient(app, headers={'origin': 'http://127.0.0.1:5173'})
        try:
            intake = core.create_intake(core.create_conversation()['id'])
            raw = 'Synthetic medication, one tablet at 00:00'
            saved = persist_module1(core, intake['id'], raw.encode(), {'medications': [{
                'name_raw': 'Synthetic medication', 'dose_raw': 'one tablet',
                'administrations': [{'timing_raw': '00:00', 'dose_raw': 'one tablet'}], 'evidence_text': raw}]},
                modality='TEXT', input_payload={'schema': 'input.v4', 'digest_basis': 'ORIGINAL_BYTES', 'text': raw},
                extractor_name='EXPLICIT_SYNTHETIC_FIXTURE', extractor_version='module45.v1')
            entry = saved['entries'][0]
            core.confirm_entry(entry['id'], entry['content_digest'], uuid4(), explicit_confirmation=True)
            snapshot = core.create_snapshot([(entry['id'], None)], data_context='SYNTHETIC_TEST')
            attempt = core.start_assessment(snapshot['id'], {'ddinter': {'synthetic': True}, 'engine_config': {}, 'limitations': ['Synthetic API test']})
            checks = empty_checks()
            for check in checks.values():
                if isinstance(check, dict):
                    check.update(execution='COMPLETED', coverage='NOT_APPLICABLE')
            assessment = core.finish_assessment(attempt['id'], checks)
            response = client.get('/api/v1/reminders/entries')
            assert response.status_code == 200, response.text
            assert response.json()[0]['id'] == str(entry['id'])
            body = {'entry_version_id': str(entry['id']), 'times': ['00:00'], 'dose_raw': 'one tablet', 'timezone': 'UTC', 'confirm': True}
            # An invalid transcription must roll back the draft as well as confirmation.
            assert client.post('/api/v1/reminders/schedules', json={**body, 'times': ['04:00']}).status_code == 409
            assert client.get('/api/v1/reminders/schedules').json() == []
            response = client.post('/api/v1/reminders/schedules', json=body)
            assert response.status_code == 201, response.text
            schedule = response.json()
            response = client.put('/api/v1/reminders/schedules/'+schedule['id']+'/reminder', json={'enabled': True})
            assert response.status_code == 409 and response.json()['code'] == 'HCP_REVIEW_REQUIRED'
            response = client.post('/api/v1/hcp/cases', json={'kind': 'SCHEDULE', 'schedule_id': schedule['id'], 'hcp_id': str(hcp), 'consent': True})
            assert response.status_code == 201, response.text
            case = response.json(); case_url = '/api/v1/hcp/cases/'+case['id']
            assert case['schedule_id'] != schedule['id']
            listed = client.get('/api/v1/reminders/schedules').json()
            assert listed[0]['id'] == schedule['id']
            assert listed[0]['pending_proposal']['id'] == case['schedule_id']
            # A pending proposal must keep the verified ancestor's doses usable.
            pending_doses = client.get('/api/v1/reminders/today').json()
            assert len(pending_doses) == 1 and pending_doses[0]['schedule_id'] == schedule['id']
            assert client.post('/api/v1/reminders/doses', json={
                'schedule_id': schedule['id'], 'scheduled_for': pending_doses[0]['scheduled_for'],
                'status': 'TAKEN',
            }).status_code == 201
            assert client.get('/api/v1/reminders/history?days=1').json()[0]['status'] == 'TAKEN'
            assert client.post(case_url+'/review', json={'decision': 'APPROVED', 'notes': 'Patient cannot approve'}).status_code == 403
            actor.update(id=other, permissions=['clinical.case_review'])
            assert client.get(case_url).status_code == 403
            assert client.get('/api/v1/hcp/cases').json() == []
            actor.update(id=hcp)
            assert len(client.get('/api/v1/hcp/cases').json()) == 1
            assert client.post(case_url+'/messages', json={'text': 'Reviewed synthetic instructions'}).status_code == 201
            response = client.post(case_url+'/review', json={'decision': 'APPROVED', 'notes': 'Synthetic review of exact schedule and assessment'})
            assert response.status_code == 201, response.text
            assert client.get(case_url).json()['status'] == 'OPEN'
            actor.update(id=core.owner, permissions=['patient.workspace'])
            newer = core.start_assessment(snapshot['id'], {'ddinter': {'synthetic': True}, 'engine_config': {}, 'limitations': ['Newer assessment']})
            core.finish_assessment(newer['id'], checks)
            response = client.post('/api/v1/reminders/schedules/'+case['schedule_id']+'/activate')
            assert response.status_code == 200, response.text
            assert client.get(case_url).json()['status'] == 'CLOSED'
            actor.update(id=hcp, permissions=['clinical.case_review'])
            assert client.post(case_url+'/review', json={'decision': 'REJECTED', 'notes': 'Cannot review twice'}).status_code == 409
            actor.update(id=core.owner, permissions=['patient.workspace'])
            schedule = client.get('/api/v1/reminders/schedules').json()[0]
            assert schedule['verification_status'] == 'HCP_VERIFIED' and schedule['reminder_enabled']
            when = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            dose = {'schedule_id': schedule['id'], 'scheduled_for': when, 'status': 'TAKEN'}
            response = client.post('/api/v1/reminders/doses', json=dose)
            assert response.status_code == 201, response.text
            record = response.json()
            assert client.post('/api/v1/reminders/doses', json={**dose, 'status': 'SKIPPED'}).status_code == 409
            assert client.post('/api/v1/reminders/doses', json={**dose, 'status': 'SKIPPED', 'supersedes': record['id']}).status_code == 201
            # A pending child makes the already verified parent ineligible for activation.
            response = client.post('/api/v1/hcp/cases', json={'kind': 'SCHEDULE', 'schedule_id': schedule['id'], 'hcp_id': str(hcp), 'consent': True})
            assert response.status_code == 201, response.text
            assert client.post('/api/v1/reminders/schedules/'+schedule['id']+'/activate').status_code == 409
            patient = DomainRepository(core.db, authenticated_actor=core.owner)
            with patient.transaction():
                grant = patient._one('SELECT id FROM msa.review_case_permissions WHERE case_id=%s', (case['id'],))
            patient.revoke_access(grant['id'])
            actor.update(id=hcp, permissions=['clinical.case_review'])
            assert client.get(case_url).status_code == 403
            assert client.post(case_url+'/messages', json={'text': 'Access revoked'}).status_code == 403
        finally:
            app.dependency_overrides.clear()
            client.close()
