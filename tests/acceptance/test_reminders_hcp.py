"""REM-xx (schedules, doses, adherence) and HCP-xx (case review → activation) over the live API."""
import uuid
from datetime import timedelta

import pytest

from tests.acceptance.conftest import (
    SET_MAJOR, SET_NONE, ZONE, create_schedule, entry_ids, error_code, intake, local_now, message_of,
    next_minute, provider_id, schedule_row, slow, wait_until_due,
)


@pytest.fixture
def assessed(patient):
    """A fresh confirmed + assessed Major-interaction draft (new medication items every time)."""
    return intake(patient, SET_MAJOR)


def far_future_time():
    """A clock time that is still ahead today (or 23:59)."""
    return min((local_now() + timedelta(hours=2)).strftime('%H:%M'), '23:59')


# ---------- schedules ----------

def test_rem02_only_confirmed_latest_entries_are_offered(patient, assessed):
    draft = intake(patient, ['Vascam'], do_confirm=False, do_assess=False)
    offered = {e['id'] for e in patient.get('/api/v1/reminders/entries').json()}
    assert set(entry_ids(assessed).values()) <= offered
    assert draft['entries'][0]['entry_version_id'] not in offered


def test_rem03_create_schedule_is_patient_confirmed_and_off(patient, assessed):
    entry = entry_ids(assessed)['Hatacil 500']
    r = create_schedule(patient, entry, ['20:00', '08:00'])
    assert r.status_code == 201, r.text
    row = schedule_row(patient, r.json()['id'])
    assert row['verification_status'] == 'PATIENT_CONFIRMED'
    assert row['reminder_enabled'] is False
    assert row['schedule_details']['times'] == ['08:00', '20:00'], 'times are stored sorted'
    assert row['timezone'] == ZONE


@pytest.mark.parametrize('times', [['25:00'], ['8:00'], ['8h'], [''], [], ['08:00', '08:00']])
def test_rem05_07_invalid_times_are_rejected(patient, assessed, times):
    r = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], times)
    assert r.status_code == 422


@pytest.mark.parametrize('zone', ['Hanoi', 'GMT+7', ''])
def test_rem08_timezone_must_be_iana(patient, assessed, zone):
    r = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], ['08:00'], timezone=zone)
    assert r.status_code == 422


def test_rem_requires_explicit_confirmation_and_dose(patient, assessed):
    entry = entry_ids(assessed)['Hatacil 500']
    body = {'entry_version_id': entry, 'times': ['08:00'], 'dose_raw': '1 viên', 'timezone': ZONE}
    assert patient.post('/api/v1/reminders/schedules', json={**body, 'confirm': False}).status_code == 422
    assert patient.post('/api/v1/reminders/schedules', json=body).status_code == 422
    assert patient.post('/api/v1/reminders/schedules', json={**body, 'confirm': True, 'dose_raw': ''}).status_code == 422


def test_rem09_one_active_schedule_per_medication(patient, assessed):
    entry = entry_ids(assessed)['Hatacil 500']
    assert create_schedule(patient, entry, ['08:00']).status_code == 201
    r = create_schedule(patient, entry, ['20:00'])
    assert r.status_code == 409
    assert 'already exists' in message_of(r)


@pytest.mark.parametrize('times,dose', [(['09:00'], '1 viên'), (['08:00', '21:00'], '1 viên'), (['08:00'], '2 viên')],
                         ids=['time-not-on-label', 'one-extra-time', 'different-dose'])
def test_rem_patient_may_only_copy_label_times_and_dose(patient, assessed, times, dose):
    """Labels say 'uống lúc 08:00 và 20:00', 1 viên. Anything else needs an HCP proposal."""
    r = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], times, dose=dose)
    assert r.status_code == 409
    # UX finding: the reason is masked as a generic conflict message.
    assert message_of(r)


def test_rem10_unconfirmed_entry_cannot_get_a_schedule(patient):
    draft = intake(patient, ['Vascam'], do_confirm=False, do_assess=False)
    r = create_schedule(patient, draft['entries'][0]['entry_version_id'], ['08:00'])
    assert r.status_code == 409


