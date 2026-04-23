# Phase 1 migration -- restructure to src/ layout, install uv, reset DB.
#
# Run this ONCE from the repository root, after pulling the latest main.
# Verbose on purpose. Each step echoes what it's about to do and fails
# loudly if something goes wrong -- no silent success.
#
# Usage:
#   cd C:\Users\natan\CVMaker
#   .\scripts\phase1_migrate.ps1
#
# Prerequisites the script checks for:
#   - Working tree clean (no uncommitted changes)
#   - On branch 'main'
#   - .env exists with DB_* values
#   - psql on PATH
#   - Python 3.12+ as 'python'

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Say([string]$msg)  { Write-Host ""; Write-Host "=== $msg ===" -ForegroundColor Cyan }
function Ok([string]$msg)   { Write-Host "  [ok] $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "  [warn] $msg" -ForegroundColor Yellow }
function Die([string]$msg)  { Write-Host "  [FAIL] $msg" -ForegroundColor Red; exit 1 }

# Run a git command, capturing stderr and dying with it on failure.
function Git-Run([string]$label, [string[]]$argv) {
    $stderrFile = [System.IO.Path]::GetTempFileName()
    try {
        $stdout = & git @argv 2> $stderrFile
        $code = $LASTEXITCODE
        $stderr = (Get-Content $stderrFile -Raw)
        if ($code -ne 0) {
            Write-Host "  [git stderr]:" -ForegroundColor Red
            if ($stderr) { $stderr -split "`n" | ForEach-Object { Write-Host ("    " + $_) -ForegroundColor Red } }
            Die ($label + " failed (git exit " + $code + ")")
        }
        if ($stderr -and $stderr.Trim()) { Write-Host ("  [git note] " + $stderr.Trim()) -ForegroundColor DarkYellow }
        return $stdout
    } finally {
        Remove-Item -Force $stderrFile -ErrorAction SilentlyContinue
    }
}

# ----------------------------------------------------------------------
# 0. Preflight
# ----------------------------------------------------------------------
Say "Preflight checks"

if (-not (Test-Path ".\.git"))                                 { Die "Run from the repository root (no .git found)." }
if (-not (Test-Path ".\pyproject.toml"))                       { Die "pyproject.toml not found -- pull latest main first." }
if (-not (Test-Path ".\manage.py"))                            { Die "manage.py not found at repo root -- pull latest main first." }
if (-not (Test-Path ".\src\cvmaker\settings\base.py"))         { Die "src/cvmaker/settings/base.py not found -- pull latest main first." }

# Detect a stale .git/index.lock (common after interrupted git commands or
# IDE/antivirus interference on Windows). Without this check the script
# would die mid-flight with "Unable to create index.lock: File exists".
if (Test-Path ".\.git\index.lock") {
    Warn "stale .git/index.lock detected -- likely from a prior interrupted git run"
    $lockAge = (Get-Date) - (Get-Item ".\.git\index.lock").LastWriteTime
    Write-Host ("    lock age: " + [int]$lockAge.TotalSeconds + "s")
    Write-Host "    Remove it? Close any git/IDE processes first, then press Y to delete, any other key to abort." -ForegroundColor Yellow
    $resp = Read-Host
    if ($resp -eq "Y" -or $resp -eq "y") {
        Remove-Item ".\.git\index.lock" -Force
        Ok "removed .git/index.lock"
    } else {
        Die "aborted -- remove .git/index.lock manually when it is safe, then re-run"
    }
}

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne "main") { Die "On branch '$branch'; expected 'main'. Switch and re-run." }

# Tree may be "dirty" by design -- Phase 1 files are staged-but-uncommitted
# on purpose, waiting on this script to add the app moves + DB reset and
# commit the whole batch. Surface what's there, then proceed.
$status = git status --porcelain
if ($status) {
    Write-Host "  working tree has changes (expected -- Phase 1 files uncommitted):"
    $status -split "`n" | Select-Object -First 40 | ForEach-Object { Write-Host ("    " + $_) }
} else {
    Write-Host "  working tree is clean"
}
Ok "on branch main"

# Cleanup: sandbox probe artifact from the previous session
if (Test-Path ".\_test_perm") {
    Remove-Item -Force ".\_test_perm"
    Ok "removed _test_perm (leftover probe file)"
}

