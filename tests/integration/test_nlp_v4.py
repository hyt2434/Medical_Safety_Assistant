"""Opt-in real Core V4 checks, exclusively on a separate marked NLP test database.

No reference imports, paid inference, Module 2/3 execution or shared DB fixtures.
"""
from copy import deepcopy
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest

from module1_intake.nlp.dialogue_management.manager import Chatbot
from module1_intake.nlp.understanding.providers import MockProvider
from module1_intake.nlp.models import Medication, Understanding
from shared.db import CoreRepository


@pytest.fixture(scope='module')
def connection():
    dsn = os.environ.get('NLP_TEST_DSN')
    if not dsn:
        pytest.skip('NLP_TEST_DSN not configured; isolated PostgreSQL integration only')
    options = conninfo_to_dict(dsn)
    if (options.get('host') not in {'localhost', '127.0.0.1', '::1'} or
            not re.fullmatch(r'msa_core_test_v4nlp[a-z0-9]*checks', options.get('dbname', ''))):
        pytest.fail('Refusing database: dedicated loopback msa_core_test_v4nlp<suffix>checks required')
    # Guard happens BEFORE bootstrap or connection. msa_core_test_v4checks is rejected.
    if os.environ.get('NLP_TEST_BOOTSTRAP') == '1':
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'db'))
        from manage import bootstrap_test
        bootstrap_test(dsn, explicit=True)
    with psycopg.connect(dsn, autocommit=True) as db:
        marker = db.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if marker != 'Medication Safety Assistant Core V4 isolated test':
            pytest.fail('Refusing unmarked database')
        yield db


@pytest.fixture
def setup(connection):
    # Synthetic identities exist only in the explicitly marked NLP fixture database.
    owner = uuid4()
    connection.execute('INSERT INTO identity.users(id) VALUES (%s)', (owner,))
    repo = CoreRepository(connection, authenticated_owner=owner)
    bot = Chatbot(repo, MockProvider())
    return connection, repo, bot, bot.start()


def send(bot, reply, text):
    return bot.send(reply.workflow_id, text, expected_revision=reply.revision)


def test_real_v4_payloads_digests_confirmation_and_resume(setup):
    db, repo, bot, r = setup
    source = 'Tôi đang uống Panadol 500mg, dạng viên nén, mỗi sáng một viên, 2 hộp x 10 vỉ x 10 viên'
    r = send(bot, r, source)
    assert r.state == 'AWAITING_CONFIRMATION'
    workflow = repo._owned('workflow_instances', r.workflow_id)
    entry = bot.store.entries(workflow)[0]
    assert entry['medication_fields']['quantity_raw'] == '2 hộp x 10 vỉ x 10 viên'
    assert entry['confirmed_at'] is None
    assert repo.digest(entry['medication_fields']) == entry['content_digest']
    restored = Chatbot(repo, MockProvider())
    r = send(restored, r, 'xác nhận')
    assert r.state == 'COMPLETED' and r.handoff.entries[0].identity_status == 'NOT_ATTEMPTED'
    assert db.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('msa','msa_ref') AND table_type='BASE TABLE'").fetchone()[0] == 20
    assert db.execute('SELECT count(*) FROM msa.entry_matches WHERE user_id=%s', (repo.owner,)).fetchone()[0] == 0


def test_real_correction_preserves_confirmed_history_and_stale_review(setup):
    db, repo, bot, r = setup
    r = send(bot, r, 'Tôi đang uống A 500mg, dạng viên nén')
    r = send(bot, r, 'xác nhận')
    original = r.handoff.entries[0]
    r = bot.revise(r.workflow_id)
    r = send(bot, r, 'sửa thuốc 1 thành A 250mg')
    version = bot.store.entries(bot.store.workflow(r.workflow_id))[0]
    assert version['supersedes_version_id'] == original.entry_version_id
    assert version['confirmed_at'] is None
    assert repo._owned('medication_entry_versions', original.entry_version_id)['confirmed_at'] is not None
    r = send(bot, r, 'xác nhận')
    assert r.handoff.entries[0].medication.strength_raw == '250mg'
    assert repo._owned('medication_entry_versions', original.entry_version_id)['medication_fields']['strength_raw'] == '500mg'


