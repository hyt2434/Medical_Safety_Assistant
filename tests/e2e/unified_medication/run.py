"""Actual image -> existing OCR -> main unified Module 2 -> official Module 3.

Ground truth is read only by evaluation; it never supplies downstream identities.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import shutil
import sys
import time
import unicodedata

HERE = Path(__file__).resolve().parent
ROOT = PROJECT_ROOT
PROJECT = PROJECT_ROOT
LEGACY = PROJECT_ROOT/'data/reference/provenance/real_medication_e2e'
from module1_intake.ocr.local import local_ocr
from module2_medications.unified import UnifiedMedicationReference, default_config
from module2_medications.service import from_module1
from module3_interactions.engine import assess


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def norm(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).casefold().split())
def strength(value): return norm(value).replace(' ', '')


class Log:
    def __init__(self, path): self.stream = path.open('w', encoding='utf-8', buffering=1)
    def log(self, value):
        print(value, flush=True)
        self.stream.write(value+'\n')


def extraction_checks(case, extraction):
    actual = (extraction or {}).get('medications', [])
    checks = [{'check':'medication_count','pass':len(actual)==len(case['medications'])}]
    for i, wanted in enumerate(case['medications']):
        found = actual[i] if i < len(actual) else {}
        for field in ('name_raw','strength_raw','dosage_form_raw'):
            normalize = strength if field == 'strength_raw' else norm
            value = found.get(field)
            okay = normalize(value)==normalize(wanted.get(field))
            # Legacy Module 1 preserves form in literal evidence, without a dedicated field.
            if field=='dosage_form_raw' and not value and wanted.get(field):
                okay = norm(wanted[field]) in norm(found.get('evidence_text'))
            checks.append({'medication_index':i,'check':field,'expected':wanted.get(field),'actual':value,'pass':okay})
        allowed = {'strength_raw'} if wanted.get('strength_raw') is None else set()
        checks.append({'medication_index':i,'check':'uncertainty','actual':found.get('uncertain_fields'),
                       'pass':not(set(found.get('uncertain_fields',[]))-allowed)})
        checks.append({'medication_index':i,'check':'no_invented_administration','pass':
            not found.get('administrations') and all(found.get(f) is None for f in
                ('dose_raw','route_raw','frequency_raw','duration_raw','quantity_raw','instructions_raw'))})
    return checks


def evaluate_m2(case, identities):
    checks = []
    for wanted, found in zip(case['medications'], identities):
        candidate = found['identified_candidate']
        code = (candidate or {}).get('product',{}).get('source_product_code')
        expected = wanted['expected']
        if expected['identity']=='VERIFIED':
            product_ok = found['identification_status']=='VERIFIED' and code in expected['source_product_codes']
        else:
            product_ok = found['identification_status'] == expected['identity'] and not found['ready_for_identifier_handoff']
        expected_ids = expected['ddinter_ids']
        mapping_ok = sorted(found['verified_ddinter_ids'])==sorted(set(x for x in expected_ids if x))
        ready_ok = found['ready_for_identifier_handoff']==expected['ready']
        ingredient_ok = (not expected.get('ingredients_raw') or
            [x['original_ingredient'] for x in found['ingredients']]==expected['ingredients_raw'])
        checks.append({'product_pass':product_ok,'mapping_pass':mapping_ok,'readiness_pass':ready_ok,
            'ingredient_pass':ingredient_ok,'expected':expected,'actual_code':code,
            'actual_identity':found['identification_status'],'actual_ids':found['verified_ddinter_ids'],
            'pass':product_ok and mapping_ok and ready_ok and ingredient_ok})
    return checks


def evaluate_m3(case, result, identities):
    expected = case['expected_pairs']
    actual = {tuple(p['drug_id_pair']):p for p in result['checked_ingredient_pairs']}
    pair_checks = []
    for pair in expected:
        found = actual.get(tuple(pair['ids']))
        pair_checks.append({'ids':pair['ids'],'expected_status':pair['status'],'expected_levels':pair['levels'],
            'actual_status':found.get('status') if found else None,
            'pass':bool(found) and found['status']==pair['status'] and
                sorted(found.get('original_levels',[]))==pair['levels']})
    wanted_unresolved = sum(not m['expected']['ready'] for m in case['medications'])
    duplicates = sorted(x['ddinter_id'] for x in result['duplicate_ingredients'])
    safety = result['safe_to_take'] is None and result['no_interactions'] is None and result['requires_hcp_review'] is True
    safety &= result['autonomous_prescribing'] is False and result['automated_schedule_optimization'] is False
    safety &= all(a['hcp_review_required'] and not a['autonomous_medication_changes'] for a in result['review_alerts'])
    safety &= all(a['display_timing']=='IMMEDIATE' and not a['wait_for_hcp_before_display'] and a['routing_priority']=='PROMPT'
                  for a in result['review_alerts'] if 'Major' in a['original_source_levels'])
    return {'pairs':pair_checks,'no_extra_pairs':set(actual)=={tuple(p['ids']) for p in expected},
        'duplicates_pass':duplicates==case['expected_duplicate_ids'],
        'unresolved_pass':bool(result['unresolved_mappings'])==bool(wanted_unresolved),
        'handoff_unchanged':result['input_medications']==[x['module3_input'] for x in identities],
        'safety_pass':bool(safety)}


def warnings_vi(result):
    if result is None: return ['Chưa xác nhận bản chép thuốc. Cần kiểm tra lại ảnh; chưa thể đánh giá tương tác.']
    messages = []
    for pair in result['matched_interactions']:
        messages.append(f"DDInter ghi nhận {pair['original_level']}: {' + '.join(pair['drug_id_pair'])}. Cần bác sĩ/dược sĩ xem xét; không tự đổi thuốc.")
    if result['duplicate_ingredients']: messages.append('Có hoạt chất trùng lặp. Cần bác sĩ/dược sĩ kiểm tra.')
    if result['unresolved_mappings']: messages.append('Chưa xác định đầy đủ thuốc/hoạt chất. Không thể kết luận an toàn; cần bác sĩ/dược sĩ kiểm tra.')
    if any(x['status']=='NO_RECORD_IN_LOADED_SUBSET' for x in result['checked_ingredient_pairs']):
        messages.append('Không có bản ghi trong dữ liệu đã nạp. Không có nghĩa là an toàn; cần bác sĩ/dược sĩ xem xét.')
    return messages or ['Dữ liệu có giới hạn. Cần bác sĩ/dược sĩ xem xét; chưa thể kết luận an toàn.']


def protected_inputs(config):
    paths = [Path(config['database']), Path(config['ddinter_index'])]
    paths += [p for p in LEGACY.rglob('*') if p.is_file() and 'tools' not in p.parts and p.name!='fix_integration.py']
    return {str(p):sha(p) for p in paths}


def run(truth_path, output, config_path=None):
    output.mkdir(parents=True, exist_ok=False)
    log = Log(output/'terminal.log')
    start = time.perf_counter()
    truth = read(truth_path)
    write(output/'ground_truth.json', truth)
    config_path = config_path or default_config(PROJECT)
    config = read(config_path)
    protected = protected_inputs(config)
    write(output/'protected_inputs.json',protected)
    snapshot=output/'executed_code'; snapshot.mkdir()
    code_paths=[Path(__file__),PROJECT/'src/module1_intake/ocr/local.py',PROJECT/'src/module1_intake/ocr/local_ocr_rows.py',PROJECT/'src/module2_medications/service.py',PROJECT/'src/module2_medications/unified.py',PROJECT/'src/module3_interactions/engine.py']
    for p in code_paths: shutil.copy2(p,snapshot/p.name)
    write(output/'executed_code_hashes.json',{str(p):sha(p) for p in code_paths})
    log.log('Using unified SQLite via main Module 2; actual local OCR; SIMULATED CONFIRMATION; official DDInter 2.0.')
    reference = UnifiedMedicationReference(config_path)
    terminology = reference.terminology()
    cases = []
    try:
        for case in truth['cases']:
            cid = case['id']; tick = time.perf_counter()
            log.log(f"\n[{cid}] {case['group']} | {case['title']} | layout={case.get('layout','legacy')}")
            if sha(case['image_path'])!=case['image_sha256']: raise ValueError('Image hash mismatch: '+cid)
            checks=[]; extraction=None; metadata=None; error=None
            m1_start=time.perf_counter()
            try:
                extraction,metadata=local_ocr(case['image_path'],output,cid,log)
                checks=extraction_checks(case,extraction)
                # Correct transcription and confidence-based confirmation are
                # distinct outcomes. Do not erase uncertainty to force a handoff.
                s1='PASS' if all(x['pass'] for x in checks if x['check']!='uncertainty') else 'FAIL'
            except Exception as exc:
                s1='BLOCKED'; error=f'{type(exc).__name__}: {exc}'
            m1={'status':s1,'executed':extraction is not None,'actual_output':extraction,'metadata':metadata,
                'expected_vs_actual':checks,'error':error,'duration_seconds':round(time.perf_counter()-m1_start,3)}
            write(output/f'{cid}_module1.json',m1)
            log.log('  Extracted: '+json.dumps([{'name':m['name_raw'],'strength':m['strength_raw'],'form':m.get('dosage_form_raw'),
                'uncertain':m['uncertain_fields']} for m in (extraction or {}).get('medications',[])],ensure_ascii=False))
            confirmed=s1=='PASS' and all(x['pass'] for x in checks)
            write(output/f'{cid}_confirmation.json',{'status':'PASS' if confirmed else 'BLOCKED','label':'SIMULATED CONFIRMATION',
                'actual_output_modified':False,'confirmed':confirmed,'real_ui_confirmation':False,'truth_sha256':sha(truth_path)})
            m2={'status':'BLOCKED','executed':False,'actual_output':None,'reason':'TRANSCRIPTION_CONFIRMATION_BLOCKED'}
            m3={'status':'BLOCKED','executed':False,'actual_output':None,'reason':'NO_ACTUAL_UPSTREAM_HANDOFF'}
            identities=None; assessment=None; causes=[]
            if s1=='FAIL':
                if not checks[0]['pass'] or any(not c['pass'] and c['check']=='dosage_form_raw' for c in checks):
                    causes.append('OCR or image-layout errors')
                if any(not c['pass'] and c['check'] in ('name_raw','strength_raw') for c in checks):
                    causes.append('Incorrect extraction of names or strengths')
            if s1=='PASS' and not confirmed: causes.append('OCR confidence review gate (correct literal transcription)')
            if s1=='BLOCKED': causes.append('OCR backend unavailable')
            if confirmed:
                step=time.perf_counter()
                try:
                    identities=from_module1(extraction,reference,terminology,prescription_id=cid,confirmed=True)
                    comparisons=evaluate_m2(case,identities)
                    s2='PASS' if len(identities)==len(case['medications']) and all(c['pass'] for c in comparisons) else 'FAIL'
                    m2={'status':s2,'executed':True,'actual_output':identities,'expected_vs_actual':comparisons,
                        'reference_kind':'unified_research_reference','duration_seconds':round(time.perf_counter()-step,3)}
                    for c in comparisons:
                        if not c['product_pass']: causes.append('Product lookup failures')
                        if not c['ingredient_pass']: causes.append('Ingredient parsing or normalization failures')
                        if not c['mapping_pass'] or not c['readiness_pass']: causes.append('Missing DDInter identities or mapping mismatch')
                    step=time.perf_counter()
                    assessment=assess([x['module3_input'] for x in identities],terminology.dataset)
                    checks3=evaluate_m3(case,assessment,identities)
                    okay=all(x['pass'] for x in checks3['pairs']) and all(v for k,v in checks3.items() if k!='pairs')
                    m3={'status':'PASS' if okay else 'FAIL','executed':True,'actual_output':assessment,'checks':checks3,
                        'duration_seconds':round(time.perf_counter()-step,3)}
                    if not okay: causes.append('Module integration errors or interaction mismatch')
                except Exception as exc:
                    causes.append('Module integration errors')
                    target=m2 if identities is None else m3
                    target.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
            write(output/f'{cid}_module2.json',m2); write(output/f'{cid}_module3.json',m3)
            for identity in identities or []:
                log.log('  Ingredients / DDInter: '+json.dumps([(x['original_ingredient'],x['ddinter_id'],x['mapping_status']) for x in identity['ingredients']],ensure_ascii=False)+
                    f" | identity={identity['identification_status']} | ready={identity['ready_for_identifier_handoff']}")
            warning=warnings_vi(assessment)
            for message in warning: log.log('  '+message)
            statuses=[s1,m2['status'],m3['status']]
            overall='FAIL' if 'FAIL' in statuses else 'BLOCKED' if 'BLOCKED' in statuses else 'PASS'
            summary={'id':cid,'group':case['group'],'module1':s1,'module2':m2['status'],'module3':m3['status'],
                'e2e':overall,'duration_seconds':round(time.perf_counter()-tick,3),'failure_categories':sorted(set(causes)),
                'warnings_vi':warning,'expected_uncertainty':any(not x['expected']['ready'] for x in case['medications'])}
            cases.append(summary)
            log.log(f"  Module 1={s1} | Module 2={m2['status']} | Module 3={m3['status']} | E2E={overall} | {summary['duration_seconds']}s")
            write(output/'partial_results.json',cases)
    finally:
        reference.close()
        if hasattr(terminology.dataset,'close'): terminology.dataset.close()
    changes=[p for p, digest in protected.items() if sha(p)!=digest]
    metrics=metrics_for(truth,cases,output)
    result={'schema_version':'unified.image_e2e.v1','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'cases':cases,'counts':dict(Counter(c['e2e'] for c in cases)), 'metrics':metrics,
        'failure_categories':dict(Counter(f for c in cases for f in c['failure_categories'])),
        'protected_input_changes':changes,'truth_sha256':sha(truth_path),'config_sha256':sha(config_path),
        'execution_seconds':round(time.perf_counter()-start,3),'clinical_validation':False,'simulated_confirmation':True}
    write(output/'results.json',result)
    log.log('\nFULL E2E TEST SUMMARY')
    log.log(f"Total cases: {len(cases)}\nPASS: {result['counts'].get('PASS',0)}\nFAIL: {result['counts'].get('FAIL',0)}\nBLOCKED: {result['counts'].get('BLOCKED',0)}")
    for name,value in metrics.items(): log.log(f'{name}: {value}')
    log.log('Most common failures: '+str(result['failure_categories']))
    log.log(f'Protected input changes: {len(changes)}; results: {output}')
    report(result,output)
    log.stream.close()
    return result


def ratio(n,d): return {'numerator':n,'denominator':d,'percent':round(100*n/d,2) if d else None}


def metrics_for(truth,cases,output):
    ocr_ok=0; ocr_n=0; products_ok=0; products_n=0; mapping_ok=0; mapping_n=0
    known_n=0; known_ok=0; evaluated_known=0; expected_pairs=0; checked_pairs=0; false_positives=0
    uncertainty_n=0; uncertainty_ok=0; missing_n=0; missing_ok=0
    reached_products=0; reached_ingredients=0; uncertainty_executed=0
    for case in truth['cases']:
        cid=case['id']; m1=read(output/f'{cid}_module1.json'); m2=read(output/f'{cid}_module2.json'); m3=read(output/f'{cid}_module3.json')
        checks=m1['expected_vs_actual']
        for i,wanted in enumerate(case['medications']):
            ocr_n+=1
            relevant=[c for c in checks if c.get('medication_index')==i and c['check'] in ('name_raw','strength_raw','dosage_form_raw')]
            ocr_ok+=len(relevant)==3 and all(c['pass'] for c in relevant) and checks[0]['pass']
            e=wanted['expected']
            if e['identity']=='VERIFIED':
                products_n+=1
                mapping_n+=len(e['ddinter_ids'])
                if m2['executed']:
                    reached_products+=1; reached_ingredients+=len(e['ddinter_ids'])
                    comparison=m2['expected_vs_actual'][i]
                    products_ok+=comparison['product_pass']
                    ids=m2['actual_output'][i]['verified_ddinter_ids']
                    mapping_ok+=sum(x is not None and x in ids and comparison['product_pass'] for x in e['ddinter_ids'])
            else:
                uncertainty_n+=1
                if m2['executed']:
                    uncertainty_executed+=1
                    uncertainty_ok+=m2['expected_vs_actual'][i]['pass']
        expected_keys={tuple(p['ids']) for p in case['expected_pairs'] if p['status']=='INTERACTION_DETECTED'}
        actual_keys={tuple(p['drug_id_pair']) for p in (m3['actual_output'] or {}).get('matched_interactions',[])}
        false_positives+=len(actual_keys-expected_keys)
        for pair in case['expected_pairs']:
            expected_pairs+=1
            evaluated=next((p for p in m3.get('checks',{}).get('pairs',[]) if p['ids']==pair['ids']),None)
            checked_pairs+=bool(evaluated and evaluated['actual_status'])
            if pair['status']=='INTERACTION_DETECTED':
                known_n+=1; known_ok+=bool(evaluated and evaluated['pass']); evaluated_known+=bool(evaluated and evaluated['actual_status'])
            if pair['status']=='NO_RECORD_IN_LOADED_SUBSET':
                missing_n+=1; missing_ok+=bool(evaluated and evaluated['pass'])
    return {'OCR extraction accuracy (exact name+strength+form per medication, all cases)':ratio(ocr_ok,ocr_n),
        'Medication identification accuracy (expected resolvable products, all cases)':ratio(products_ok,products_n),
        'DDInter mapping coverage (all ingredient occurrences of expected resolvable products)':ratio(mapping_ok,mapping_n),
        'Medication identification accuracy (products actually reaching Module 2)':ratio(products_ok,reached_products),
        'DDInter mapping coverage (ingredient occurrences actually reaching Module 2)':ratio(mapping_ok,reached_ingredients),
        'Known interaction detection (unique pair per case, all cases; source level must match)':ratio(known_ok,known_n),
        'Known interaction detection (pairs actually reaching Module 3)':ratio(known_ok,evaluated_known),
        'Known interaction pairs reached Module 3':ratio(evaluated_known,known_n),
        'Expected ingredient pairs reached Module 3':ratio(checked_pairs,expected_pairs),
        'Unexpected positive pair detections':false_positives,
        'Expected unresolved product handling (all cases)':ratio(uncertainty_ok,uncertainty_n),
        'Missing interaction record handling (all cases)':ratio(missing_ok,missing_n)}


def report(result,output):
    lines=['# Unified image E2E results','',f"Actual cases: {len(result['cases'])}; {result['counts']}. Execution: {result['execution_seconds']}s.",'',
        'Actual local Tesseract.js OCR -> simulated confirmation -> main unified Module 2 service -> official DDInter Module 3. Ground truth was established before predictions using retained product shards and direct read-only official SQL. It shares the retained evidence with the system; this is not an independent clinical gold standard. No failed extraction was corrected or handed off.', '',
        '| Case | M1 | M2 | M3 | E2E | Seconds |','|---|---|---|---|---|---|']
    lines += [f"| {c['id']} | {c['module1']} | {c['module2']} | {c['module3']} | {c['e2e']} | {c['duration_seconds']} |" for c in result['cases']]
    lines += ['', 'Metrics count all selected cases, including downstream stages blocked by OCR. Medication identification excludes deliberately unknown/ambiguous/incomplete products; their conservative handling is measured separately. Mapping denominator includes ingredients without a DDInter identity. Pair denominators include within-product combinations, deduplicated per case; duplicate active ingredients are evaluated separately. OCR matches ignore case and whitespace; strength spaces are ignored. Extra or missing rows make every row in that case incorrect. A correct literal transcription with low OCR confidence passes Module 1 text evaluation but blocks simulated confirmation and downstream execution; uncertainty is never erased.', '']
    lines += [f'- {k}: {v}' for k,v in result['metrics'].items()]
    lines += ['',f"Actual failure categories: {result['failure_categories']}.",f"Protected historical artifacts/database changes: {result['protected_input_changes']}.",'',
        'PASS means expected engineering behavior, including correct unresolved/missing-record handling. FAIL means an observed mismatch. BLOCKED means no executable backend or no confirmed upstream output; downstream BLOCKED stages do not hide an upstream FAIL. No result establishes clinical safety. Major alerts are immediate, HCP review is required, safe_to_take stays null and no medication changes are made. Real UI confirmation/HCP delivery and Gemini recovery are outside this test.', '',
        'Reproduce from workspace root:', '', '```powershell', '.\\scripts\\run-e2e.ps1', '```','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--truth',type=Path,default=HERE/'ground_truth.json')
    parser.add_argument('--output',type=Path,default=PROJECT/'tests/artifacts/e2e'/datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    parser.add_argument('--unified-config',type=Path)
    args=parser.parse_args()
    result=run(args.truth,args.output,args.unified_config)
    sys.exit(1 if result['counts'].get('FAIL') or result['protected_input_changes'] else 2 if result['counts'].get('BLOCKED') else 0)
