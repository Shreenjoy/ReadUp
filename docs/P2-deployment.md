# Part 5 — Deployment, cost and production readiness

ReadUp · Team 5 (Shreenjoy Sengupta, Pranay Varanasi, Anishka Kharana) · INFO 490

---

## 5.1 Deployment

**Target:** PythonAnywhere free tier, `readup.pythonanywhere.com`. Full procedure in
[`deploy/DEPLOY.md`](../deploy/DEPLOY.md), with the WSGI entry point in
[`deploy/wsgi_pythonanywhere.py`](../deploy/wsgi_pythonanywhere.py).

**Status, stated honestly:** the configuration is written and the application is verified
reproducible from a clean clone — `git clone`, `pip install -r requirements.txt`, `migrate`,
`seed_demo`, and all 63 tests pass with no manual fixes. It is **not yet live**, and the
reason is a platform constraint rather than a technical one: a free PythonAnywhere account
allows exactly one web app, and our account's single slot currently serves a different
project. Resolving it means upgrading, using a second account, or retiring the existing app.

Nothing about ReadUp requires special hardware. It is a Django app with no model weights, no
GPU and no background workers, so it deploys anywhere Django deploys.

## 5.2 Infrastructure requirements

Measured or derived from the running application, not guessed.

| Resource | Requirement | Why |
|---|---|---|
| **CPU** | Negligible. Median practice-page response **2.4 ms**; the slowest measured path is a 7 ms cold template compile. | The adaptive engine is pure Python over two indexed queries. **No model runs on our servers** — that is the whole point of using a hosted API. |
| **GPU** | **None.** | Deliberate. See 5.3. |
| **RAM** | ~80–120 MB for one Django worker. | No torch, no transformers, no embeddings held in memory. The entire dependency list is Django, django-environ and requests. |
| **Storage** | <50 MB. The seeded database is ~200 KB; a year of pilot traffic adds a few MB. | Rows are small: an `Attempt` is seven integers and a short string. |
| **Database** | SQLite is genuinely sufficient at pilot scale. | Writes are one row per answered question — roughly 8 per session, a few hundred per week across the whole program. SQLite handles that with room to spare. It becomes the bottleneck on concurrent writes, which is the trigger to move to Postgres (5.4). |
| **AI inference** | **None self-hosted.** One outbound HTTPS call per lesson draft, a few seconds, initiated by a tutor. | Zero inference infrastructure is the single biggest cost decision in the project. |

## 5.3 Cost comparison

The real choice we made: **self-hosted model vs hosted API** for the lesson authoring
assistant.

| Factor | Self-hosted (local Hugging Face model) | **Hosted API (chosen)** |
|---|---|---|
| **Hardware** | 5+ GB RAM for a 2B model; a GPU to be usable at speed | None beyond the existing web server |
| **Est. monthly cost** | $0 on paper, but **not runnable on a free tier at all**. The smallest box that holds a 2B model comfortably is ~$12–25/mo; with a GPU, $50+ | **$0** at pilot volume on Groq's free tier. At paid rates, ~1,200 input + 600 output tokens per draft puts a semester of drafting in **cents** |
| **Latency** | 7+ s per generation on CPU; **219 s on a cold start** while the model loads into memory | 2–6 s, no cold start |
| **Maintenance** | Model files, version pinning, memory tuning, OOM debugging | An API key and a timeout |
| **Scalability** | Each concurrent draft needs its own multi-GB process | Scales with the provider, not with us |
| **Privacy** | **Better.** Nothing leaves the server | Tutor-typed passages leave the server. **No child data ever does** — the assistant never receives a name, level or history, which is what makes this acceptable |
| **Reliability** | No external dependency | Needs a fallback, which we built (`draft_offline`) |

**The decision, and the evidence behind it.** PythonAnywhere's free tier allows **100
CPU-seconds per day for the entire account**. A 2B model costs several CPU-seconds per
generation, so lesson drafting alone would exhaust the day's budget in roughly **two dozen
lessons** and take the site down for every tutor — including the child mid-session, who needs
nothing more than a database read. We had measured exactly this in earlier coursework before
choosing.

The privacy row is the one that would have changed our mind. It does not, because the feature
is scoped so that no child data is ever sent. Had the assistant needed a student's history to
personalise questions, self-hosting would have been the right answer and the free tier simply
would not have been viable.

## 5.4 Scalability to 10,000 daily active users

**Stated assumptions**, since the estimate is worthless without them:

- 10,000 DAU here means ~10,000 *children*, served by roughly **500 tutors** at a 20:1 ratio.
- One session per child per day, 8 questions → **80,000 writes/day**.
- Traffic concentrates into after-school hours: assume **70% inside a 4-hour window**, giving
  a peak of ~14,000 answers/hour ≈ **4 writes/second**, with bursts to perhaps 20/s.
