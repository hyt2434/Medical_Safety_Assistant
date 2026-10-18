"""Shared offline test paths and source-preserving evaluation queries."""
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import sys
WORKSPACE = PROJECT_ROOT
PROJECT = PROJECT_ROOT
DOCS = PROJECT_ROOT/'tests/artifacts/preprocessing'
sys.path.insert(0,str(PROJECT))
from module2_medications.unified import (read,write,default_config,discover_sources,
    normalize_product,normalized_form,normalized_strength,strength_signature,preprocess,UnifiedMedicationReference)
from module2_medications.research import ResearchSupplementReference
from module2_medications.service import identify,assess_prescriptions
from module2_medications.terminology import load_ddinter,DirectDDInter
from module2_medications.text import key
from shared.dav_import.common import file_hash as sha

def native_query(p, **changes):
    return {k:p.get(k) for k in ('brand_name','source_product_code','strength','dosage_form')} | changes

def canonical_query(p, **changes):
    normalized = {'strength':normalized_strength(p.get('strength')), 'dosage_form':normalized_form(p.get('dosage_form'))}
    return native_query(p,**(normalized | changes))

def source_products():
    paths = discover_sources(PROJECT)
    ref = ResearchSupplementReference(paths[-1])
    try: return [e['product'] for e in ref.products]
    finally: ref.close()
