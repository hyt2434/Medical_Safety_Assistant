"""Independent official SQL truth for new unified-reference integration cases."""
from .common import *
from itertools import combinations
import json
import sqlite3

def prepare(output, products, mapper):
    def select(brand):
        return next(p for p in products if key(p['brand_name']) == key(brand) or p.get('source_search_priority') == brand)
    index = PROJECT/'data/reference/ddinter2/official_20261013/official.sqlite'
    cases = []; index_sha = sha(index)
    with sqlite3.connect(index.resolve().as_uri()+'?mode=ro',uri=True) as db:
        def identifier(name):
            if name is None: return None
            rows = db.execute("SELECT DISTINCT i.identifier FROM identities i LEFT JOIN json_each(i.identity_json,'$.synonyms') s "
                              "WHERE json_extract(i.identity_json,'$.name')=? COLLATE NOCASE OR s.value=? COLLATE NOCASE",(name,name)).fetchall()
            if len(rows)!=1: raise ValueError('Independent SQL identity missing/ambiguous: '+name)
            return rows[0][0]
        def source_rows(ids):
            rows = []
            for a,b in combinations(sorted({i for i in ids if i}),2):
                rows.extend([dict(zip(('filename','row_number','id_a','name_a','id_b','name_b','level'),r)) for r in
                             db.execute('SELECT filename,row_number,id_a,name_a,id_b,name_b,level FROM source_rows WHERE low_id=? AND high_id=? ORDER BY filename,row_number',(a,b))])
            return rows
        def add(group,title,drugs,names,kind='supported',confirmed=True):
            ids = [identifier(n) for n in names]
            cases.append({'id':f'TC{len(cases)+1:02d}','group':group,'title':title,'kind':kind,
                          'input':{'medications':drugs},'confirmed':confirmed,'expected_component_ids':ids,
                          'expected_sql_rows':source_rows(ids),'expected_index_sha256':index_sha})
        add('Diabetes','Lantus + Janumet',[canonical_query(select('LANTUS')),canonical_query(select('JANUMET'))],
            ['Insulin glargine','Sitagliptin','Metformin'])
        add('Diabetes','Synjardy + Janumet: duplicate Metformin',[canonical_query(select('SYNJARDY')),canonical_query(select('JANUMET'))],
            ['Empagliflozin','Metformin','Sitagliptin','Metformin'],'duplicate')
        add('Diabetes','Ryzodeg premix + Telmisartan',[canonical_query(select('RYZODEG')),canonical_query(select('MICARDIS'))],
            ['Insulin degludec','Insulin aspart (aspart)','Telmisartan'])
        add('Diabetes','Mounjaro unresolved + Lantus',[canonical_query(select('MOUNJARO')),canonical_query(select('LANTUS'))],
            [None,'Insulin glargine'],'unresolved_mapping')
        add('Cardiovascular','Warfarin + Ibuprofen',[canonical_query(select('A.T Warfarin 1 mg')),canonical_query(select('IBUPROFEN'))],
            ['Warfarin','Ibuprofen'])
        add('Cardiovascular','Apixaban + Naproxen',[canonical_query(select('ELIQUIS')),canonical_query(select('NAPROXEN'))],
            ['Apixaban','Naproxen'])
        add('Cardiovascular','Clopidogrel + Omeprazole',[canonical_query(select('PLAVIX')),canonical_query(select('OMEPRAZOLE'))],
            ['Clopidogrel','Omeprazole'])
        add('Cardiovascular','Entresto + Eplerenone',[canonical_query(select('ENTRESTO')),canonical_query(select('INSPRA'))],
            ['Sacubitril','Valsartan','Eplerenone'])
        add('Cardiovascular','Cozaar + Hyzaar: duplicate Losartan',[canonical_query(select('COZAAR')),canonical_query(select('HYZAAR'))],
            ['Losartan','Losartan','Hydrochlorothiazide'],'duplicate')
        add('Common medications','Sulfamethoxazole/Trimethoprim + Warfarin',
            [canonical_query(select('SULFAMETHOXAZOLE AND TRIMETHOPRIM')),canonical_query(select('A.T Warfarin 1 mg'))],
            ['Sulfamethoxazole','Trimethoprim','Warfarin'])
        add('Common medications','Symbicort + Clarithromycin',[canonical_query(select('SYMBICORT')),canonical_query(select('CLARITHROMYCIN'))],
            ['Budesonide','Formoterol','Clarithromycin'])
        add('Common medications','Tacrolimus + Fluconazole',[canonical_query(select('PROGRAF')),canonical_query(select('DIFLUCAN'))],
            ['Tacrolimus','Fluconazole'])
        add('Common medications','Levetiracetam + Levofloxacin: absent pair',[canonical_query(select('KEPPRA')),canonical_query(select('LEVAQUIN'))],
            ['Levetiracetam','Levofloxacin'],'missing_pair')
        add('Common medications','Escitalopram + Ondansetron',[canonical_query(select('LEXAPRO')),canonical_query(select('ONDANSETRON'))],
            ['Escitalopram','Ondansetron'])
        add('Common medications','Generic full Janumet composition + Fluconazole',
            [canonical_query(select('JANUMET'),brand_name=None,generic_name='Sitagliptin + Metformin'),canonical_query(select('DIFLUCAN'))],
            ['Sitagliptin','Metformin','Fluconazole'])
        # Lower severities are selected from actual SQL among explicitly labeled one-component products.
        single = {}
        for p in products:
            n, parsed = normalize_product(p)
            if len(parsed['ingredients']) != 1: continue
            mapped = mapper.match(parsed['ingredients'][0]['normalized_ingredient'])
            if mapped['mapping_status']=='VERIFIED': single.setdefault(mapped['ddinter_id'],p)
        ids = sorted(single); ph = ','.join('?' for _ in ids)
        for level in ('Moderate','Minor'):
            r = db.execute(f'SELECT id_a,id_b,name_a,name_b FROM source_rows WHERE level=? AND id_a IN ({ph}) AND id_b IN ({ph}) ORDER BY name_a DESC,name_b LIMIT 1',[level]+ids+ids).fetchone()
            if not r: raise ValueError('No supported '+level+' pair')
            add('Common medications',r[2]+' + '+r[3]+' (official '+level+')',
                [canonical_query(single[r[0]]),canonical_query(single[r[1]])],[r[2],r[3]])
        add('Unknown and duplicate cases','Ultracet + Acetaminophen: duplicate ingredient',
            [canonical_query(select('ULTRACET')),canonical_query(select('TYLENOL EXTRA STRENGTH'))],
            ['Tramadol','Acetaminophen','Acetaminophen'],'duplicate')
        add('Unknown and duplicate cases','Unknown medication + Lantus',
            [{'brand_name':'UNREADABLE MEDICATION'},canonical_query(select('LANTUS'))],[None,'Insulin glargine'],'unknown')
        add('Unknown and duplicate cases','Ambiguous Ryzodeg device + Telmisartan',
            [canonical_query(select('RYZODEG'),source_product_code=None),canonical_query(select('MICARDIS'))],
            [None,None,'Telmisartan'],'ambiguous')
        add('Unknown and duplicate cases','Incorrect insulin concentration + Ibuprofen',
            [canonical_query(select('LANTUS'),strength='900 IU/mL'),canonical_query(select('IBUPROFEN'))],
            [None,'Ibuprofen'],'wrong_qualifier')
        add('Unknown and duplicate cases','Uncertain Escitalopram transcription + Ondansetron',
            [canonical_query(select('LEXAPRO'),uncertain_fields=['strength']),canonical_query(select('ONDANSETRON'))],
            [None,'Ondansetron'],'uncertain')
        add('Unknown and duplicate cases','Unconfirmed Warfarin + Ibuprofen',
            [canonical_query(select('A.T Warfarin 1 mg')),canonical_query(select('IBUPROFEN'))],
            ['Warfarin','Ibuprofen'],'unconfirmed',False)
        first_raw = json.loads(next((PROJECT/'data/raw/dav/records.jsonl').open(encoding='utf-8-sig')))
        add('Unknown and duplicate cases','Unreviewed DAV observation + Lantus',
            [{k:first_raw[k] for k in ('brand_name','registration_number','strength','dosage_form')},canonical_query(select('LANTUS'))],
            [None,'Insulin glargine'],'unadmitted_dav')
        add('Unknown and duplicate cases','Ferrous sulfate unresolved + Sertraline',
            [canonical_query(select('FERROUS SULFATE')),canonical_query(select('ZOLOFT'))],[None,'Sertraline'],'unresolved_mapping')
        add('Cardiovascular','One CLI input across all three batches',
            [canonical_query(select('LANTUS')),canonical_query(select('A.T Warfarin 1 mg')),canonical_query(select('IBUPROFEN'))],
            ['Insulin glargine','Warfarin','Ibuprofen'])
    levels = {r['level'] for c in cases for r in c['expected_sql_rows']}
    if not {'Major','Moderate','Minor'}.issubset(levels): raise ValueError('Required severities unavailable')
    write(output/'official_sql_ground_truth.json',cases)
    return cases
