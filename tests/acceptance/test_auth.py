"""AUTH-xx and role-guard checks over the live API."""
import uuid

import httpx
import pytest

from tests.acceptance.conftest import API, ACCOUNTS, client, error_code


def login_raw(email, password, **headers):
    with client(**headers) as c:
        return c.post('/api/auth/login', json={'email': email, 'password': password})


def test_auth02_patient_login_sets_httponly_cookie(patient):
    """AUTH-02: patient login opens the patient context and an HttpOnly, SameSite=Lax cookie."""
    assert patient.me['activeContext'] == 'patient'
    assert patient.me['roles'] == ['patient']
    assert set(patient.me['contextPermissions']) == {'patient.workspace', 'intake.ocr'}
    r = login_raw(*ACCOUNTS['patient'])
    cookie = r.headers['set-cookie'].lower()
    assert r.status_code == 200
    assert 'msa_session=' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie
    assert ACCOUNTS['patient'][1].lower() not in r.text.lower()


def test_auth03_wrong_password_is_401_without_cookie():
    """AUTH-03"""
    r = login_raw(ACCOUNTS['patient'][0], 'definitely-wrong')
    assert r.status_code == 401
    assert 'set-cookie' not in r.headers
    assert error_code(r) == 'UNAUTHENTICATED'


def test_auth04_unknown_email_looks_identical_to_wrong_password():
    """AUTH-04: no account enumeration."""
    unknown = login_raw(f'nobody-{uuid.uuid4().hex[:8]}@example.com', 'x')
    wrong = login_raw(ACCOUNTS['patient'][0], 'definitely-wrong')
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()['detail'] == wrong.json()['detail']


def test_auth05_locked_account_is_403():
    """AUTH-05"""
    r = login_raw('locked.demo@example.com', 'Locked-patient-2026')
    assert r.status_code == 403
    assert 'set-cookie' not in r.headers


SECRET = 'Secret-Value-9137'


@pytest.mark.parametrize('body', [
    {'email': '', 'password': SECRET},
    {'email': 'abc', 'password': SECRET},
    {'email': 'a b@example.com', 'password': SECRET},
    {'email': 'a@example.com', 'password': ''},
    {'email': 'a@example.com', 'password': SECRET, 'role': 'admin'},   # extra fields are forbidden
])
def test_auth06_invalid_login_body_is_422_and_never_echoes_password(body):
    """AUTH-06"""
    with client() as c:
        r = c.post('/api/auth/login', json=body)
    assert r.status_code == 422
    assert error_code(r) == 'INVALID_INPUT'
    assert SECRET not in r.text


def test_auth07_me_returns_active_session(patient):
    """AUTH-07"""
    r = patient.get('/api/auth/me')
    assert r.status_code == 200
    assert r.json()['account']['email'] == ACCOUNTS['patient'][0]


def test_auth08_logout_invalidates_the_server_session():
    """AUTH-08: logout deletes the session; replaying the old cookie is rejected."""
    with client() as c:
        assert c.post('/api/auth/login', json=dict(zip(('email', 'password'), ACCOUNTS['patient']))).status_code == 200
        token = c.cookies.get('msa_session')
        assert c.post('/api/auth/logout').status_code == 204
    with client() as replay:
        replay.cookies.set('msa_session', token)
        assert replay.get('/api/auth/me').status_code == 401
        assert replay.get('/api/v1/reminders/schedules').status_code == 401


@pytest.mark.parametrize('path', ['/api/auth/me', '/api/v1/reminders/schedules', '/api/v1/hcp/cases',
                                  '/api/admin/accounts', '/api/reference/medications?q=a'])
def test_auth09_anonymous_requests_are_401(path):
    """AUTH-09"""
    assert httpx.get(API + path).status_code == 401


