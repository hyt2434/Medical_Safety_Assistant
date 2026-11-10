import argparse
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from .mapping import DDInterAdapter, RxNormAdapter, map_ingredients
from .pipeline import import_export
from .reporting import report, save_report


def main():
    parser = argparse.ArgumentParser(description='Offline authorized-export ingestion; no DAV acquisition')
    sub = parser.add_subparsers(dest='command', required=True)
    imp = sub.add_parser('import')
    imp.add_argument('--input', required=True, type=Path)
    imp.add_argument('--manifest', required=True, type=Path)
    imp.add_argument('--db', required=True, type=Path)
    imp.add_argument('--as-of', required=True, help='Authorization review date, YYYY-MM-DD')
    imp.add_argument('--archive', type=Path)
    imp.add_argument('--column-map', type=Path)
    imp.add_argument('--sheet')
    imp.add_argument('--delimiter', default=',')
    imp.add_argument('--chunk-size', type=int, default=1000)
    imp.add_argument('--stop-after', type=int)
    imp.add_argument('--report', type=Path)
    rep = sub.add_parser('report')
    rep.add_argument('--db', required=True, type=Path)
    rep.add_argument('--source-id')
    rep.add_argument('--output', required=True, type=Path)
    mapping = sub.add_parser('map')
    mapping.add_argument('--db', required=True, type=Path)
    mapping.add_argument('--namespace', choices=['RxNorm', 'DDInter'], required=True)
    mapping.add_argument('--snapshot', type=Path, required=True)
    mapping.add_argument('--allow-synthetic', action='store_true')
    a = parser.parse_args()
    if a.command == 'import':
        column_map = json.loads(a.column_map.read_text(encoding='utf-8-sig')) if a.column_map else {}
        sid = import_export(a.input, a.manifest, a.db, archive_dir=a.archive, column_map=column_map,
                            sheet=a.sheet, delimiter=a.delimiter, chunk_size=a.chunk_size,
                            stop_after=a.stop_after, as_of=a.as_of)
        value = report(a.db, sid)
        if a.report:
            save_report(a.report, value)
        print(json.dumps({'source_id': sid, 'batch': value['sources'][0]['batch']}))
    elif a.command == 'report':
        save_report(a.output, report(a.db, a.source_id))
    else:
        adapter = {'RxNorm': RxNormAdapter, 'DDInter': DDInterAdapter}[a.namespace].from_snapshot(a.snapshot, allow_synthetic=a.allow_synthetic)
        print(json.dumps({'new_ingredient_mappings': map_ingredients(a.db, adapter)}))


if __name__ == '__main__':
    main()
