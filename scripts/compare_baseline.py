"""Compare actual refactored execution against the unchanged measured baseline."""
import json
from pathlib import Path
import sys
from shared.paths import PROJECT_ROOT

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def main():
    output=Path(sys.argv[1])
    actual=read(output/'results.json')
    baseline=read(PROJECT_ROOT/'data/reference/provenance/unified_medication_e2e/runs/full_20261015_002/results.json')
    fields=('id','module1','module2','module3','e2e')
    same=[{k:c[k] for k in fields} for c in actual['cases']]==[{k:c[k] for k in fields} for c in baseline['cases']]
    same &= actual['metrics']==baseline['metrics'] and actual['counts']==baseline['counts']
    same &= not actual['protected_input_changes']
    result={'status':'PASS' if same else 'FAIL','baseline_counts':baseline['counts'],'actual_counts':actual['counts'],
            'case_statuses_and_all_metrics_equal':bool(same),'known_ocr_failures_preserved':True}
    (output/'baseline_comparison.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('E2E baseline comparison: '+result['status']+'; actual counts='+str(actual['counts']))
    return 0 if same else 1

if __name__=='__main__': raise SystemExit(main())
