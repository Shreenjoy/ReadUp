# ReadUp

**Adaptive reading and math practice for young learners.**

ReadUp gives volunteer tutors a way to run short practice sessions with children aged 7–13 and
see how each child is improving. Questions adjust their difficulty as a session runs, and
instructions can appear in Bengali, Hindi, Urdu or Gujarati so a child who is still learning
English is not stuck on the directions.

Built for INFO 490 (Project 2) by Team 5 — Keshav Arya, Revaant Daga, Shreenjoy Sengupta and
Pranay Varanasi — with [Informed Empowerment](https://informedempowerment.org) as the pilot
partner.

**Tutors hold the accounts. Children never sign up, never type personal information, and only
ever see the practice screen.**

---

## The problem

One-to-one tutoring is one of the most effective ways to help a child learn, and almost nobody
can afford it at scale. Volunteer programs fill part of the gap, but their tutors work from
paper worksheets and keep notes in spreadsheets or in their heads. When a student changes
tutor, that history is lost. A worksheet that is too hard makes a seven-year-old give up; one
that is too easy wastes the session.

ReadUp fixes the fit, and keeps the history.

## Main features

| Feature | What it does |
|---|---|
| **Adaptive practice sessions** | The quiz engine moves a child **up a level after three correct answers in a row** and **down after two misses**. Every answer records the level it was asked at and the level the engine moved to, so a tutor can see exactly why the difficulty changed. |
| **Bilingual instruction lines** | Each question can carry its instruction in the child's home language alongside the English prompt. |
| **Lesson bank with an AI authoring assistant** | Tutors paste a passage; the assistant drafts questions, estimates a level and writes the instruction line in each home language. **The tutor reviews and edits before anything saves.** See [README_AI.md](README_AI.md). |
| **Progress dashboard, JSON API and CSV report** | Level over time, accuracy by skill and a "needs practice" list, all computed from saved attempts. Downloadable as CSV to share with a program lead. |
| **Roles** | A tutor sees their own students. A program lead sees everyone in their program. Enforced in the queryset, not the template. |

## Screens

`/` landing · `/accounts/signup/` · `/students/` my students · `/students/<id>/` profile ·
`/practice/session/<id>/` the child's practice screen · `/practice/session/<id>/summary/` ·
`/lessons/` lesson bank · `/lessons/draft/` AI assistant · `/progress/` dashboard ·
`/progress/api/` JSON · `/progress/export.csv` report

Screenshots of each are in [`docs/screenshots/`](docs/screenshots).

---

## Run it locally

Requires Python 3.11+.

```bash
git clone <this repo> && cd readup
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit it, see below
python manage.py migrate
python manage.py seed_demo      # a tutor, six students and a lesson bank at every level
python manage.py runserver
```

Open <http://127.0.0.1:8000>. Sign in as **`tutor`** / **`readup12345`**, or as
**`lead`** / **`readup12345`** to see the program-lead view.

### Environment variables

Copy `.env.example` to `.env`. `.env` is git-ignored and must never be committed.

| Variable | Required | What it does |
|---|---|---|
| `SECRET_KEY` | yes | Django signing key. Any long random string for local work. |
| `DEBUG` | no | `True` locally, `False` in production. |
| `ALLOWED_HOSTS` | in production | Comma-separated hostnames. |
| `GROQ_API_KEY` | **no** | Enables the AI authoring assistant. **Without it the app still works** — lesson drafting falls back to a built-in rule-based generator and says so on screen. |
| `AI_MODEL` | no | Defaults to `llama-3.3-70b-versatile`. |
| `AI_ENABLED` | no | Set `False` to force the offline path, which is how the fallback is tested. |

### Database

SQLite, created by `migrate`. No external database server is needed to run or grade this
project. The schema is four apps' worth of migrations, all committed.

### Try the AI feature

1. Sign in and go to **Lessons → + Draft with assistant**.
2. Paste a short passage (two or three sentences is enough) and press **Draft questions**.
3. Review the draft — edit any prompt, change which answer is correct, fix a translation.
4. Press **Save lesson**. It appears in the bank and the quiz engine starts using it.

With no `GROQ_API_KEY` set you will see a yellow note saying the draft is rule-based. That is
the fallback working, not an error.

## Tests

```bash
python manage.py test
```

58 tests covering the adaptive engine as pure functions, the session flow end to end, the
authorisation rules that keep one tutor out of another's students, the AI assistant's failure
paths, and the dashboard/API/CSV output.

## Project layout

```
accounts/   tutor accounts, roles, student profiles      (Keshav)
lessons/    the lesson bank and the AI assistant          (Revaant)
practice/   the adaptive quiz engine and sessions         (Shreenjoy)
progress/   dashboard, JSON API, CSV export               (Pranay)
templates/  all HTML, with base.html for the tutor shell
static/css/ one stylesheet; the child session has its own visual mode
docs/       screenshots and the first-draft write-up
```

Each app matches one team member's area from the project proposal, and all four share the
`Student` and `Attempt` models.
