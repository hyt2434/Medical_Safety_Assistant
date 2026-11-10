"""Operator attestation checks, not a substitute for institutional/legal review."""
from datetime import date, datetime
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from urllib.parse import urlparse
import json
from .common import file_hash


def authorize(manifest_path, input_path, as_of):
    manifest_path = Path(manifest_path)
    m = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if m.get('schema_version') != 'dav.authorization.v1':
        raise ValueError('Unsupported authorization manifest')
    if m.get('artifact_sha256') != file_hash(input_path):
        raise ValueError('Export hash differs from authorized artifact')
    kind = m.get('source_kind')
    if kind not in {'dav', 'synthetic'}:
        raise ValueError('source_kind must be dav or synthetic')
    snapshot = datetime.fromisoformat(m.get('snapshot_at', ''))
    if snapshot.tzinfo is None:
        raise ValueError('Source snapshot_at needs a timezone')
    if kind == 'synthetic':
        if not m.get('source_url', '').startswith('synthetic://') or m.get('acquisition_method') != 'generated_fixture':
            raise ValueError('Synthetic source must be generated_fixture and synthetic://')
        if m.get('synthetic_fixture') is not True:
            raise ValueError('Synthetic manifest must be explicitly labelled')
        return m
    if m.get('synthetic_fixture') is not False:
        raise ValueError('Real manifest must declare synthetic_fixture=false')
    if m.get('acquisition_method') not in {'approved_file_export', 'dav_supplied_dataset'}:
        raise ValueError('Approved offline acquisition method required; no scraping/API method')
    host = urlparse(m.get('source_url', '')).hostname or ''
    if host != 'dav.gov.vn' and not host.endswith('.dav.gov.vn'):
        raise ValueError('DAV provenance requires official DAV source URL')
    auth = m.get('authorization', {})
    if auth.get('status') != 'APPROVED' or not auth.get('approved_by') or not auth.get('reference'):
        raise ValueError('Recorded source authorization is required')
    rights = auth.get('rights', {})
    if any(rights.get(right) is not True for right in ('extract', 'transform', 'store')):
        raise ValueError('Explicit extract/transform/store rights required')
    check = date.fromisoformat(as_of)
    if check < date.fromisoformat(auth.get('valid_from', '')) or check > date.fromisoformat(auth.get('valid_until', '')):
        raise ValueError('Source authorization is not valid on --as-of')
    evidence = auth.get('evidence', {})
    evidence_path = (manifest_path.parent / evidence.get('path', '')).resolve()
    if not evidence_path.is_file() or evidence.get('sha256') != file_hash(evidence_path):
        raise ValueError('Authorization evidence missing or hash mismatch')
    if not auth.get('approved_scope') or not m.get('license_or_permission'):
        raise ValueError('Document approved dataset scope and permission terms')
    return m
