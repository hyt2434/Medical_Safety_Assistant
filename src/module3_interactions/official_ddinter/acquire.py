"""Download only public CSV hyperlinks explicitly present on the official page."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import re
import shutil
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from shared.dav_import.common import file_hash

BASE = 'https://ddinter2.scbdd.com/'
LICENSE = {'name': 'CC BY-NC-SA 4.0', 'url': BASE + 'terms/',
           'use_context': 'non-commercial university research; attribution retained'}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.words = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])

    def handle_data(self, data):
        self.words.append(data)

    @property
    def text(self):
        return ' '.join(' '.join(self.words).split())


def _request(url, target):
    if target.exists():
        raise ValueError('Existing official source bytes are immutable: ' + str(target))
    started = datetime.now(timezone.utc).isoformat()
    request = Request(url, headers={'User-Agent': 'MedicationSafetyAssistant-AcademicDataset/1.0'})
    partial = target.with_suffix(target.suffix + '.partial')
    with urlopen(request, timeout=60) as response:
        resolved = response.geturl()
        if urlparse(resolved).scheme != 'https' or urlparse(resolved).hostname != 'ddinter2.scbdd.com':
            raise ValueError('Unexpected off-site redirect; acquisition stopped')
        if response.status != 200:
            raise ValueError('Official download did not return HTTP 200')
        with partial.open('xb') as stream:
            shutil.copyfileobj(response, stream)
        metadata = {'source_url': url, 'resolved_url': resolved, 'http_status': response.status,
            'content_type': response.headers.get('Content-Type'), 'last_modified': response.headers.get('Last-Modified'),
            'retrieval_started_utc': started, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}
    partial.replace(target)
    return {**metadata, 'filename': target.name, 'sha256': file_hash(target), 'bytes': target.stat().st_size}


def statistics(text):
    patterns = {'drug_entries': r'([\d,]+)\s+approved drug entries',
                'distinct_drugs': r'([\d,]+)\s+distinct drugs',
                'ddi_records': r'([\d,]+)\s+DDI records'}
    result = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if not match:
            raise ValueError('Published statistics format changed: ' + name)
        result[name] = int(match[1].replace(',', ''))
    return result


def acquire(project, output):
    project, output = Path(project), Path(output)
    old = project / 'data/reference/provenance/module2_api_quicktest/ingredient_ddinter_poc/evidence'
    old_manifest = json.loads((old / 'approved_download_manifest.json').read_text(encoding='utf-8-sig'))
    old_file = old / old_manifest['filename']
    if old_manifest['sha256'].lower() != file_hash(old_file):
        raise ValueError('Existing Category-A evidence hash mismatch; do not replace prior evidence')
    # Audit is recorded before any network access.
    output.mkdir(parents=True, exist_ok=False)
    existing = [{'filename': old_file.name, 'path': str(old_file.resolve()), 'sha256': file_hash(old_file),
        'bytes': old_file.stat().st_size, 'original_manifest_sha256': file_hash(old / 'approved_download_manifest.json')}]
    (output / 'existing_file_audit.json').write_text(json.dumps(existing, indent=2)+'\n', encoding='utf-8')
    pages = {}
    for name in ('download', 'statistics', 'terms'):
        pages[name] = _request(BASE + name + '/', output / (name + '.html'))
    download = Page()
    download.feed((output / 'download.html').read_text(encoding='utf-8'))
    urls = {}
    for href in download.links:
        url = urljoin(BASE + 'download/', href)
        parsed = urlparse(url)
        filename = Path(parsed.path).name
        if not filename.endswith('.csv'):
            continue
        if (parsed.scheme != 'https' or parsed.hostname != 'ddinter2.scbdd.com'
                or not re.fullmatch(r'ddinter_downloads_code_[A-Z]\.csv', filename)):
            raise ValueError('Unexpected CSV hyperlink; review actual offered file: ' + url)
        if filename in urls and urls[filename] != url:
            raise ValueError('Conflicting official links for one filename')
        urls[filename] = url
    if not urls:
        raise ValueError('No explicit official CSV links found')
    terms = Page()
    terms.feed((output / 'terms.html').read_text(encoding='utf-8'))
    if 'Attribution-NonCommercial-ShareAlike 4.0' not in terms.text:
        raise ValueError('Official license wording changed; inspect before using data')
    stats = Page()
    stats.feed((output / 'statistics.html').read_text(encoding='utf-8'))
    artifacts = []
    for filename, url in sorted(urls.items()):
        if filename == old_file.name:
            if url != old_manifest['source_url']:
                raise ValueError('Existing artifact URL differs from current official hyperlink')
            shutil.copyfile(old_file, output / filename)
            artifacts.append({'filename': filename, 'source_url': url, 'sha256': file_hash(output / filename),
                'bytes': old_file.stat().st_size, 'retrieved_at_utc': old_manifest['completed_at_utc'],
                'last_modified': old_manifest.get('response_last_modified'), 'acquisition': 'reused_existing_original_bytes',
                'original_manifest_sha256': file_hash(old / 'approved_download_manifest.json'), 'license': LICENSE})
        else:
            artifacts.append({**_request(url, output / filename), 'acquisition': 'official_download_page_hyperlink',
                              'license': LICENSE})
    manifest = {'schema_version': 'ddinter.official_collection.v1',
        'collection_created_at_utc': datetime.now(timezone.utc).isoformat(), 'official_pages': pages,
        'published_statistics': statistics(stats.text), 'artifacts': artifacts,
        'all_explicit_csv_hyperlinks_acquired': len(artifacts) == len(urls),
        'official_file_release_version_independently_verified': False, 'license': LICENSE,
        'scope': 'all CSVs explicitly offered on the saved official download page',
        'authorization': 'User requested acquisition of all missing official DDInter CSV downloads',
        'no_private_endpoints_or_access_bypass': True}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'collection': str(output), 'files': len(artifacts), 'published_statistics': manifest['published_statistics']}))
    return manifest
