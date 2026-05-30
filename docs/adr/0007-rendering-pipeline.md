# ADR-0007: Rendering pipeline — RQ over Redis, content-hash cache, hardened Typst subprocess

- **Status:** accepted
- **Date:** 2026-04-27
- **Phase:** 3

## Context

PDF rendering is the user-facing payoff of the entire system. A user
clicks "render" and expects a finished PDF in seconds. Today (Phase 0–2)
the render runs synchronously in the request thread: ``download_cv``
serializes the CV, hands it to rendercv, blocks while Typst writes the
PDF, and streams the bytes back. That has four problems we can no
longer ignore:

1. **Latency under load.** Typst takes 1–3 seconds for a typical CV,
   plus 100–300 ms of rendercv overhead. Doing this in a gunicorn
   worker means one render blocks one HTTP slot for that whole window.
   Two simultaneous renders block two slots, four block four. At
   gunicorn's default `--workers=4 --threads=1` we can't even hold a
   browser tab open while a render is in flight.
2. **Wasted re-renders.** Most "renders" are duplicates -- the user
   clicks the button twice, or refreshes the result page, or has a
   cached PDF in a browser tab and asks for it again. Today every
   click runs Typst from scratch.
3. **Sandboxing.** Typst is a parser + compiler that reads templates
   the user can influence. Even with a curated theme list, we want
   *defense in depth* -- no network, capped memory, no shared
   filesystem with user data, hard time bound.
