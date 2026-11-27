"""Opt-in PostgreSQL integration: only an explicitly marked isolated test DB."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def test_unified_auth_core_and_ocr(monkeypatch, tmp_path):
    dsn = os.environ.get('UNIFIED_POSTGRES_TEST_DSN')
    if not dsn:
        pytest.skip('UNIFIED_POSTGRES_TEST_DSN is required')
    from db.manage import TEST_MARKER
    from db.setup_system import install_core
    from shared.auth.db import initialize, reset_connection
    options = conninfo_to_dict(dsn)
    assert options.get('host') in ('localhost', '127.0.0.1', '::1')
    assert options['dbname'].startswith('msa_core_test_v4') and options['dbname'].endswith('checks')
    with psycopg.connect(dsn, autocommit=True) as db:
        assert db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0] == TEST_MARKER
        url = URL.create('postgresql+psycopg', username=options.get('user'), password=options.get('password'),
                         host=options['host'], port=int(options.get('port', 5432)), database=options['dbname'])
        monkeypatch.setenv('AUTH_DATABASE_URL', url.render_as_string(hide_password=False))
        monkeypatch.setenv('CORE_DB_DSN', dsn)
        monkeypatch.setenv('AUTH_ENV', 'test')
        monkeypatch.setenv('AUTH_SEED_DEMO', '1')
        monkeypatch.setenv('AUTH_ALLOWED_ORIGINS', 'http://testserver')
        reset_connection()
        try:
            initialize()
            accounts = db.execute('SELECT user_id,email,password_hash,account_status FROM public.users ORDER BY user_id').fetchall()
            grants = db.execute('SELECT * FROM public.user_roles ORDER BY grant_id').fetchall()
            first = install_core(db, ROOT / 'data/datasets')
            second = install_core(db, ROOT / 'data/datasets')
            assert second['migrations'] == [] and second['reused_build']
            assert first['dataset_build'] == second['dataset_build']
            assert db.execute('SELECT user_id,email,password_hash,account_status FROM public.users ORDER BY user_id').fetchall() == accounts
            assert db.execute('SELECT * FROM public.user_roles ORDER BY grant_id').fetchall() == grants
            assert second['linked_accounts'] == len(accounts)
            with db.transaction(force_rollback=True):
                uid = uuid4()
                db.execute("INSERT INTO public.users(user_id,email,password_hash,full_name,account_status) VALUES (%s,%s,'test-only','Test','active')", (uid, f'{uid}@example.invalid'))
                assert db.execute('SELECT id FROM identity.users WHERE id=%s', (uid,)).fetchone()
            monkeypatch.setenv('CORE_REFERENCE_BUILD', first['dataset_build'])
            # Missing DDInter must not make OCR intake fail; never fabricate safety findings.
            monkeypatch.setenv('MSA_DDINTER_INDEX', str(ROOT / 'artifacts/nonexistent-ddinter.sqlite'))
            from apps.backend.api.app import app
            with TestClient(app, headers={'Origin': 'http://testserver'}) as client:
                login = client.post('/api/auth/login', json={'email': 'mai.demo@example.com', 'password': 'Mai-patient-2026'})
                assert login.status_code == 200
                assert client.get('/api/v1/intake/capabilities').json()['persistent_intake'] is True
                workflow = client.post('/api/v1/intake/workflows', json={})
                assert workflow.status_code == 200, workflow.text
                review = workflow.json()
                catalog = client.get('/api/reference/medications', params={'q': 'Panadol'}).json()
                assert catalog['medications']
                product = catalog['medications'][0]
                saved = client.post('/api/v1/intake/manual', json={
                    'workflow_id': review['workflow_id'], 'revision': review['revision'],
                    'source_medication_id': product['source_medication_id'], 'dataset_build': first['dataset_build'],
                    'medication': {'name_raw': product['brand_name'], 'evidence_text': product['brand_name']}})
                assert saved.status_code == 200, saved.text
                assert saved.json()['entries']
                assert not saved.json()['entries'][0]['confirmed']
                assert client.get(f"/api/v1/intake/workflows/{review['workflow_id']}/details").status_code == 200
                if os.environ.get('RUN_UNIFIED_OCR') == '1':
                    from PIL import Image, ImageDraw, ImageFont
                    font_path = os.environ.get('UNIFIED_OCR_TEST_FONT', 'C:/Windows/Fonts/arial.ttf')
                    image_path = tmp_path / 'synthetic-prescription.png'
                    canvas = Image.new('RGB', (2000, 1100), 'white')
                    draw = ImageDraw.Draw(canvas)
                    font = ImageFont.truetype(font_path, 46)
                    for y, text in [(60, 'DON THUOC - DU LIEU KIEM THU'),
                                    (220, '1. Panadol 500mg (Paracetamol)'),
                                    (300, 'Sang: 1 vien'), (380, 'Cach dung: Uong sau an'),
                                    (580, '2. Clopidogrel 75mg'),
                                    (660, 'Sang: 1 vien'), (740, 'Cach dung: Uong sau an')]:
                        draw.text((80, y), text, fill='black', font=font)
                    for y in (220, 580):
                        draw.text((1250, y), 'x10 ngay = 10 vien', fill='black', font=font)
                    canvas.save(image_path)
                    ocr_workflow = client.post('/api/v1/intake/workflows', json={}).json()
                    with image_path.open('rb') as image:
                        result = client.post(f"/api/v1/intake/workflows/{ocr_workflow['workflow_id']}/ocr",
                                             data={'revision': str(ocr_workflow['revision'])},
                                             files={'file': ('prescription.png', image, 'image/png')})
                    assert result.status_code == 200, result.text
                    assert result.json()['review']['entries']
                client.post('/api/auth/logout')
        finally:
            reset_connection()