def test_rem11_reminder_needs_an_assessment(patient):
    unassessed = intake(patient, SET_NONE, do_assess=False)
    schedule = create_schedule(patient, entry_ids(unassessed)['Agigout 100'], ['08:00']).json()
    r = patient.put(f"/api/v1/reminders/schedules/{schedule['id']}/reminder", json={'enabled': True})
    assert r.status_code == 409
    assert 'assessment' in message_of(r).lower()


@pytest.mark.parametrize('medications', [SET_MAJOR, SET_NONE], ids=['major', 'no-interaction'])
def test_rem12_reminder_needs_hcp_review_when_coverage_is_partial(patient, medications):
    """Locally DDI coverage is never ASSESSED, so every reminder needs HCP approval first."""
    wf = intake(patient, medications)
    schedule = create_schedule(patient, wf['entries'][0]['entry_version_id'], ['08:00']).json()
    r = patient.put(f"/api/v1/reminders/schedules/{schedule['id']}/reminder", json={'enabled': True})
    assert r.status_code == 409
    assert error_code(r) == 'HCP_REVIEW_REQUIRED'
    assert schedule_row(patient, schedule['id'])['reminder_enabled'] is False


def test_rem_strict_boolean_for_reminder_toggle(patient, assessed):
    schedule = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], ['08:00']).json()
    r = patient.put(f"/api/v1/reminders/schedules/{schedule['id']}/reminder", json={'enabled': 'true'})
    assert r.status_code == 422


# ---------- doses ----------

def test_rem13_14_future_dose_is_pending_and_not_due(patient):
    at = far_future_time()
    if at <= local_now().strftime('%H:%M'):
        pytest.skip('too close to midnight')
    wf = intake(patient, SET_MAJOR, timing=f'uống lúc {at}')
    schedule = create_schedule(patient, entry_ids(wf)['Hatacil 500'], [at]).json()
    rows = [d for d in patient.get('/api/v1/reminders/today').json() if d['schedule_id'] == schedule['id']]
    assert len(rows) == 1
    assert rows[0]['status'] == 'PENDING' and rows[0]['due'] is False and rows[0]['time'] == at


def test_rem22_future_dose_cannot_be_recorded(patient, assessed):
    schedule = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], ['08:00']).json()
    r = patient.post('/api/v1/reminders/doses', json={'schedule_id': schedule['id'], 'status': 'TAKEN',
                                                      'scheduled_for': '2030-01-01T08:00:00+07:00'})
    assert r.status_code == 409
    assert 'future' in message_of(r).lower()


def test_rem_dose_requires_timezone_and_valid_status(patient, assessed):
    schedule = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], ['08:00']).json()
    base = {'schedule_id': schedule['id'], 'scheduled_for': '2026-01-01T08:00:00', 'status': 'TAKEN'}
    assert patient.post('/api/v1/reminders/doses', json=base).status_code == 422
    base['scheduled_for'] += '+07:00'
    assert patient.post('/api/v1/reminders/doses', json={**base, 'status': 'DONE'}).status_code == 422


