"""Small invented products for offline engineering evaluation, never DAV facts."""
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from shared.dav_import.common import file_hash
from .reference import build_reference


def synthetic_rows():
    base = {'dosage_form': 'Viên nén', 'manufacturer': 'Synthetic Test Manufacturer',
            'event_type': 'original_grant', 'synthetic_fixture': True, 'verification_status': 'REVIEW_REQUIRED'}
    definitions = [
        ('Fixture Para', 'VD-100-26', 'Paracetamol', '500mg'),
        ('Fixture Para', 'VD-101-26', 'Paracetamol', '1g'),
        ('Fixture Dolutegravir', 'VD-102-26', 'Dolutegravir', '50mg'),
        ('Fixture Antacid', 'VD-103-26', 'Aluminum hydroxide', '500mg'),
        ('Fixture Combination', 'VD-104-26', 'Paracetamol 500mg; Dolutegravir 50mg', ''),
        ('Fixture Missing', 'VD-105-26', 'Paracetamol', ''),
        ('Fixture Unknown', 'VD-106-26', 'NotARealIngredient', '5mg'),
        ('Fixture Inline', 'VD-107-26', 'Empagliflozin 10mg', ''),
        ('Fixture Inline', 'VD-108-26', 'Empagliflozin 25mg', ''),
        ('Fixture Conflict', 'VD-109-26', 'Paracetamol', '500mg'),
        ('Fixture Conflict', 'VD-109-26', 'Dolutegravir', '50mg'),
        ('Fixture Slash', 'VD-110-26', 'Paracetamol/Dolutegravir', '500mg'),
        ('Thuốc Thử', 'VD-111-26', 'Paracetamol', '500mg'),
    ]
    return [{**base, 'brand_name': b, 'registration_number': r, 'ingredients': i, 'strength': s}
            for b, r, i, s in definitions]


def fixture_db(folder):
    folder = Path(folder)
    source = folder / 'fixtures.jsonl'
    source.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in synthetic_rows()), encoding='utf-8')
    manifest = {'schema_version': 'dav.authorization.v1', 'source_kind': 'synthetic',
        'synthetic_fixture': True, 'source_url': 'synthetic://module2-direct-tests',
        'snapshot_at': '2026-10-13T00:00:00+07:00', 'acquisition_method': 'generated_fixture',
        'artifact_sha256': file_hash(source), 'expected_records': len(synthetic_rows()),
        'license_or_permission': 'Synthetic engineering cases; no real brand-to-ingredient claims'}
    manifest_path = folder / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    db = folder / 'reference.sqlite'
    build_reference(source, manifest_path, db, as_of='2026-10-13')
    return db, source, manifest_path