# .env: required for DJANGO_SECRET_KEY + DB_* values. If missing but an
# .env.example is available, bootstrap it automatically with a fresh key
# so the first run works out of the box.
if (-not (Test-Path ".\.env")) {
    if (-not (Test-Path ".\.env.example")) {
        Die ".env and .env.example both missing. Create one with DB_* and DJANGO_SECRET_KEY."
    }
    Write-Host "  .env not found -- generating from .env.example with a fresh secret key..."
    $secret = (python -c "import secrets; print(secrets.token_urlsafe(50))").Trim()
    if (-not $secret) { Die "failed to generate a random secret key" }
    $lines = Get-Content ".\.env.example"
    $lines = $lines | ForEach-Object {
        if ($_ -match "^DJANGO_SECRET_KEY=") { "DJANGO_SECRET_KEY=" + $secret } else { $_ }
    }
    # PS 5.1 Set-Content -Encoding UTF8 writes a BOM which python-environ
    # rejects as an invalid line. Use .NET directly for UTF-8 no-BOM.
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    $envPath = (Resolve-Path ".").Path + "\.env"
    [System.IO.File]::WriteAllLines($envPath, [string[]]$lines, $utf8NoBom)
    Ok ".env created from .env.example (DJANGO_SECRET_KEY regenerated)"
    Warn "review .env -- adjust DB_PASSWORD if your local postgres uses something other than 'postgres'"
} else {
    Ok ".env present"
}

try { python --version | Out-Null; Ok "python available" } catch { Die "python not on PATH" }
try { psql --version | Out-Null;  Ok "psql available"  } catch { Die "psql not on PATH (needed to reset dev DB)" }

# ----------------------------------------------------------------------
# 1. Install uv if missing
# ----------------------------------------------------------------------
Say "Install uv"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "  Installing uv via the official installer..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = ($env:USERPROFILE + "\.local\bin;" + $env:Path)
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) { Die "uv installed but not on PATH. Restart shell and rerun." }
}
$uvVersion = (uv --version).Trim()
Ok "uv: $uvVersion"

# ----------------------------------------------------------------------
# 2. Move apps from cvmaker/<app> to apps/<app>
# ----------------------------------------------------------------------
Say "Move apps to apps/"
New-Item -ItemType Directory -Force -Path ".\apps" | Out-Null

$apps = @("accounts", "cv", "entries", "sections")
foreach ($app in $apps) {
    $src = ".\cvmaker\" + $app
    $dst = ".\apps\"    + $app
    if (Test-Path $dst) { Warn ($dst + " already exists -- skipping"); continue }
    if (-not (Test-Path $src)) { Warn ($src + " not found -- skipping"); continue }
    Git-Run ("mv " + $src + " -> " + $dst) @("mv", $src, $dst) | Out-Null
    Ok ("moved " + $src + " -> " + $dst)
}

# ----------------------------------------------------------------------
# 3. Move templates, static, media to repo root
# ----------------------------------------------------------------------
Say "Move templates/, static/, media/ to repo root"

foreach ($dir in @("templates", "static", "media")) {
    $src = ".\cvmaker\" + $dir
    $dst = ".\"         + $dir
    if (-not (Test-Path $src)) { Warn ($src + " not found -- skipping"); continue }
    if (Test-Path $dst)        { Warn ($dst + " already exists at repo root -- check manually; skipping git mv"); continue }
    Git-Run ("mv " + $src + " -> " + $dst) @("mv", $src, $dst) | Out-Null
    Ok ("moved " + $src + " -> " + $dst)
}

# ----------------------------------------------------------------------
# 4. Delete the old nested cvmaker/cvmaker/ package and old manage.py
# ----------------------------------------------------------------------
Say "Remove old cvmaker/cvmaker/ and cvmaker/manage.py"
if (Test-Path ".\cvmaker\cvmaker") {
    Git-Run "rm cvmaker/cvmaker" @("rm", "-rf", ".\cvmaker\cvmaker") | Out-Null
    Ok "removed cvmaker/cvmaker/"
}
if (Test-Path ".\cvmaker\manage.py") {
    Git-Run "rm cvmaker/manage.py" @("rm", ".\cvmaker\manage.py") | Out-Null
    Ok "removed cvmaker/manage.py"
}

# ----------------------------------------------------------------------
# 5. Delete old migrations -- they reference auth.User, pointless after swap
# ----------------------------------------------------------------------
Say "Delete old migration files (they will be regenerated)"

