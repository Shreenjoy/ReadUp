# ReadUp — 4-minute presentation script (240s)

Team 5 — Shreenjoy Sengupta, Pranay Varanasi, Anishka Kharana · INFO 490.
Spoken words in quotes. `[ ]` lines are what you do on screen.
Pace ≈ 145 wpm. Total ≈ 545 spoken words, which leaves room to breathe.

---

## Before you record

1. `python manage.py migrate && python manage.py seed_demo && python manage.py runserver`
2. Sign in as `tutor` / `readup12345`. **Run one full session first** so the demo data looks
   lived-in and so you know which answers are correct.
3. Four tabs, in order: **My students** · **a student profile** · **Lessons → Draft** ·
   **Progress**.
4. If you have a `GROQ_API_KEY`, set it — the assistant's output is much better to show. If
   you don't, the fallback still demos fine and the yellow note is honest. Don't hide it.
5. Browser at 1340px, zoom 110%, notifications off. Do one timed dry run.

---

## 1. Product introduction — 0:00–0:20 (10 pts)

`[ Landing page ]`

> "This is **ReadUp** — adaptive reading and math practice for young learners.
>
> It's built for volunteer tutors at small non-profits. Our pilot partner is Informed
> Empowerment, which teaches English free to children aged seven to thirteen who speak
> Bengali, Hindi, Urdu or Gujarati. The tutors are the users. The children are who it's for."

## 2. Problem and solution — 0:20–0:50 (15 pts)

> "One-to-one tutoring is one of the most effective things in education, and almost nobody can
> afford it at scale. Volunteers fill the gap, but they work from paper worksheets and keep
> notes in their heads. When a child changes tutor, that history is gone.
>
> And the fit is wrong. A worksheet that's too hard makes a seven-year-old give up. Too easy
> wastes the session. Kids still learning English hit a second wall, because the instructions
> are in English too.
>
> ReadUp fixes the fit automatically, and keeps the history."

`[ Click into My students — six student cards with levels and languages ]`

## 3. Product demonstration — 0:50–2:50 (35 pts)

### 3a. The adaptive session — the complete flow, 0:50–1:50

`[ Student card → Start reading session ]`

> "Here's the whole loop. **Input**: the tutor picks a child and starts a session."

`[ Practice screen is up ]`

> "**Processing**: the engine reads this child's entire attempt history, works out what level
> they're on, and pulls a question at that level.
>
> **Output** is this — and this is the only screen a child ever sees. One question. Four big
> buttons. No score, no timer, no navigation to wander into."

`[ Point at the second line under the question ]`

> "The instruction appears in English *and* in the child's home language — this is Hindi, for
> Arjun. That's stored per question, not translated live, so a child never waits on a model."

`[ Answer three questions correctly — narrate as you click ]`

> "Watch the level. Three correct in a row…"

`[ Level in the header changes ]`

> "…and it moves up. Two misses in a row moves them back down. That asymmetry is deliberate:
> dropping a struggling kid costs almost nothing, but promoting them too fast produces exactly
> the thing we're trying to prevent."

`[ Finish the session → summary appears ]`

> "At the end the tutor — not the child — sees accuracy, the level change, and every question
> that was missed. The note they write here follows the student to the next tutor."

### 3b. The lesson bank and the AI assistant, 1:50–2:30

`[ Lessons → + Draft with assistant, paste a short passage ]`

> "The engine is only as good as the bank it draws from, and writing questions by hand is what
> stops the bank from growing. So: a tutor pastes a passage."

`[ Press Draft questions ]`

> "The assistant estimates a reading level, writes the questions with four answers each, and
> writes the instruction line in all four home languages."

`[ Draft appears ]`

> "And then it stops. **Nothing is saved yet.** The tutor edits any prompt, changes which
> answer is correct, fixes a translation — and only then saves. There is no path in this app
> that puts model output in front of a child without an adult reading it first."

### 3c. Progress, 2:30–2:50

`[ Progress tab ]`

> "Everything a child answers rolls up here: level over time, accuracy by skill, and what needs
> practice. A program lead sees their whole program, a tutor sees only their own students. And
> it downloads as a CSV to share with a lead or a parent."

## 4. Technical implementation — 2:50–3:30 (20 pts)

> "Django, four apps — one per feature area — over SQLite, with seven models.
>
> The design decision I'd point at: **a child's level isn't stored anywhere.** It's derived
> from their attempt history. Every attempt records the level it was asked at and the level the
> engine moved to, so the adaptation is auditable, and the dashboard and the quiz engine can
> never disagree about the same child.
>
> The AI is a hosted model — Llama 3.3 70B through Groq — and that's a measured choice, not a
> default. Our deployment tier gives a hundred CPU-seconds a day for the whole account. A local
> model would burn that in a few dozen lessons and take the site down. Drafting also isn't on
> the child's critical path, so a few seconds of network latency is fine there when it wouldn't
> be inside a session.
>
> There's a JSON API, a CSV export, and fifty-eight tests."

## 5. Challenges and future improvements — 3:30–3:50 (10 pts)

> "The hardest problem is one we **haven't** solved: we validate that a translation exists, not
> that it's any good. None of us reads all four languages. Right now the tutor is the only
> check, and we should say that plainly rather than claim the AI handles it.
>
> So the next thing we build is a flag-this-translation control, so the tutors who *do* read
> Bengali and Gujarati can correct the bank for everyone. After that, deployment and the audio
> playback button that's in our wireframes and isn't built yet."

## 6. Conclusion — 3:50–4:00 (5 pts)

> "ReadUp makes every practice session fit the child in front of you, and keeps the record when
> the tutor changes. Built for real tutors, with real kids starting in January. Thank you."

---

## If you run long

Cut in this order:

1. **3c, Progress** (20s) — the dashboard is the least surprising part.
2. The JSON API / test-count line in section 4 (~6s).
3. The second paragraph of section 2 (~10s).

**Never cut 3a.** It's the complete Input → Processing → Output flow the rubric asks for and
it carries most of the demonstration marks.

## Claims made, and where they're backed

| Claim | Backing |
|---|---|
| three up / two down | `practice/engine.py`, `PROMOTE_AFTER` / `DEMOTE_AFTER`, pinned by tests |
| level derived, not stored | `Student.current_level()` reads the last `Attempt.level_after` |
| instructions stored per question | `Question.instruction_translations`, a JSON field |
| nothing saves unreviewed | drafting and saving are two views, `lesson_draft` / `lesson_save_draft` |
| 100 CPU-seconds/day | PythonAnywhere free tier; the reason for the hosted model |
| 58 tests | `python manage.py test` |
| translation quality unverified | stated as limitation 1 in README_AI.md |
