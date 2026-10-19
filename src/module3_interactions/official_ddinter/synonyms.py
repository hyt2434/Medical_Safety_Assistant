"""Small explicit official synonym evidence; no heuristic chemical equivalence."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import re
from .acquire import _request, Page
from shared.dav_import.common import file_hash


def capture_official_synonyms(project, collection):
    collection = Path(collection).resolve()
    output = collection / 'official_synonyms.json'
    if output.exists():
        raise ValueError('Existing synonym evidence is immutable')
    prior = Path(project).resolve() / 'data/reference/provenance/module2_api_quicktest/ingredient_ddinter_poc/evidence/ddinter_public_record.json'
    records = deepcopy(json.loads(prior.read_text(encoding='utf-8'))['records'])
    url = 'https://ddinter2.scbdd.com/server/drug-detail/DDInter20/'
    html = collection / 'DDInter20.html'
    response_path = collection / 'DDInter20.response.json'
    if html.exists():
        # Preserve bytes from an interrupted validation rather than fetching again.
        metadata = json.loads(response_path.read_text(encoding='utf-8')) if response_path.exists() else {
            'filename': html.name, 'source_url': url, 'sha256': file_hash(html), 'bytes': html.stat().st_size,
            'retrieved_at_utc': datetime.fromtimestamp(html.stat().st_mtime, timezone.utc).isoformat(),
            'retrieval_timestamp_basis': 'local saved-file completion timestamp; response headers unavailable',
            'acquisition': 'reuse_page_bytes_saved_by_prior_capture_attempt'}
    else:
        metadata = _request(url, html)
    if not response_path.exists():
        response_path.write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    page = Page()
    page.feed((collection / 'DDInter20.html').read_text(encoding='utf-8'))
    if not (re.search(r'Drugs Information:\s*Acetylsalicylic acid', page.text) and
            re.search(r'ID\s+DDInter20\b', page.text) and
            re.search(r'Also known as _?Aspirin_?,\s+acetylsalicylic acid', page.text)):
        raise ValueError('Official identity/synonym statement changed; do not infer a relation')
    records.append({'ddinter_id': 'DDInter20', 'name': 'Acetylsalicylic acid', 'source_url': url,
        'synthetic': False, 'review_method': 'assistant_explicit_official_identity_statement_review',
        'independent_clinical_review': False,
        'name_evidence': {'section': 'Drugs Information', 'value': 'Acetylsalicylic acid'},
        'identifier_evidence': {'section': 'Basic Information', 'value': 'DDInter20'},
        'synonyms': [{'name': 'Aspirin', 'verification': 'explicit_official_record_synonym', 'source_url': url,
            'section': 'Description', 'excerpt': 'Also known as _Aspirin_, acetylsalicylic acid'}]})
    snapshot = {'schema_version': 'ddinter.official_synonyms.v1',
        'reviewed_at_utc': datetime.now(timezone.utc).isoformat(), 'records': records,
        'source_artifacts': [{'path': str(prior), 'sha256': file_hash(prior), 'kind': 'preserved_prior_official_page_transcription'},
            {'path': str(collection / 'DDInter20.html'), 'sha256': metadata['sha256'], 'kind': 'official_page_bytes', **metadata}],
        'scope': 'explicit terminology synonyms only; no product or salt/base equivalence',
        'license': {'name': 'CC BY-NC-SA 4.0', 'url': 'https://ddinter2.scbdd.com/terms/'}}
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return output