def test_rem_dose_before_schedule_existed_is_rejected(patient, assessed):
    schedule = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], ['08:00']).json()
    yesterday = (local_now() - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    r = patient.post('/api/v1/reminders/doses', json={'schedule_id': schedule['id'], 'status': 'TAKEN',
                                                      'scheduled_for': yesterday.isoformat()})
    assert r.status_code == 409


@slow
def test_rem15_21_record_correct_and_count_a_due_dose(patient):
    """Waits ~2 minutes for a real dose time; covers due flag, TAKEN, correction, history, adherence."""
    clock, _ = next_minute(2)
    if clock < local_now().strftime('%H:%M'):
        pytest.skip('too close to midnight')
    wf = intake(patient, SET_MAJOR, timing=f'uống lúc {clock}')
    schedule = create_schedule(patient, entry_ids(wf)['Hatacil 500'], [clock]).json()
    wait = (local_now().replace(hour=int(clock[:2]), minute=int(clock[3:]), second=0, microsecond=0)
            - local_now()).total_seconds() + 3
    before = patient.get('/api/v1/reminders/adherence').json()
    wait_until_due(wait)

    dose = next(d for d in patient.get('/api/v1/reminders/today').json() if d['schedule_id'] == schedule['id'])
    assert dose['due'] is True and dose['status'] == 'PENDING'
    after_due = patient.get('/api/v1/reminders/adherence').json()
    assert after_due['total_due'] == before['total_due'], 'REM-18: a dose <60 min overdue is not counted yet'

    r = patient.post('/api/v1/reminders/doses', json={'schedule_id': schedule['id'], 'status': 'TAKEN',
                                                      'scheduled_for': dose['scheduled_for']})
    assert r.status_code == 201, r.text
    taken = next(d for d in patient.get('/api/v1/reminders/today').json() if d['schedule_id'] == schedule['id'])
    assert taken['status'] == 'TAKEN' and taken['record_id']
    adherence = patient.get('/api/v1/reminders/adherence').json()
    # Spec (G11-D, tests/unit/module5/test_adherence.py): even a TAKEN dose only counts after 60 minutes.
    assert (adherence['taken'], adherence['total_due']) == (before['taken'], before['total_due'])

    r = patient.post('/api/v1/reminders/doses', json={'schedule_id': schedule['id'], 'status': 'TAKEN',
                                                      'scheduled_for': dose['scheduled_for']})
    assert r.status_code == 201 and r.json()['id'] == taken['record_id'], 'same status again is idempotent'
    r = patient.post('/api/v1/reminders/doses', json={'schedule_id': schedule['id'], 'status': 'SKIPPED',
                                                      'scheduled_for': dose['scheduled_for']})
    assert r.status_code == 409, 'changing a recorded dose requires supersedes'
    r = patient.post('/api/v1/reminders/doses', json={'schedule_id': schedule['id'], 'status': 'SKIPPED',
                                                      'scheduled_for': dose['scheduled_for'],
                                                      'supersedes': taken['record_id']})
    assert r.status_code == 201, r.text
    skipped = next(d for d in patient.get('/api/v1/reminders/today').json() if d['schedule_id'] == schedule['id'])
    assert skipped['status'] == 'SKIPPED'
    history = [d for d in patient.get('/api/v1/reminders/history?days=7').json() if d['schedule_id'] == schedule['id']]
    assert [d['status'] for d in history] == ['SKIPPED']


# ---------- HCP case review ----------

def test_hcp02_schedule_case_requires_an_assessment(patient, hcp):
    unassessed = intake(patient, SET_NONE, do_assess=False)
    schedule = create_schedule(patient, entry_ids(unassessed)['Agigout 100'], ['08:00']).json()
    r = patient.post('/api/v1/hcp/cases', json={'kind': 'SCHEDULE', 'schedule_id': schedule['id'],
                                                'hcp_id': provider_id(patient, hcp), 'consent': True})
    assert r.status_code == 409


@pytest.mark.parametrize('body', [
    {'consent': False}, {'consent': 'yes'}, {'kind': 'SAFETY', 'schedule_id': None}, {'kind': 'OTHER'},
], ids=['no-consent', 'truthy-consent', 'safety-without-assessment', 'unknown-kind'])
def test_hcp21_case_request_validation(patient, hcp, assessed, body):
    schedule = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], ['08:00']).json()
    payload = {'kind': 'SCHEDULE', 'schedule_id': schedule['id'], 'hcp_id': provider_id(patient, hcp),
               'consent': True, **body}
    assert patient.post('/api/v1/hcp/cases', json=payload).status_code == 422


def test_hcp_unknown_provider_is_rejected(patient, assessed):
    schedule = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], ['08:00']).json()
    r = patient.post('/api/v1/hcp/cases', json={'kind': 'SCHEDULE', 'schedule_id': schedule['id'],
                                                'hcp_id': str(uuid.uuid4()), 'consent': True})
    assert r.status_code == 409


