# P2-A3 — ReadUp first draft

**Team 5** · Shreenjoy Sengupta, Pranay Varanasi, Anishka Kharana
INFO 490 · University of Illinois Urbana-Champaign

Repository: this repo. Run instructions in [README.md](../README.md), AI details in
[README_AI.md](../README_AI.md), screenshots in [docs/screenshots](screenshots).

---

## 1. Updated product scope

**Startup name.** ReadUp.

**The problem.** Volunteer tutors cannot easily match practice to each child's level or track
progress over time. They work from paper worksheets and keep notes in spreadsheets or in their
heads, so when a student changes tutor the history is lost. A worksheet that is too hard makes
a seven-year-old give up; one that is too easy wastes the session. Children learning English
as a second language face a second barrier, because the instructions themselves are in English.

**Target users.** Volunteer tutors and program leads at small non-profit tutoring programs.
Our pilot partner is Informed Empowerment, which teaches English free of charge to children
aged 7–13 who speak Bengali, Hindi, Urdu or Gujarati. The children are the end beneficiaries
but are deliberately **not** users of the account system.

**Core value proposition.** Practice that fits each child without the tutor having to plan it,
and a progress record that survives a change of tutor.

**Three core features.**

1. **Adaptive practice sessions.** The quiz engine moves a child up a level after three
   correct answers in a row and down after two misses. Every attempt stores the level it was
   asked at and the level the engine moved to, so the adaptation is auditable rather than
   mysterious.
2. **A lesson bank with an AI authoring assistant.** Tutors paste a passage; the assistant
   drafts questions, estimates a level and writes the instruction line in each home language.
   The tutor reviews and edits before anything is saved.
3. **A progress dashboard with a downloadable report.** Level over time, accuracy by skill and
   a "needs practice" list, computed from saved attempts, exportable as CSV for a program lead
   or parent.

**Changes from P2-A2.** The concept, the screens and the flow are unchanged — the wireframes
submitted in P2-A2 still describe the product.

**The team has changed.** P2-A2 was submitted by four members: Keshav Arya, Revaant Daga,
Shreenjoy Sengupta and Pranay Varanasi. The team is now three: Shreenjoy Sengupta, Pranay
Varanasi and Anishka Kharana. The four Django apps were originally scoped one per member; with
three members they are split by feature area instead, and the roadmap below reflects the
current allocation.

Three further refinements, all made for technical reasons during the build:

- **A child's level is derived, not stored.** The proposal implied a level on the student
  record. We compute it from the most recent attempt instead, so the attempt history is the
  single source of truth and the dashboard can never disagree with the quiz engine.
- **The AI feature is scoped to lesson authoring.** The proposal did not commit to a specific
  AI integration. We chose the one that unblocks the product: a thin lesson bank starves the
  adaptive engine, and writing questions by hand is what keeps it thin.
- **Audio playback of the instruction line is deferred.** It is in the wireframes (screen 5)
  and is not built. It is on the roadmap below rather than quietly dropped.

## 2. Functional Django foundation

All of the following is implemented, running and tested in this repository.

| Requirement | Where |
|---|---|
| A functional Django project | `readup/`, four installed apps |
| At least one Django application | Four: `accounts`, `lessons`, `practice`, `progress` |
| At least two meaningful models | Seven: `TutorProfile`, `Student`, `Lesson`, `Question`, `Choice`, `Session`, `Attempt` |
| At least one relationship | Many: `Student → tutor (FK)`, `Question → Lesson (FK)`, `Choice → Question (FK)`, `Attempt → Session, Student, Question` |
| Working views and templates | 15 views, 13 templates with inheritance from `base.html` |
| At least one form | `TutorSignUpForm`, `StudentForm`, `DraftRequestForm`, `LessonForm`, plus the draft review form |
| A database-backed user workflow | Below |

**The complete workflow (Input → View → Database → Visible result):**