$migrationFiles = Get-ChildItem -Path ".\apps" -Recurse -Filter "0*_*.py" |
                  Where-Object { $_.FullName -match "\\migrations\\" }
foreach ($m in $migrationFiles) {
    # -f forces removal even when the file has a staged rename from an
    # earlier partial run -- we want those files gone, not preserved.
    Git-Run ("rm -f " + $m.Name) @("rm", "-f", $m.FullName) | Out-Null
    $rel = $m.FullName.Replace((Get-Location).Path + "\", "")
    Ok ("removed " + $rel)
}

# ----------------------------------------------------------------------
# 6. Clean up the now-empty cvmaker/ directory if anything's left
# ----------------------------------------------------------------------
Say "Remove leftover cvmaker/ directory"
if (Test-Path ".\cvmaker") {
    $remaining = Get-ChildItem -Path ".\cvmaker" -Recurse -File -Force |
                 Where-Object { $_.FullName -notmatch "__pycache__" }
    if ($remaining) {
        Warn "cvmaker/ still contains files -- review manually before finishing:"
        $remaining | ForEach-Object { Write-Host ("    " + $_.FullName) }
    } else {
        Remove-Item -Recurse -Force ".\cvmaker"
        Ok "cvmaker/ removed"
    }
}

# ----------------------------------------------------------------------
# 6b. Strip UTF-8 BOM from .env if present (prior runs left it there)
# ----------------------------------------------------------------------
Say "Normalize .env encoding (strip BOM if present)"
# .NET file APIs use the process cwd, not PowerShell's cwd. Resolve to absolute.
$envAbs = Join-Path (Get-Location).Path ".env"
if (Test-Path $envAbs) {
    $envBytes = [System.IO.File]::ReadAllBytes($envAbs)
    if ($envBytes.Length -ge 3 -and $envBytes[0] -eq 0xEF -and $envBytes[1] -eq 0xBB -and $envBytes[2] -eq 0xBF) {
        $stripped = New-Object byte[] ($envBytes.Length - 3)
        [Array]::Copy($envBytes, 3, $stripped, 0, $stripped.Length)
        [System.IO.File]::WriteAllBytes($envAbs, $stripped)
        Ok "stripped BOM from .env"
    } else {
        Ok ".env has no BOM"
    }
}

# ----------------------------------------------------------------------
# 6c. Sanity: every moved app must be importable before we call Django
# ----------------------------------------------------------------------
Say "Verify apps/ layout"
foreach ($app in @("core", "accounts", "cv", "entries", "sections")) {
    $pkg = ".\apps\" + $app + "\__init__.py"
    if (-not (Test-Path $pkg)) {
        $srcPkg = ".\cvmaker\" + $app + "\__init__.py"
        if (Test-Path $srcPkg) {
            Die ("apps/" + $app + "/ is missing but cvmaker/" + $app + "/ still exists. The git mv did not run. Run: git mv cvmaker/" + $app + " apps/" + $app)
        } else {
            Die ("apps/" + $app + "/__init__.py missing AND cvmaker/" + $app + "/ gone. Check `git status` -- the package is lost.")
        }
    }
}
Ok "apps/ layout looks correct"
# (The python -c probe here was fragile across PS versions due to quoting.
# The file checks above catch the git-mv-didn't-happen case; any real
# import problem surfaces at makemigrations with a clearer error.)

# ----------------------------------------------------------------------
# 7. Sync dependencies via uv
# ----------------------------------------------------------------------
Say "Sync dependencies with uv"
uv sync
if ($LASTEXITCODE -ne 0) { Die "uv sync failed" }
Ok "uv sync complete"

# ----------------------------------------------------------------------
# 8. Reset the dev database
# ----------------------------------------------------------------------
Say "Reset dev database (dropdb + createdb cvmaker)"

$envLines = Get-Content ".\.env" | Where-Object { $_ -match "^DB_" }
$dbName = ($envLines | Where-Object { $_ -match "^DB_NAME=" }) -replace "^DB_NAME=", ""
$dbUser = ($envLines | Where-Object { $_ -match "^DB_USER=" }) -replace "^DB_USER=", ""
$dbHost = ($envLines | Where-Object { $_ -match "^DB_HOST=" }) -replace "^DB_HOST=", ""
if (-not $dbName) { $dbName = "cvmaker" }
if (-not $dbUser) { $dbUser = "postgres" }
if (-not $dbHost) { $dbHost = "localhost" }
Write-Host ("  target: " + $dbUser + "@" + $dbHost + "/" + $dbName)

& dropdb -U $dbUser -h $dbHost --if-exists $dbName
if ($LASTEXITCODE -ne 0) { Die "dropdb failed (wrong password? wrong host?)" }
& createdb -U $dbUser -h $dbHost $dbName
if ($LASTEXITCODE -ne 0) { Die "createdb failed" }
Ok ("database " + $dbName + " recreated")

# ----------------------------------------------------------------------
# 9. makemigrations + migrate -- fresh start with custom User
# ----------------------------------------------------------------------
Say "Generate new migrations and apply"

uv run python manage.py makemigrations accounts core cv entries sections
if ($LASTEXITCODE -ne 0) { Die "makemigrations failed" }
Ok "makemigrations complete"

uv run python manage.py migrate
if ($LASTEXITCODE -ne 0) { Die "migrate failed" }
Ok "migrate complete"

# ----------------------------------------------------------------------
# 10. Sanity check -- manage.py check must pass
# ----------------------------------------------------------------------
Say "Django system check"
uv run python manage.py check
if ($LASTEXITCODE -ne 0) { Die "manage.py check failed" }
Ok "system check clean"

# ----------------------------------------------------------------------
# 11. Stage new files + commit
# ----------------------------------------------------------------------
Say "Stage and commit"
git add -A
git status --short

Write-Host ""
Write-Host "About to commit Phase 1 (all sub-phases). Review the staged diff above." -ForegroundColor Yellow
Write-Host "Press Enter to continue, Ctrl-C to abort..." -ForegroundColor Yellow
Read-Host | Out-Null

$commitLines = @(
    "Phase 1: foundations (layout, tooling, docker, CI, tests, custom User)",
    "",
    "1.1 src/ layout, split settings, uv:",
    "- Move project package to src/cvmaker/ with settings/{base,dev,prod,test}.py",
    "- Move apps under apps/ (accounts, cv, entries, sections) + new apps/core",
    "- Move templates/, static/, media/ to repo root",
    "- pyproject.toml with uv-managed deps; requirements.txt fallback retained",
    "- manage.py at repo root; sys.path adjusted so 'from accounts.X' still works",
    "",
    "1.2 dev tooling:",
    "- .pre-commit-config.yaml (ruff + djlint + django-upgrade + mypy)",
    "- Makefile (dev/test/lint/fmt/typecheck/ci/up/down, all via uv run)",
    "- .editorconfig",
    "",
    "1.3 docker:",
    "- docker/web.Dockerfile + docker/worker.Dockerfile (multi-stage, Typst baked)",
    "- docker/entrypoint.sh (wait-for-db, opt-in migrations)",
    "- compose.yaml (web + worker + postgres 16 + redis 7 + minio)",
    "- .dockerignore",
    "",
    "1.4 CI:",
    "- .github/workflows/ci.yml (lint / typecheck / test / docker-build)",
    "",
    "1.5 custom User:",
    "- accounts.User(AbstractUser) with email identifier + UserManager",
    "- All FKs updated to settings.AUTH_USER_MODEL",
    "- Migrations regenerated from scratch (dev DB reset; no real data)",
    "",
    "1.6 tests:",
    "- tests/{unit,integration,e2e}/ scaffolding",
    "- tests/factories.py (User, CV, Section, every Entry subtype)",
    "- tests/conftest.py (user / admin_client / cv / section fixtures)",
    "- Unit tests for User model and entry serialize() contracts",
    "- Integration smoke tests for URL reversal + signup/login + admin",
    "",
    "ADR-0001 (project structure) and ADR-0004 (custom User) added."
)
$commitMsg = $commitLines -join "`r`n"

git commit -m $commitMsg
if ($LASTEXITCODE -ne 0) { Die "commit failed" }

Say "Done"
Ok "Phase 1 committed. Review with 'git log --stat -1', then 'git push origin main'."
Write-Host ""
Write-Host "Next: run 'uv run python manage.py createsuperuser' to make an admin account." -ForegroundColor Cyan
Write-Host "Then: 'uv run python manage.py runserver' and confirm the site loads."        -ForegroundColor Cyan
