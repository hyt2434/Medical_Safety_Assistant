"""Live acceptance suite: drives the RUNNING local app over HTTP, like a user would.

Opt-in only, because it writes real (append-only) records to the configured database:

    $env:ACCEPTANCE_LIVE = '1'
    .\\.venv\\Scripts\\python.exe -m pytest tests/acceptance -v

Settings (environment variables):
    ACCEPTANCE_API     backend URL            (default http://127.0.0.1:8000)
    ACCEPTANCE_ORIGIN  allowed browser origin (default http://127.0.0.1:5173)
    ACCEPTANCE_SLOW=0  skip tests that wait for a dose time or call Qwen/Whisper/OCR

Each account logs in once per run: the login throttle counts successful attempts
(20 per account and 100 per client address per 5 minutes).
Test IDs in docstrings refer to docs/testing/manual-test-plan.md.
"""
import os

import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

API = os.environ.get('ACCEPTANCE_API', 'http://127.0.0.1:8000')
ORIGIN = os.environ.get('ACCEPTANCE_ORIGIN', 'http://127.0.0.1:5173')
ZONE = 'Asia/Ho_Chi_Minh'

ACCOUNTS = {
    'patient': ('mai.demo@example.com', 'Mai-patient-2026'),
    'hcp': ('an.demo@example.com', 'An-hcp-2026'),
    'multi': ('multi.demo@example.com', 'Multi-role-2026'),
    'reviewer': ('huy.demo@example.com', 'Huy-review-2026'),
    'support': ('khoa.demo@example.com', 'Khoa-support-2026'),
    'admin': ('ha.demo@example.com', 'Ha-admin-2026'),
}

# Catalog products verified against this deployment's reference build and DDInter index.
# strength is what a patient copies from the label.
PRODUCTS = {
    'Fremedol 500': '500mg',     # Paracetamol
    'LOPECOL': '500mg',          # Paracetamol (duplicate ingredient with Fremedol 500)
    'Agigout 100': '100mg',      # Allopurinol
    'Hatacil 500': '500mg',      # Clarithromycin
    'DOMESIM 20 mg': '20mg',     # Simvastatin   (Major with Clarithromycin)
    'Vascam': '5mg',             # Amlodipine
    'Ibu Hera 400': '400mg',     # Ibuprofen     (Moderate with Amlodipine)
    'Somecid': '20mg',           # Omeprazole pellet: strength needs human review -> AMBIGUOUS
}
SET_NONE = ['Fremedol 500', 'Agigout 100']
SET_MAJOR = ['Hatacil 500', 'DOMESIM 20 mg']
SET_MODERATE = ['Vascam', 'Ibu Hera 400']
SET_DUPLICATE = ['Fremedol 500', 'LOPECOL']

if os.environ.get('ACCEPTANCE_LIVE') != '1':
    collect_ignore_glob = ['test_*.py']

slow = pytest.mark.skipif(os.environ.get('ACCEPTANCE_SLOW') == '0', reason='ACCEPTANCE_SLOW=0')


def client(**headers):
    return httpx.Client(base_url=API, headers={'Origin': ORIGIN, **headers}, timeout=300)


@pytest.fixture(scope='session', autouse=True)
def live_app():
    try:
        httpx.get(API + '/health', timeout=5).raise_for_status()
    except httpx.HTTPError as error:
        pytest.exit(f'Backend not reachable at {API}: {error}', returncode=2)


class Sessions:
    """Logs each account in at most once per run and reuses the cookie."""

    def __init__(self):
        self._clients = {}

    def __call__(self, name):
        if name not in self._clients:
            email, password = ACCOUNTS[name]
            c = client()
            r = c.post('/api/auth/login', json={'email': email, 'password': password})
            assert r.status_code == 200, f'login {name}: {r.status_code} {r.text}'
            c.me = r.json()
            self._clients[name] = c
        return self._clients[name]

    def close(self):
        for c in self._clients.values():
            c.close()


@pytest.fixture(scope='session')
def login():
    sessions = Sessions()
    yield sessions
    sessions.close()


@pytest.fixture(scope='session')
def patient(login):
    return login('patient')


@pytest.fixture(scope='session')
def hcp(login):
    return login('hcp')


@pytest.fixture(scope='session')
def admin(login):
    return login('admin')


# ---------- intake helpers ----------

def product(c, name):
    rows = c.get('/api/reference/medications', params={'q': name}).json()['medications']
    matches = [m for m in rows if m['brand_name'] == name]
    assert matches, f'{name} not found in catalog'
    return matches[0]