def test_hcp_full_review_cycle(patient, hcp, login, assessed):
    """HCP-01 … HCP-19: send → message → changes requested → resend → approve → activate → toggle."""
    hcp_id = provider_id(patient, hcp)
    schedule = create_schedule(patient, entry_ids(assessed)['Hatacil 500'], ['08:00', '20:00']).json()

    # HCP-03: send for review
    r = patient.post('/api/v1/hcp/cases', json={'kind': 'SCHEDULE', 'schedule_id': schedule['id'],
                                                'hcp_id': hcp_id, 'consent': True})
    assert r.status_code == 201, r.text
    case = r.json()
    assert case['status'] == 'OPEN' and case['case_type'] == 'SCHEDULE'
    row = schedule_row(patient, schedule['id'])
    assert row['pending_proposal']['verification_status'] == 'UNVERIFIED', 'proposal waits under the current schedule'
    assert any(c['id'] == case['id'] for c in patient.get('/api/v1/hcp/cases/mine').json())

    # HCP-05: cannot send the same schedule twice while pending
    r = patient.post('/api/v1/hcp/cases', json={'kind': 'SCHEDULE', 'schedule_id': schedule['id'],
                                                'hcp_id': hcp_id, 'consent': True})
    assert r.status_code == 409

    # HCP-06/07: assigned HCP sees the case with schedule, medications and the Major finding
    assert any(c['id'] == case['id'] for c in hcp.get('/api/v1/hcp/cases').json())
    detail = hcp.get(f"/api/v1/hcp/cases/{case['id']}").json()
    assert detail['schedule']['name'] == 'Hatacil 500'
    assert detail['schedule']['schedule_details']['times'] == ['08:00', '20:00']
    assert {m['medication_fields']['name_raw'] for m in detail['medications']} == set(SET_MAJOR)
    assert 'MAJOR' in {f['severity'] for f in detail['findings']}
    assert detail['assessment']['execution_status'] == 'COMPLETED'

    # HCP-11: an HCP who was not assigned cannot see it
    other = login('multi')
    other.post('/api/auth/switch-context', json={'context': 'hcp'})
    assert case['id'] not in [c['id'] for c in other.get('/api/v1/hcp/cases').json()]
    assert other.get(f"/api/v1/hcp/cases/{case['id']}").status_code in (403, 404)
    assert other.post(f"/api/v1/hcp/cases/{case['id']}/messages", json={'text': 'x'}).status_code in (403, 404)
    assert other.post(f"/api/v1/hcp/cases/{case['id']}/review",
                      json={'decision': 'APPROVED', 'notes': 'x'}).status_code in (403, 404)

    # HCP-08/09/10: messaging both ways, with validation
    assert hcp.post(f"/api/v1/hcp/cases/{case['id']}/messages", json={'text': 'Bạn uống lúc mấy giờ?'}).status_code == 201
    assert patient.post(f"/api/v1/hcp/cases/{case['id']}/messages", json={'text': 'Sáng 8 giờ ạ'}).status_code == 201
    assert patient.post(f"/api/v1/hcp/cases/{case['id']}/messages", json={'text': '   '}).status_code == 422
    assert patient.post(f"/api/v1/hcp/cases/{case['id']}/messages", json={'text': 'a' * 5001}).status_code == 422
    texts = [m['content'] for m in patient.get(f"/api/v1/hcp/cases/{case['id']}").json()['messages']]
    assert texts == ['Bạn uống lúc mấy giờ?', 'Sáng 8 giờ ạ']

    # Patients cannot review
    assert patient.post(f"/api/v1/hcp/cases/{case['id']}/review",
                        json={'decision': 'APPROVED', 'notes': 'self'}).status_code == 403

    # HCP-12/13: changes requested, only one outcome per case
    r = hcp.post(f"/api/v1/hcp/cases/{case['id']}/review", json={'decision': 'CHANGES_REQUESTED', 'notes': 'Tách giờ uống'})
    assert r.status_code == 201, r.text
    r = hcp.post(f"/api/v1/hcp/cases/{case['id']}/review", json={'decision': 'APPROVED', 'notes': 'x'})
    assert r.status_code == 409
    mine = next(c for c in patient.get('/api/v1/hcp/cases/mine').json() if c['id'] == case['id'])
    assert mine['latest_outcome']['decision'] == 'CHANGES_REQUESTED'
    assert mine['latest_outcome']['notes'] == 'Tách giờ uống'
    rejected = [s for s in patient.get('/api/v1/reminders/schedules').json()
                if s.get('review_decision') == 'CHANGES_REQUESTED' and s['name'] == 'Hatacil 500']
    assert rejected, 'reviewed proposal is listed with its decision'
    proposal = rejected[0]

    # HCP-19: an unapproved proposal cannot be activated
    r = patient.post(f"/api/v1/reminders/schedules/{proposal['id']}/activate")
    assert r.status_code == 409

    # HCP-14: resend → HCP-16 approve → activate
    r = patient.post('/api/v1/hcp/cases', json={'kind': 'SCHEDULE', 'schedule_id': proposal['id'],
                                                'hcp_id': hcp_id, 'consent': True})
    assert r.status_code == 201, r.text
    second = r.json()
    r = hcp.post(f"/api/v1/hcp/cases/{second['id']}/review", json={'decision': 'APPROVED', 'notes': 'Đồng ý'})
    assert r.status_code == 201, r.text
    approved = next(s for s in patient.get('/api/v1/reminders/schedules').json()
                    if s.get('review_decision') == 'APPROVED' and s['name'] == 'Hatacil 500'
                    and s['verification_status'] == 'UNVERIFIED')
    r = patient.post(f"/api/v1/reminders/schedules/{approved['id']}/activate")
    assert r.status_code == 200, r.text

    active = schedule_row(patient, approved['id'])
    assert active['verification_status'] == 'HCP_VERIFIED'
    assert active['reminder_enabled'] is True
    closed = next(c for c in patient.get('/api/v1/hcp/cases/mine').json() if c['id'] == second['id'])
    assert closed['status'] == 'CLOSED'
    assert second['id'] not in [c['id'] for c in hcp.get('/api/v1/hcp/cases').json()
                                if c['status'] != 'CLOSED']
    today = [d for d in patient.get('/api/v1/reminders/today').json() if d['name'] == 'Hatacil 500']
    assert any(d['schedule_id'] == approved['id'] and d['reminder_enabled'] for d in today)

    # HCP-17: toggle off and on again without a new review
    r = patient.put(f"/api/v1/reminders/schedules/{approved['id']}/reminder", json={'enabled': False})
    assert r.status_code == 200, r.text
    r = patient.put(f"/api/v1/reminders/schedules/{approved['id']}/reminder", json={'enabled': True})
    assert r.status_code == 200, r.text
    assert schedule_row(patient, approved['id'])['reminder_enabled'] is True

    # Activating twice is harmless / rejected, never duplicates
    r = patient.post(f"/api/v1/reminders/schedules/{approved['id']}/activate")
    assert r.status_code in (200, 409)


