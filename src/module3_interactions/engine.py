"""Deterministic bounded DDI lookup, not prescribing or a clinical safety verdict."""
from collections import defaultdict
from copy import deepcopy
import hashlib
from itertools import combinations
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import re
import unicodedata

HEADERS=['DDInterID_A','Drug_A','DDInterID_B','Drug_B','Level']
SOURCE='https://ddinter2.scbdd.com/static/media/download/ddinter_downloads_code_A.csv'

def text_key(value):return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())
def valid_id(value):return isinstance(value,str) and re.fullmatch(r'DDInter\d+',value) is not None
def file_hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pair_key(a,b):return tuple(sorted((a,b)))
def prescription_ids(medication):
    values=medication.get('prescription_ids')
    return [p for p in values if isinstance(p,str) and p.strip()] if isinstance(values,list) else []

class BoundedDataset:
    """Explicitly bounded rows (default ten); source conflicts remain explicit."""
    def __init__(self,rows,coverage,additional_identities=None,*,row_limit=10):
        if not isinstance(row_limit,int) or isinstance(row_limit,bool) or row_limit<1:raise ValueError('Explicit positive row limit required')
        if not isinstance(rows,list) or not 1<=len(rows)<=row_limit:raise ValueError('Rows exceed the explicitly configured scope (default: ten previously inspected rows)')
        if not isinstance(coverage,dict) or coverage.get('loaded_rows')!=len(rows):raise ValueError('Coverage must match the loaded bounded scope')
        self.coverage=deepcopy(coverage)
        self.records=defaultdict(list);self.identities={}
        for index,row in enumerate(rows,1):
            if not isinstance(row,dict) or set(row)!=set(HEADERS):raise ValueError('Unexpected CSV schema; do not infer extra fields')
            for side in ('A','B'):
                identifier,name=row['DDInterID_'+side],row['Drug_'+side]
                if not valid_id(identifier) or not isinstance(name,str) or not name.strip():raise ValueError('Source endpoint needs explicit DDInter ID and name')
                known=self.identities.get(identifier)
                if known and known['name']!=name:raise ValueError('Conflicting source names for one DDInter identifier')
                self.identities[identifier]={'name':name,'synonyms':[],
                  'evidence':{'kind':'synthetic_endpoint' if coverage.get('synthetic_fixture') else 'official_csv_endpoint','source_url':coverage.get('source_url'),
                    'csv_sha256':coverage.get('csv_sha256'),'csv_record_1_based':index,
                    'id_column':'DDInterID_'+side,'name_column':'Drug_'+side,'review_scope':'drug_entity_only'}}
            if not isinstance(row['Level'],str) or not row['Level'].strip():raise ValueError('Missing source interaction level; do not invent severity')
            a,b=row['DDInterID_A'],row['DDInterID_B']
            if a==b:raise ValueError('Self-pair source record needs separate source review')
            record={'drug_id_pair':list(pair_key(a,b)),'original_level':row['Level'],
              'raw_source_row':deepcopy(row),'evidence':{'source_url':coverage.get('source_url'),
                'csv_sha256':coverage.get('csv_sha256'),'csv_record_1_based':index,
                'level_column':'Level','inspection_sha256':coverage.get('inspection_sha256'),
                'source_kind':'synthetic_fixture' if coverage.get('synthetic_fixture') else 'approved_official_csv_sample'},
              'mechanism':None,'management':None,'clinical_references':None}
            self.records[pair_key(a,b)].append(record)
        for identifier,identity in (additional_identities or {}).items():
            if not valid_id(identifier) or not identity.get('name') or not identity.get('evidence'):raise ValueError('Additional identity needs explicit reviewed evidence')
            if identifier in self.identities and text_key(self.identities[identifier]['name'])!=text_key(identity['name']):raise ValueError('Additional identity conflicts with loaded sample')
            self.identities[identifier]=deepcopy(identity)
        self.coverage.update(unique_interaction_pairs=len(self.records),
          unique_pair_endpoint_ids=len({identifier for pair in self.records for identifier in pair}),
          identity_evidence_entries=len(self.identities),interaction_coverage_complete=False,
          clinical_mechanisms_available=False,management_available=False,clinical_references_available=False,
          rxcui_crosswalk_available=False)

    def lookup(self,a,b):
        records=deepcopy(self.records.get(pair_key(a,b),[]))
        if not records:return {'status':'NO_RECORD_IN_LOADED_SUBSET','source_records':[],
          'coverage_conclusion':'INSUFFICIENT_COVERAGE','original_level':None,'safe':None}
        levels=list(dict.fromkeys(record['original_level'] for record in records))
        return {'status':'INTERACTION_DETECTED' if len(levels)==1 else 'CONFLICTING_SOURCE_RECORDS',
          'original_level':levels[0] if len(levels)==1 else None,'original_levels':levels,
          'source_records':records,'coverage_conclusion':'POSITIVE_RECORD_ONLY_NOT_EXHAUSTIVE','safe':None}

