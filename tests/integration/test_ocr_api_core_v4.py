"""Actual Tesseract image -> authenticated API -> existing Core V4 -> official DDInter.

The image and reviewed form are independently authored engineering test input.
Auth uses a separate marked PostgreSQL test DB; reference data is never written.
"""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url

from apps.backend.api.app import app
from shared.auth.db import reset_connection, initialize, transaction
from shared.auth.models import User, Role, UserRole
from shared.auth.passwords import hash_password
from shared.auth.sessions import timestamp
from shared.intake_contracts import Medication, Administration
from tests.integration.test_module1_sources_real_e2e import (
    case, postgres_repo, ddinter, counts, findings, assert_ddinter_csv, PANADOL_ID, ALLTREX_ID, ROOT,
)


def test_real_ocr_review_confirmation_identity_safety_and_owner_api(case, tmp_path, monkeypatch):
    repo, build, products, dataset = case
    auth_url = os.environ.get('RBAC_POSTGRES_TEST_URL')
    assert auth_url, 'RBAC_POSTGRES_TEST_URL must select the separate marked Auth test database'
    url = make_url(auth_url)
    assert url.host in {'localhost', '127.0.0.1'} and url.database.startswith('msa_auth_test_')
    monkeypatch.setenv('AUTH_DATABASE_URL', auth_url)
    monkeypatch.setenv('AUTH_SEED_DEMO', '1')
    monkeypatch.setenv('AUTH_ENV', 'test')
    monkeypatch.setenv('CORE_DB_DSN', os.environ['MODULE2_TEST_DSN'])
    monkeypatch.setenv('CORE_REFERENCE_BUILD', build)
    monkeypatch.setenv('CORE_DATA_CONTEXT', 'SYNTHETIC_TEST')
    monkeypatch.setenv('AUTH_ALLOWED_ORIGINS', 'http://127.0.0.1:5173')
    other_owner, other_account = uuid4(), 'ocr-other-' + uuid4().hex
    repo.db.execute('INSERT INTO identity.users(id) VALUES (%s)', (other_owner,))
    monkeypatch.setenv('CORE_USER_BINDINGS', json.dumps({'u-patient': str(repo.owner), other_account: str(other_owner)}))
    reset_connection()
    initialize()
    with transaction() as db:
        db.add(User(user_id=other_account, email=other_account+'@example.test', password_hash=hash_password('Other-test-2026'),
                    full_name='Other synthetic owner', account_status='active'))
        db.flush()
        role = db.scalar(select(Role).where(Role.role_code == 'patient'))
        db.add(UserRole(user_id=other_account, role_id=role.role_id, granted_at=timestamp()))

    image = Image.new('RGB', (1700, 1050), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 48)
    lines = [('Thuốc điều trị - DỮ LIỆU KIỂM THỬ', 170, 45),
        ('1. Panadol Viên Sủi 500mg', 170, 250),
        ('Uống, Sáng: 1 viên', 170, 335),
        ('2. Alltrex 2,5mg', 170, 480),
        ('Uống, Sáng: 1 viên', 170, 565)]
    for text, x, y in lines:
        draw.text((x, y), text, font=font, fill='black')
    image_path = tmp_path / 'authored_panadol_alltrex.png'
    image.save(image_path)
    origin = {'origin': 'http://127.0.0.1:5173'}
    with TestClient(app, headers=origin) as client:
        assert client.post('/api/v1/intake/workflows').status_code == 401
        for email, password, allowed in [('ha', 'Ha-admin-2026', False), ('khoa', 'Khoa-support-2026', False),
                                          ('an', 'An-hcp-2026', True), ('huy', 'Huy-review-2026', True)]:
            assert client.post('/api/auth/login', json={'email': email+'.demo@example.com', 'password': password}).status_code == 200
            assert client.post('/api/v1/ocr/extractions', files={'file': ('bad.txt', b'bad', 'text/plain')}).status_code == (415 if allowed else 403)
            assert client.post('/api/v1/intake/workflows').status_code == 403
        assert client.post('/api/auth/login', json={'email': 'mai.demo@example.com', 'password': 'Mai-patient-2026'}).status_code == 200
        catalog = client.get('/api/reference/medications', params={'q': 'Panadol Viên Sủi'})
        assert catalog.status_code == 200, catalog.text
        assert catalog.json()['counts']['medications'] == 10670
        assert catalog.json()['dataset_build'] == build
        assert any(p['source_medication_id'] == PANADOL_ID and p['id'] == str(products[PANADOL_ID]['id'])
                   for p in catalog.json()['medications'])
        correct_bindings = os.environ['CORE_USER_BINDINGS']
        monkeypatch.setenv('CORE_USER_BINDINGS', '{}')
        assert client.post('/api/v1/intake/workflows').status_code == 403
        monkeypatch.setenv('CORE_USER_BINDINGS', json.dumps({'u-patient': str(uuid4())}))
        assert client.post('/api/v1/intake/workflows').status_code == 403
        assert not any(counts(repo).values())
        monkeypatch.setenv('CORE_USER_BINDINGS', correct_bindings)
        assert client.post('/api/v1/intake/workflows', json={'owner': str(other_owner)}).status_code == 422
        current = client.post('/api/v1/intake/workflows').json()
        workflow = current['workflow_id']
        with image_path.open('rb') as stream:
            response = client.post(f'/api/v1/intake/workflows/{workflow}/ocr', data={'revision': current['revision']},
                files={'file': (image_path.name, stream, 'image/png')})
        assert response.status_code == 200, response.text
        result = response.json()
        raw = result['ocr']['extraction_run']['raw_output']
        print('\nREAL_OCR_RAW:', json.dumps({'text': raw['ocr']['text'], 'parsed': raw['parsed']['medications']}, ensure_ascii=False))
        current = result['review']
        assert len(current['entries']) == 2 and not any(e['confirmed'] for e in current['entries'])
        assert not any(counts(repo).values())
        original_revision = current['revision']
        for index, source_id in enumerate((PANADOL_ID, ALLTREX_ID)):
            product = products[source_id]
            med = Medication(name_raw=product['brand_name'], strength_raw='500mg' if index == 0 else '2,5mg',
                dosage_form_raw=product['dosage_form'], dose_raw='một viên',
                administrations=[Administration(timing_raw='mỗi sáng', dose_raw='một viên')],
                evidence_text=f"Người dùng đối chiếu ảnh: {product['brand_name']}, một viên mỗi sáng")
            edited = client.post('/api/v1/intake/ocr/edit', json={'workflow_id': workflow, 'revision': current['revision'],
                'entry_version_id': current['entries'][index]['entry_version_id'], 'medication': med.model_dump(mode='json')})
            assert edited.status_code == 200, edited.text
            current = edited.json()
        assert current['state'] == 'AWAITING_CONFIRMATION'
        for action in ('IDENTIFY', 'ASSESS'):
            blocked = client.post('/api/v1/intake/actions', json={'workflow_id': workflow, 'revision': current['revision'],
                'request_key': str(uuid4()), 'action': action, 'explicit_request': True})
            assert blocked.status_code == 409
        assert not any(counts(repo).values())
        print('OCR_BEFORE_CONFIRM_COUNTS:', counts(repo))
        assert client.post('/api/v1/intake/confirm', json={'workflow_id': workflow, 'revision': original_revision,
            'request_key': str(uuid4()), 'explicit_confirmation': True}).status_code == 409
        confirmed = client.post('/api/v1/intake/confirm', json={'workflow_id': workflow, 'revision': current['revision'],
            'request_key': str(uuid4()), 'explicit_confirmation': True})
        assert confirmed.status_code == 200, confirmed.text
        current = confirmed.json()
        assert current['state'] == 'COMPLETED' and not any(counts(repo).values())
        identified = client.post('/api/v1/intake/actions', json={'workflow_id': workflow, 'revision': current['revision'],
            'request_key': str(uuid4()), 'action': 'IDENTIFY', 'explicit_request': True})
        assert identified.status_code == 200, identified.text
        identities = identified.json()['identification_results']
        assert {r['identified_candidate']['id'] for r in identities} == {str(p['id']) for p in products.values()}
        assert {r['identified_candidate']['source_medication_id'] for r in identities} == {PANADOL_ID, ALLTREX_ID}
        assert all(r['ready_for_identifier_handoff'] for r in identities)
        assessed = client.post('/api/v1/intake/actions', json={'workflow_id': workflow, 'revision': current['revision'],
            'request_key': str(uuid4()), 'action': 'ASSESS', 'explicit_request': True})
        assert assessed.status_code == 200, assessed.text
        saved = repo._owned('safety_assessments', assessed.json()['assessment_id'])
        assert saved['execution_status'] == 'COMPLETED' and saved['check_results']['ddi']['coverage'] == 'PARTIAL'
        ddi = [f for f in findings(repo, saved) if f['finding_type'] == 'DDI']
        assert {f['source_severity'] for f in ddi} == {'Moderate'}
        oracle = assert_ddinter_csv(dataset)
        assert any(s['record']['raw_source_row'] == oracle['raw_source_row'] for f in ddi for s in f['evidence']['sources'])
        inp = repo._all("SELECT * FROM msa.intake_inputs WHERE user_id=%s AND modality='IMAGE'", (repo.owner,))[0]
        retained = ROOT / raw['ocr']['preprocessing']['artifacts'] / 'original.png'
        assert retained.is_file() and inp['input_digest'] == hashlib.sha256(retained.read_bytes()).hexdigest()
        assert inp['payload_or_locator']['object_locator']['uri'] == retained.resolve().as_uri()
        print('OCR_MODULE2_3:', json.dumps({'workflow': workflow, 'assessment': str(saved['id']), 'coverage': 'PARTIAL',
            'severity': 'Moderate', 'products': [{'source_id': r['identified_candidate']['source_medication_id'],
            'core_id': r['identified_candidate']['id'], 'ingredients': r['verified_ddinter_ids']} for r in identities]}))
        assert client.post('/api/auth/login', json={'email': other_account+'@example.test', 'password': 'Other-test-2026'}).status_code == 200
        assert client.get(f'/api/v1/intake/workflows/{workflow}').status_code == 404
        assert client.post('/api/v1/intake/confirm', json={'workflow_id': workflow, 'revision': current['revision'],
            'request_key': str(uuid4()), 'explicit_confirmation': True}).status_code == 404
    reset_connection()
