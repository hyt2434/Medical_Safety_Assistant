"""Build the portrait model/specification section from the original specification."""
from pathlib import Path
import re

root = Path(__file__).resolve().parent
source = (root / 'sections/02-use-case-specifications.tex').read_text(encoding='utf-8')
source = source.replace(r'\section{Use-case Specifications}', r'\section{Use-case Models and Specifications}')
# Start each use case on its own page, regardless of source-editor spacing.
source, heading_count = re.subn(
    r'(\\subsection\{Use-case: [^\n]+\})',
    lambda match: '\\clearpage\n' + match[1], source,
)
assert heading_count == 18, heading_count
macro = r'''
\renewcommand{\arraystretch}{1.05}
\setlength{\parskip}{2pt}
% Extend only the figure into the margins: 19 cm on a 21 cm portrait A4 page.
\newcommand{\InlineUCModel}[1]{%
  \par\noindent
  \begin{minipage}{\linewidth}
    \centering
    \makebox[\linewidth][c]{%
      \includegraphics[width=19cm,height=0.60\textheight,keepaspectratio]{UC_#1.pdf}%
    }
    \captionsetup{hypcap=false}
    \captionof{figure}{UC-#1: detailed use-case model.}
    \label{fig:uc-model-#1}
  \end{minipage}
  \par\smallskip
}
'''
source = macro + source
overview = r'''
\clearpage
\begin{center}
  % The supplied overview image already contains its own title and caption.
  \includegraphics[width=\textwidth,height=0.94\textheight,keepaspectratio]{UC_00_Overview_Attached.jpg}
\end{center}
'''
# The unnumbered overview has its own page and preserves Figure 1--18.
first_use_case = r'\subsection{Use-case: Sign In}'
assert source.count(first_use_case) == 1
source = source.replace(first_use_case, overview + '\n\\clearpage\n' + first_use_case, 1)
source = source.replace(r'\par\smallskip', r'\par')
source = re.sub(
    r'\\\\\s*\\hline\s*(\\textbf\{(?:Pre-conditions|Post-conditions)\})',
    lambda m: '\\\\* \\hline\\noalign{\\penalty10000}\n' + m[1], source,
)
source, count = re.subn(r'(\\label\{uc:uc-(\d{2})\})', lambda m: m[1] + '\n\\InlineUCModel{' + m[2] + '}\n', source)
assert count == 18, count
# Let long use cases flow naturally instead of forcing the whole alternatives
# section onto a second page. Each alternative remains an indivisible table row.
def paginate_use_case(match):
    block = match[0]
    number = match[1]
    table_start = r'\begin{longtable}{|p{0.20\textwidth}|p{0.71\textwidth}|}'
    header = (
        table_start + '\n\\hline\n\\endfirsthead\n'
        + '\\multicolumn{2}{l}{\\textbf{UC-' + number
        + ': Specification (continued)}} \\\\\n\\hline\n\\endhead'
    )
    block = block.replace(table_start + '\n\\hline', header, 1)
    alternative_start = block.index(r'\textbf{Alternative Flows}')
    alternative_end = block.index(r'\textbf{Pre-conditions}', alternative_start)
    alternatives = block[alternative_start:alternative_end]
    alternatives = re.sub(
        r'\\par\s*(?=\\textbf\{A[2-9]\.)',
        lambda _: '\\\\ \\hline\n\\textbf{Alternative Flows} &\n',
        alternatives,
    )
    block = block[:alternative_start] + alternatives + block[alternative_end:]
    # Keep the final alternative and both condition rows together. A nested
    # tabular is indivisible, unlike longtable's rules around starred rows.
    final_alternative = block.rindex(r'\textbf{Alternative Flows} &')
    table_end = block.index(r'\end{longtable}', final_alternative)
    tail = block[final_alternative:table_end].strip()
    tail = tail.replace(r'\noalign{\penalty10000}', '')
    tail = tail.replace(r'\\*', r'\\')
    boxed_tail = (
        '\\multicolumn{2}{@{}c@{}}{%\n'
        '\\begin{tabular}{|p{0.20\\textwidth}|p{0.71\\textwidth}|}\n'
        + tail + '\n\\end{tabular}}\\\\\n'
    )
    return block[:final_alternative] + boxed_tail + block[table_end:]

source, table_count = re.subn(
    r'\\label\{uc:uc-(\d{2})\}[\s\S]*?\\end\{longtable\}',
    paginate_use_case, source,
)
assert table_count == 18, table_count
(root / 'sections/03-use-cases-combined.tex').write_text(source, encoding='utf-8')