def load_existing_dataset(project_root):
    evidence=Path(project_root)/'data/reference/provenance/module2_api_quicktest/ingredient_ddinter_poc/evidence'
    inspection_path=evidence/'csv_first10_inspection.json'
    manifest_path=evidence/'approved_download_manifest.json'
    inspection=json.loads(inspection_path.read_text(encoding='utf-8'))
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if inspection.get('exact_headers')!=HEADERS or inspection.get('rows_inspected')!=10 or len(inspection.get('rows',[]))!=10:
        raise ValueError('Default input must be the exact previously inspected ten-row sample')
    if manifest.get('source_url')!=SOURCE or inspection.get('sha256','').lower()!=manifest.get('sha256','').lower():raise ValueError('Official source provenance mismatch')
    # Hashing retains integrity; it does not parse any additional CSV rows.
    if file_hash(evidence/'ddinter_downloads_code_A.csv')!=inspection['sha256']:raise ValueError('Original approved CSV hash mismatch')
    public_path=evidence/'ddinter_public_record.json'
    public=json.loads(public_path.read_text(encoding='utf-8'))
    additional={}
    for record in public['records']:
        if record['ddinter_id']!='DDInter14' or record['name']!='Acetaminophen':raise ValueError('Additional identity scope is only the prior reviewed DDInter14 page')
        additional[record['ddinter_id']]={'name':record['name'],
          'synonyms':[s['name'] for s in record.get('synonyms',[]) if s.get('verification')=='explicit_official_record_synonym' and s.get('source_url')==record['source_url']],
          'evidence':{'kind':'prior_assistant_official_page_review','source_url':record['source_url'],
            'snapshot_sha256':file_hash(public_path),'review_scope':'drug_entity_only_not_local_product'}}
    coverage={'source_url':SOURCE,'csv_sha256':inspection['sha256'],'inspection_sha256':file_hash(inspection_path),
      'inspection_path':str(inspection_path),'download_manifest_sha256':file_hash(manifest_path),
      'loaded_rows':10,'scope':'first ten previously inspected records of category-A CSV',
      'complete_database_loaded':False,'file_release_version_independently_verified':False,
      'advertised_source':'DDInter 2.0 official download page; exact file release unverified',
      'license':'CC BY-NC-SA 4.0','license_url':'https://ddinter2.scbdd.com/terms/',
      'synthetic_fixture':False}
    return BoundedDataset(inspection['rows'],coverage,additional)