def test_real_multi_drug_correction_target_and_foreign_owner(setup):
    db, repo, bot, r = setup
    r = send(bot, r, 'Tôi đang uống A 500mg; đang dùng B 250mg')
    r = send(bot, r, 'sửa hàm lượng 100mg')
    assert 'số mấy' in r.text
    r = send(bot, r, 'sửa thuốc 2 thành B 100mg')
    r = send(bot, r, 'không rõ')
    assert r.state == 'CLARIFYING'  # The other target still needs its own unknown decision.
    r = send(bot, r, 'không rõ')
    rows = bot.store.entries(bot.store.workflow(r.workflow_id))
    assert [e['medication_fields']['strength_raw'] for e in rows] == ['500mg', '100mg']
    foreign = Chatbot(CoreRepository(db, authenticated_owner=uuid4()), MockProvider())
    with pytest.raises(PermissionError):
        send(foreign, r, 'xác nhận')
    send(bot, r, 'xác nhận')


def test_real_retry_partial_confirmation_and_side_question(setup, monkeypatch):
    db, repo, bot, r = setup
    r = send(bot, r, 'Tôi đang uống A 500mg, dạng viên nén; đang dùng B 250mg, dạng viên nén')
    r = send(bot, r, 'cách xác nhận')
    assert r.state == 'AWAITING_CONFIRMATION'
    original = repo.confirm_entry
    calls = []
    def flaky(*args, **kwargs):
        calls.append(args[0])
        if len(calls) == 2:
            raise RuntimeError('synthetic failure after first durable confirmation')
        return original(*args, **kwargs)
    monkeypatch.setattr(repo, 'confirm_entry', flaky)
    key = uuid4()
    with pytest.raises(RuntimeError):
        bot.confirm(r.workflow_id, expected_revision=r.revision, request_key=key, explicit_confirmation=True)
    assert bot.store.workflow(r.workflow_id)['state'] == 'AWAITING_CONFIRMATION'
    done = bot.confirm(r.workflow_id, expected_revision=r.revision, request_key=key, explicit_confirmation=True)
    assert done.handoff and len(done.handoff.entries) == 2
    assert bot.confirm(r.workflow_id, expected_revision=r.revision, request_key=key, explicit_confirmation=True).handoff == done.handoff


def test_real_failed_inference_retains_input_only(setup):
    db, repo, _, r = setup
    bot = Chatbot(repo, MockProvider(['{"product_id":"fake", "answer":"safe"}'] * 2))
    r = send(bot, r, 'unsafe model fixture')
    assert r.state == 'CLARIFYING'
    attempts = repo._all('SELECT status,result FROM msa.intake_extractions WHERE user_id=%s', (repo.owner,))
    assert attempts[0]['status'] == 'FAILED' and attempts[0]['result']['medications'] == []


def test_real_negation_uncertainty_and_handoff_preflight(setup, monkeypatch):
    from module1_intake.nlp.integration.handoff import identify_confirmed
    db, repo, _, r = setup
    text = 'Có lẽ không dùng A 500mg, dạng viên nén'
    med = Medication(name_raw='A', strength_raw='500mg', dosage_form_raw='viên nén', evidence_text=text)
    bot = Chatbot(repo, MockProvider([Understanding(medications=[med]).model_dump_json()]))
    r = send(bot, r, text)
    r = send(bot, r, 'xác nhận')
    assert r.handoff.entries[0].medication.negation_raw == 'không dùng'
    assert r.handoff.entries[0].medication.uncertainty_raw == 'Có lẽ'
    # This exercises only DTO preflight/negation filtering, never real identity inference.
    def forbidden(*a, **kw):
        pytest.fail('Negated exposure must not enter identification')
    monkeypatch.setattr('shared.db.identification_adapter.run_identification', forbidden)
    assert identify_confirmed(repo, r.handoff, dataset_build='0' * 64) == []
    bad = r.handoff.model_copy(update={'conversation_id': uuid4()})
    with pytest.raises(ValueError, match='conversation'):
        identify_confirmed(repo, bad, dataset_build='0' * 64)


def test_real_revising_one_drug_preserves_other_confirmations(setup):
    db, repo, bot, r = setup
    r = send(bot, r, 'Tôi đang uống A 500mg, dạng viên nén; đang dùng B 250mg, dạng viên nén')
    r = send(bot, r, 'xác nhận')
    unchanged = deepcopy(repo._owned('medication_entry_versions', r.handoff.entries[0].entry_version_id))
    r = bot.revise(r.workflow_id)
    r = send(bot, r, 'sửa thuốc 2 thành B 100mg')
    r = send(bot, r, 'xác nhận')
    assert [e.medication.strength_raw for e in r.handoff.entries] == ['500mg', '100mg']
    assert repo._owned('medication_entry_versions', unchanged['id']) == unchanged
