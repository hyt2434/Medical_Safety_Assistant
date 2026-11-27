import base64
import math
from types import SimpleNamespace as NS

import numpy as np
import pytest

from module1_intake.voice import (ASRResult, VoiceInputError, WhisperASR,
                                  confidence_from_segments, transcribe_voice, whisper_language)


class FakeASR:
    def __init__(self, text="augmentin sáng một viên", confidence=0.8):
        self.text, self.confidence, self.calls = text, confidence, []

    def transcribe(self, audio, language):
        self.calls.append((audio, language))
        return ASRResult(self.text, self.confidence)


def code_of(fn):
    with pytest.raises(VoiceInputError) as e:
        fn()
    return e.value.code


def test_bytes_and_base64():
    eng = FakeASR()
    out = transcribe_voice(b"abc", engine=eng)
    assert out == {"raw_transcript": "augmentin sáng một viên", "confidence_score": 0.8}
    transcribe_voice(base64.b64encode(b"abc").decode(), engine=eng)
    transcribe_voice("data:audio/webm;base64," + base64.b64encode(b"abc").decode(), engine=eng)
    assert [c[0] for c in eng.calls] == [b"abc"] * 3 and eng.calls[0][1] == "vi-VN"


def test_invalid_payloads():
    eng = FakeASR()
    assert code_of(lambda: transcribe_voice("###", engine=eng)) == "INVALID_AUDIO"
    assert code_of(lambda: transcribe_voice(b"", engine=eng)) == "INVALID_AUDIO"
    assert code_of(lambda: transcribe_voice(123, engine=eng)) == "INVALID_AUDIO"
    assert code_of(lambda: transcribe_voice(b"x", language="", engine=eng)) == "INVALID_AUDIO"
    assert eng.calls == []


def test_empty_transcript_is_no_speech():
    assert code_of(lambda: transcribe_voice(b"x", engine=FakeASR(text="  "))) == "NO_SPEECH_DETECTED"


def test_confidence_none_passthrough():
    assert transcribe_voice(b"x", engine=FakeASR(confidence=None))["confidence_score"] is None


def test_confidence_from_segments():
    segs = [NS(start=0, end=1, avg_logprob=math.log(0.9)), NS(start=1, end=4, avg_logprob=math.log(0.5))]
    c = confidence_from_segments(segs)
    assert 0.5 < c < 0.9 and c == round(math.exp((math.log(0.9) * 1 + math.log(0.5) * 3) / 4), 4)
    assert confidence_from_segments([NS(start=0, end=1, avg_logprob=0.5)]) == 1.0   # kẹp <= 1
    assert confidence_from_segments([]) is None


def test_whisper_language():
    assert whisper_language("vi-VN") == "vi" and whisper_language("EN") == "en"


class StubModel:
    def __init__(self, segs):
        self.segs, self.kwargs = segs, None

    def transcribe(self, samples, **kw):
        self.kwargs = kw
        return iter(self.segs), None


def make_asr(samples, segs, max_duration_s=30.0):
    asr = WhisperASR(model=StubModel(segs), max_duration_s=max_duration_s)
    asr._decode = lambda audio: samples
    return asr


def tone(seconds):
    t = np.arange(int(16000 * seconds)) / 16000
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_whisper_flow_ok():
    seg = NS(start=0, end=2, text=" Augmentin sáng ", avg_logprob=math.log(0.7))
    asr = make_asr(tone(2), [seg])
    r = asr.transcribe(b"x", "vi-VN")
    assert r.text == "Augmentin sáng" and r.confidence == 0.7
    assert asr._model.kwargs["language"] == "vi" and asr._model.kwargs["vad_filter"] is True


def test_whisper_too_long_silent_and_empty():
    assert code_of(lambda: make_asr(tone(31), []).transcribe(b"x", "vi-VN")) == "AUDIO_TOO_LONG"
    assert code_of(lambda: make_asr(np.zeros(16000, np.float32), []).transcribe(b"x", "vi-VN")) == "NO_SPEECH_DETECTED"
    assert code_of(lambda: make_asr(tone(1), []).transcribe(b"x", "vi-VN")) == "NO_SPEECH_DETECTED"
    assert code_of(lambda: make_asr(tone(1), [NS(start=0, end=1, text=" ", avg_logprob=-1)]).transcribe(b"x", "vi-VN")) == "NO_SPEECH_DETECTED"


def test_whisper_decode_failure_is_invalid_audio():
    asr = WhisperASR(model=StubModel([]))

    def boom(audio):
        raise RuntimeError("corrupt")
    asr._decode = boom
    assert code_of(lambda: asr.transcribe(b"x", "vi-VN")) == "INVALID_AUDIO"


@pytest.mark.parametrize('lazy', [False, True])
def test_inference_and_lazy_segment_failures_are_retryable(lazy):
    class BrokenModel:
        def transcribe(self, *args, **kwargs):
            def broken_segments():
                raise RuntimeError('test decoder or inference failure')
                yield
            if lazy:
                return broken_segments(), None
            raise RuntimeError('test inference failure')
    asr = WhisperASR(model=BrokenModel())
    asr._decode = lambda _: tone(1)
    assert code_of(lambda: asr.transcribe(b'audio', 'vi-VN')) == 'ASR_UNAVAILABLE'
