"""Conservative adapter for numbered, printed medication columns.

Only Tesseract words/geometry are inputs. Never reads a drug dictionary or truth.
Returns None for older layouts so their existing adapter stays available.
"""
import re


def extract_printed_rows(raw):
    words=raw['words']
    starters=sorted([w for w in words if re.fullmatch(r'\d+[.)]',w['text'])],key=lambda w:w['bbox']['y0'])
    # Product names may contain "Strength". A column header must precede rows.
    first_y=starters[0]['bbox']['y0'] if starters else float('inf')
    headers=[w for w in words if w['text'].casefold().strip(':')=='strength' and w['bbox']['y0']<first_y]
    if len(headers)!=1: return None
    cutoff=headers[0]['bbox']['x0']-35
    if not starters: raise ValueError('No numbered medication rows found')
    medications=[]
    for i,starter in enumerate(starters):
        y=starter['bbox']['y0']
        line=sorted([w for w in words if abs(w['bbox']['y0']-y)<25 and w['bbox']['x0']>starter['bbox']['x1']],key=lambda w:w['bbox']['x0'])
        names=[w for w in line if w['bbox']['x0']<cutoff]
        strengths=[w for w in line if w['bbox']['x0']>=cutoff]
        name=' '.join(w['text'] for w in names) or None
        strength=' '.join(w['text'] for w in strengths) or None
        next_y=starters[i+1]['bbox']['y0'] if i+1<len(starters) else y+160
        below=[w for w in words if y+30<w['bbox']['y0']<next_y-20]
        anchors=[w for w in below if w['text'].casefold() in ('form:','form')]
        form_words=[]
        if len(anchors)==1:
            anchor=anchors[0]
            form_words=sorted([w for w in below if abs(w['bbox']['y0']-anchor['bbox']['y0'])<20 and w['bbox']['x0']>anchor['bbox']['x1']],key=lambda w:w['bbox']['x0'])
        form=' '.join(w['text'] for w in form_words) or None
        uncertain=[]
        if not name: uncertain.append('name_raw')
        if not strength: uncertain.append('strength_raw')
        if not form: uncertain.append('dosage_form_raw')
        if any(w['confidence']<85 for w in names+strengths+form_words): uncertain.append('ocr_low_confidence')
        medications.append({'name_raw':name,'strength_raw':strength,'dosage_form_raw':form,
            'dose_raw':None,'route_raw':None,'frequency_raw':None,'duration_raw':None,'quantity_raw':None,
            'instructions_raw':None,'administrations':[],
            'evidence_text':' '.join(w['text'] for w in line+form_words),'uncertain_fields':uncertain})
    return {'medications':medications,'document_instructions_raw':[],
        'warnings':['Printed enumerated rows only; literal fields require confirmation'], 'requires_user_review':True}