def validate_component(medication,component,index,dataset):
    result={'medication_id':medication['medication_id'],'component_index':index,
      'prescription_ids':deepcopy(medication.get('prescription_ids',[])),
      'ingredient_name':component.get('name') if isinstance(component,dict) else None,
      'ddinter_id':component.get('ddinter_id') if isinstance(component,dict) else None,
      'source_strength':component.get('strength') if isinstance(component,dict) else None,
      'status':'UNRESOLVED','issues':[],'identity_evidence':[]}
    if not isinstance(component,dict):result['issues'].append('INVALID_COMPONENT');return result
    if medication.get('identity_status')!='VERIFIED':result['issues'].append('MEDICATION_IDENTITY_'+str(medication.get('identity_status','MISSING')))
    if not medication.get('identity_evidence'):result['issues'].append('MEDICATION_IDENTITY_EVIDENCE_MISSING')
    if not isinstance(medication.get('prescription_ids'),list) or not medication['prescription_ids'] or any(not isinstance(p,str) or not p.strip() for p in medication['prescription_ids']):
        result['issues'].append('SOURCE_PRESCRIPTION_IDS_MISSING_OR_INVALID')
    candidates=component.get('candidate_ddinter_ids',[])
    result['candidate_ddinter_ids']=deepcopy(candidates)
    if not isinstance(candidates,list) or any(not valid_id(i) for i in candidates):result['issues'].append('INVALID_CANDIDATE_IDENTIFIERS')
    elif len(set(candidates))>1 or (candidates and result['ddinter_id'] and any(i!=result['ddinter_id'] for i in candidates)):
        result['issues'].append('AMBIGUOUS_OR_CONFLICTING_IDENTIFIERS')
    if component.get('mapping_status')!='VERIFIED':result['issues'].append('MAPPING_'+str(component.get('mapping_status','MISSING')))
    if not valid_id(result['ddinter_id']):result['issues'].append('MISSING_OR_INVALID_DDINTER_IDENTIFIER')
    else:
        identity=dataset.identities.get(result['ddinter_id'])
        if not identity:result['issues'].append('IDENTIFIER_OUTSIDE_LOADED_IDENTITY_EVIDENCE')
        elif identity.get('identity_status')=='REVIEW_REQUIRED':result['issues'].append('CONFLICTING_DATASET_IDENTIFIER_NAMES')
        elif not isinstance(result['ingredient_name'],str) or text_key(result['ingredient_name']) not in {text_key(n) for n in [identity['name'],*identity.get('synonyms',[])]}:
            result['issues'].append('INGREDIENT_NAME_IDENTIFIER_CONFLICT')
        else:result['identity_evidence'].append(deepcopy(identity['evidence']))
    if component.get('mapping_status')=='AMBIGUOUS' or 'AMBIGUOUS_OR_CONFLICTING_IDENTIFIERS' in result['issues']:
        result['status']='AMBIGUOUS'
    elif not result['issues']:result['status']='VERIFIED_FOR_PAIR_LOOKUP'
    return result

def review_alert(kind,contexts,levels=None,evidence=None):
    """Workflow routing only; original source level is never converted to advice."""
    levels=levels or []
    return {'kind':kind,'contexts':deepcopy(contexts),'original_source_levels':levels,
      'evidence':deepcopy(evidence or []),'display_timing':'IMMEDIATE','wait_for_hcp_before_display':False,
      'hcp_review_required':True,'routing_priority':'PROMPT' if 'Major' in levels or kind in {'SOURCE_CONFLICT','UNRESOLVED_IDENTITY'} else 'REVIEW',
      'priority_basis':'local workflow policy, not a clinical severity reinterpretation',
      'message':'Ask an HCP to review the source finding and medication identities.',
      'autonomous_medication_changes':False,'mechanism':None,'treatment_guidance':None}

