<#
.SYNOPSIS
Supply explicitly selected, reviewed reference files for local runtime use.
.DESCRIPTION
No datasets, databases, images or patient records are included by default.
Inspect licensing and contents before selecting files. Never copy whole data
trees, raw DAV exports, research SQLite files, credentials or historical runs.

Bounded Module 2/3 needs the original category-A CSV, whose hash is recorded in
the included approved_download_manifest.json. Example:
  .\scripts\provision-data.ps1 -SourceData ..\Medication-Safety-Assistant\data -RelativePath reference/provenance/module2_api_quicktest/ingredient_ddinter_poc/evidence/ddinter_downloads_code_A.csv

For official-all, supply the eight original CSVs named in
data/reference/ddinter2/official_20261013/manifest.json. Rebuild locally:
  $env:PYTHONPATH=(Join-Path (Get-Location) 'src')
  & .\scripts\.venv\Scripts\python.exe -B -m module3_interactions.official_ddinter build --collection data/reference/ddinter2/official_20261013 --output data/reference/ddinter2/official_20261013/official.sqlite
The included DDInter14 page summary is used by default. Full historical synonym
coverage also needs official_synonyms.json and all its linked page evidence.

Unified Reference needs reviewed Batch 1-3 supplement manifests, product shards,
reviewed_equivalences.json and every hash-linked source/use artifact. Supply
these individually at their original data/reference-relative paths; the included
path_aliases.json relocates historical evidence locally. Rebuild under
data/processed using scripts/preprocess.ps1. Original preprocessing also needs
a separately authorized local data/raw/dav/records.jsonl for its audit; this
script deliberately does not import raw DAV. Without those inputs Unified/E2E
remains unavailable. Never copy an existing research SQLite snapshot.

Historical E2E additionally needs its original synthetic prescription images,
OCR evidence and measured baseline. Do not substitute new data for sealed
historical expectations. scripts/test.ps1 runs focused synthetic regressions;
-ResearchData attempts all original tests. Local dataset files must remain
untracked; inspect git status before publishing any separately supplied data.
.PARAMETER SourceData
Existing source data directory, read only.
.PARAMETER RelativePath
Explicit reviewed files relative to SourceData, each under reference/.
#>
param([Parameter(Mandatory=$true)][string]$SourceData,
      [Parameter(Mandatory=$true)][string[]]$RelativePath)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$source=(Resolve-Path -LiteralPath $SourceData).Path
$destination=[IO.Path]::GetFullPath((Join-Path $root 'data'))
$planned=@()
foreach ($relative in $RelativePath) {
    $normalized=$relative.Replace('\','/')
    if ($normalized -notmatch '^reference/' -or $normalized -match '(^|/)\.\.(/|$)' -or
        $normalized -match '(^|/)(private_runs|runs|node_modules|__pycache__)(/|$)' -or
        [IO.Path]::GetExtension($relative) -notin @('.csv','.json','.jsonl','.html','.xml','.pdf')) {
        throw "Only explicitly reviewed reference files are accepted: $relative"
    }
    $inputPath=[IO.Path]::GetFullPath((Join-Path $source $relative))
    $outputPath=[IO.Path]::GetFullPath((Join-Path $destination $relative))
    if (-not $inputPath.StartsWith($source+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or
        -not $outputPath.StartsWith($destination+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes data directory' }
    if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) { throw "Missing source: $relative" }
    foreach ($path in @($inputPath,$outputPath)) {
        $ancestor=$path
        while ($ancestor) {
            if ((Test-Path -LiteralPath $ancestor) -and ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Linked paths are not accepted' }
            $ancestor=Split-Path $ancestor -Parent
        }
    }
    if (Test-Path -LiteralPath $outputPath) { throw "Existing file preserved: $relative" }
    $planned+=@{Source=$inputPath;Destination=$outputPath}
}
foreach ($item in $planned) {
    New-Item -ItemType Directory -Path (Split-Path $item.Destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $item.Source -Destination $item.Destination
}
Write-Output ('Copied '+$planned.Count+' selected reference files. Rebuild databases locally.')
