param(
    [string]$InputFile = "RISK_DASHBOARD_DEBUG.md",
    [string]$OutputDir = "Documents\\exports",
    [switch]$AllMarkdown,
    [switch]$Timestamped,
    [switch]$GenerateFeaturesDoc,
    [switch]$IncludeDocsMarkdown
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[docs] $Message" -ForegroundColor Cyan
}

function Write-WarnMsg {
    param([string]$Message)
    Write-Host "[docs] $Message" -ForegroundColor Yellow
}

function Get-PdfEngine {
    $engines = @("xelatex", "pdflatex", "wkhtmltopdf", "weasyprint")
    foreach ($engine in $engines) {
        if (Get-Command $engine -ErrorAction SilentlyContinue) {
            return $engine
        }
    }
    return $null
}

function Get-PandocExecutable {
    $cmd = Get-Command pandoc -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $commonPaths = @(
        "C:\\Program Files\\Pandoc\\pandoc.exe",
        "C:\\Program Files (x86)\\Pandoc\\pandoc.exe",
        (Join-Path $env:LOCALAPPDATA "Pandoc\\pandoc.exe")
    )
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            return $path
        }
    }
    return $null
}

function Convert-Markdown {
    param(
        [Parameter(Mandatory = $true)][string]$SourceFile,
        [Parameter(Mandatory = $true)][string]$DestinationDir,
        [bool]$UseTimestamp
    )

    $sourcePath = Resolve-Path $SourceFile
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($sourcePath)
    $suffix = ""
    if ($UseTimestamp) {
        $suffix = "-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    }

    $docxPath = Join-Path $DestinationDir "$baseName$suffix.docx"
    $htmlPath = Join-Path $DestinationDir "$baseName$suffix.html"
    $pdfPath = Join-Path $DestinationDir "$baseName$suffix.pdf"

    Write-Info "Converting $sourcePath"

    $pandocArgsDocx = @($sourcePath, "-o", $docxPath)
    & $script:PandocExe @pandocArgsDocx
    Write-Info "Created: $docxPath"

    $pandocArgsHtml = @($sourcePath, "-o", $htmlPath)
    & $script:PandocExe @pandocArgsHtml
    Write-Info "Created: $htmlPath"

    $pdfEngine = Get-PdfEngine
    if ($pdfEngine) {
        $pandocArgsPdf = @($sourcePath, "-o", $pdfPath, "--pdf-engine=$pdfEngine")
        & $script:PandocExe @pandocArgsPdf
        Write-Info "Created: $pdfPath (engine: $pdfEngine)"
    }
    else {
        Write-WarnMsg "Skipped PDF for $sourcePath (no PDF engine found: xelatex/pdflatex/wkhtmltopdf/weasyprint)."
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    $script:PandocExe = Get-PandocExecutable
}
else {
    $script:PandocExe = (Get-Command pandoc).Source
}

if (-not $script:PandocExe) {
    Write-Error @"
Pandoc is not installed.

Install options (Windows):
  winget install --id JohnMacFarlane.Pandoc -e
  choco install pandoc

Then re-run:
  .\scripts\build-docs.ps1
"@
}

Write-Info "Using Pandoc: $script:PandocExe"

if ($GenerateFeaturesDoc) {
    Write-Info "Generating docs/AUTO_FEATURES.md from code comments/docstrings..."
    & python ".\\scripts\\generate-feature-docs.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Feature doc generation failed."
    }
    if ((-not $AllMarkdown) -and (-not $PSBoundParameters.ContainsKey('InputFile'))) {
        $InputFile = "docs\\AUTO_FEATURES.md"
    }
}

$exportDir = Join-Path $repoRoot $OutputDir
if (-not (Test-Path $exportDir)) {
    New-Item -ItemType Directory -Path $exportDir | Out-Null
}

if ($AllMarkdown) {
    $files = Get-ChildItem -Path $repoRoot -File -Filter *.md | Select-Object -ExpandProperty FullName
    if ($IncludeDocsMarkdown -or $GenerateFeaturesDoc) {
        $docsDir = Join-Path $repoRoot "docs"
        if (Test-Path $docsDir) {
            $files += Get-ChildItem -Path $docsDir -File -Filter *.md | Select-Object -ExpandProperty FullName
        }
    }
    $files = $files | Sort-Object -Unique
    if (-not $files) {
        Write-WarnMsg "No markdown files found at repo root."
        exit 0
    }
    foreach ($file in $files) {
        Convert-Markdown -SourceFile $file -DestinationDir $exportDir -UseTimestamp:$Timestamped.IsPresent
    }
}
else {
    if (-not (Test-Path $InputFile)) {
        Write-Error "Input markdown file not found: $InputFile"
    }
    Convert-Markdown -SourceFile $InputFile -DestinationDir $exportDir -UseTimestamp:$Timestamped.IsPresent
}

Write-Info "Done."
