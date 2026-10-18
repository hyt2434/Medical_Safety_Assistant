"""Standard-library, offline conversion of ONE user-captured MYPARA 500 row.

No network, Kendo widget data-source access, expected-answer filling or integration.
HTML input is a standalone table fragment, not a saved authenticated full page.
"""
import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

SOURCE = 'https://06dichvucong.dav.gov.vn/congbothuoc/index'
FIELDS = ('medication_name','active_ingredients','strengths','dosage_form','manufacturer',
          'registration_number','previous_registration_number','registration_expiry','packaging')


def load_json(text):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate JSON key: '+key)
            result[key]=value
        return result
    def invalid_constant(value):raise ValueError('Invalid JSON constant: '+value)
    return json.loads(text,object_pairs_hook=unique,parse_constant=invalid_constant)


def clean(text):
    return ' '.join(unicodedata.normalize('NFKC',text or '').split()) or None


def header_key(text):
    value=unicodedata.normalize('NFD',clean(text) or '').casefold().replace('đ','d')
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).split())


def role(header):
    value=header_key(header)
    if 'dang ky' in value and any(s in value for s in ('cu','da cap','truoc')):
        return 'previous_registration_number'
    if any(s in value for s in ('ngay het hieu luc','ngay het han','han giay phep','registration expiry')):
        return 'registration_expiry'
    if any(s in value for s in ('so dang ky','so gplh','so giay phep luu hanh')):
        return 'registration_number'
    if any(s in value for s in ('ten thuoc','medication name')):
        return 'medication_name'
    if any(s in value for s in ('hoat chat','thanh phan','active ingredient')):
        return 'active_ingredients'
    if any(s in value for s in ('ham luong','nong do','strength')):
        return 'strengths'
    if 'dang bao che' in value or 'dosage form' in value:
        return 'dosage_form'
    if any(s in value for s in ('co so san xuat','cong ty san xuat','nha san xuat','manufacturer')) and not any(s in value for s in ('dia chi','nuoc','address','country')):
        return 'manufacturer'
    if 'quy cach dong goi' in value or 'packaging' in value:
        return 'packaging'
    return None


def column_role(header):
    """Use visible grouped labels, not a duplicate leaf or private widget state."""
    path=header.get('header_path') or [header.get('header_text') or header.get('raw_header')]
    return role(' '.join(p for p in path if p))


REG_ID = r'(?:(?:VD|VN|QLĐB)-\d+-\d+|\d{12})'


def registration_cell(value):
    """Explicit old-ID annotation only; an unlabelled pair remains ambiguous."""
    pattern=rf'(?P<primary>{REG_ID})(?:\s*\((?P<status>Hiệu lực|Hết hiệu lực)\))?(?:\s*\(SĐK cũ:\s*(?P<old>{REG_ID})\))?'
    match=re.fullmatch(pattern,value,re.I)
    return match.groupdict() if match else None


