<#
.SYNOPSIS
    Phase 4.1 frontend bootstrap.

.DESCRIPTION
    The Python side (pyproject.toml, settings, templates) is already
    updated. This script handles the Windows-side work the Linux sandbox
    can't reach:

      1. Delete legacy Bootstrap + jQuery static assets.
      2. `npm install` (pulls Tailwind, HTMX, Alpine, esbuild).
      3. `npm run build` (produces static/dist/app.css + app.js).
      4. `uv sync` (pulls django-cotton, drops crispy_forms +
         widget_tweaks).
      5. `uv run python manage.py check` (system check after the deps
         shift).
      6. `uv run pytest -q` (regression check).

    Run from the repo root.

.NOTES
    Fonts (Fraunces, Inter, JetBrains Mono) still need to be added to
    static/fonts/ manually -- the variable WOFF2 files have inconsistent
    download URLs and a script that fetches them tends to bit-rot. See
    docs/DESIGN.md for the chosen weights.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Run-Step {
    param([string]$Title, [scriptblock]$Block)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
        Write-Host "Step '$Title' failed (exit $LASTEXITCODE). Stopping." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# 1. Drop the legacy Bootstrap/jQuery static assets. Git keeps history,
# so this is reversible if we ever need them back.
Run-Step "Remove legacy Bootstrap + jQuery" {
    foreach ($path in @(
        'static/css/bootstrap.min.css',
        'static/js/bootstrap.bundle.min.js',
        'static/js/jquery-3.7.1.min.js',
        'static/css/app.css'  # tailwind regenerates static/dist/app.css instead
    )) {
        if (Test-Path $path) {
            Remove-Item -Force $path
            Write-Host "  removed $path"
        } else {
            Write-Host "  skip:   $path (already gone)"
        }
    }
}

# 2-3. Frontend deps.
Run-Step "npm install" { npm install }
Run-Step "npm run build" { npm run build }

# 4-6. Python side.
Run-Step "uv sync" { uv sync }
Run-Step "Django system check" { uv run python manage.py check }
Run-Step "pytest" { uv run pytest -q }

Write-Host ""
Write-Host "Phase 4.1 bootstrap complete." -ForegroundColor Green
Write-Host "Next: add variable WOFF2 fonts to static/fonts/, then start Phase 4.2 (component library)." -ForegroundColor Green
