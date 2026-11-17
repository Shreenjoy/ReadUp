# Part 4 — Evaluation, testing and improvement

ReadUp · Team 5 (Shreenjoy Sengupta, Pranay Varanasi, Anishka Kharana) · INFO 490

Every number here was measured on the real application through the real Django request path
by `python manage.py evaluate`, which writes `docs/evaluation-results.json`. Nothing is
estimated. Re-running the command reproduces the table.

Latency is the median of five runs. Median rather than mean, because the first request pays
for template compilation and one outlier should not define the number.

---

## 4.1 Evaluation criteria

ReadUp is used by a volunteer with a seven-year-old sitting next to them, so the metrics that
matter are not the usual ones:

| Metric | Why it is the right one here |
|---|---|
| **Adaptation correctness** | The product's only real algorithm. If "three up, two down" is wrong, the product does not work, and nothing else matters. |
| **Practice-page latency** | A child is watching this screen. Anything a child notices is too slow, so the target is **under 200 ms**, far tighter than a normal web page. |
| **Authorisation correctness** | A tutor reaching another tutor's student is a child-privacy failure, not a bug. Binary: it works or the product is unshippable. |
| **AI draft usability** | Measured as *structural validity* (four choices, exactly one correct) and *translation coverage*, because a structurally broken question cannot be scored by the engine at all. |
| **Report fidelity** | The CSV must carry one row per recorded attempt. A report a program lead cannot trust is worse than no report. |

Quality is scored 1–10 against the expected behaviour stated in each row.

## 4.2 Five realistic tests

| # | Input | Expected | Actual | Quality | Latency |
|---|---|---|---|---|---|
| 1 | A student at level 1 answers three correctly in a row | Level rises to 2 **after the third**, not before | `level_after` per answer: **[1, 1, 2]** | 10/10 | 2.5 ms |
| 2 | A student at level 4 misses two in a row | Level drops to 3 after the second miss | `level_after` per answer: **[4, 3]** | 10/10 | — |
| 3 | A 157-character passage, 4 questions requested | 4 structurally valid questions with translated instruction lines | `source=offline`, 4 questions, **all well-formed = True**, level 4, **0/4 carry a translation** | 4/10 | <1 ms |
| 4 | GET the practice screen (engine picks a level and a question) | Under 200 ms | HTTP 200, **median 2.7 ms** over 5 loads `[7.1, 2.6, 3.0, 2.7, 2.6]` | 10/10 | 2.7 ms |
| 5 | A second tutor requests another tutor's student by primary key | 404 on profile and session, 0 attempts in the API | profile **404**, start **404**, API attempts visible **0** | 10/10 | — |
| 6 | Load the dashboard, then download the CSV | Both 200; one CSV row per attempt | dashboard 200 in 1.7 ms; CSV 200 in 1.1 ms with **13 rows against 13 attempts** | 9/10 | 1.7 ms |

**6 of 6 passed.** Test 3 passed structurally and still scores 4/10 — see failure 2.

Latency is dominated by nothing: the slowest measured path is a 7 ms cold template compile.
The adaptive engine is pure Python over indexed queries, so the child never waits. That is a
direct consequence of keeping the AI off the session path.

## 4.3 Failure analysis

### Failure 1 — the engine served a level it did not admit to

**What failed.** The lesson bank has no questions at reading L5, reading L6, math L5 or math
L6 (measured: `bank_coverage` in the results file). When a child earned level 5,
`pick_question` fell outward to level 4 and served a level 4 question — while the practice
header still displayed **"Level 5"**.

Reproduced directly:

```
engine asked for level : 5
question actually served: level 4  ('Inference')
MISMATCH: True
```

**Why it failed.** The outward fallback is deliberate and correct — a gap in the bank should
not end a child's session. The bug was that the substitution was *invisible*. The view passed
the engine's requested level to the template instead of the level of the question it had
actually chosen, and no record of the substitution was kept.

