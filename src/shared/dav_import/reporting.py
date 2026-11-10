from collections import Counter
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from .common import now
from .pipeline import connect


def report(db_path, source_id=None):
    db = connect(db_path)
    try:
        sources = db.execute('SELECT id,kind,manifest_json FROM sources' + (' WHERE id=?' if source_id else ''),
                             (source_id,) if source_id else ()).fetchall()
        if source_id and not sources:
            raise ValueError('Unknown source ID')
        output = {'schema_version': 'dav.quality_report.v1', 'generated_at': now(), 'sources': []}
        for source in sources:
            sid = source['id']
            batch = dict(db.execute('SELECT * FROM batches WHERE id=?', (sid,)).fetchone())
            rows = db.execute('SELECT o.*,r.row_number FROM raw_records r JOIN observations o ON r.observation_id=o.id WHERE r.source_id=? ORDER BY r.row_number', (sid,))
            states, missing, issues, completeness = Counter(), Counter(), Counter(), Counter()
            obs = set()
            meds = set()
            registrations = set()
            parsed = total_components = multi = raw_count = 0
            fields = ['brand_name', 'registration_number', 'manufacturer', 'dosage_form', 'route', 'strength', 'valid_until', 'effective_date']
            for row in rows:
                raw_count += 1
                states[row['validation_status']] += 1
                obs.add(row['id'])
                if row['medication_id']:
                    meds.add(row['medication_id'])
                if row['registration_id']:
                    registrations.add(row['registration_id'])
                n = json.loads(row['normalized_json'])
                for field in fields:
                    completeness[field] += bool(n[field])
                    missing[field] += not bool(n[field])
                cs = n['components']
                multi += len(cs) > 1
                total_components += len(cs)
                parsed += sum(c['strength']['status'] == 'PARSED' for c in cs)
            for item in db.execute('SELECT i.code,COUNT(*) AS count FROM raw_records r JOIN issues i ON r.observation_id=i.observation_id WHERE r.source_id=? GROUP BY i.code', (sid,)):
                issues[item['code']] = item['count']
            manifest = json.loads(source['manifest_json'])
            expected = manifest.get('expected_records')
            output['sources'].append({'source_id': sid, 'source_kind': source['kind'], 'batch': batch,
                'input_rows_committed': raw_count, 'distinct_observations': len(obs),
                'duplicate_occurrences_within_source': raw_count - len(obs),
                'candidate_formulations': len(meds), 'registration_identifiers': len(registrations),
                'validation_occurrences': dict(states), 'issue_occurrences': dict(issues),
                'field_completeness': {f: {'present': completeness[f], 'missing': missing[f], 'denominator': raw_count,
                                           'fraction': completeness[f] / raw_count if raw_count else None} for f in fields},
                'multi_component_occurrences': multi,
                'strength_parsing': {'parsed': parsed, 'denominator': total_components,
                                     'fraction': parsed / total_components if total_components else None},
                'authorized_export_coverage': {'expected_rows': expected, 'committed_rows': raw_count,
                                             'fraction': raw_count / expected if isinstance(expected, int) and expected > 0 else None},
                'national_population_coverage': None, 'national_unique_medication_count': None,
                'current_authorization_verified': 0})
        totals = {}
        for table in ['sources','raw_records','observations','medications','ingredients','components','registrations','registration_events','registration_links','reviews','terminology_mappings']:
            totals[table] = db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
        output['database_totals'] = totals
        output['candidate_verification_statuses'] = {r[0]: r[1] for r in db.execute('SELECT verification_status,COUNT(*) FROM medications GROUP BY verification_status')}
        output['mapping_coverage'] = []
        for synthetic in (0, 1):
            denominator = db.execute('SELECT COUNT(*) FROM ingredients WHERE synthetic=?', (synthetic,)).fetchone()[0]
            for namespace in ('RxNorm', 'DDInter'):
                statuses = {r[0]: r[1] for r in db.execute('SELECT t.status,COUNT(DISTINCT t.ingredient_id) FROM terminology_mappings t JOIN ingredients i ON t.ingredient_id=i.id WHERE i.synthetic=? AND t.namespace=? GROUP BY t.status', (synthetic, namespace))}
                resolved = db.execute("SELECT COUNT(DISTINCT t.ingredient_id) FROM terminology_mappings t JOIN ingredients i ON t.ingredient_id=i.id WHERE i.synthetic=? AND t.namespace=? AND t.status='CANDIDATE'", (synthetic, namespace)).fetchone()[0]
                reviewed = db.execute("SELECT COUNT(DISTINCT t.ingredient_id) FROM terminology_mappings t JOIN ingredients i ON t.ingredient_id=i.id WHERE i.synthetic=? AND t.namespace=? AND (SELECT r.status FROM reviews r WHERE r.entity_type='mapping' AND r.entity_id=t.id AND r.scope='ingredient_mapping' ORDER BY r.id DESC LIMIT 1)='VERIFIED'", (synthetic, namespace)).fetchone()[0]
                output['mapping_coverage'].append({'namespace': namespace, 'synthetic': bool(synthetic),
                    'distinct_ingredient_denominator': denominator, 'candidate_ingredients': resolved,
                    'candidate_fraction': resolved / denominator if denominator else None,
                    'independently_reviewed_ingredients': reviewed, 'statuses_across_releases': statuses})
        output['integrity'] = {'quick_check': db.execute('PRAGMA quick_check').fetchone()[0],
                               'foreign_key_errors': [list(r) for r in db.execute('PRAGMA foreign_key_check')]}
        return output
    finally:
        db.close()


def save_report(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
