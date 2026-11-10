"""Offline ingredient identifiers only. No network, interaction queries or admission."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from shared.paths import ProjectPath as Path
import re
import unicodedata
from urllib.parse import urlencode

BASE='https://rxnav.nlm.nih.gov/REST/'

def key(value):
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())

def strength(value):
    if not isinstance(value,str):return None
    match=re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*(mg|g|mcg)\s*',value,re.I)
    if not match or Decimal(match[1].replace(',','.'))<=0:return None
    return {'amount':str(Decimal(match[1].replace(',','.'))),'unit':match[2].lower(),'source_text':value}

class SavedRxNorm:
    """Read-only cached exact lookup; no fallback to live/normalized/fuzzy APIs."""
    def __init__(self,directory):self.directory=Path(directory)

    def read(self,path,**params):
        url=BASE+path+('?' + urlencode(params) if params else '')
        digest=hashlib.sha256(url.encode()).hexdigest()
        file=self.directory/(digest+'.json')
        evidence={'url':url,'request_id':digest,'local_path':str(file),'cache_only':True}
        if not file.is_file():return None,{**evidence,'error':'CACHE_MISS'}
        try:record=json.loads(file.read_text(encoding='utf-8'))
        except (OSError,ValueError):return None,{**evidence,'error':'INVALID_CACHE_JSON'}
        if not isinstance(record,dict):return None,{**evidence,'error':'INVALID_CACHE_RECORD'}
        evidence.update(sha256=hashlib.sha256(file.read_bytes()).hexdigest(),recorded_at_utc=record.get('recorded_at_utc'))
        if record.get('url')!=url or record.get('request_id')!=digest:
            return None,{**evidence,'error':'CACHE_IDENTITY_MISMATCH'}
        if record.get('http_status')!=200 or record.get('error'):
            return None,{**evidence,'error':'SAVED_REQUEST_FAILED','saved_error':record.get('error')}
        response=record.get('response')
        if not isinstance(response,dict):return None,{**evidence,'error':'INVALID_RESPONSE'}
        return response,evidence

    def resolve(self,name):
        result={'status':'UNRESOLVED','method':'exact_cached_ingredient','rxcui':None,
                'international_name':None,'tty':None,'concept_status_at_recording':None,
                'evidence':[],'candidates':[],'issues':[]}
        payload,evidence=self.read('rxcui.json',name=key(name),search=0,allsrc=0)
        result['evidence'].append(evidence)
        if payload is None:result['issues'].append(evidence['error']);return result
        group=payload.get('idGroup')
        if not isinstance(group,dict):
            result.update(status='REVIEW_REQUIRED',issues=['INVALID_ID_GROUP']);return result
        ids=group.get('rxnormId',[])
        if not isinstance(ids,list) or any(not isinstance(i,str) or not i.isdigit() for i in ids):
            result.update(status='REVIEW_REQUIRED',issues=['INVALID_RXCUI_LIST']);return result
        ids=list(dict.fromkeys(ids))
        if len(ids)>1:result.update(status='AMBIGUOUS',candidates=ids);return result
        if not ids:result['issues'].append('NO_EXACT_SAVED_MATCH');return result
        rxcui=ids[0]
        prop,proof=self.read(f'rxcui/{rxcui}/properties.json');result['evidence'].append(proof)
        history,proof=self.read(f'rxcui/{rxcui}/historystatus.json');result['evidence'].append(proof)
        if prop is None or history is None:
            result.update(status='REVIEW_REQUIRED',issues=['ENRICHMENT_MISSING_OR_FAILED'],candidates=ids);return result
        properties=prop.get('properties') or {}
        hist=history.get('rxcuiStatusHistory') or {}
        if not isinstance(properties,dict) or not isinstance(hist,dict):
            result.update(status='REVIEW_REQUIRED',issues=['INVALID_ENRICHMENT_SHAPE']);return result
        attrs=hist.get('attributes') or {}
        if not isinstance(properties,dict) or not isinstance(hist,dict) or not isinstance(attrs,dict):
            result.update(status='REVIEW_REQUIRED',issues=['INVALID_ENRICHMENT_SHAPE']);return result
        metadata=hist.get('metaData') or {}
        if not isinstance(metadata,dict):
            result.update(status='REVIEW_REQUIRED',issues=['INVALID_ENRICHMENT_SHAPE']);return result
        status=metadata.get('status')
        if (properties.get('rxcui')!=rxcui or attrs.get('rxcui')!=rxcui or
            properties.get('tty') not in {'IN','PIN'} or properties.get('tty')!=attrs.get('tty') or
            not properties.get('name') or key(properties['name'])!=key(attrs.get('name','')) or status!='Active'):
            result.update(status='REVIEW_REQUIRED',issues=['NOT_A_CONSISTENT_ACTIVE_INGREDIENT'],candidates=ids);return result
        result.update(status='VERIFIED',rxcui=rxcui,international_name=properties['name'],tty=properties['tty'],
                      concept_status_at_recording=status,verification_scope='exact_ingredient_concept_in_saved_release')
        return result

class DDInterIndex:
    """One reviewed public record or separately labelled synthetic drug fixtures."""
    def __init__(self,records,allow_synthetic=False):
        if records is None:self.records=None;return
        self.records=[]
        by_id={}
        for raw in records:
            record=deepcopy(raw)
            if not re.fullmatch(r'DDInter\d+',record.get('ddinter_id','')) or not record.get('name'):
                raise ValueError('Expected actual DDInter-prefixed ID and drug name; RxCUI is a different namespace')
            if record.get('synthetic') and not allow_synthetic:raise ValueError('Synthetic entry cannot enter real evidence index')
            if not record.get('synthetic'):
                public_record=record.get('source_url')==f"https://ddinter2.scbdd.com/server/drug-detail/{record['ddinter_id']}/"
                official_csv=(record.get('source_url')=='https://ddinter2.scbdd.com/static/media/download/ddinter_downloads_code_A.csv'
                              and record.get('evidence_kind')=='approved_csv_endpoint'
                              and re.fullmatch(r'[0-9a-f]{64}',record.get('csv_sha256',''))
                              and 1<=record.get('csv_record_1_based',0)<=10)
                if not public_record and not official_csv:
                    raise ValueError('Real entry needs corresponding official source URL')
                if record.get('identifier_evidence',{}).get('value')!=record['ddinter_id'] or record.get('name_evidence',{}).get('value')!=record['name']:
                    raise ValueError('Real entry lacks explicit name/ID evidence')
            signature=json.dumps(record,sort_keys=True)
            if record['ddinter_id'] in by_id:
                if by_id[record['ddinter_id']]!=signature:raise ValueError('Conflicting repeated DDInter ID')
                continue
            by_id[record['ddinter_id']]=signature;self.records.append(record)

    def match(self,name):
        result={'status':'UNMATCHED','ddinter_id':None,'name':None,'method':None,'candidates':[],
                'coverage_scope':'provided_bounded_drug_entries_only',
                'evidence':[],'interaction_assessment':'NOT_PERFORMED','absence_of_mapping_means_no_interactions':False}
        if self.records is None:result['status']='DATA_UNAVAILABLE';return result
        candidates=[]
        for record in self.records:
            if key(name)==key(record['name']):candidates.append((record,'EXACT','exact_canonical_name'))
            for synonym in record.get('synonyms',[]):
                if key(name)==key(synonym['name']) and synonym.get('verification')=='explicit_official_record_synonym' and synonym.get('source_url')==record.get('source_url'):
                    candidates.append((record,'VERIFIED_SYNONYM','explicit_source_synonym'))
        ids={r['ddinter_id'] for r,_,_ in candidates}
        if len(ids)>1:
            result.update(status='AMBIGUOUS',candidates=sorted(ids));return result
        if not candidates:return result
        record,status,method=next((c for c in candidates if c[1]=='EXACT'),candidates[0])
        result.update(status=status,ddinter_id=record['ddinter_id'],name=record['name'],method=method,
                      evidence=[deepcopy(record)],synthetic=record.get('synthetic',False),
                      verification_scope='drug_entity_identity_only')
        return result

def entries_from_csv_sample(inspection,manifest):
    """Map IDs/names from ONLY the ten approved inspected records; ignore Level."""
    required=['DDInterID_A','Drug_A','DDInterID_B','Drug_B','Level']
    if inspection.get('exact_headers')!=required:raise ValueError('Unknown official CSV schema; do not guess column roles')
    rows=inspection.get('rows',[])
    if not isinstance(rows,list) or len(rows)>10 or len(rows)!=inspection.get('rows_inspected'):
        raise ValueError('CSV inspection scope must remain at most ten records')
    if inspection.get('sha256','').lower()!=manifest.get('sha256','').lower():raise ValueError('CSV evidence hashes disagree')
    if manifest.get('source_url')!='https://ddinter2.scbdd.com/static/media/download/ddinter_downloads_code_A.csv':
        raise ValueError('Use only the approved official file')
    entries={}
    for row_index,row in enumerate(rows,1):
        if set(row)!=set(required):raise ValueError('Malformed CSV record')
        for side in ('A','B'):
            identifier,name=row['DDInterID_'+side],row['Drug_'+side]
            if not isinstance(identifier,str) or not re.fullmatch(r'DDInter\d+',identifier) or not isinstance(name,str) or not name.strip():
                raise ValueError('CSV endpoint lacks an explicit identifier/name')
            if identifier in entries:
                if entries[identifier]['name']!=name:raise ValueError('CSV identifier has conflicting names')
                entries[identifier]['additional_csv_record_evidence'].append({'csv_record_1_based':row_index,'endpoint':side})
                continue
            entries[identifier]={'ddinter_id':identifier,'name':name,'synthetic':False,'synonyms':[],
              'source_url':manifest['source_url'],'evidence_kind':'approved_csv_endpoint',
              'csv_sha256':inspection['sha256'],'csv_record_1_based':row_index,'endpoint':side,
              'identifier_evidence':{'label':'DDInterID_'+side,'value':identifier},
              'name_evidence':{'label':'Drug_'+side,'value':name},'additional_csv_record_evidence':[],
              'mapping_review':'machine_csv_field_association_only'}
    return list(entries.values())

def normalize_medication(candidate,rxnorm,ddinter):
    """Preserve all components; an unmatched component blocks complete handoff."""
    local=deepcopy(candidate.get('local_medication'))
    raw_components=candidate.get('ingredients')
    result={'schema_version':'module2.ingredient_ddinter_poc.v1','status':'REVIEW_REQUIRED',
      'synthetic_fixture':candidate.get('synthetic_fixture',False),
      'local_medication':local,'ingredients':[],'source_candidate_status':candidate.get('status'),
      'local_review_issues':deepcopy(candidate.get('issues',[])),
      'source_evidence':deepcopy(candidate.get('evidence',[])),
      'identifier_pipeline_status':'INCOMPLETE','ddinter_drug_ids':[],
      'ready_for_identifier_handoff':False,'interaction_assessment':'NOT_PERFORMED',
      'interaction_lookup_required':True,'no_interactions':None,
      'unmapped_ingredient_means_no_interactions':False,'automatic_reference_acceptance':False,
      'product_rxcui':None,'current_authorization':'NOT_VERIFIED','issues':[]}
    if not local or not isinstance(raw_components,list) or not raw_components:
        result.update(status='UNRESOLVED',issues=['LOCAL_IDENTITY_OR_COMPONENTS_MISSING']);return result
    seen=set()
    for index,component in enumerate(raw_components):
        if not isinstance(component,dict):
            result['ingredients'].append({'component_index':index,'status':'REVIEW_REQUIRED','issues':['INVALID_COMPONENT_SHAPE']});continue
        name=component.get('inn_name')
        dose=component.get('strength')
        item={'component_index':index,'source_ingredient_name':name,'source_strength':dose,
              'strength_parsed':strength(dose),'evidence':deepcopy(component.get('evidence',[])),
              'rxnorm':None,'ddinter':None,'status':'REVIEW_REQUIRED','issues':[]}
        if not isinstance(name,str) or not name.strip():item['issues'].append('INGREDIENT_NAME_MISSING')
        elif key(name) in seen:item['issues'].append('DUPLICATE_COMPONENT_REQUIRES_REVIEW')
        else:seen.add(key(name))
        if not item['strength_parsed']:item['issues'].append('STRENGTH_MISSING_OR_UNSUPPORTED')
        if item['issues']:
            result['ingredients'].append(item);continue
        item['rxnorm']=rxnorm.resolve(name)
        if item['rxnorm']['status']=='VERIFIED':
            item['ddinter']=ddinter.match(item['rxnorm']['international_name'])
            item['ddinter_original_name_check']=ddinter.match(name)
            if item['ddinter'].get('synthetic') and not candidate.get('synthetic_fixture'):
                item['issues'].append('SYNTHETIC_MAPPING_BLOCKED_FOR_REAL_INPUT')
            elif item['ddinter']['status'] in {'EXACT','VERIFIED_SYNONYM'}:
                item['status']='MAPPED_IDENTIFIER'
                result['ddinter_drug_ids'].append(item['ddinter']['ddinter_id'])
            else:item['issues'].append('DDINTER_IDENTITY_'+item['ddinter']['status'])
        else:
            item['issues'].append('RXNORM_'+item['rxnorm']['status'])
        result['ingredients'].append(item)
    normalized_seen=set()
    for item in result['ingredients']:
        if item['status']=='MAPPED_IDENTIFIER':
            signature=(item['rxnorm']['rxcui'],item['ddinter']['ddinter_id'])
            if signature in normalized_seen:
                item['status']='REVIEW_REQUIRED';item['issues'].append('DUPLICATE_NORMALIZED_COMPONENT_REQUIRES_REVIEW')
            normalized_seen.add(signature)
    complete=all(item['status']=='MAPPED_IDENTIFIER' for item in result['ingredients'])
    if complete:
        result['identifier_pipeline_status']='COMPLETE_IDENTIFIER_MAPPING'
        result['ready_for_identifier_handoff']=True
    else:result['issues'].append('INCOMPLETE_COMPONENT_MAPPING_NOT_A_NEGATIVE_INTERACTION_RESULT')
    result['ddinter_drug_ids']=list(dict.fromkeys(result['ddinter_drug_ids']))
    if any((item.get('rxnorm') or {}).get('status')=='AMBIGUOUS' or (item.get('ddinter') or {}).get('status')=='AMBIGUOUS' for item in result['ingredients']):
        result['status']='AMBIGUOUS'
    result['issues'].extend(['INDEPENDENT_LOCAL_REVIEW_PENDING','CURRENT_REGISTRATION_NOT_RECONCILED','INTERACTIONS_NOT_ASSESSED'])
    return result