4. **Future async features.** Phase 9 ships translation memory ("AI
   suggested rewrites for your bullet points") and Phase 7 ships
   billing-aware quotas ("free tier renders monthly"). Both want a
   queue with a clean job model -- one we can attach quotas, retries,
   and metrics to.

The right shape is a **fire-and-forget render queue with a
content-hash cache**.

## Decision

Three coupled choices.

### 1. Queue: RQ over Redis (not Celery)

We already run Redis (cache + sessions). RQ is a thin layer over Redis
that:

- Accepts a Python callable (no manifest of "registered tasks").
- Has zero broker-side scheduling logic -- jobs are just LPUSH/BRPOP.
- Trivially supports per-queue worker pools (`render` queue with one
  worker per CPU).
- Has a Django integration (`django-rq`) that wires jobs into the
  Django app registry, plumbs Redis URL through Django settings, and
  ships an admin dashboard at `/django-rq/` for ops.

Celery is the alternative. We rejected it because:

- Celery wants its own broker abstraction, its own result backend, its
  own monitoring (Flower), and its own scheduling primitives. We don't
  need any of that yet.
- Celery's task-discovery + decorator pattern hides Python code paths
  behind a magic string registry. RQ keeps the entry point as a plain
  function reference (`rendering.tasks.render_cv`), which means we can
  unit-test it directly with no harness.
- Celery's worker startup is ~3x slower than RQ's, which matters in
  CI and in `docker compose` cold starts.

If Phase 9's "AI rewrites" feature ever needs Celery's scheduling
primitives (chains, groups, beats), we can add Celery alongside RQ
without ripping RQ out -- they're orthogonal. We're not betting the
whole queue strategy on RQ; we're choosing the smallest tool that
solves Phase 3's problem.

### 2. Cache key: SHA-256 over canonical (payload, style, language)

Every Render row carries a ``payload_hash`` column (db-indexed). The
hash derivation is in ``rendering/services.py::compute_payload_hash``:

```python
canonical = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    default=str,
    ensure_ascii=True,
)
raw = f"{canonical}|style={style}|language={language}".encode()
hash = hashlib.sha256(raw).hexdigest()
```

Determinism rules, in order of subtlety:

- **`sort_keys=True`** -- dict ordering doesn't affect the hash.
  Critical because `dict(...)` insertion order varies across CPython
  optimizations and OS rebuilds.
- **`separators=(",", ":")`** -- whitespace doesn't either. Default
  json.dumps inserts `, ` and `: ` which would land us with two hashes
  for visually identical payloads.
- **`default=str`** -- `datetime.date`, `uuid.UUID`, and `pathlib.Path`
  cast cleanly. Without this, a payload containing a date raises
  TypeError; with it, the date and its `.isoformat()` string hash to
  the same value (intentional -- they're the same logical content).
- **`ensure_ascii=True`** -- the byte representation is platform-
  independent. Workers on a different OS than the web server can't
  silently disagree about the hash for a CV with Spanish accents.
- **`style` and `language` participate explicitly**, not just
  transitively via the payload. Critical edge case: a CV without an
  attached `CVLocale` produces an identical payload regardless of
  which language was requested, but the resulting PDF still must
  differ. Including them as first-class inputs prevents that cache
  collision.

The cache hot-path query is:

```sql
SELECT * FROM rendering_render
 WHERE payload_hash = $1 AND status = 'done'
 ORDER BY completed_at DESC
 LIMIT 1
```

`Meta.indexes = (Index(fields=("payload_hash", "status")),)` makes
this an index-only scan. With even a few thousand renders a day,
the cache lookup stays sub-millisecond.

We rejected MD5 (collision risk, not crypto-relevant here but a code
smell), and Python's built-in `hash()` (process-local randomization,
not durable across web/worker process boundaries). SHA-256 is fast
enough -- a 10 KB payload hashes in microseconds -- and produces a
fixed-width 64-hex string that fits in a `CharField(max_length=64)`
with a clean btree index.

Failed renders deliberately do **not** short-circuit the cache.
The reasoning: if the user clicks "Retry", we want to actually retry,
not return the same failure. The cache lookup filters
`status='done'` precisely so a `failed` row doesn't poison future
attempts.

### 3. Sandbox: container-level + subprocess-level

Three layers, none of which are the only line of defense:

- **Container**: the worker container runs as a non-root user (uid
  1000, no shell), uses `python:3.12-slim-bookworm` as base (small
  attack surface), and -- in compose -- has no outbound network
  policy. Typst doesn't need the network at render time; rendercv
  has gathered all inputs by the time we invoke the binary. In prod
  (Phase 8) the container additionally runs with a 256 MiB memory
  limit and `cap_drop=ALL`.
- **Subprocess**: rendercv invokes Typst via `subprocess.run(...,
  shell=False, timeout=30)`. The shell-false flag eliminates argument-
  parsing tricks. The timeout is 30 seconds -- generous for a normal
  render, hard cap on a runaway compile.
- **Queue-level**: RQ's `DEFAULT_TIMEOUT = 35` for the `render` queue.
  This is the Typst hard cap (30s) plus 5s of orchestration slack
  (Render row updates, file write to S3). If Typst respects its 30s
  timeout but the worker stalls on storage, RQ's timeout escalates and
  we record the failure rather than letting the worker hang.

The Typst subprocess invocation lives inside rendercv's own code; we
don't reimplement it. We trust rendercv's `subprocess.run` posture
(verified in Phase 1) and add the sandboxing layers around it.

### 4. Storage: signed S3 URLs (MinIO in dev)

The `Render.pdf_file` FileField uses Django's storage abstraction:

- **Test**: `InMemoryStorage` -- bytes never hit disk.
- **Bare `runserver`**: `FileSystemStorage` -- writes under
  `media/renders/`.
- **`compose up`**: MinIO via `storages.backends.s3.S3Storage`.
- **Production**: real S3, same backend.

Signed URLs expire after 1 hour. The render result page itself is
un-cachable (it's behind login + per-user authorization), so the
signed URL only ever lands in the user's browser tab; a leaked URL
is briefly useful but not durable. Phase 7's billing changes will
likely shorten this further for free-tier users.

## Lifecycle

```
POST /renders/cv/<cv_id>/                  -- enqueue_render_view
  └─ enqueue_render(cv, language, style)   -- service
       ├─ build_render_payload(cv, …)      -- side-effect-free
       ├─ compute_payload_hash(...)        -- 64-hex
       ├─ if matching done Render: return it (cache hit)
       └─ else: create queued Render
                _dispatch_render_job(render)
                  └─ django_rq.enqueue("rendering.tasks.render_cv", id)

(worker picks up the job)

render_cv(render_id)                       -- task
  ├─ load Render (select_related cv__locale)
  ├─ if already terminal: return (idempotent)
  ├─ status -> running
  ├─ _render_payload_to_pdf(payload, style)  -- subprocess
  │    └─ rendercv 2.x → Typst CLI → PDF bytes
  ├─ on success: pdf_file.save(...); status -> done; completed_at
  ├─ on _RenderError (user-readable): error stored verbatim; status -> failed
  └─ on Exception (genuine bug): generic error; status -> failed; re-raise

GET /renders/<render_id>/                  -- render_status_view
  └─ HTMX self-polls every 500 ms while non-terminal;
     fragment swaps to download link (done) or error+retry (failed)

GET /renders/<render_id>/pdf/              -- render_pdf_view
  └─ FileResponse streams from configured storage backend
```

## Consequences

### Positive

- **Web workers stop blocking on Typst.** A render request returns in
  well under 100 ms (DB round-trip + cache check + RQ enqueue). The
  user's browser polls a tiny HTMX fragment until the worker finishes.
- **Identical inputs never re-render.** A user clicking "render" five
  times in a row gets the cached PDF five times. Two users with the
  same content (e.g., a shared template) only run Typst once.
- **Sandbox is layered.** A vulnerability in any one layer
  (container, subprocess, queue) doesn't compromise the others.
- **Failure is loud and recoverable.** `_RenderError` stores its
  message verbatim in `Render.error`; the UI shows it directly with a
  Retry button that re-enqueues. No silent failure modes.
- **Future-proofed for billing/quotas.** A `Render` row per request
  means Phase 7's quota check is a `Render.objects.filter(user=…,
  requested_at__gt=…).count()` -- one indexed query.

### Negative

- **The cache hash is deterministic but not invariant.** Adding a new
  field to `build_render_payload` shifts the hash for every CV. We
  intentionally treat that as a feature -- when the payload changes,
  we *should* re-render -- but it means schema migrations to
  `CVInfo`/`CVDesign`/etc. invalidate the cache wholesale. Acceptable;
  the cache is opportunistic, not load-bearing.
- **Two simultaneous identical requests both enqueue jobs.** The
  cache hit only triggers when a `done` row already exists. If two
  users hit "render" at the exact same moment, both end up with
  queued rows pointing at the same content; the worker runs Typst
  twice. We accept this for simplicity -- a content-hash mutex would
  add Redis state we'd then need to manage. Phase 9 can revisit.
- **RQ has no native task-routing-by-priority.** We use one queue per
  priority level (`render`, plus future `default`); RQ doesn't allow a
  single queue to have priority within it. Fine for now.

### Neutral

- **Redis is now a hard dependency.** It already was for cache + the
  cache backend in prod; this just makes it required at boot rather
  than degraded-mode-graceful. Acceptable; the dev compose ships
  Redis, prod hosts ship Redis.

## Alternatives considered

- **Celery instead of RQ.** Discussed in §1 above. Heavier than what
  we need; we'd be paying for features we don't use.
- **Sync rendering with a streaming response.** Keep the request
  thread, but flush a "loading…" page first and the PDF after. Doesn't
  solve the worker-blocking problem, just hides it. And it loses
  caching entirely -- every request runs Typst.
- **Render in a separate web service (microservice).** A "render
  service" container with its own HTTP API. Defers the queue choice
  to "the API call queue" but adds an HTTP boundary, error
  serialization, and a service-discovery story. Wrong shape for
  Phase 3's complexity budget.
- **MD5 instead of SHA-256.** A few microseconds faster. Not
  collision-resistant. Cargo-culting collision-resistance for a non-
  crypto cache key is silly, but ruling out collisions on a 50-million-
  row table is cheap insurance.
- **Pre-render every CV asynchronously on every edit.** "Push" model:
  every entry change re-renders the user's CV. Way too eager for users
  who edit frequently. The pull model (cache-on-request) self-tunes to
  actual demand.
- **Store rendered PDFs on local disk, not S3.** Works for one web
  container; falls over the moment we scale to two. S3 is the
  Schelling point for shared object storage.

## References

- [django-rq](https://github.com/rq/django-rq)
- [RQ documentation](https://python-rq.org/)
- [django-storages S3 backend](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html)
- [Typst CLI](https://github.com/typst/typst) — the binary we sandbox.
- [rendercv](https://github.com/sinaatalay/rendercv) — drives Typst.
- ADR-0006 (per-entry translations) — how `language` flows into the payload.
