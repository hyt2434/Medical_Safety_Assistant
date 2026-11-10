$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    python combine_sections.py
    if ($LASTEXITCODE -ne 0) { throw 'Combining use-case sections failed.' }
    python prepare_figures.py
    if ($LASTEXITCODE -ne 0) { throw 'SVG conversion failed. Install Python dependency: pip install -r requirements.txt' }
    latexmk -xelatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
    if ($LASTEXITCODE -ne 0) { throw 'LaTeX compilation failed. See main.log.' }
    Write-Output ('Report: ' + (Join-Path $PSScriptRoot 'main.pdf'))
} finally {
    Pop-Location
}