@pytest.mark.parametrize('account,path,expected', [
    ('patient', '/api/v1/hcp/cases', 403),          # HCP queue
    ('patient', '/api/admin/accounts', 403),
    ('hcp', '/api/v1/reminders/schedules', 403),    # patient workspace
    ('hcp', '/api/admin/status', 403),
    ('reviewer', '/api/v1/hcp/cases', 403),
    ('reviewer', '/api/v1/reminders/today', 403),
    ('support', '/api/admin/accounts', 403),
    ('support', '/api/v1/reminders/today', 403),
    ('admin', '/api/v1/reminders/today', 403),
    ('admin', '/api/v1/hcp/cases', 403),
    ('hcp', '/api/v1/hcp/cases', 200),
    ('patient', '/api/v1/hcp/cases/mine', 200),
    ('admin', '/api/admin/status', 200),
])
def test_auth10_11_role_guards(login, account, path, expected):
    """AUTH-10/11, ADM-11: every role is limited to its own API area."""
    assert login(account).get(path).status_code == expected


def test_auth13_14_multi_role_contexts_are_not_merged(login):
    """AUTH-13/14: permissions come only from the active context."""
    multi = login('multi')
    contexts = {c['code'] for c in multi.get('/api/auth/contexts').json()['contexts']}
    assert contexts == {'hcp', 'medical_reviewer'}
    r = multi.post('/api/auth/switch-context', json={'context': 'hcp'})
    assert r.status_code == 200 and r.json()['activeContext'] == 'hcp'
    assert 'catalog.review' not in r.json()['contextPermissions']
    assert multi.get('/api/v1/hcp/cases').status_code == 200
    r = multi.post('/api/auth/switch-context', json={'context': 'medical_reviewer'})
    assert r.status_code == 200 and 'clinical.case_review' not in r.json()['contextPermissions']
    assert multi.get('/api/v1/hcp/cases').status_code == 403
    assert multi.post('/api/auth/switch-context', json={'context': 'admin'}).status_code == 403
    multi.post('/api/auth/switch-context', json={'context': 'hcp'})


def test_auth16_login_throttle_returns_429_with_retry_after():
    """AUTH-16: uses a throwaway email so no real account is locked out."""
    email = f'throttle-{uuid.uuid4().hex[:8]}@example.com'
    statuses = [login_raw(email, 'wrong').status_code for _ in range(21)]
    assert statuses[:20] == [401] * 20
    last = login_raw(email, 'wrong')
    assert statuses[20] == 429 or last.status_code == 429
    assert int(last.headers.get('retry-after', '0')) > 0


@pytest.mark.parametrize('headers,expected', [
    ({}, 403),                                   # AUTH-17: no Origin / Referer
    ({'Origin': 'http://evil.example'}, 403),    # AUTH-19
    ({'Origin': 'http://localhost:5173'}, 403),  # localhost is a different origin
])
def test_auth17_19_writes_require_allowed_origin(headers, expected):
    r = httpx.post(API + '/api/auth/login', headers=headers,
                   json=dict(zip(('email', 'password'), ACCOUNTS['patient'])))
    assert r.status_code == expected
    assert 'set-cookie' not in r.headers


def test_auth17_cross_site_fetch_is_rejected_even_with_allowed_origin():
    from tests.acceptance.conftest import ORIGIN
    r = httpx.post(API + '/api/auth/login', headers={'Origin': ORIGIN, 'Sec-Fetch-Site': 'cross-site'},
                   json=dict(zip(('email', 'password'), ACCOUNTS['patient'])))
    assert r.status_code == 403


def test_auth20_security_headers(patient):
    """AUTH-20"""
    r = patient.get('/api/auth/me')
    assert r.headers['cache-control'] == 'no-store'
    assert r.headers['x-content-type-options'] == 'nosniff'
    assert r.headers['x-frame-options'] == 'DENY'
    assert r.headers['referrer-policy'] == 'no-referrer'


def test_auth22_cannot_read_another_account(patient, hcp):
    """AUTH-22"""
    assert patient.get('/api/auth/accounts/' + patient.me['account']['id']).status_code == 200
    assert patient.get('/api/auth/accounts/' + hcp.me['account']['id']).status_code == 403


def test_sup04_support_and_admin_cannot_use_ocr(login):
    """SUP-04: OCR permission is limited to patient/hcp/reviewer contexts."""
    for name in ('support', 'admin'):
        r = login(name).post('/api/v1/ocr/extractions', files={'file': ('a.png', b'x', 'image/png')})
        assert r.status_code == 403, name
