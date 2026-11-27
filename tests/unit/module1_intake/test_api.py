import pytest

from module1_intake import api
from module1_intake.voice import ASRResult, VoiceInputError

from .synth import small_dataset


class FakeASR:
    def transcribe(self, audio, language):
        return ASRResult("augmentin sáng một viên", 0.9)


@pytest.fixture(autouse=True)
def _reset():
    yield
    api._suggester = None
    api.set_asr_engine(None)


def test_suggest_via_env_var_lazy_init(tmp_path, monkeypatch):
    small_dataset(tmp_path)
    monkeypatch.setenv("MEDICATION_DATA_DIR", str(tmp_path))
    api._suggester = None
    res = api.suggest_medication_names("augmen")          # tự khởi tạo ở lần gọi đầu
    assert res[0]["brand_name"] == "Augmentin 625mg"
    assert res[0]["active_ingredient"] == ["Amoxicillin", "Acid clavulanic"]
    assert api.suggest_medication_names("x") == []
    assert len(api.suggest_medication_names("am", limit=1)) == 1


def test_suggest_missing_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDICATION_DATA_DIR", str(tmp_path / "nope"))
    api._suggester = None
    from module1_intake.manual_input.dictionary import DictionaryError
    with pytest.raises(DictionaryError):
        api.suggest_medication_names("augmentin")


def test_transcribe_voice_with_injected_engine():
    api.set_asr_engine(FakeASR())
    assert api.transcribe_voice(b"abc") == {"raw_transcript": "augmentin sáng một viên", "confidence_score": 0.9}
    with pytest.raises(VoiceInputError) as e:
        api.transcribe_voice(b"")
    assert e.value.code == "INVALID_AUDIO"


def test_default_dictionary_path_is_independent_of_cwd(tmp_path, monkeypatch):
    seen = []
    monkeypatch.delenv('MEDICATION_DATA_DIR', raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, 'load_dictionary', lambda path: seen.append(path) or [])
    api.init_suggester()
    assert seen == [api.DEFAULT_MEDICATION_DATA_DIR]
    assert api.DEFAULT_MEDICATION_DATA_DIR.is_absolute()
    assert api.DEFAULT_MEDICATION_DATA_DIR.parts[-2:] == ('data', 'datasets')


def test_public_exports_use_the_common_api():
    import module1_intake
    assert module1_intake.suggest_medication_names is api.suggest_medication_names
    assert module1_intake.transcribe_voice is api.transcribe_voice


def test_parent_import_keeps_optional_dependencies_lazy():
    import os
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    code = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'rapidfuzz', 'faster_whisper', 'av', 'numpy'}:
        raise AssertionError('Optional dependency loaded eagerly: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import module1_intake.nlp.models
from module1_intake import suggest_medication_names, transcribe_voice
assert callable(suggest_medication_names) and callable(transcribe_voice)
'''
    result = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], cwd=root,
        env={**os.environ, 'PYTHONPATH': str(root / 'src')}, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