class TableHTML(HTMLParser):
    """Restricted single-table input; split grids should use the JSON snippet."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[];self.table=None;self.row=None;self.cell=None;self.section=None
        self.skip=0;self.depth=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in {'script','style'}: self.skip+=1;return
        if self.skip:return
        if tag=='table':
            self.depth+=1
            if self.depth>1:raise ValueError('Nested tables are unsupported; use bounded JSON capture')
            self.table={'headers':[],'rows':[]};self.tables.append(self.table)
        elif tag in {'thead','tbody'}:self.section=tag
        elif tag=='tr' and self.table is not None:
            self.row={'cells':[],'uid':attrs.get('data-uid')}
        elif tag in {'th','td'} and self.row is not None:
            hidden='hidden' in attrs or 'display:none' in attrs.get('style','').replace(' ','').lower() or 'k-hidden' in attrs.get('class','').split()
            self.cell={'raw_text':'','rendered':not hidden,'colspan':int(attrs.get('colspan','1')),
                       'rowspan':int(attrs.get('rowspan','1')),'data_field':attrs.get('data-field'),
                       'header_id':attrs.get('id'),'aria_colindex':attrs.get('aria-colindex')}
            self.row['cells'].append(self.cell)
        elif tag=='br' and self.cell:self.cell['raw_text']+='\n'
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.skip=max(0,self.skip-1);return
        if self.skip:return
        if tag in {'td','th'}:self.cell=None
        elif tag=='tr' and self.table is not None and self.row is not None:
            self.table['headers' if self.section=='thead' else 'rows'].append(self.row);self.row=None
        elif tag in {'thead','tbody'}:self.section=None
        elif tag=='table':self.table=None;self.depth-=1
    def handle_data(self,data):
        if self.cell is not None and not self.skip and self.cell['rendered']:self.cell['raw_text']+=data


def capture_from_html(text):
    parser=TableHTML();parser.feed(text)
    if len(parser.tables)!=1:raise ValueError('HTML mode needs one standalone table with headers; split grids require the JSON snippet')
    table=parser.tables[0]
    if len(table['headers'])!=1 or len(table['rows'])!=1:raise ValueError('HTML needs one header row and one medication row; use JSON for grouped headers')
    headers=[]
    for index,cell in enumerate(table['headers'][0]['cells']):
        if cell['colspan']!=1 or cell['rowspan']!=1:raise ValueError('Use JSON capture for spanned headers')
        headers.append({**cell,'physical_column':index,'raw_header':cell['raw_text'],'header_text':clean(cell['raw_text'])})
    cells=[]
    for index,cell in enumerate(table['rows'][0]['cells']):
        if cell['colspan']!=1:raise ValueError('Merged data cell is unsupported')
        cells.append({'physical_column':index,'header_column':index,'raw_text':cell['raw_text'] if cell['rendered'] else None,
                      'rendered':cell['rendered'],'alignment_method':'standalone_table_physical_order'})
    return {'schema_version':'dav.grid_capture.v1','source_url':SOURCE,'requested_record':'MYPARA 500',
      'capture_method':'user_provided_standalone_html','linkage':'single_table','grid_parts':[
        {'name':'single','headers':headers,'row':{'dom_row_index':0,'row_uid':table['rows'][0]['uid'],'cells':cells}}],
      'notes':['Offline HTML cannot reproduce external CSS visibility; restrict the saved fragment to the displayed target table.']}


def validate_capture(capture):
    if not isinstance(capture,dict):raise ValueError('Capture must be a JSON object')
    if capture.get('schema_version')!='dav.grid_capture.v1':raise ValueError('Unsupported capture schema')
    source=urlsplit(capture.get('source_url',''))
    if source.scheme!='https' or source.hostname!='06dichvucong.dav.gov.vn' or source.path.rstrip('/')!='/congbothuoc/index' or source.query or source.fragment:
        raise ValueError('Expected canonical DAV source URL without query/session information')
    if clean(capture.get('requested_record','')).upper()!='MYPARA 500':raise ValueError('Only MYPARA 500 is authorized')
    parts=capture.get('grid_parts',[])
    if not isinstance(parts,list):raise ValueError('grid_parts must be a list')
    if len(parts) not in (1,2):raise ValueError('Expected one table or two linked table parts')
    for part in parts:
        if not isinstance(part,dict) or not isinstance(part.get('row'),dict) or not isinstance(part.get('headers'),list) or not isinstance(part['row'].get('cells'),list):
            raise ValueError('Each part requires headers and exactly one row object with cells')
        if not part['headers']:raise ValueError('No column headers')
    if len(parts)==2:
        a,b=[part['row'] for part in parts]
        if a.get('row_uid') and b.get('row_uid'):
            if a['row_uid']!=b['row_uid']:raise ValueError('Split rows have different grid identities')
        elif a.get('dom_row_index')!=b.get('dom_row_index'):
            raise ValueError('Split-table row ordering is ambiguous')
    columns=[]
    for part in parts:
        headers,cells=part['headers'],part['row']['cells']
        if len(headers)!=len(cells):raise ValueError('Header/cell count mismatch')
        lookup={h['physical_column']:h for h in headers}
        if len(lookup)!=len(headers):raise ValueError('Duplicate header positions')
        positions=[cell.get('physical_column',i) for i,cell in enumerate(cells)]
        if positions!=list(range(len(cells))) or sorted(lookup)!=list(range(len(headers))):
            raise ValueError('Noncontiguous or reordered physical positions')
        mapped=[]
        for cell in cells:
            if not isinstance(cell.get('raw_text'),(str,type(None))):raise ValueError('Cell text must be a string or null')
            index=cell['header_column']
            if index not in lookup:raise ValueError('Cell points to a missing header')
            mapped.append(index)
            h=lookup[index]
            columns.append({'part':part['name'],'header':h,'cell':cell})
        if len(set(mapped))!=len(mapped):raise ValueError('Multiple cells map to one header')
    return columns


def convert(capture):
    columns=validate_capture(capture)
    result={field:None for field in FIELDS}
    result.update(schema_version='module2.grid_medication.v1',source_url=SOURCE,extraction_method='offline_read_only_dom_conversion',
      verification_status='REVIEW_REQUIRED',current_authorization='NOT_VERIFIED',
      current_registration_status='NOT_RECONCILED',registration_status_displayed=None,route=None,rxnorm_mapping=None,
      independent_review_required=True,automatic_reference_acceptance=False,
      captured_at_utc=capture.get('captured_at_utc'),
      data_reuse_permissions='UNRESOLVED',capture_origin='synthetic_test_fixture' if capture.get('synthetic_test_fixture') else capture.get('capture_method'),
      raw_source=columns,field_evidence={},issues=[])
    if len(capture['grid_parts'])==2 and not all(part['row'].get('row_uid') for part in capture['grid_parts']):
        result['issues'].append('split_row_linkage_needs_visual_confirmation')
    buckets={}
    for item in columns:
        if not item['cell'].get('rendered',True) or not item['header'].get('rendered',True):continue
        header=item['header'].get('header_text') or item['header'].get('raw_header')
        field=column_role(item['header'])
        if field:
            buckets.setdefault(field,[]).append(item)
    for field,items in buckets.items():
        values={clean(item['cell']['raw_text']) for item in items}
        if len(values)!=1:
            result['issues'].append(field+'_multiple_or_conflicting_columns');continue
        value=next(iter(values))
        result['field_evidence'][field]=items
        if not value:continue
        result[field]=[value] if field in {'active_ingredients','strengths'} else value
    if clean(result['medication_name'] or '').upper()!='MYPARA 500':
        raise ValueError('The mapped medication-name field is not exactly MYPARA 500')
    ingredient_items=buckets.get('active_ingredients',[])
    if ingredient_items and any('ham luong' in header_key(i['header'].get('header_text')) for i in ingredient_items):
        raw=result['active_ingredients'][0] if result['active_ingredients'] else ''
        matches=list(re.finditer(r'(?<![\w.,+\-])(\d+(?:[.,]\d+)?)\s*(mcg|mg|g)\b',raw,re.I))
        if len(matches)==1 and not clean(raw[matches[0].end():]) and clean(raw[:matches[0].start()]):
            match=matches[0]
            result['active_ingredients']=[clean(raw[:match.start()])]
            combined=clean(match[0])
            if result['strengths'] and result['strengths']!=[combined]:result['issues'].append('combined_and_separate_strength_conflict')
            else:result['strengths']=[combined];result['field_evidence']['strengths']=ingredient_items
        else:
            result['issues'].append('combined_composition_requires_review')
            result['active_ingredients']=None
    if result['strengths']:
        value=result['strengths'][0]
        match=re.fullmatch(r'(\d+(?:[.,]\d+)?)\s*(mg|mcg|g)(?:\s*/\s*(\d+(?:[.,]\d+)?)\s*(ml|l))?',value,re.I)
        if not match or Decimal(match[1].replace(',','.'))<=0 or (match[3] and Decimal(match[3].replace(',','.'))<=0):
            result['issues'].append('strength_unit_missing_or_unsupported');result['strengths']=None
    for field in ('active_ingredients','strengths'):
        if result[field] and re.search(r'[;+]',result[field][0]):
            result['issues'].append('combination_association_not_verified');result[field]=None
    if result['registration_number']:
        parsed=registration_cell(result['registration_number'])
        if parsed:
            result['registration_number']=parsed['primary']
            result['registration_status_displayed']=parsed['status']
            if parsed['old']:
                if result['previous_registration_number'] and result['previous_registration_number']!=parsed['old']:
                    result['previous_registration_number']=None
                    result['issues'].append('previous_registration_number_conflicting_sources')
                elif 'previous_registration_number_multiple_or_conflicting_columns' not in result['issues']:
                    result['previous_registration_number']=parsed['old']
                    result['field_evidence']['previous_registration_number']=result['field_evidence']['registration_number']
            if parsed['status']:
                result['field_evidence']['registration_status_displayed']=result['field_evidence']['registration_number']
        else:
            result['issues'].append('registration_number_ambiguous_or_unsupported');result['registration_number']=None
    for field in ('registration_number','previous_registration_number'):
        if result[field] and not re.fullmatch(REG_ID,result[field],re.I):
            result['issues'].append(field+'_ambiguous_or_unsupported');result[field]=None
    if result['registration_expiry'] and not re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}',result['registration_expiry']):
        result['issues'].append('expiry_not_an_explicit_date');result['registration_expiry']=None
    elif result['registration_expiry']:
        try:
            datetime.strptime(result['registration_expiry'],'%d/%m/%Y' if '/' in result['registration_expiry'] else '%Y-%m-%d')
        except ValueError:
            result['issues'].append('expiry_invalid_calendar_date');result['registration_expiry']=None
    for field in FIELDS:
        if result[field] is None:result['issues'].append(field+'_unavailable')
    result['issues']=sorted(set(result['issues']))
    result['issues'].extend(['independent_source_review_pending','current_registration_events_not_reconciled','data_reuse_permissions_unresolved'])
    return result


def compare_pdf(record,reference_path):
    reference=json.loads(Path(reference_path).read_text(encoding='utf-8'))
    expected=next(r for r in reference['records'] if r['id']=='mypara')
    actual={'medication_name':record['medication_name'],'ingredients':record['active_ingredients'],'strengths':record['strengths'],
            'dosage_form':record['dosage_form'],'manufacturer':record['manufacturer'],
            'registration_numbers':[record[f] for f in ('registration_number','previous_registration_number') if record[f]]}
    def norm(value):
        if isinstance(value,list):return sorted(norm(v) for v in value)
        text=(clean(value) or '').casefold()
        return re.sub(r'(?<=\d)\s+(?=mg|mcg|g\b)','',text)
    outcomes={field:'unavailable' if value is None or value==[] else 'matches_prior_pdf' if norm(value)==norm(expected[field]) else 'discrepancy_review_required'
              for field,value in actual.items()}
    return {'reference_basis':expected['review_method']+'; not independently human/clinician verified',
            'comparison_type':'cross_source_agreement_not_extraction_accuracy',
            'field_outcomes':outcomes,'actual_values':actual,'previous_pdf_values':{field:expected[field] for field in actual},
            'strict_agreements':sum(v=='matches_prior_pdf' for v in outcomes.values()),'field_groups':len(outcomes),
            'explicit_previous_identifier_matches_pdf':record['previous_registration_number'] in expected['registration_numbers'],
            'manufacturer_punctuation_only_difference':re.sub(r'[^\w]','',norm(record['manufacturer']))==re.sub(r'[^\w]','',norm(expected['manufacturer'])),
            'current_authorization_verified':False,'values_repaired_from_pdf':False}


def hybrid_schema_candidate(record):
    """Isolated projection into existing Module 2 shape; no pipeline/import/admission."""
    strengths=record['strengths'] or []
    names=record['active_ingredients'] or []
    ingredients=[{'inn_name':name,'strength':strengths[i] if i<len(strengths) else None,
                  'international_name':None,'rxcui':None,'tty':None,'status':'REVIEW_REQUIRED',
                  'evidence':record['field_evidence'].get('active_ingredients',[])+record['field_evidence'].get('strengths',[]),
                  'candidates':[]} for i,name in enumerate(names)]
    return {'schema_version':'module2.hybrid.v1','input':{'name_raw':record['medication_name'],'strength_raw':strengths[0] if len(strengths)==1 else None},
            'status':'REVIEW_REQUIRED','verification_scope':'machine_captured_local_identity_candidate_only',
            'local_medication':{'reference_id':None,'brand_name':record['medication_name'],
              'strength':strengths[0] if len(strengths)==1 else None,'dosage_form':record['dosage_form'],
              'manufacturer':record['manufacturer'],'route':None,'rxcui':None,
              'verification_method':'user_supplied_dom_capture_machine_conversion',
              **{f:record[f] for f in ('registration_number','previous_registration_number','registration_expiry','packaging')}},
            'ingredients':ingredients,'product_rxcui':None,'evidence':[{'source_url':record['source_url'],
              'capture_sha256':record.get('capture_sha256'),'captured_at_utc':record['captured_at_utc'],
              'raw_source':record['raw_source']}],'issues':list(record['issues']),
            'requires_user_review':True,'automatic_reference_acceptance':False,
            'current_authorization':'NOT_VERIFIED','data_reuse_permissions':'UNRESOLVED'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--compare-pdf',type=Path)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a new output path; never replace previous results')
    raw=args.input.read_text(encoding='utf-8-sig')
    capture=capture_from_html(raw) if args.input.suffix.lower() in {'.html','.htm'} else load_json(raw)
    record=convert(capture)
    record['capture_sha256']=hashlib.sha256(args.input.read_bytes()).hexdigest()
    if args.compare_pdf:
        record['pdf_comparison']=compare_pdf(record,args.compare_pdf)
        for field,outcome in record['pdf_comparison']['field_outcomes'].items():
            if outcome=='discrepancy_review_required':record['issues'].append('prior_pdf_'+field+'_discrepancy')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':record['verification_status'],'issues':record['issues']},ensure_ascii=False))


if __name__=='__main__':main()
