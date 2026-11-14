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
    from module1_intake.dictionary import DictionaryError
    with pytest.raises(DictionaryError):
        api.suggest_medication_names("augmentin")


def test_transcribe_voice_with_injected_engine():
    api.set_asr_engine(FakeASR())
    assert api.transcribe_voice(b"abc") == {"raw_transcript": "augmentin sáng một viên", "confidence_score": 0.9}
    with pytest.raises(VoiceInputError) as e:
        api.transcribe_voice(b"")
    assert e.value.code == "INVALID_AUDIO"
