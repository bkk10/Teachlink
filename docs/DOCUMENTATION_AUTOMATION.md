# Documentation Automation (No Word Typing)

Use Markdown files in this repo and generate export files automatically.

## One-command usage

From the project root:

```powershell
.\scripts\build-docs.ps1
```

This converts `RISK_DASHBOARD_DEBUG.md` into:

- `Documents\exports\RISK_DASHBOARD_DEBUG.docx`
- `Documents\exports\RISK_DASHBOARD_DEBUG.html`
- `Documents\exports\RISK_DASHBOARD_DEBUG.pdf` (if a PDF engine is installed)

## Convert a specific markdown file

```powershell
.\scripts\build-docs.ps1 -InputFile ".\RISK_DASHBOARD_DEBUG.md"
```

## Convert all root markdown files

```powershell
.\scripts\build-docs.ps1 -AllMarkdown
```

## Add timestamps to output files

```powershell
.\scripts\build-docs.ps1 -AllMarkdown -Timestamped
```

## Auto-generate feature documentation from code comments/docstrings

Generate `docs\AUTO_FEATURES.md` from Python files, then export it:

```powershell
.\scripts\build-docs.ps1 -GenerateFeaturesDoc
```

If you also want all markdown exports (root + docs):

```powershell
.\scripts\build-docs.ps1 -AllMarkdown -GenerateFeaturesDoc
```

You can run the feature extractor directly too:

```powershell
python .\scripts\generate-feature-docs.py
```

## If Pandoc is missing

Install on Windows with one of:

```powershell
winget install --id JohnMacFarlane.Pandoc -e
```

or

```powershell
choco install pandoc
```

Then run the script again.

## PDF support note

PDF export requires a PDF engine (`xelatex`, `pdflatex`, `wkhtmltopdf`, or `weasyprint`).
If none is present, DOCX and HTML are still generated.
