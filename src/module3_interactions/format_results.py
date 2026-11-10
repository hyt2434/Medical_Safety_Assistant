"""Read-only terminal presentation of actual Module 3 and E2E results.

No engine, OCR, model, product-reference, network, or ground-truth imports.
The same formatter accepts runtime objects and saved JSON artifacts.
"""
import argparse
import json
import os
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import re
import sys

DEFAULT_RUNS = PROJECT_ROOT / 'data/reference/provenance/real_medication_e2e/runs'


def _text(value, missing='CHƯA XÁC ĐỊNH'):
    if value is None or value == '':
        return missing
    # Keep names/strengths readable; source fields cannot inject terminal controls.
    return re.sub(r'[\x00-\x1f\x7f]', ' ', str(value)).strip()


def _color_enabled(mode, stream):
    if mode == 'never' or 'NO_COLOR' in os.environ:
        return False
    if mode == 'always':
        return True
    if not stream.isatty() or os.environ.get('TERM') == 'dumb':
        return False
    if os.name == 'nt':
        return bool(os.environ.get('WT_SESSION') or os.environ.get('ANSICON') or
                    os.environ.get('TERM_PROGRAM') == 'vscode' or os.environ.get('TERM'))
    return True


def format_case_summary(case, module1, module2, module3, confirmation=None, *, color=False):
    """Return presentation lines; never modify or re-evaluate source results."""
    def paint(text, shade):
        return f'\033[{shade}m{text}\033[0m' if color else text

    extraction = module1.get('actual_output') or {}
    identities = module2.get('actual_output') or []
    assessment = module3.get('actual_output') or {}
    lines = [f'=== {_text(case.get("id"))} ===', '', 'Thuốc (tên và hàm lượng gốc):']
    medications = extraction.get('medications', [])
    for number, medication in enumerate(medications, 1):
        lines.append(f'{number}. {_text(medication.get("name_raw"))} | Hàm lượng: {_text(medication.get("strength_raw"))}')
    if not medications:
        lines.append('Chưa có kết quả trích xuất thuốc.')
    lines.extend(['', 'Hoạt chất đã nhận diện:'])
    components = [component for identity in identities for component in identity.get('ingredients', [])]
    for component in components:
        original = _text(component.get('normalized_ingredient') or component.get('original_ingredient'))
        generic = component.get('ddinter_generic_name')
        name = f'{original} -> {_text(generic)}' if generic and original.casefold() != str(generic).casefold() else original
        identifier = component.get('ddinter_id')
        status = component.get('mapping_status')
        label = f'{name} ({_text(identifier)})' if status == 'VERIFIED' and identifier else f'{name} — CHƯA ÁNH XẠ ĐƯỢC'
        lines.append('- ' + (paint(label, '33') if status != 'VERIFIED' else label))
    if not components:
        lines.append('Chưa có kết quả nhận diện hoạt chất.')

    interactions = assessment.get('matched_interactions', [])
    for interaction in interactions:
        severity = interaction.get('original_level')
        contexts = interaction.get('contexts') or []
        records = interaction.get('source_records') or []
        if contexts:
            names = [_text(contexts[0][side].get('ingredient_name')) for side in ('left', 'right')]
        elif records:
            row = records[0].get('raw_source_row') or {}
            names = [_text(row.get('Drug_A')), _text(row.get('Drug_B'))]
        else:
            names = [_text(identifier) for identifier in interaction.get('drug_id_pair', [])]
        pair_name = ' và '.join(names) or 'cặp hoạt chất chưa rõ'
        shade = '31' if severity == 'Major' else '33'
        lines.extend(['', paint('[WARNING] PHÁT HIỆN TƯƠNG TÁC THUỐC', shade),
                      paint(f'Severity (DDInter): {_text(severity).upper()}', shade),
                      f'Mô tả: DDInter 2.0 ghi nhận tương tác mức {_text(severity)} giữa {pair_name}.',
                      'Nguồn CSV đã tải chỉ xác nhận cặp thuốc và mức độ; chưa có mô tả cơ chế được xác minh.'])
        evidence = []
        for record in records:
            source = record.get('evidence') or {}
            if source.get('filename') and source.get('csv_record_1_based'):
                evidence.append(f'{_text(source["filename"])} #{source["csv_record_1_based"]}')
        lines.append('Bằng chứng: ' + ' + '.join(map(_text, interaction.get('drug_id_pair', []))) +
                     (' | ' + '; '.join(dict.fromkeys(evidence)) if evidence else ' | CHƯA CÓ NGUỒN'))

    if assessment.get('conflicting_source_pairs'):
        lines.extend(['', paint('[CAUTION] NGUỒN TƯƠNG TÁC CÓ MỨC ĐỘ MÂU THUẪN; CẦN XEM XÉT.', '33')])
    if assessment.get('unresolved_mappings') or assessment.get('unassessed_ingredient_pairs'):
        lines.extend(['', paint('[CAUTION] CÒN HOẠT CHẤT HOẶC CẶP THUỐC CHƯA ĐƯỢC ĐÁNH GIÁ.', '33')])
    if not interactions:
        finding = 'Chưa có kết quả Module 3.' if not assessment else 'Chưa có tương tác được xác nhận trong kết quả này; không thể kết luận an toàn.'
        lines.extend(['', paint('[CAUTION] ' + finding, '33')])
    if assessment and not assessment.get('completeness', {}).get('dataset_coverage_complete', False):
        lines.append(paint('Phạm vi DDInter: GIỚI HẠN; không xác nhận đầy đủ an toàn.', '33'))
    if assessment.get('duplicate_ingredients'):
        lines.append(paint('[CAUTION] CÓ HOẠT CHẤT TRÙNG LẶP; CẦN HCP XEM XÉT.', '33'))

    lines.extend(['', 'Hành động tiếp theo:', 'Cần bác sĩ hoặc dược sĩ xem xét.',
                  'Không tự ý thay đổi hoặc ngừng thuốc.'])
    hcp = assessment.get('requires_hcp_review')
    lines.append('HCP Review: ' + ('REQUIRED' if hcp is True else 'NOT RECORDED' if hcp is None else 'NOT REQUIRED IN SOURCE OUTPUT'))
    safe = assessment.get('safe_to_take')
    lines.append('Safety Conclusion: ' + ('NOT DETERMINED' if safe is None else 'SOURCE SAFETY FLAG REQUIRES REVIEW'))
    if safe is not None:
        lines.append(paint(f'[CAUTION] Cờ safe_to_take trong nguồn: {_text(safe)}; không phải kết luận lâm sàng.', '33'))
    confirmation = confirmation or {}
    if confirmation.get('simulated') or confirmation.get('label') == 'SIMULATED CONFIRMATION':
        boundary = 'SIMULATED CONFIRMATION'
    elif confirmation.get('real_ui_confirmation') is True:
        boundary = 'REAL UI CONFIRMATION (source-recorded)'
    else:
        boundary = 'NOT RECORDED'
    lines.extend([f'Confirmation: {boundary}', f'Provider: {_text(case.get("provider") or module1.get("provider"))}',
                  'Modules: ' + ' | '.join(f'M{number}={_text(module.get("status"))}' for number,module in enumerate((module1,module2,module3),1))])
    reasons = case.get('root_causes') or [module['reason'] for module in (module1,module2,module3) if module.get('reason')]
    if reasons:
        lines.append('Lý do: ' + '; '.join(map(_text, reasons)))
    status = _text(case.get('e2e'), 'BLOCKED')
    lines.extend(['', paint(f'E2E RESULT: {status} — kết quả kiểm thử, chưa xác nhận an toàn lâm sàng.',
                           '32' if status == 'PASS' else '31' if status == 'FAIL' else '33'), ''])
    return lines


