"""Small offline CLI checks; HTTP is mocked and no database is opened."""
import json
import subprocess
import sys

import httpx
import pytest

from module1_intake.nlp.__main__ import main
from module1_intake.nlp.interactive import run_extraction_test
from module1_intake.nlp.models import Administration, Intent, IntentCandidate, Medication, Understanding
from module1_intake.nlp.providers import OllamaProvider


def run_lines(provider, lines):
    inputs, output = iter(lines), []
    run_extraction_test(provider, read=lambda prompt: next(inputs), write=output.append)
    return output


def test_repeated_inputs_are_validated_independently_and_rendered():
    a = 'Tôi đang uống Panadol 500mg, mỗi sáng 1 viên. Bác sĩ kê 2 hộp.'
    b = 'Có lẽ tôi đang dùng Vitamin C.'
    values = iter([
        Understanding(intents=[IntentCandidate(intent=Intent.ADD_MEDICATION, evidence_text=a)], medications=[
            Medication(name_raw='Panadol', strength_raw='500mg', dose_raw='1 viên', quantity_raw='2 hộp',
                       administrations=[Administration(timing_raw='mỗi sáng', dose_raw='1 viên')], evidence_text=a)]),
        Understanding(medications=[Medication(name_raw='Vitamin C', evidence_text=b)]),
    ])
    calls = []
    def handler(request):
        payload = json.loads(request.content)
        calls.append(json.loads(payload['messages'][1]['content']))
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
                                       'message': {'content': next(values).model_dump_json()}})
    output = run_lines(OllamaProvider('test', transport=httpx.MockTransport(handler)), [a, b, '/exit'])
    assert calls == [{'text': a, 'context': {}}, {'text': b, 'context': {}}]
    first, second = [item for item in output if item.startswith('Validation:')]
    for expected in ('ADD_MEDICATION', 'name_raw: "Panadol"', 'strength_raw: "500mg"', 'dose_raw: "1 viên"',
                     'quantity_raw: "2 hộp"', 'timing_raw: "mỗi sáng"', 'Validation errors: none'):
        assert expected in first
    assert 'Missing/unreported data slots: dosage_form_raw' in first
    assert 'Panadol' not in second and '500mg' not in second
    assert 'strength_raw: null' in second and 'quantity_raw: null' in second
    assert 'Uncertain fields (reported/marked): name_raw' in second
    assert 'STATELESS NLP EXTRACTION TEST' in output[0]
    assert 'No dialogue, confirmation, persistence' in '\n'.join(output)
    assert output[-1] == 'Extraction test ended.'


def test_evidence_failure_is_safe_and_loop_continues():
    invalid = Understanding(medications=[Medication(name_raw='UNTRUSTED_MODEL_SENTINEL', evidence_text='Panadol')])
    good = Understanding(medications=[Medication(name_raw='Panadol', evidence_text='Panadol')])
    values = iter([invalid, invalid, good])
    def handler(request):
        return httpx.Response(200, json={'done': True, 'message': {'content': next(values).model_dump_json()}})
    output = '\n'.join(run_lines(OllamaProvider('test', transport=httpx.MockTransport(handler)),
                                 ['Panadol', 'Panadol', '/exit']))
    assert 'Extraction/validation: FAILED' in output
    assert 'Attempt 1: evidence' in output and 'Attempt 2: evidence' in output
    assert 'Source spans or medication slot roles failed' in output
    assert 'UNTRUSTED_MODEL_SENTINEL' not in output
    assert 'Validation: PASSED' in output


def test_http_failure_displays_category_and_status_without_body():
    provider = OllamaProvider('test', transport=httpx.MockTransport(lambda r: httpx.Response(404, text='PRIVATE_BODY')))
    output = '\n'.join(run_lines(provider, ['Panadol', '/exit']))
    assert 'http_status' in output and 'HTTP 404' in output
    assert 'PRIVATE_BODY' not in output


@pytest.mark.parametrize('stop', [EOFError, KeyboardInterrupt])
def test_empty_oversized_input_and_terminal_exit_do_not_call_provider(stop):
    def unexpected(request):
        pytest.fail('Input guards and terminal exit must not call Ollama')
    inputs = iter(['', 'x' * 12001])
    def read(prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise stop
    output = []
    run_extraction_test(OllamaProvider('test', transport=httpx.MockTransport(unexpected)), read=read, write=output.append)
    assert any('maximum 12000' in line for line in output)
    assert output[-1] == 'Extraction test ended.'


def test_control_characters_in_validated_source_are_escaped():
    text = 'Panadol\x1b[31m\nnext line'
    med = Medication(name_raw='Panadol', evidence_text=text)
    body = Understanding(medications=[med]).model_dump_json()
    provider = OllamaProvider('test', transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={'done': True, 'message': {'content': body}})))
    output = '\n'.join(run_lines(provider, [text, '/exit']))
    assert '\x1b' not in output and '\\u001b' in output and '\\nnext line' in output


def test_cli_extraction_path_needs_no_postgres_import_owner_or_dsn():
    # Fresh process catches eager imports in both __init__ and __main__ even if
    # other unit tests already imported the full database-backed chatbot.
    code = '''
import builtins, os
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'psycopg' or name.startswith('psycopg.') or name == 'shared.db' or name.startswith('shared.db.'):
        raise AssertionError('PostgreSQL stack imported')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
os.environ.pop('CORE_DB_DSN', None)
os.environ.pop('NLP_OLLAMA_MODEL', None)
from module1_intake.nlp.__main__ import main
from module1_intake.nlp import interactive
interactive.run_extraction_test = lambda provider: print(provider.model)
main(['--nlp-test'])
'''
    result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'qwen3.5:9b'


@pytest.mark.parametrize('extra', [['--provider', 'mock'], ['--owner', '00000000-0000-0000-0000-000000000001'],
                                 ['--workflow', '00000000-0000-0000-0000-000000000001'], ['--reference-build', 'synthetic']])
def test_extraction_mode_rejects_dialogue_options(extra):
    with pytest.raises(SystemExit) as caught:
        main(['--nlp-test', *extra])
    assert caught.value.code == 2


def test_persisted_cli_still_requires_owner(capsys):
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
    assert '--owner is required' in capsys.readouterr().err


def test_public_chatbot_export_still_works():
    from module1_intake.nlp import Chatbot
    from module1_intake.nlp.dialogue import Chatbot as Original
    assert Chatbot is Original
