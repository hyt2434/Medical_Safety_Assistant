import argparse
import json
from shared.paths import ProjectPath as Path, PROJECT_ROOT
from .acquire import acquire
from .dataset import build_index, OfficialDataset


def main():
    parser = argparse.ArgumentParser(description='Explicit official DDInter acquisition and offline indexing')
    parser.add_argument('--project', type=Path, default=PROJECT_ROOT)
    sub = parser.add_subparsers(dest='command', required=True)
    acquisition = sub.add_parser('acquire')
    acquisition.add_argument('--output', type=Path, required=True)
    build = sub.add_parser('build')
    build.add_argument('--collection', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    build.add_argument('--synonyms', type=Path)
    synonyms = sub.add_parser('capture-synonyms')
    synonyms.add_argument('--collection', type=Path, required=True)
    lookup = sub.add_parser('lookup')
    lookup.add_argument('--index', type=Path, required=True)
    lookup.add_argument('drug_a')
    lookup.add_argument('drug_b')
    args = parser.parse_args()
    if args.command == 'acquire':
        acquire(args.project, args.output)
    elif args.command == 'build':
        report = build_index(args.collection, args.output, public_record=args.synonyms or args.project /
            'data/reference/provenance/module2_api_quicktest/ingredient_ddinter_poc/evidence/ddinter_public_record.json')
        print(json.dumps(report['coverage'], ensure_ascii=False))
    elif args.command == 'capture-synonyms':
        from .synonyms import capture_official_synonyms
        print(capture_official_synonyms(args.project, args.collection))
    else:
        print(json.dumps(OfficialDataset(args.index).lookup(args.drug_a, args.drug_b), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
