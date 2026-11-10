"""Compose individually reviewed research facts without changing bulk DAV ingestion.

Each shard retains the existing CuratedFactReference evidence and matching checks.
Source product codes disambiguate real presentations; no fuzzy names or insulin
form collapse is introduced. Clinical/current regulatory verification stays false.
"""
from copy import deepcopy
import hashlib
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from .curated import CuratedFactReference
from .terminology import DirectDDInter

class ResearchSupplementReference:
    def __init__(self,path,*,base=None):
        self.path=Path(path)
        artifact=json.loads(self.path.read_text(encoding='utf-8'))
        if artifact.get('schema_version')!='module2.research_supplement.v1':
            raise ValueError('Unsupported research supplement')
        scopes={1:'diabetes_DDI_research',2:'cardiovascular_DDI_research',
                3:'common_medications_DDI_research'}
        if artifact.get('batch') not in scopes or artifact.get('scope')!=scopes[artifact['batch']]:
            raise ValueError('Research supplement must use its declared batch scope')
        self.reference_kind={1:'diabetes_research_supplement',
                             2:'cardiovascular_research_supplement',
                             3:'common_medications_research_supplement'}[artifact['batch']]
        self.references=[]
        self.products=[]
        seen=set()
        for item in artifact['shards']:
            ref=CuratedFactReference(self.path.parent/item['path'])
            if len(ref.products)!=1:raise ValueError('One individually reviewed presentation per research shard')
            product=ref.products[0]['product']
            code=product.get('source_product_code')
            if not code or code in seen:raise ValueError('Unique source presentation code required')
            if item.get('source_product_code')!=code:
                raise ValueError('Shard presentation code does not match its manifest')
            seen.add(code)
            self.references.append(ref);self.products.extend(ref.products)
        self.base=base

    def terminology(self,dataset):
        """Load the supplement's explicit equivalences after checking local evidence."""
        entries=json.loads((self.path.parent/'reviewed_equivalences.json').read_text(encoding='utf-8'))
        for entry in entries:
            for proof in entry.get('evidence',[]):
                if not proof.get('source_url') or not proof.get('path'):
                    raise ValueError('Research equivalence requires a retained source artifact')
                if hashlib.sha256(Path(proof['path']).read_bytes()).hexdigest()!=proof.get('sha256'):
                    raise ValueError('Research equivalence source hash mismatch')
        return DirectDDInter(dataset,entries)

    def lookup(self,medication):
        results=[]
        code=medication.get('source_product_code')
        for ref in self.references:
            product=ref.products[0]['product']
            if code and code!=product['source_product_code']:continue
            results.append(ref.lookup(medication))
        if self.base is not None and not code:results.append(self.base.lookup(medication))
        candidates=[]
        for result in results:candidates.extend(result['candidates'])
        result={'identification_status':'UNRESOLVED','lookup_method':'SOURCE_SUPPORTED_RESEARCH_FACTS',
            'candidates':deepcopy(candidates),'suggestions':[],'issues':[],'current_authorization':'UNKNOWN',
            'reference_kind':self.reference_kind,'identity_verification_scope':'source_supported_historical_product_facts_only',
            'clinical_verified':False,'regulatory_current_verified':False}
        if len(candidates)==1:
            result['identification_status']='VERIFIED'
        elif candidates:
            result.update(identification_status='REVIEW_REQUIRED',issues=['MULTIPLE_SOURCE_SUPPORTED_PRESENTATIONS'])
        else:
            result['issues'].append('NO_CANDIDATE_SATISFIES_SUPPLIED_IDENTITY')
        return result

    def close(self):
        for ref in self.references:ref.close()
        if self.base is not None:self.base.close()
