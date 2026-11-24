"""Compare local OCR rectangles without replacing the full-page evidence.

Usage: python apps/backend/scripts/test_ocr_regions.py IMAGE REGIONS_JSON OUTPUT_DIR
REGIONS_JSON maps region names to {left, top, width, height} in input pixels.
"""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('regions', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parents[1] / 'src/module1_intake/ocr/node/local_ocr.cjs'
    results = []
    for index, (name, rectangle) in enumerate(json.loads(args.regions.read_text(encoding='utf-8')).items()):
        for psm in (6, 7):
            stem = f'region-{index}-psm-{psm}'
            config = args.output / f'{stem}-options.json'
            evidence = args.output / f'{stem}.json'
            config.write_text(json.dumps({'psm': psm, 'rectangle': rectangle}), encoding='utf-8')
            subprocess.run(['node', str(script), str(args.image), str(evidence), str(config)], check=True, timeout=180)
            raw = json.loads(evidence.read_text(encoding='utf-8'))
            results.append({'region': name, 'psm': psm, 'rectangle': rectangle,
                            'text': raw['text'], 'confidence': raw['confidence'],
                            'duration_seconds': raw['duration_seconds']})
    (args.output / 'comparison.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
