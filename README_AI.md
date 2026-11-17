# AI in ReadUp

ReadUp has one AI feature: **the lesson authoring assistant**. This document covers what it
does, why it is built this way, how it fails, and what it is not.

---

## 1. The problem it solves

Our pilot tutors write practice questions by hand. Writing eight multiple-choice questions at
the right level, each with three plausible wrong answers, and then writing the instruction
line in Bengali, Hindi, Urdu and Gujarati, is the most time-consuming thing a volunteer does —
and it is what stops the lesson bank from growing. A thin lesson bank starves the adaptive
quiz engine: if there is nothing at level 4, a child who earns level 4 cannot be served.

So the AI does not sit on top of the product as a chatbot. It feeds the thing the product is
built around.

## 2. Workflow

```
Tutor pastes a passage
        │
        ▼
Django view  lessons.views.lesson_draft
        │
        ├── preprocessing ── validate_passage()      length limits, early rejection
        │                    estimate_level()        transparent readability heuristic
        ▼
AI model  llama-3.3-70b-versatile via the Groq API   (JSON mode, temperature 0.3)
        │
        ▼
postprocessing  _validate_draft()                    structural validation, bad questions dropped
        │
        ▼
Tutor reviews and edits on screen   ← nothing has been saved yet
        │
        ▼
lessons.views.lesson_save_draft     atomic write to Lesson / Question / Choice
        │
        ▼
The adaptive quiz engine serves those questions to a child
```

**What enters the system:** a short passage or topic typed by a tutor, plus the chosen skill
and question count. No child's name, level or history is ever sent — the assistant writes
generic lessons, not personalised ones, so no data about a child leaves the server.

**How it is prepared:** trimmed, length-checked (20 to 4,000 characters), and paired with a
locally computed level estimate used as a prior in the prompt.

**How results are validated:** every returned question must have exactly four choices and
exactly one correct answer. Questions failing that are **dropped, not repaired**. An
out-of-range level is replaced with the local estimate. If nothing survives, the whole
response is discarded and the offline generator runs instead.

**How the user receives it:** as an editable form. Every prompt, every answer, which answer is
correct, and every translation can be changed before saving. A lesson saved from a draft is
flagged `ai_generated=True` so the bank shows which lessons were machine-drafted.

## 3. Model selection, and why

**Chosen: `llama-3.3-70b-versatile`, hosted, through the Groq API.**

| Factor | Reasoning |
|---|---|
| **Capability** | Needs instruction-following, reliable JSON, and genuine multilingual output in four Indic scripts. Small local models were not close on the translation requirement, which is a core product promise rather than a nice-to-have. |
| **Compute** | This is the decisive one. Our deployment target gives **100 CPU-seconds per day for the whole account**. A 2B local model costs several CPU-seconds per generation, so lesson drafting alone would exhaust the daily budget in a few dozen lessons and take the site down for every tutor. A hosted call costs us ~0 CPU: the work happens elsewhere. |
| **Latency** | 2–6 seconds, which is acceptable **because of where it sits**. Drafting happens once, while an adult waits. It is never on a child's critical path — the practice session only reads rows already in the database, so a child never waits for a model. |
| **Cost** | Groq's free tier covers our pilot volume. At roughly 1,200 input and 600 output tokens per draft, even paid rates put a semester of drafting in cents. |
| **Privacy** | Only tutor-authored passages leave the server. No child data is ever sent, which is what makes a hosted API acceptable here at all. Had the feature needed a child's history, we would have had to reconsider. |
| **Scalability** | Drafting is bounded by the number of tutors, not the number of children, so it does not grow with usage the way session traffic does. |

**Rejected: a local Hugging Face model.** Correct for privacy, wrong for this deployment — see
the compute row. We had measured evidence of exactly this failure mode from earlier coursework
before choosing.

## 4. Reliability: what happens when it fails

The design rule is that **the feature degrades, it never errors**. Every path below returns a
usable draft, and each has a test.

| Failure | What the tutor sees |
|---|---|
| No API key configured | Rule-based draft, yellow note explaining why |
| Request times out | Rule-based draft, "the assistant timed out" |
| Network or API error | Rule-based draft, "could not be reached" |
| Response is not valid JSON | Rule-based draft, "answer could not be used" |
| A question has two correct answers, or five choices | **That question is dropped**; the good ones are kept |
| No question survives validation | Rule-based draft |
| Model returns level 99 | Replaced with the local readability estimate |
| Passage too short or too long | Rejected before any call, with a message naming the fix |

The fallback (`draft_offline`) builds real vocabulary questions from the passage's own words
with no network and no key. It is plainer than the model's output — that is the point. It
exists so a volunteer at 9pm with a dead API key is never blocked.

## 5. Safety

- **A tutor is always in the loop.** There is no path that writes model output to a child
  without an adult reading it first. This is why drafting and saving are two steps.
- **No child data is sent anywhere.** The assistant receives only tutor-typed text.
- **Structural validation before display**, so a malformed question cannot reach the bank and
  be served to a child mid-session.
- **Atomic saves**, so a half-written lesson cannot sit in the bank looking complete.
- **The API key lives in `.env`**, which is git-ignored, and is read through `django-environ`.
- **Model output is escaped** by Django's template autoescaping like any other untrusted text.

## 6. Known limitations

1. **We do not verify translation quality.** We validate that a translation is *present*, not
   that it is *good*. None of us reads all four languages. Our pilot tutors do, and the review
   step is where that check actually happens — but the honest statement is that ReadUp cannot
   detect a bad Gujarati instruction line on its own. This is the limitation we would fix
   first, probably with a tutor-facing "flag this translation" control.
2. **The level estimate is a readability heuristic, not a model.** Mean sentence and word
   length map onto six levels. It is transparent and overridable, and it is crude.
3. **Math questions are weaker than reading questions.** The prompt is written for text, and
   generated arithmetic needs more editing.
4. **The offline fallback is noticeably plainer.** Recognition questions, not comprehension.
5. **No caching.** Drafting the same passage twice costs two API calls.
6. **The adaptive engine is rules, not ML** — three up, two down. That is a deliberate choice
   for a product used on real children by volunteers: it is explainable to a tutor and
   auditable after the fact. A learned policy would be neither, on the data volume we have.