> A tutor signs in → **My students** → *Start session* → the engine reads the child's attempt
> history, decides a level and picks a question → the child taps one of four large answers →
> `practice.views.answer` writes an `Attempt`, recomputes the level and redirects → after
> eight questions the **session summary** shows accuracy, level change and best streak → the
> tutor writes a note, which saves to the student profile and appears for the next tutor.

Every step of that loop is implemented. The screenshots in `docs/screenshots/` are from a real
run of it, not mockups.

**Also working:** sign-up and login with roles, student CRUD, lesson bank with filtering, the
AI drafting and review flow, the progress dashboard, a JSON API at `/progress/api/`, and a CSV
export at `/progress/export.csv`.

**Tests:** 58, all passing (`python manage.py test`).

## 3. Initial AI implementation

**Implemented, not just planned.** Full detail in [README_AI.md](../README_AI.md).

- **Technique:** structured generation with validation — a passage goes in, a structurally
  checked JSON lesson comes out.
- **Model:** `llama-3.3-70b-versatile` through the Groq API. Hosted rather than local because
  our deployment tier allows 100 CPU-seconds per day for the whole account, and a local 2B
  model would exhaust that in a few dozen lessons. Drafting is also off the child's critical
  path, so a few seconds of network latency is acceptable where it would not be in a session.
- **Input:** a tutor-typed passage or topic, the skill, and how many questions. No child data
  is ever sent.
- **Output:** a draft lesson — title, estimated level, questions with four choices and one
  correct answer, and the instruction line in Bengali, Hindi, Urdu and Gujarati.
- **How it interacts with Django:** the draft is rendered as an editable form; on save it
  writes `Lesson`, `Question` and `Choice` rows inside a transaction, and the adaptive engine
  immediately begins serving those questions to children.
- **Evidence it works:** the flow runs end to end (screenshot `7b-ai-draft.png`), and the
  failure paths are covered by tests — timeout, network error, unparseable output, a question
  with two correct answers, an out-of-range level, and no API key at all. Each degrades to a
  rule-based draft rather than an error page.

## 4. Development progress and roadmap

Status as of 16 November 2026. Final push due 8 December 2026.

| Task | Current status | Responsible member | Expected completion |
|---|---|---|---|
| **Django core features** | **Done.** Four apps, seven models, 15 views, 13 templates, auth with tutor/lead roles, forms with validation. | All three | Complete |
| **Database and APIs** | **Done.** Migrations committed; JSON API at `/progress/api/`; CSV export; search and filtering. Remaining: per-lesson JSON endpoint. | Pranay Varanasi | 24 Nov |
| **AI integration** | **Working.** Drafting, validation, review-before-save and the full fallback chain are implemented and tested. Remaining: translation-quality flagging, caching repeat drafts, better math prompts. | Shreenjoy Sengupta | 30 Nov |
| **Evaluation and testing** | **Partly done.** 58 automated tests pass. Remaining: the five-test evaluation table with latency and quality scores, two documented failure cases, and one before/after improvement. | Shreenjoy Sengupta | 1 Dec |
| **Deployment** | **Not started.** Target PythonAnywhere at `readup.pythonanywhere.com`. Remaining: deploy, `collectstatic`, `.env` on the server, seed the demo program, cost and scalability write-up. | Anishka Kharana | 3 Dec |
| **Documentation** | **Mostly done.** README, README_AI and this document are written. Remaining: deployment notes, the cost comparison table, and the 3-minute demo video. | Pranay Varanasi, all | 7 Dec |
| **Audio for instruction lines** | **Deferred from P2-A2.** In the wireframes, not built. | Anishka Kharana | 5 Dec, if time |

**Known gaps we are not hiding.** There is no deployment yet, so Part 5 is unaddressed. The
evaluation table required by Part 4 is not written — the automated tests are not a substitute
for it. Translation quality is unverified by anything except a tutor's eyes. The audio button
in the wireframes does not exist.

## 5. GitHub submission

All code in this repository, with migrations, `requirements.txt`, `.gitignore` and a README
that runs the prototype from a clean clone in four commands. No `.env`, no API keys and no
model weights are committed.
