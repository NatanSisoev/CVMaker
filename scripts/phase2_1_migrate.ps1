<#
.SYNOPSIS
    Phase 2.1 migration: SectionEntry GenericForeignKey -> direct FK to BaseEntry.

.DESCRIPTION
    Drops the old SectionEntry columns (content_type, object_id) and adds
    `entry = FK(BaseEntry)` per ADR-0005. The dev/CI databases have no
    real fixture data, so this is a structural migration only -- nothing
    to backfill.

    Steps:
      1. `uv run python manage.py makemigrations sections`
         -> generates the AlterField/RemoveField/AddField migration.
      2. `uv run python manage.py migrate sections`
         -> applies it.
      3. `uv run python manage.py check`
         -> sanity-check that no other app's model state regressed.
      4. `uv run pytest -q`
         -> the full Phase 1.6 test suite. Updated entry/section tests
            land in Phase 2's test task; this run validates that the
            existing tests still pass with the new shape.

    Run from the repo root.

.NOTES
    If you have ANY data in the local Postgres DB you want to keep, stop
    and back it up first -- the dropped columns lose their data.
    Phase 2 has no real users; this is dev/CI only.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Run-Step {
    param([string]$Title, [string]$Command)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
    Write-Host "+ $Command" -ForegroundColor DarkGray
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Step '$Title' failed (exit $LASTEXITCODE). Stopping." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# Step 1 -- the 0002_sectionentry_entry_fk migration is hand-written (Django's
# auto-detector can't infer that entry_id should be backfilled from
# object_id). Verify makemigrations sees nothing else outstanding.
Run-Step "Verify no outstanding model diffs" "uv run python manage.py makemigrations --check --dry-run sections"

# Step 2 -- apply the hand-written migration plus any others.
Run-Step "Apply migrations" "uv run python manage.py migrate"

# Step 3 -- system check after the schema shifts.
Run-Step "Django system check" "uv run python manage.py check"

# Step 4 -- run the test suite.
Run-Step "pytest" "uv run pytest -q"

Write-Host ""
Write-Host "Phase 2.1 migration complete." -ForegroundColor Green
Write-Host "Inspect the generated migration in apps/sections/migrations/ before committing." -ForegroundColor Green
