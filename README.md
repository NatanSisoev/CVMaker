# CVMaker

A Django web app for composing CVs from reusable, per-user building blocks —
your entries, your sections, your info — and rendering them to PDF via Typst.
The product vision: write each experience once, translate it to the languages
you care about, then assemble the right CV for each role at the click of a
button.

> **Status:** active refactor. See [`ROADMAP.md`](ROADMAP.md) for the plan,
> [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) for what exists today, and
> [`docs/DESIGN.md`](docs/DESIGN.md) for the design direction.

## Quick start

Prerequisites: **Python 3.12+** and a running **PostgreSQL 14+**.

```bash
# 1. Clone
git clone https://github.com/NatanSisoev/CVMaker.git
cd CVMaker

# 2. Virtual env
python -m venv .venv
source .venv/bin/activate           # macOS / Linux
# .venv\Scripts\activate            # Windows (PowerShell)

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment
cp .env.example .env
# Open .env and set DJANGO_SECRET_KEY (and DB_* if your Postgres isn't local)
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 5. Database
createdb cvmaker                    # or whatever DB_NAME you set
cd cvmaker
python manage.py migrate
python manage.py createsuperuser    # optional, for /admin access

# 6. Run
python manage.py runserver
```

Visit <http://localhost:8000>.

## Layout

```
CVMaker/
├── ROADMAP.md           ← the plan
├── docs/                ← design, audit, ADRs
├── cvmaker/             ← Django project (Phase 1 moves this under src/)
│   ├── manage.py
│   ├── cvmaker/         ← project settings / urls / wsgi
│   ├── accounts/        ← auth
│   ├── cv/              ← CV aggregate + Info / Design / Locale / Settings
│   ├── sections/        ← ordered collections of entries
│   ├── entries/         ← polymorphic entry types (education, experience, …)
│   ├── templates/
│   ├── static/
│   └── media/           ← user uploads (gitignored)
├── requirements.txt
├── .env.example         ← template for your .env
└── .env                 ← local only, gitignored
```

## Development

A few things to know while we're in the refactor:

- **PDF rendering** happens in the request thread today. Phase 3 moves it to a
  queue — don't be surprised if downloads stall on cold starts.
- **Settings** live in `cvmaker/cvmaker/settings.py`. Phase 1 splits this into
  `settings/{base,dev,prod,test}.py`.
- **Frontend** is still Bootstrap 5 + crispy-forms. Phase 4 replaces it with
  Tailwind + HTMX + Alpine; see `docs/DESIGN.md`.

## Contributing to yourself

Every session, pick the next unchecked item in `ROADMAP.md`, do the work, tick
the box, and append a dated line to the roadmap's "Session log" section.
