"""Streaming export readers. No formulas, macros, external links, or network execution."""
import csv
import json
import posixpath
import re
from shared.paths import ProjectPath as Path, PROJECT_ROOT
import xml.etree.ElementTree as ET
from zipfile import ZipFile

MAX_ROW_BYTES = 2 * 1024 * 1024
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def json_array(path):
    """Decode one top-level array element at a time, rejecting truncation/trailing junk."""
    decoder = json.JSONDecoder(parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    with path.open(encoding='utf-8-sig') as f:
        buf = ''
        eof = False

        def fill():
            nonlocal buf, eof
            chunk = f.read(65536)
            eof = not chunk
            buf += chunk

        def trim():
            nonlocal buf
            buf = buf.lstrip()
            while not buf and not eof:
                fill()
                buf = buf.lstrip()

        trim()
        if not buf.startswith('['):
            raise ValueError('JSON export must be a top-level array; NDJSON uses .jsonl')
        buf = buf[1:]
        first = True
        while True:
            trim()
            if buf.startswith(']'):
                buf = buf[1:]
                break
            if not first:
                if not buf.startswith(','):
                    raise ValueError('Missing array separator or truncated JSON')
                buf = buf[1:]
                trim()
                if buf.startswith(']'):
                    raise ValueError('Trailing array comma')
            while True:
                try:
                    value, end = decoder.raw_decode(buf)
                    # A numeric token may continue in the next block; objects are required anyway.
                    break
                except json.JSONDecodeError:
                    if eof or len(buf.encode('utf-8')) > MAX_ROW_BYTES:
                        raise ValueError('Invalid/truncated JSON or row exceeds 2 MiB')
                    fill()
            if not isinstance(value, dict):
                raise ValueError('Each export record must be an object')
            yield value
            buf = buf[end:]
            first = False
        trim()
        while not eof:
            fill()
        if buf.strip():
            raise ValueError('Unexpected data after JSON array')


def headers_ok(headers):
    if not headers or any(not isinstance(h, str) or not h.strip() for h in headers):
        raise ValueError('Headers must be nonempty text')
    if len(set(headers)) != len(headers):
        raise ValueError('Duplicate export headers')


def xlsx_rows(path, sheet=None):
    """Read-only OOXML text/numeric cells with row locators; reject formulas and numeric dates."""
    with ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > 1024 ** 3:
            raise ValueError('Workbook uncompressed size exceeds 1 GiB')
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            with z.open('xl/sharedStrings.xml') as f:
                for _, el in ET.iterparse(f, events=['end']):
                    if el.tag == NS + 'si':
                        shared.append(''.join(t.text or '' for t in el.iter(NS + 't')))
                        el.clear()
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets = {r.attrib['Id']: posixpath.normpath('xl/' + r.attrib['Target'])
                   if not r.attrib['Target'].startswith('/') else r.attrib['Target'].lstrip('/')
                   for r in rels if r.attrib.get('TargetMode') != 'External'}
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        sheets = workbook.find(NS + 'sheets')
        choices = [s for s in sheets if sheet is None or s.attrib['name'] == sheet]
        if (sheet is None and len(choices) != 1) or len(choices) != 1:
            raise ValueError('Choose one worksheet explicitly with --sheet')
        chosen = choices[0]
        target = targets[chosen.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
        if not target.startswith('xl/worksheets/'):
            raise ValueError('Unexpected worksheet target')
        date_styles = set()
        if 'xl/styles.xml' in z.namelist():
            styles = ET.fromstring(z.read('xl/styles.xml'))
            formats = {int(n.attrib['numFmtId']): n.attrib.get('formatCode', '')
                       for n in styles.findall(NS + 'numFmts/' + NS + 'numFmt')}
            xfs = styles.find(NS + 'cellXfs')
            if xfs is not None:
                for index, xf in enumerate(xfs):
                    fid = int(xf.attrib.get('numFmtId', '0'))
                    if 14 <= fid <= 22 or 45 <= fid <= 47 or re.search('[ydh]', formats.get(fid, ''), re.I):
                        date_styles.add(index)
        headers = None
        with z.open(target) as f:
            for event, row in ET.iterparse(f, events=['end']):
                if row.tag != NS + 'row':
                    continue
                cells = {}
                for c in row.findall(NS + 'c'):
                    letters = re.match(r'[A-Z]+', c.attrib.get('r', ''))
                    if not letters:
                        raise ValueError('Cell reference missing')
                    index = 0
                    for letter in letters.group():
                        index = index * 26 + ord(letter) - 64
                    if c.find(NS + 'f') is not None:
                        raise ValueError('Formula cells require an authorized values-only export')
                    value = c.findtext(NS + 'v', '')
                    kind = c.attrib.get('t', '')
                    if kind == 's':
                        value = shared[int(value)]
                    elif kind == 'inlineStr':
                        value = ''.join(t.text or '' for t in c.iter(NS + 't'))
                    elif kind == 'e':
                        raise ValueError('Excel error cell')
                    elif value and int(c.attrib.get('s', '0')) in date_styles:
                        raise ValueError('Export Excel dates as ISO or dd/MM/yyyy text before import')
                    cells[index - 1] = value
                locator = {'sheet': chosen.attrib['name'], 'excel_row': int(row.attrib['r'])}
                row.clear()
                if headers is None:
                    headers = [cells.get(i, '') for i in range(max(cells, default=-1) + 1)]
                    headers_ok(headers)
                else:
                    if any(i >= len(headers) for i in cells):
                        raise ValueError('Excel row exceeds header width')
                    yield dict(zip(headers, [cells.get(i, '') for i in range(len(headers))])), locator


def records(path, sheet=None, delimiter=','):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.csv':
        csv.field_size_limit(MAX_ROW_BYTES)
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            headers_ok(reader.fieldnames)
            for index, row in enumerate(reader, 1):
                if None in row or any(v is None for v in row.values()):
                    raise ValueError('CSV row width differs from header')
                yield row, {'record': index, 'csv_line_end': reader.line_num}
    elif suffix == '.json':
        for index, row in enumerate(json_array(path), 1):
            yield row, {'array_index': index - 1}
    elif suffix in {'.jsonl', '.ndjson'}:
        with path.open(encoding='utf-8-sig') as f:
            for line, raw in enumerate(f, 1):
                if len(raw.encode('utf-8')) > MAX_ROW_BYTES:
                    raise ValueError('JSONL row exceeds 2 MiB')
                row = json.loads(raw)
                if not isinstance(row, dict):
                    raise ValueError('Each JSONL line must be an object')
                yield row, {'line': line}
    elif suffix == '.xlsx':
        yield from xlsx_rows(path, sheet)
    else:
        raise ValueError('Supported: UTF-8 CSV, JSON array, JSONL, values-only XLSX; convert legacy XLS explicitly')