# A patient may only self-confirm a schedule whose clock times and dose are copied
# verbatim from the confirmed instructions (DB rule msa.schedule_copies_instructions).
TIMING = 'uống lúc 08:00 và 20:00'


def medication_fields(name, strength, form, dose='1 viên', timing=TIMING):
    return {'name_raw': name, 'strength_raw': strength, 'dosage_form_raw': form, 'dose_raw': dose,
            'administrations': [{'timing_raw': timing, 'dose_raw': dose, 'timing_slots_raw': []}],
            'evidence_text': f'{name}, {strength}, {dose}, {timing}'}


def start_workflow(c):
    r = c.post('/api/v1/intake/workflows')
    assert r.status_code == 200, r.text
    return r.json()


def add_manual(c, wf, name, strength=None, **fields):
    p = product(c, name)
    r = c.post('/api/v1/intake/manual', json={
        'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
        'source_medication_id': p['source_medication_id'], 'dataset_build': p['dataset_build'],
        'medication': medication_fields(name, strength or PRODUCTS[name], p['dosage_form'], **fields)})
    assert r.status_code == 200, r.text
    return r.json()


def confirm(c, wf):
    r = c.post('/api/v1/intake/confirm', json={'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
                                              'request_key': str(uuid.uuid4()), 'explicit_confirmation': True})
    assert r.status_code == 200, r.text
    return r.json()


def assess(c, wf, request_key=None):
    r = c.post('/api/v1/intake/actions', json={'workflow_id': wf['workflow_id'], 'revision': wf['revision'],
                                              'request_key': request_key or str(uuid.uuid4()),
                                              'action': 'ASSESS', 'explicit_request': True})
    assert r.status_code == 200, r.text
    return r.json()


def details(c, wf):
    r = c.get(f"/api/v1/intake/workflows/{wf['workflow_id']}/details")
    assert r.status_code == 200, r.text
    return r.json()


def intake(c, names, *, do_confirm=True, do_assess=True, **fields):
    """Manual intake of catalog products → optional confirm → optional assess."""
    wf = start_workflow(c)
    for name in names:
        wf = add_manual(c, wf, name, **fields)
    if do_confirm:
        wf = confirm(c, wf)
    if do_assess:
        wf = assess(c, wf)
    return wf


def findings(c, wf):
    a = details(c, wf)['assessment']
    return [(f['finding_type'], f['severity']) for f in (a or {}).get('findings', [])]


# ---------- reminder helpers ----------

def local_now():
    return datetime.now(ZoneInfo(ZONE))


def entry_ids(wf):
    return {e['medication']['name_raw']: e['entry_version_id'] for e in wf['entries']}


def create_schedule(c, entry_version_id, times, dose='1 viên', timezone=ZONE):
    return c.post('/api/v1/reminders/schedules', json={'entry_version_id': entry_version_id, 'times': times,
                                                      'dose_raw': dose, 'timezone': timezone, 'confirm': True})


def schedule_row(c, schedule_id):
    rows = c.get('/api/v1/reminders/schedules').json()
    for row in rows:
        if row['id'] == schedule_id:
            return row
        if (row.get('pending_proposal') or {}).get('id') == schedule_id:
            return row['pending_proposal']
    return None


def next_minute(offset=1):
    """HH:MM at least `offset` minutes ahead (local), and seconds until it is due."""
    target = (local_now() + timedelta(minutes=offset)).replace(second=0, microsecond=0)
    if target <= local_now():
        target += timedelta(minutes=1)
    return target.strftime('%H:%M'), (target - local_now()).total_seconds() + 3


def wait_until_due(seconds):
    time.sleep(max(0, seconds))


def provider_id(patient_client, hcp_client):
    """UUID of a logged-in HCP, asserted to be offered in the patient's provider list."""
    hcp_id = hcp_client.me['account']['id']
    rows = patient_client.get('/api/v1/hcp/providers').json()
    assert hcp_id in [row['id'] for row in rows], f'{hcp_id} not offered: {rows}'
    return hcp_id


def account_id(admin_client, email):
    for a in admin_client.get('/api/admin/accounts').json()['accounts']:
        if a['email'] == email:
            return a['id']
    raise AssertionError(email)


def error_code(r):
    try:
        body = r.json()
    except ValueError:
        return None
    return (body.get('error') or {}).get('code') or body.get('code')


def message_of(r):
    try:
        body = r.json()
    except ValueError:
        return r.text
    detail = body.get('detail')
    return detail if isinstance(detail, str) else str(body)


__all__ = [n for n in dir() if not n.startswith('_')]

