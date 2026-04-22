# Phase 0 handoff

Everything Claude could do from the sandbox is done. Three things need your
hand on a Windows terminal before the checkpoint is real.

## 1. Physically delete the dead directories

These live on your Windows filesystem and the sandbox can't touch them. From
the repo root:

```powershell
# PowerShell
Remove-Item -Recurse -Force .\auxil, .\out, .\desktop.ini, .\cvmaker.tex, .\.idea
```

(`.idea/` is optional — keep it if you still use PyCharm; it's now gitignored
either way. `cvmaker.tex` already lives at `docs/diagrams/architecture.tex`
with the `];` typos fixed, so the copy at the repo root is redundant.)

Then clean up any `__pycache__` directories that the sandbox also couldn't
touch:

```powershell
git clean -fdX     # deletes gitignored files; safe because .gitignore now
                   # excludes all __pycache__ and .pyc artifacts
```

## 2. Install the new requirements

The `requirements.txt` has been rewritten (UTF-8 now) and `django-environ` was
added. Re-sync your venv:

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Create your `.env`

`.env.example` is the source of truth for variables. Copy it and fill in your
own values:

```powershell
Copy-Item .env.example .env
```

Generate a fresh `DJANGO_SECRET_KEY`:

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the output into `.env`. Set `DB_*` to match your local Postgres.

The sandbox wrote a throwaway `.env` too — it's gitignored, so it won't hit
the repo either way, but replace it with real values.

## 4. Verify

```powershell
cd cvmaker
python manage.py check
python manage.py runserver
```

You should see "System check identified no issues" and the dev server on
<http://localhost:8000>. Hit `/about/`, `/help/`, `/contact/`, `/status/`,
`/templates/`, `/import/`, `/accounts/profile/` — all of them now return a
friendly "Coming soon" page instead of crashing.

## 5. Commit and tag

When you're satisfied:

```powershell
git add -A
git status     # sanity-check what's staged
git commit -m "Phase 0: triage — UTF-8 encoding, secrets to env, fix URL stubs, narrow pre_delete signal"
git tag v0.0.0-pre-refactor
git push origin main --tags
```

You can always `git diff v0.0.0-pre-refactor` to see what the refactor has
changed since.

## What changed in this phase

- `requirements.txt` — rewritten UTF-8, dead deps removed
- `.gitignore` — rewritten UTF-8, comprehensive
- `.env.example` — new; `.env` — new (local only, gitignored)
- `cvmaker/cvmaker/settings.py` — secrets from env, security headers, `STORAGES` dict
- `cvmaker/cvmaker/urls.py` — lambda → `TemplateView` placeholders
- `cvmaker/accounts/urls.py` — same for `profile`
- `cvmaker/templates/placeholder.html` — new; shared "coming soon" page
- `cvmaker/cv/views.py` — two URL-name typos fixed
- `cvmaker/entries/models.py` — `get_entry_model` raises on unknown; registry
- `cvmaker/sections/models.py` — `pre_delete` narrowed to 10 entry senders
- `docs/diagrams/architecture.tex` — relocated from root, `];` typos fixed
- `README.md` — rewritten with accurate setup for macOS/Linux and Windows
- `docs/CURRENT_STATE.md`, `docs/DESIGN.md`, `ROADMAP.md`, `HANDOFF.md` — new
- 48 stale `.pyc` files untracked from the git index

Next session starts **Phase 1.1 — project layout + uv migration**.
