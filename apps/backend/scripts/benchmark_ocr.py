"""Reproducible local OCR comparison; never uploads prescription images.

Manifest: [{"id": "case", "image": "path.png", "text": "optional transcription"}].
Run separately in each engine's environment with --engine tesseract or paddle.
CER is case/diacritic sensitive after NFC + whitespace normalization. Layout
cases without transcription are not scored. Outputs may contain private data.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import unicodedata
import hashlib
import importlib.metadata


def normalized(text):
    return ' '.join(unicodedata.normalize('NFC', text).split())


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        nxt = [i]
        for j, y in enumerate(b, 1):
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j-1] + (x != y)))
        row = nxt
    return row[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--engine', choices=['tesseract', 'paddle'], required=True)
    parser.add_argument('--paddle-detector', default='PP-OCRv5_mobile_det')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = json.loads(args.manifest.read_text(encoding='utf-8'))
    start = time.perf_counter()
    if args.engine == 'paddle':
        os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')
        from paddleocr import PaddleOCR, TextRecognition
        engine = PaddleOCR(text_detection_model_name=args.paddle_detector,
                          text_recognition_model_name='latin_PP-OCRv5_mobile_rec', device='cpu',
                          use_doc_orientation_classify=False, use_doc_unwarping=False,
                          use_textline_orientation=False, enable_mkldnn=False,
                          return_word_box=False, cpu_threads=2, text_recognition_batch_size=1,
                          text_det_limit_side_len=960, text_det_limit_type='max')
        line_engine = TextRecognition(model_name='latin_PP-OCRv5_mobile_rec',
                                      device='cpu', enable_mkldnn=False, cpu_threads=2)
    initialization = time.perf_counter() - start
    script = Path(__file__).resolve().parents[3] / 'src/module1_intake/ocr/node/local_ocr.cjs'
    report = []
    for case in cases:
        output = args.output / (case['id'] + '.json')
        start = time.perf_counter()
        if args.engine == 'paddle':
            recognizer = line_engine if case.get('text') is not None else engine
            results = list(recognizer.predict(case['image']))
            results[0].save_to_json(str(output))
            raw = json.loads(output.read_text(encoding='utf-8'))
            text = raw['rec_text'] if 'rec_text' in raw else '\n'.join(raw['rec_texts'])
        else:
            # A known line crop uses single-line mode; whole pages use auto layout.
            options = args.output / 'options.json'
            options.write_text(json.dumps({'psm': 7 if case.get('text') else 3}), encoding='utf-8')
            subprocess.run(['node', str(script), case['image'], str(output), str(options)],
                           check=True, capture_output=True, timeout=120)
            raw = json.loads(output.read_text(encoding='utf-8'))
            text = raw['text']
        elapsed = time.perf_counter() - start
        item = {'id': case['id'], 'seconds': elapsed, 'text': text}
        if case.get('text') is not None:
            truth, actual = normalized(case['text']), normalized(text)
            item.update(characters=len(truth), edits=distance(truth, actual),
                        exact=truth == actual, reference=truth)
        report.append(item)
        print(case['id'], round(elapsed, 3), 's', flush=True)
        (args.output / 'results.json').write_text(json.dumps({
            'engine': args.engine,
            'versions': {name: importlib.metadata.version(name) for name in ('paddleocr', 'paddlepaddle')} if args.engine == 'paddle' else {'tesseract.js': '6.0.1'},
            'paddle_detector': args.paddle_detector if args.engine == 'paddle' else None,
            'recognizer': 'latin_PP-OCRv5_mobile_rec' if args.engine == 'paddle' else 'vie+eng best_int',
            'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            'initialization_seconds': initialization,
            'timing_note': 'Paddle model initialization separate; Tesseract includes worker startup per call.',
            'cases': report,
            'character_error_rate': sum(r.get('edits', 0) for r in report) / max(1, sum(r.get('characters', 0) for r in report)),
        }, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
