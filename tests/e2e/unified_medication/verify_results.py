"""Audit saved handoffs and safety behavior, without rerunning prediction."""
import argparse
import hashlib
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify(output):
    truth=read(output/'ground_truth.json'); result=read(output/'results.json')
    checks=[]
    def check(label,condition):
        checks.append({'check':label,'pass':bool(condition)})
    check('Case count and unique IDs',len(truth['cases'])==len(result['cases'])==29 and len({c['id'] for c in truth['cases']})==29)
    check('Previous images still pass',all(c['e2e']=='PASS' for c in result['cases'] if c['id'] in ('TC01','TC02')))
    check('Protected inputs unchanged',not result['protected_input_changes'] and all(sha(p)==s for p,s in read(output/'protected_inputs.json').items()))
    for case in truth['cases']:
        cid=case['id']; m1=read(output/f'{cid}_module1.json'); m2=read(output/f'{cid}_module2.json'); m3=read(output/f'{cid}_module3.json')
        confirmation=read(output/f'{cid}_confirmation.json')
        check(cid+' image unchanged',sha(case['image_path'])==case['image_sha256'])
        check(cid+' confirmation depends on all actual extraction checks',confirmation['confirmed']==(m1['status']=='PASS' and all(c['pass'] for c in m1['expected_vs_actual'])))
        if not confirmation['confirmed']:
            check(cid+' blocked handoff without replacement',not m2['executed'] and not m3['executed'] and m2['actual_output'] is None and m3['actual_output'] is None)
            continue
        extraction=m1['actual_output']['medications']; identities=m2['actual_output']; assessment=m3['actual_output']
        check(cid+' real actual output counts',len(extraction)==len(identities))
        check(cid+' actual OCR fields preserved in Module 2',all(all(identity['original_medication'].get(k)==v for k,v in raw.items()) for raw,identity in zip(extraction,identities)))
        check(cid+' exact Module 2 to Module 3 handoff',assessment['input_medications']==[i['module3_input'] for i in identities])
        check(cid+' null safety and HCP behavior',assessment['safe_to_take'] is None and assessment['no_interactions'] is None and assessment['requires_hcp_review'] and not assessment['autonomous_prescribing'])
        check(cid+' immediate Major alerts',all(a['display_timing']=='IMMEDIATE' and not a['wait_for_hcp_before_display'] and a['hcp_review_required'] and a['routing_priority']=='PROMPT' and not a['autonomous_medication_changes'] for a in assessment['review_alerts'] if 'Major' in a['original_source_levels']))
        check(cid+' exact original severities',all(p['original_level']==r['raw_source_row']['Level'] for p in assessment['matched_interactions'] for r in p['source_records']))
    verified={'checks':checks,'passed':sum(c['pass'] for c in checks),'failed':sum(not c['pass'] for c in checks)}
    (output/'artifact_verification.json').write_text(json.dumps(verified,indent=2)+'\n',encoding='utf-8')
    print(f"Artifact checks: {verified['passed']} PASS, {verified['failed']} FAIL")
    for c in checks:
        if not c['pass']: print(c)
    return verified

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('output',type=Path); args=parser.parse_args()
    raise SystemExit(1 if verify(args.output)['failed'] else 0)
