import argparse
from datetime import datetime, timezone, timedelta
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from .audit import audit_dataset
from .reference import build_reference, MedicationReference
from .research import ResearchSupplementReference
from .service import identify, assess_prescriptions
from .terminology import load_ddinter, DirectDDInter
from .unified import UnifiedMedicationReference, default_config, preprocess, read as read_config


def main():
    parser = argparse.ArgumentParser(description='Offline Vietnamese medication reference and direct DDInter mapping')
    parser.add_argument('--project', type=Path, default=PROJECT_ROOT)
    parser.add_argument('--ddinter-scope', choices=['bounded', 'category-a', 'official-all'])
    parser.add_argument('--ddinter-index', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    audit = sub.add_parser('audit')
    audit.add_argument('--input', type=Path, required=True)
    audit.add_argument('--output', type=Path, required=True)
    audit.add_argument('--review-queue', type=Path)
    audit.add_argument('--as-of', default=datetime.now(timezone(timedelta(hours=7))).date().isoformat())
    build = sub.add_parser('build')
    build.add_argument('--input', type=Path, required=True)
    build.add_argument('--manifest', type=Path, required=True)
    build.add_argument('--db', type=Path, required=True)
    build.add_argument('--as-of', required=True)
    crosswalk = sub.add_parser('crosswalk')
    crosswalk.add_argument('--output', type=Path, required=True)
    process = sub.add_parser('preprocess', help='Build the opt-in processed research reference')
    process.add_argument('--config', type=Path)
    process.add_argument('--db', type=Path)
    process.add_argument('--supplement', type=Path, action='append')
    for name in ('lookup', 'pipeline'):
        p = sub.add_parser(name)
        source = p.add_mutually_exclusive_group(required=True)
        source.add_argument('--db', type=Path)
        source.add_argument('--research-supplement', type=Path,
                            help='Batch 1, 2 or 3 source-reviewed research supplement manifest')
        source.add_argument('--reference', choices=['unified'], help='Opt-in processed Batch 1-3 research reference')
        p.add_argument('--unified-config', type=Path, help='Defaults to unified.runtime.config.json when present, otherwise unified.config.json under data/processed/medication_reference')
        p.add_argument('--input', type=Path, required=True)
        p.add_argument('--output', type=Path, required=True)
        p.add_argument('--allow-synthetic', action='store_true')
    args = parser.parse_args()
    if args.command == 'build':
        result = build_reference(args.input, args.manifest, args.db, as_of=args.as_of)
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.command == 'preprocess':
        if args.ddinter_scope not in (None,'official-all'):
            parser.error('Unified preprocessing uses the recorded official-all research index')
        processed = preprocess(args.project, manifests=args.supplement, database=args.db, config=args.config,
                               dataset=load_ddinter(args.project,'official-all',index_path=args.ddinter_index))
        print('Processed research presentations: '+str(processed['summary']['source_presentations']))
        return
    unified = getattr(args,'reference',None) == 'unified'
    config_path = (args.unified_config or default_config(args.project)) if unified else None
    config = read_config(config_path) if unified else None
    if unified and args.ddinter_scope not in (None,config['ddinter_scope']):
        parser.error('Unified reference requires its configured official-all scope')
    scope = config['ddinter_scope'] if unified else args.ddinter_scope or 'bounded'
    index = args.ddinter_index or (Path(config['ddinter_index']) if unified else None)
    terminology = DirectDDInter(load_ddinter(args.project, scope, index_path=index))
    if args.output.exists():
        raise ValueError('Choose a fresh output path; prior evidence is immutable')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.command == 'audit':
        result = audit_dataset(args.input, terminology, as_of=args.as_of, review_queue=args.review_queue)
    elif args.command == 'crosswalk':
        result = terminology.crosswalk()
    else:
        reference = (UnifiedMedicationReference(config_path) if unified else
                     ResearchSupplementReference(args.research_supplement) if args.research_supplement
                     else MedicationReference(args.db, allow_synthetic=args.allow_synthetic))
        try:
            if unified or args.research_supplement:
                terminology = reference.terminology(terminology.dataset)
            value = json.loads(args.input.read_text(encoding='utf-8-sig'))
            result = identify(value, reference, terminology) if args.command == 'lookup' else assess_prescriptions(value, reference, terminology)
        finally:
            reference.close()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'network_requests': 0}))


if __name__ == '__main__':
    main()