def _read(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def latest_successful_run(runs):
    """Select newest saved successful run, without executing any pipeline stage."""
    candidates = []
    for path in Path(runs).glob('*/results.json'):
        try:
            result = _read(path)
            cases = result.get('cases') or []
            if result.get('overall') == 'PASS' and cases and all(
                    case.get('e2e') == 'PASS' and all(case.get(stage) == 'PASS' for stage in ('module1','module2','module3'))
                    for case in cases):
                candidates.append(path)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    if not candidates:
        raise ValueError('No saved successful E2E run found; use --run for a saved failed/blocked run')
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path))).parent


def saved_case_inputs(run, case):
    identifier = case.get('id', '')
    if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
        raise ValueError('Invalid case identifier in saved result')
    modules = [_read(Path(run) / f'{identifier}_module{number}.json') for number in (1,2,3)]
    for number, module in enumerate(modules,1):
        if module.get('status') != case.get(f'module{number}'):
            raise ValueError(f'{identifier}: inconsistent saved stage status')
        if module.get('status') == 'PASS' and module.get('actual_output') is None:
            raise ValueError(f'{identifier}: PASS without actual stage output')
    if case.get('e2e') == 'PASS' and any(module.get('status') != 'PASS' for module in modules):
        raise ValueError(f'{identifier}: inconsistent E2E PASS')
    path = Path(run) / f'{identifier}_confirmation.json'
    return (*modules, _read(path) if path.exists() else {})


def display_saved_run(run, *, stream=None, color='auto'):
    stream = stream or sys.stdout
    run = Path(run).resolve()
    result = _read(run / 'results.json')
    prepared = [(case, saved_case_inputs(run, case)) for case in result['cases']]
    enabled = _color_enabled(color, stream)
    print(f'MEDICATION SAFETY ASSISTANT | saved run: {run.name}', file=stream)
    print('Chỉ hiển thị JSON đã lưu; không chạy Gemini, OCR, Module 2 hoặc Module 3.\n', file=stream)
    for case, inputs in prepared:
        print('\n'.join(format_case_summary(case, *inputs, color=enabled)), file=stream)
    print(f'Chi tiết JSON và terminal.log: {run}', file=stream)
    print(f'Thời gian E2E đã ghi nhận: {_text(result.get("execution_seconds"))} giây.', file=stream)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, help='Saved run directory; default: latest successful run')
    parser.add_argument('--runs', type=Path, default=DEFAULT_RUNS, help='Parent directory used for latest-run selection')
    parser.add_argument('--color', choices=['auto','always','never'], default='auto')
    args = parser.parse_args()
    try:
        display_saved_run(args.run or latest_successful_run(args.runs), color=args.color)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # No JSON payload or exception body: only a safe error category and guidance.
        parser.exit(2, f'Cannot display saved results ({type(exc).__name__}). Check --run and its module JSON files.\n')


if __name__ == '__main__':
    main()
