"""Relocated actual local OCR invocation and conservative legacy row adapter."""
import hashlib
import json
import re
import subprocess
from shared.paths import ProjectPath as Path

def read(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def local_ocr(image,output,cid,log):
    image = Path(image)
    # Defined below when a local OCR backend is provisioned; never substitute truth.
    script=Path(__file__).parent/'node/local_ocr.cjs'
    destination=output/f'{cid}_ocr_evidence.json'
    process=subprocess.run(['node',str(script),str(image),str(destination)],capture_output=True,text=True,encoding='utf-8',timeout=180)
    if process.returncode:raise RuntimeError('Local OCR process failed; see backend availability')
    raw=read(destination)
    # The shared local printed-row adapter uses OCR geometry only. Keep the
    # historical Vietnamese layout adapter below for existing artifacts/callers.
    from .local_ocr_rows import extract_printed_rows, find_numbered_row_starters
    printed = extract_printed_rows(raw)
    if printed is not None:
        log.log(f'[{cid}] Local OCR actual rows={len(printed["medications"])}; confidence={raw["confidence"]}; evidence={destination}')
        return printed,{'provider':'Tesseract.js','language':'vie+eng','numeric_ocr_confidence':raw['confidence'],
            'evidence_path':str(destination),'evidence_sha256':sha(destination),
            'limitation':'Printed enumerated rows only; mandatory transcription confirmation'}
    # Conversion reads OCR rows/coordinates alone, never a truth/reference product list.
    medications=[]
    words=raw['words']
    starters=find_numbered_row_starters(words)
    for index,starter in enumerate(sorted(starters,key=lambda w:w['bbox']['y0'])):
        y=starter['bbox']['y0']; line=[w for w in words if abs(w['bbox']['y0']-y)<25 and w['bbox']['x0']>starter['bbox']['x1']]
        name_words=sorted([w for w in line if w['bbox']['x0']<1100],key=lambda w:w['bbox']['x0'])
        strength_words=sorted([w for w in line if w['bbox']['x0']>=1100],key=lambda w:w['bbox']['x0'])
        name=' '.join(w['text'] for w in name_words)
        dose=' '.join(w['text'] for w in strength_words) or None
        next_y=min((s['bbox']['y0'] for s in starters if s['bbox']['y0']>y),default=y+190)
        form_words=sorted([w for w in words if y+35<w['bbox']['y0']<next_y-25],key=lambda w:(round(w['bbox']['y0']/20),w['bbox']['x0']))
        evidence=' '.join(w['text'] for w in name_words+strength_words+form_words)
        uncertain=[]
        if not name:uncertain.append('name_raw')
        if not dose or not re.fullmatch(r'\d+(?:[.,]\d+)?\s*(mg|g|mcg)',dose,re.I):uncertain.append('strength_raw')
        if any(w['confidence']<85 for w in name_words+strength_words):uncertain.append('ocr_low_confidence')
        medications.append({'name_raw':name or None,'strength_raw':dose,'dose_raw':None,'route_raw':None,
            'frequency_raw':None,'duration_raw':None,'quantity_raw':None,'instructions_raw':None,
            'administrations':[],'evidence_text':evidence,'uncertain_fields':uncertain})
    if not medications:raise ValueError('No unambiguous enumerated medication rows from OCR')
    result={'medications':medications,'document_instructions_raw':[],
        'warnings':['Local OCR row adapter is limited to printed enumerated name/strength/form layouts; all fields require confirmation'],
        'requires_user_review':True}
    log.log(f'[{cid}] Local OCR actual rows={len(medications)}; confidence={raw["confidence"]}; evidence={destination}')
    return result,{'provider':'Tesseract.js','language':'vie+eng','numeric_ocr_confidence':raw['confidence'],
        'evidence_path':str(destination),'evidence_sha256':sha(destination),
        'limitation':'Minimal printed-test-layout adapter; no dosing inference; mandatory transcription confirmation'}


