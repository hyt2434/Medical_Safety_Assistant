"""Run the common public API on a checked-in speech sample (no NLP/DB writes)."""
import argparse
import os
from pathlib import Path

from ..api import set_asr_engine, transcribe_voice
from . import VoiceInputError, WhisperASR


DEFAULT_SAMPLE = Path(__file__).resolve().parents[3] / 'data/samples/voice/sample3.wav'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument('--language', default='en-US')
    parser.add_argument('--model', default=os.environ.get('WHISPER_MODEL_SIZE', 'small'))
    args = parser.parse_args(argv)
    set_asr_engine(WhisperASR(model_size=args.model, device='cpu', compute_type='int8'))
    try:
        result = transcribe_voice(args.audio.read_bytes(), language=args.language)
    except (OSError, VoiceInputError) as exc:
        parser.exit(1, f'{exc}\n')
    print(result)


if __name__ == '__main__':
    main()
