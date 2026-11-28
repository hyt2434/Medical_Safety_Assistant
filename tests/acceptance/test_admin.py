"""ADM-xx: account directory, role grants, expiry, revocation and audit (live API).

Grants are applied to khoa.demo (technical_support) and always revoked afterwards.
"""
import time
from datetime import datetime, timedelta, timezone

import pytest

from tests.acceptance.conftest import ACCOUNTS, account_id, client

SUPPORT_EMAIL, SUPPORT_PASSWORD = ACCOUNTS['support']


def fresh_support_login():
    c = client()
    r = c.post('/api/auth/login', json={'email': SUPPORT_EMAIL, 'password': SUPPORT_PASSWORD})
    assert r.status_code == 200, r.text
    c.me = r.json()
    return c


def iso(delta):
    return (datetime.now(timezone.utc) + delta).isoformat()


@pytest.fixture
def support_id(admin):
    target = account_id(admin, SUPPORT_EMAIL)
    yield target
    # Always restore: technical_support only.
    roles = next(a['roles'] for a in admin.get('/api/admin/accounts').json()['accounts'] if a['id'] == target)
    if 'hcp' in roles:
        admin.delete(f'/api/admin/users/{target}/roles/hcp')


def test_adm02_directory_lists_demo_accounts_with_roles(admin):
    accounts = {a['email']: a for a in admin.get('/api/admin/accounts').json()['accounts']}
    for name, (email, _) in ACCOUNTS.items():
        assert email in accounts, email
    assert accounts['locked.demo@example.com']['accountStatus'] == 'locked'
    assert set(accounts['multi.demo@example.com']['roles']) == {'hcp', 'medical_reviewer'}
    assert all('grants' in a for a in accounts.values())


def test_adm09_role_catalog_matches_rbac_defaults(admin):
    roles = {r['code']: set(r['permissions']) for r in admin.get('/api/admin/roles').json()['roles']}
    assert roles == {
        'patient': {'patient.workspace', 'intake.ocr'},
        'hcp': {'clinical.case_review', 'intake.ocr'},
        'medical_reviewer': {'catalog.review', 'catalog.edit', 'intake.ocr'},
        'admin': {'staff.directory', 'admin.accounts', 'admin.roles', 'admin.audit', 'operations.assign'},
        'technical_support': {'staff.directory', 'operations.queue'},
    }
    assert admin.get('/api/admin/permissions').status_code == 200


def test_adm03_04_07_grant_then_revoke_hcp_role(admin, login, support_id):
    """ADM-03 grant → target must re-login → gains hcp context; ADM-04 appears as provider; ADM-07 revoke."""
    before = fresh_support_login()
    r = admin.post(f'/api/admin/users/{support_id}/roles', json={'roleCode': 'hcp', 'expiresAt': None})
    assert r.status_code == 200, r.text
    # Granting more privilege forces the target to sign in again.
    assert before.get('/api/auth/me').status_code == 401

    support = fresh_support_login()
    assert 'hcp' in support.me['roles']
    assert support.post('/api/auth/switch-context', json={'context': 'hcp'}).status_code == 200
    assert support.get('/api/v1/hcp/cases').status_code == 200
    offered = [p['id'] for p in login('patient').get('/api/v1/hcp/providers').json()]
    assert support_id in offered, 'ADM-04: newly granted HCP is offered to patients'

    r = admin.delete(f'/api/admin/users/{support_id}/roles/hcp')
    assert r.status_code == 200, r.text
    assert support.get('/api/v1/hcp/cases').status_code in (401, 403)
    assert support_id not in [p['id'] for p in login('patient').get('/api/v1/hcp/providers').json()]


def test_adm05_expiry_in_the_past_or_without_timezone_is_rejected(admin, support_id):
    r = admin.post(f'/api/admin/users/{support_id}/roles', json={'roleCode': 'hcp', 'expiresAt': iso(timedelta(days=-1))})
    assert r.status_code == 422
    naive = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
    r = admin.post(f'/api/admin/users/{support_id}/roles', json={'roleCode': 'hcp', 'expiresAt': naive})
    assert r.status_code == 422


def test_adm06_role_stops_working_after_expiry(admin, support_id):
    r = admin.post(f'/api/admin/users/{support_id}/roles', json={'roleCode': 'hcp', 'expiresAt': iso(timedelta(seconds=20))})
    assert r.status_code == 200, r.text
    support = fresh_support_login()
    assert support.post('/api/auth/switch-context', json={'context': 'hcp'}).status_code == 200
    assert support.get('/api/v1/hcp/cases').status_code == 200
    time.sleep(25)
    assert support.get('/api/v1/hcp/cases').status_code in (401, 403)


def test_adm08_admin_cannot_remove_own_admin_role(admin):
    me = admin.me['account']['id']
    r = admin.delete(f'/api/admin/users/{me}/roles/admin')
    assert r.status_code == 409
    assert admin.get('/api/admin/status').status_code == 200


def test_adm_grant_unknown_account_is_404(admin):
    r = admin.post('/api/admin/users/00000000-0000-0000-0000-000000000000/roles', json={'roleCode': 'hcp'})
    assert r.status_code == 404


def test_adm_non_admin_cannot_grant(login, support_id):
    r = login('hcp').post(f'/api/admin/users/{support_id}/roles', json={'roleCode': 'admin'})
    assert r.status_code == 403


def test_adm10_audit_records_security_events(admin):
    client().post('/api/auth/login', json={'email': SUPPORT_EMAIL, 'password': 'wrong-password'})
    events = admin.get('/api/admin/audit').json()['events']
    assert events, 'audit is empty'
    actions = {e['actionCode'] for e in events}
    assert any(not e['success'] for e in events), 'failed login not audited'
    assert any('role' in a or 'grant' in a for a in actions), actions