def test_hcp15_rejection_blocks_activation(patient, hcp, assessed):
    hcp_id = provider_id(patient, hcp)
    schedule = create_schedule(patient, entry_ids(assessed)['DOMESIM 20 mg'], ['20:00']).json()
    case = patient.post('/api/v1/hcp/cases', json={'kind': 'SCHEDULE', 'schedule_id': schedule['id'],
                                                   'hcp_id': hcp_id, 'consent': True}).json()
    assert hcp.post(f"/api/v1/hcp/cases/{case['id']}/review",
                    json={'decision': 'REJECTED', 'notes': 'Không dùng cùng Clarithromycin'}).status_code == 201
    proposal = next(s for s in patient.get('/api/v1/reminders/schedules').json()
                    if s.get('review_decision') == 'REJECTED' and s['name'] == 'DOMESIM 20 mg')
    assert patient.post(f"/api/v1/reminders/schedules/{proposal['id']}/activate").status_code == 409
    original = schedule_row(patient, schedule['id'])
    assert original['verification_status'] == 'PATIENT_CONFIRMED' and original['reminder_enabled'] is False


def test_hcp20_safety_case_without_schedule(patient, hcp, assessed):
    """HCP-20: only reachable through the API (no UI button yet)."""
    r = patient.post('/api/v1/hcp/cases', json={'kind': 'SAFETY', 'assessment_id': assessed['assessment_id'],
                                                'hcp_id': provider_id(patient, hcp), 'consent': True})
    assert r.status_code == 201, r.text
    case = r.json()
    assert case['case_type'] == 'SAFETY'
    queue = {c['id']: c for c in hcp.get('/api/v1/hcp/cases').json()}
    assert case['id'] in queue
    detail = hcp.get(f"/api/v1/hcp/cases/{case['id']}").json()
    assert detail['schedule'] is None and 'MAJOR' in {f['severity'] for f in detail['findings']}
    assert hcp.post(f"/api/v1/hcp/cases/{case['id']}/review",
                    json={'decision': 'APPROVED', 'notes': 'Theo dõi men gan'}).status_code == 201


def test_hcp_cannot_see_patient_workspace(hcp):
    assert hcp.get('/api/v1/hcp/cases/mine').status_code == 403
    assert hcp.get('/api/v1/hcp/providers').status_code == 403



