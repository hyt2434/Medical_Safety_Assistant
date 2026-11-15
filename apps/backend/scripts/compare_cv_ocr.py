"""Local OpenCV experiments. Keeps original input and saves separate outputs.

Run from repository root; no prescription images are sent to external services.
"""

import argparse
import json
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np


def deskew(gray):
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 1800, 40,
                            minLineLength=gray.shape[1] // 8, maxLineGap=15)
    angles = []
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            angle = float(np.degrees(np.arctan2(y2-y1, x2-x1)))
            if abs(angle) < 8:
                angles.append(angle)
    angle = float(np.median(angles)) if len(angles) >= 5 else 0.0
    matrix = cv2.getRotationMatrix2D((gray.shape[1]/2, gray.shape[0]/2), angle, 1)
    rotated = cv2.warpAffine(gray, matrix, (gray.shape[1], gray.shape[0]),
                             flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                             borderValue=255)
    return rotated, angle


def variants(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    yield 'upscale_gray', enlarged, {}
    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(enlarged)
    yield 'upscale_clahe', clahe, {}
    background = cv2.GaussianBlur(enlarged, (0, 0), 25)
    normalized = cv2.divide(enlarged, background, scale=255)
    yield 'illumination_normalized', normalized, {}
    yield 'adaptive_threshold', cv2.adaptiveThreshold(
        normalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15), {}
    rotated, angle = deskew(enlarged)
    yield 'upscale_deskew', rotated, {'rotation_degrees': angle}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    image = cv2.imdecode(np.fromfile(args.image, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Cannot decode input image')
    args.output.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parents[1] / 'src/module1_intake/ocr/node/local_ocr.cjs'
    report = []
    # Preserve the exact input encoding for the baseline.
    for name, processed, metadata in [('original', None, {}), *variants(image)]:
        path = args.image.resolve()
        if processed is not None:
            path = (args.output / f'{name}.png').resolve()
            cv2.imencode('.png', processed)[1].tofile(path)
        evidence = (args.output / f'{name}.json').resolve()
        started = time.perf_counter()
        subprocess.run(['node', str(script), str(path), str(evidence)], check=True, timeout=180)
        raw = json.loads(evidence.read_text(encoding='utf-8'))
        (args.output / f'{name}.txt').write_text(raw['text'], encoding='utf-8')
        result = {'variant': name, 'confidence': raw['confidence'],
                  'seconds': round(time.perf_counter()-started, 3),
                  'image': str(path), **metadata}
        report.append(result)
        print(json.dumps(result), flush=True)
    (args.output / 'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
