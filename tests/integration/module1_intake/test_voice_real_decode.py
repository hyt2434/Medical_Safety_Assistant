"""Giải mã âm thanh thật bằng PyAV/faster-whisper (bỏ qua nếu chưa cài). Không cần tải model."""
import io
import math
import struct
import wave

import pytest

pytest.importorskip("faster_whisper")
av = pytest.importorskip("av")
np = pytest.importorskip("numpy")

from module1_intake.voice import VoiceInputError, WhisperASR  # noqa: E402


def wav(seconds, rate=16000, silent=False):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(
            struct.pack("<h", 0 if silent else int(0.3 * 32767 * math.sin(2 * math.pi * 220 * i / rate)))
            for i in range(int(seconds * rate))))
    return buf.getvalue()


def webm_opus(seconds, rate=48000):
    out = io.BytesIO()
    c = av.open(out, "w", format="webm")
    st = c.add_stream("libopus", rate=rate)
    st.layout = "mono"
    t = np.arange(int(seconds * rate)) / rate
    pcm = (0.3 * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16)[None, :]
    fr = av.AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
    fr.sample_rate = rate
    for pkt in st.encode(fr):
        c.mux(pkt)
    for pkt in st.encode(None):
        c.mux(pkt)
    c.close()
    return out.getvalue()


def code_of(data):
    with pytest.raises(VoiceInputError) as e:
        WhisperASR().transcribe(data, "vi-VN")  # các lỗi này xảy ra trước khi nạp model
    return e.value.code


def test_decode_resamples_to_16k():
    assert len(WhisperASR._decode(wav(2, rate=44100))) == 32000
    assert abs(len(WhisperASR._decode(webm_opus(2))) - 32000) < 1600   # WebM/Opus từ trình duyệt


def test_real_audio_errors():
    assert code_of(wav(31)) == "AUDIO_TOO_LONG"
    assert code_of(webm_opus(31)) == "AUDIO_TOO_LONG"
    assert code_of(wav(2, silent=True)) == "NO_SPEECH_DETECTED"
    assert code_of(b"not audio at all") == "INVALID_AUDIO"


def test_model_load_failure_is_asr_unavailable(monkeypatch):
    import faster_whisper

    def boom(*a, **k):
        raise RuntimeError("no network")
    monkeypatch.setattr(faster_whisper, "WhisperModel", boom)
    with pytest.raises(VoiceInputError) as e:
        WhisperASR().transcribe(wav(2), "vi-VN")
    assert e.value.code == "ASR_UNAVAILABLE"