**Impact.** The worst kind: silent and slow. A child who reaches the top of the bank practises
below their level indefinitely, the interface tells the tutor they are at level 5, and the
progress dashboard agrees. Nobody has any reason to look. This is precisely the "worksheet
that is too easy wastes the session" problem the product exists to solve, reintroduced by the
product itself.

**What could be improved.** Surface the substitution everywhere it is relevant: the header,
the session summary and the lesson bank. Implemented — see 4.4.

### Failure 2 — the offline draft is structurally perfect and pedagogically weak

**What failed.** With no `GROQ_API_KEY` configured, lesson drafting falls back to the
rule-based generator. Test 3: **4 of 4 questions structurally valid, 0 of 4 carrying any
translation**, and every question of the form *"Which word appears in the passage: 'stopped'?"*

**Why it failed.** By design, and the design is a compromise. The fallback exists so a tutor
is never blocked by a missing key, a timeout or a spent quota. It produces *recognition*
questions because generating genuine comprehension questions and four plausible distractors is
the thing the language model is for. It cannot translate at all, because translation without a
model would mean shipping a phrasebook.

**Impact.** Bounded but real. The flow works end to end and nothing breaks, but a lesson
drafted offline is markedly worse than one drafted with a model, and a tutor who never
configures a key gets the weak version permanently. The yellow banner says the draft is
rule-based, which is honest, but honesty is not quality.

**What could be improved.** Two things we have *not* done, stated plainly rather than claimed:
seed a small bank of hand-written distractors per level so the offline generator can at least
produce comprehension-shaped questions, and cache successful model drafts so a program with
intermittent connectivity accumulates good lessons rather than regenerating weak ones.

### A third limitation worth recording

We validate that a translation *exists*, never that it is *correct*. None of the team reads
all four languages. The tutor review step is the only check, and the product cannot detect a
bad Gujarati instruction line on its own.

## 4.4 Demonstrated improvement

**Target: failure 1**, because it is silent and it attacks the product's core promise.

### Before

| | |
|---|---|
| Practice header at requested level 5 | displayed **"Level 5"** while asking a level 4 question |
| Attempt record | stored `level_before=5`; no way to know a level 4 question was served |
| Session summary | no mention of the substitution |
| Lesson bank | no indication that L5 and L6 were empty |
| Signal available to the tutor | **none** |

### Modification

No migration and no new columns — both facts were already in the database and simply never
compared.

1. `Attempt.served_level` — the level of the question actually asked, from
   `question.lesson.level`.
2. `Attempt.level_mismatch` — true when `served_level != level_before`.
3. `Session.coverage_gaps` — which requested levels the bank could not supply.
4. The practice view now passes **the served level** to the header, with the requested level
   alongside it.
5. The session summary shows a warning naming the missing level and linking to the lesson
   assistant.
6. The lesson bank shows a coverage matrix so a tutor can see the hole *before* a child
   reaches it.

### After

| | |
|---|---|
| Practice header | shows **Level 4**, the level actually being asked |
| Attempt record | `served_level=4`, `level_mismatch=True` |
| Session summary | *"Mitali earned level 6 but there are no level 6 reading questions, so level 4 was asked instead."* |
| Lesson bank | coverage matrix with the empty levels marked |
| Signal available to the tutor | **three places, one of them unavoidable** |

### Did it work?

Yes, and it is pinned by five new tests in `practice/tests.py::CoverageGapTests` and
`lessons/tests.py::test_the_bank_page_reports_coverage_gaps`:

- a substituted question is recorded as a mismatch (`served_level == 4` when 6 was asked)
- the session reports `[{"asked": 6, "served": [4]}]`
- the practice view's context carries `level=4, requested_level=6, level_mismatch=True`
- no mismatch is reported when the bank *does* have the right level
- the bank page reports `has_gaps`

**Test suite: 58 → 63, all passing.**

**What the improvement does not do:** it does not fill the gap. A tutor still has to write the
missing lesson. The change converts a silent failure into a visible, actionable one, which is
the most a product can do about content it does not have.