- Lesson drafting scales with *tutors*, not children: ~500 tutors × 2 drafts/week ≈ **140
  drafts/day**.

**What breaks first: SQLite.** Not CPU, not the AI, not bandwidth. SQLite serialises writes,
and the practice loop is write-heavy by design — one row per answer. At 4 writes/second with
bursts, lock contention arrives long before anything else strains.

| Pressure | At 10,000 DAU | Response |
|---|---|---|
| **Database writes** | 80,000/day, bursty | **Move to Postgres.** The only change required is `DATABASES`; the ORM code is untouched. This is the first and most important migration. |
| **Web tier** | ~4 req/s sustained, peaks higher | Stateless already. Run 2–4 gunicorn workers behind a load balancer; add workers, not machines. |
| **AI inference cost** | ~140 drafts/day ≈ 4,200/month. At ~1,800 tokens each ≈ 7.6M tokens/month | **Single-digit dollars per month.** It does not scale with children, which is why this architecture holds. Add a cache keyed on the passage hash and it drops further. |
| **Static assets** | One 6 KB stylesheet | Serve via WhiteNoise or a CDN. Not a real problem. |
| **Read load on the dashboard** | Program leads aggregating across hundreds of students | Add indexes on `Attempt(student, created_at)`, then a nightly rollup table if aggregation gets slow. Do not optimise this before measuring it. |

**Architectural changes that become necessary, in order:**

1. **Postgres**, for concurrent writes.
2. **A connection pool** (PgBouncer), once worker count rises.
3. **Caching the progress dashboard**, which is the only read-heavy page.
4. **Moving lesson drafting off the request path** into a queue, so a slow provider cannot
   hold a web worker. At 140 drafts/day this is not yet worth the complexity — it is the
   change to make when provider latency starts blocking workers, not before.
5. **Per-program data partitioning**, if ReadUp is ever used by multiple organisations with
   separate data-residency expectations.

**What does not need to change:** the adaptive engine. It is two indexed queries and some
arithmetic per answer, and it costs the same at 10 children as at 10,000.

## 5.5 Security and reliability

Implemented, not aspirational — each row names where it lives.

| Concern | What we do |
|---|---|
| **Environment variables** | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` and `GROQ_API_KEY` all read via `django-environ` from `.env`. `.env` is git-ignored; `.env.example` documents the shape. `settings.py` contains no secret. |
| **Input validation** | Django forms on every write path. `StudentForm` rejects a one-character name; `validate_passage` bounds assistant input at 20–4,000 characters *before* an API call is spent; the draft save refuses any question lacking four answers and exactly one correct. |
| **Authentication and permissions** | `@login_required` on every view except the landing page. Authorisation is a **queryset rule** (`Student.visible_to`), not a template check, so a hand-typed primary key cannot reach another tutor's student. Verified by test 5 and by `AuthorisationTests`. |
| **API key protection** | Server-side only, never rendered, never logged. The key is read at call time from settings. |
| **Error handling** | The AI assistant has **no path that raises to the user**: timeout, connection error, unparseable JSON, malformed questions and a missing key all degrade to a rule-based draft with an on-screen explanation. Each is covered by a test. |
| **Rate limiting** | **Not implemented, and this is our main gap.** Drafting is login-only and tutor-initiated, which bounds abuse to authenticated adults, but a logged-in tutor could spend the API quota in a loop. Per-user throttling on `/lessons/draft/` is the next security change we would make. |
| **Logging and monitoring** | Assistant failures log at `warning` with the reason. Uptime monitoring is not configured. |
| **User privacy** | **Children have no accounts.** A `Student` row holds a first name, grade and home language and nothing else — there is no surname, date of birth, contact detail or address field, and a test asserts those fields do not exist so a later migration cannot quietly add one. Nothing about a child is ever sent to the AI provider. |
| **AI-specific risks** | A tutor reviews every generated question before it saves, so no model output reaches a child unread. Structural validation drops malformed questions rather than repairing them. Saves are atomic, so a half-written lesson cannot sit in the bank. Model output is escaped by Django's autoescaping like any other untrusted text. |
| **CSV injection** | Report fields beginning `=`, `+`, `-` or `@` are prefixed with `'`, so a tutor-written prompt cannot execute as a formula when a program lead opens the report in Excel. Covered by a test. |

**Known gaps, not hidden:** no rate limiting, no uptime monitoring, no automated backups of
the SQLite file, and translation quality is unverified by anything except a tutor's eyes.
