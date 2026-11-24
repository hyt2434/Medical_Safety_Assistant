"""Project CLI composition; no medical decision rules are added here."""
import argparse
import json
import sys
from .paths import PROJECT_ROOT, ProjectPath


def main():
    if len(sys.argv)>1 and sys.argv[1]=='medications':
        from module2_medications.__main__ import main as medications
        del sys.argv[1]
        return medications()
    parser=argparse.ArgumentParser(description='Medication Safety Assistant research CLI')
    sub=parser.add_subparsers(dest='command',required=True)
    image=sub.add_parser('image',help='Actual local OCR, with required review')
    image.add_argument('image',type=ProjectPath)
    image.add_argument('--output',type=ProjectPath,required=True)
    sub.add_parser('medications',help='Main Module 2 lookup/pipeline CLI; --reference unified supported')
    args=parser.parse_args()
    if args.command=='image':
        from module1_intake.ocr.application.service import LocalOcrService
        args.output.mkdir(parents=True,exist_ok=False)
        result = LocalOcrService().extract(args.image)
        extracted = result.extraction_run.raw_output['parsed']
        metadata = {'provider': result.extraction_run.engine_name,
                    'run_id': str(result.extraction_run.extraction_run_id), 'requires_user_review': True}
        (args.output/'extraction.json').write_text(json.dumps({'extraction':extracted,'metadata':metadata},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(extracted,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
