r"""Merge a split PA3 LaTeX document (main.tex + metadata.tex + \input sections)
into one self-contained main.tex for PA4.

Usage: python docs/pa/pa4/tools/merge_pa3_tex.py "<pa3 doc dir>" "<pa4 doc dir>"
"""
import re
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
main = (src / 'main.tex').read_text(encoding='utf-8')
meta_path = src / 'metadata.tex'
if meta_path.exists():
    meta = meta_path.read_text(encoding='utf-8')
    main = main.replace(r'\input{metadata}', '% -------------------- Metadata --------------------\n' + meta)


def inline(match):
    name = match.group(1)
    path = src / name if name.endswith('.tex') else src / (name + '.tex')
    return f'% ===== {name} =====\n' + path.read_text(encoding='utf-8')


main = re.sub(r'\\input\{(sections/[^}]+)\}', inline, main)
(dst / 'main.tex').write_text(main, encoding='utf-8')
print(len(main.splitlines()), 'lines; remaining inputs:', main.count('\\input{'))