def assess(medications,dataset):
    if not isinstance(medications,list):raise ValueError('Expected a medication list')
    ids=[m.get('medication_id') for m in medications if isinstance(m,dict)]
    if len(ids)!=len(medications) or any(not isinstance(i,str) or not i.strip() for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('Medication IDs must be nonempty and unique; do not silently merge prescriptions')
    for medication in medications:
        if not isinstance(medication.get('ingredients'),list):raise ValueError('Every medication needs an explicit ingredient array; an empty array is unresolved')
    inputs=deepcopy(medications)
    components=[];unresolved=[]
    for medication in sorted(inputs,key=lambda m:m['medication_id']):
        if not medication['ingredients']:
            unresolved.append({'medication_id':medication['medication_id'],'prescription_ids':medication.get('prescription_ids',[]),
                               'status':'UNRESOLVED','issues':['NO_INGREDIENTS']})
        for index,component in enumerate(medication['ingredients']):
            item=validate_component(medication,component,index,dataset)
            components.append(item)
            if item['status']!='VERIFIED_FOR_PAIR_LOOKUP':unresolved.append(deepcopy(item))
    verified_groups=defaultdict(list)
    for item in components:
        if item['status']=='VERIFIED_FOR_PAIR_LOOKUP':verified_groups[item['ddinter_id']].append(item)
    duplicates=[{'ddinter_id':identifier,'source_name':dataset.identities[identifier]['name'],
      'status':'DUPLICATE_ACTIVE_INGREDIENT','occurrences':deepcopy(items),
      'clinical_interpretation':'Possible duplicate exposure; intentionality and actual administration not assessed',
      'dosage_totals_computed':False} for identifier,items in sorted(verified_groups.items()) if len(items)>1]
    lookup_groups={};unassessed_pairs=[];duplicate_pairs=[]
    for left,right in combinations(components,2):
        context={'left':deepcopy(left),'right':deepcopy(right),
                 'within_one_medication':left['medication_id']==right['medication_id']}
        if left['status']!='VERIFIED_FOR_PAIR_LOOKUP' or right['status']!='VERIFIED_FOR_PAIR_LOOKUP':
            unassessed_pairs.append({'status':'UNASSESSED_IDENTITY','context':context,'safe':None});continue
        if left['ddinter_id']==right['ddinter_id']:
            duplicate_pairs.append({'status':'DUPLICATE_INGREDIENT_RULE_ONLY','context':context,'safe':None});continue
        pair=pair_key(left['ddinter_id'],right['ddinter_id'])
        if pair not in lookup_groups:lookup_groups[pair]={'drug_id_pair':list(pair),'contexts':[],**dataset.lookup(*pair)}
        lookup_groups[pair]['contexts'].append(context)
    checked_pairs=list(lookup_groups.values())
    interactions=[deepcopy(check) for check in checked_pairs if check['status']=='INTERACTION_DETECTED']
    conflicts=[deepcopy(check) for check in checked_pairs if check['status']=='CONFLICTING_SOURCE_RECORDS']
    missing=[deepcopy(check) for check in checked_pairs if check['status']=='NO_RECORD_IN_LOADED_SUBSET']
    medication_pairs=[]
    ordered_medications=sorted(inputs,key=lambda m:m['medication_id'])
    for left,right in combinations(ordered_medications,2):
        med_pair=pair_key(left['medication_id'],right['medication_id'])
        relevant=[check for check in checked_pairs if any(pair_key(c['left']['medication_id'],c['right']['medication_id'])==med_pair for c in check['contexts'])]
        unchecked=[p for p in unassessed_pairs if pair_key(p['context']['left']['medication_id'],p['context']['right']['medication_id'])==med_pair]
        duplicate_checks=[p for p in duplicate_pairs if pair_key(p['context']['left']['medication_id'],p['context']['right']['medication_id'])==med_pair]
        has_empty=not left['ingredients'] or not right['ingredients']
        statuses={check['status'] for check in relevant}
        status=('INTERACTION_DETECTED' if 'INTERACTION_DETECTED' in statuses else
                'SOURCE_CONFLICT' if 'CONFLICTING_SOURCE_RECORDS' in statuses else
                'UNASSESSED' if unchecked or has_empty else
                'DUPLICATE_INGREDIENT_ONLY' if duplicate_checks and not relevant else 'NO_RECORD_IN_LOADED_SUBSET')
        medication_pairs.append({'medication_id_pair':list(med_pair),'prescription_ids':sorted(set(prescription_ids(left)+prescription_ids(right))),
          'status':status,'ingredient_pair_references':[c['drug_id_pair'] for c in relevant],
          'unassessed_component_pairs':len(unchecked),'duplicate_component_pairs':len(duplicate_checks),
          'has_missing_component_list':has_empty,'assessment_complete':False,'safe':None})
    alerts=[]
    for check in interactions:alerts.append(review_alert('DDI_SOURCE_RECORD',check['contexts'],check['original_levels'],check['source_records']))
    for check in conflicts:alerts.append(review_alert('SOURCE_CONFLICT',check['contexts'],check['original_levels'],check['source_records']))
    for duplicate in duplicates:alerts.append(review_alert('DUPLICATE_ACTIVE_INGREDIENT',duplicate['occurrences']))
    if unresolved:alerts.append(review_alert('UNRESOLVED_IDENTITY',unresolved))
    alerts.append(review_alert('LIMITED_DATASET_COVERAGE',[],evidence=[dataset.coverage]))
    result={'schema_version':'module3.ddi_poc.v1','assessment_context':'offline_feasibility_not_clinical_validation',
      'input_medications':inputs,'ingredient_identity_checks':components,
      'checked_medication_pairs':medication_pairs,'checked_ingredient_pairs':checked_pairs,
      'matched_interactions':interactions,'conflicting_source_pairs':conflicts,
      'duplicate_ingredients':duplicates,'duplicate_ingredient_pairs':duplicate_pairs,
      'unresolved_mappings':unresolved,'unassessed_ingredient_pairs':unassessed_pairs,
      'coverage':deepcopy(dataset.coverage),'review_alerts':alerts,
      'assessment_status':'INCOMPLETE_IDENTITIES' if unresolved else 'SOURCE_CONFLICT_REVIEW_REQUIRED' if conflicts else 'INTERACTIONS_DETECTED_LIMITED_COVERAGE' if interactions else 'INSUFFICIENT_COVERAGE',
      'completeness':{'medication_pairs_generated':len(medication_pairs),
        'all_component_pairs_generated':len(components)*(len(components)-1)//2,
        'unique_unordered_ingredient_pairs_looked_up':len(checked_pairs),
        'component_pair_contexts_looked_up':sum(len(p['contexts']) for p in checked_pairs),
        'unassessed_component_pairs':len(unassessed_pairs),'duplicate_component_pairs':len(duplicate_pairs),
        'identifiers_complete':bool(inputs) and not unresolved,'scope_lookup_complete':bool(inputs) and not unresolved,
        'clinical_assessment_complete':False,'dataset_coverage_complete':False},
      'safe_to_take':None,'no_interactions':None,'requires_hcp_review':True,
      'clinical_recommendations':None,'autonomous_prescribing':False,
      'automated_schedule_optimization':False,'network_requests':0,'external_ai_calls':0}
    return result

def module2_input(candidate,prescription_ids,medication_id='mypara500'):
    """Preserve ingredient IDs but never promote an upstream REVIEW_REQUIRED product."""
    local=deepcopy(candidate.get('local_medication') or {})
    ingredients=[]
    for item in candidate.get('ingredients',[]):
        mapping=item.get('ddinter') or {}
        ingredients.append({'name':mapping.get('name') or item.get('source_ingredient_name'),
          'original_ingredient_name':item.get('source_ingredient_name'),'strength':item.get('source_strength'),
          'ddinter_id':mapping.get('ddinter_id'),
          'mapping_status':'VERIFIED' if mapping.get('status') in {'EXACT','VERIFIED_SYNONYM'} else mapping.get('status','UNRESOLVED'),
          'mapping_evidence':deepcopy(mapping.get('evidence',[])),
          'upstream_rxnorm':deepcopy(item.get('rxnorm'))})
    return {'medication_id':medication_id,'prescription_ids':list(prescription_ids),
      'brand_name':local.get('brand_name'),'local_medication':local,
      'identity_status':'VERIFIED' if candidate.get('status')=='VERIFIED' else 'REVIEW_REQUIRED',
      'identity_evidence':deepcopy(candidate.get('source_evidence',[])),
      'upstream_review_issues':deepcopy(candidate.get('local_review_issues',[])),
      'source_kind':'existing_real_module2_candidate','ingredients':ingredients}
