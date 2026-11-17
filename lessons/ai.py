"""
The lesson authoring assistant: ReadUp's AI feature.

**The problem it solves.** Our pilot tutors write practice questions by hand. Writing eight
multiple-choice questions at the right reading level, each with three plausible wrong answers,
and then writing the instruction line in Bengali, Hindi, Urdu or Gujarati, is the single most
time-consuming thing a volunteer does. It is also the thing that stops the lesson bank from
growing, which starves the quiz engine.

**What it does.** A tutor pastes a short passage (or a topic). The assistant returns a draft
lesson: an estimated level, a set of questions with four answers each, and the instruction
line translated into the home languages the program serves. The tutor reviews and edits
before anything is saved -- nothing reaches a child unreviewed.

**Why a hosted API and not a local model.** Measured, not assumed. Our deployment tier allows
100 CPU-seconds per day for the whole account; a 2B local model costs several CPU-seconds per
generation, so lesson drafting alone would exhaust the daily budget in a few dozen lessons and
take the site down for everyone. Drafting is also not on the child's critical path -- it
happens once, while a tutor waits -- so a network call of a few seconds is acceptable where it
would not be inside a session. See README_AI.md.

**What happens when it fails.** Everything here degrades to `draft_offline()`, a deterministic
rule-based generator that produces a usable skeleton with no network and no key. A tutor whose
API key is missing, whose quota is spent, or whose request timed out still gets a lesson to
edit, clearly labelled as a fallback. The feature never returns an error page.
"""

import json
import logging
import re

import requests
from django.conf import settings

from accounts.models import Language
from lessons.models import MAX_LEVEL, MIN_LEVEL, Skill

logger = logging.getLogger(__name__)

TARGET_LANGUAGES = [Language.BENGALI, Language.HINDI, Language.URDU, Language.GUJARATI]
LANGUAGE_NAMES = dict(Language.choices)


class DraftError(Exception):
    """Raised only for input the user can fix; never for service failures."""


def validate_passage(text):
    """Reject input the model cannot do anything useful with, before spending a call."""
    text = (text or "").strip()
    if len(text) < 20:
        raise DraftError("Give the assistant a bit more to work with -- at least a sentence or two.")
    limit = getattr(settings, "AI_MAX_PASSAGE_CHARS", 4000)
    if len(text) > limit:
        raise DraftError(f"That passage is too long. Keep it under {limit:,} characters.")
    return text


def estimate_level(passage):
    """A transparent readability heuristic, used as a prior and as the offline fallback.

    Deliberately simple and inspectable rather than a trained model: mean sentence length and
    mean word length map onto our six levels. A tutor can see why a passage was called L3 and
    overrule it, which matters more here than squeezing out accuracy -- the tutor is the one
    who knows the child.
    """
    sentences = [s for s in re.split(r"[.!?]+", passage) if s.strip()]
    words = re.findall(r"[A-Za-z']+", passage)
    if not sentences or not words:
        return MIN_LEVEL
    mean_sentence = len(words) / len(sentences)
    mean_word = sum(len(w) for w in words) / len(words)
    score = (mean_sentence / 4.0) + (mean_word - 3.0) * 1.4
    return max(MIN_LEVEL, min(MAX_LEVEL, round(score)))


def is_configured():
    return bool(getattr(settings, "AI_ENABLED", False) and getattr(settings, "AI_API_KEY", ""))


PROMPT = """You write practice questions for children aged 7 to 13 who are learning English.

Return ONLY a JSON object, no prose, with this exact shape:
{{"title": str, "level": int 1-6, "questions": [
  {{"prompt": str,
    "choices": [{{"text": str, "is_correct": bool}}, ...exactly 4, exactly one correct],
    "instructions": {{"bn": str, "hi": str, "ur": str, "gu": str}}}}
]}}

Rules:
- Write exactly {n} questions about the material below, at {skill} level {level} of 6.
- Each question has exactly four short answers and exactly one correct answer.
- Wrong answers must be plausible, not silly, and must be clearly wrong.
- "instructions" is the SHORT instruction line ("Choose the word that means the same.")
  translated into Bengali (bn), Hindi (hi), Urdu (ur) and Gujarati (gu). Translate the
  instruction only, never the answer choices.
- Use words a child of this level would know.

Material:
{passage}
"""


def draft_lesson(passage, skill=Skill.READING, level=None, n_questions=4):
    """Draft a lesson. Always returns a dict; never raises for a service failure.

    The returned dict carries `source`: "ai" when the model produced it, "offline" when the
    rule-based fallback did. The template shows that to the tutor, because a tutor reviewing
    a draft should know whether a model wrote it.
    """
    passage = validate_passage(passage)
    level = level or estimate_level(passage)

    if not is_configured():
        return draft_offline(passage, skill, level, n_questions,
                             note="No AI key is configured, so this is a rule-based draft.")
    try:
        payload = {
            "model": settings.AI_MODEL,
            "messages": [{"role": "user", "content": PROMPT.format(
                n=n_questions, skill=Skill(skill).label.lower(), level=level, passage=passage)}],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        response = requests.post(
            settings.AI_BASE_URL, json=payload,
            headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
            timeout=settings.AI_TIMEOUT_SECONDS)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        draft = _validate_draft(json.loads(content), level)
        draft["source"] = "ai"
        draft["note"] = ""
        return draft
    except requests.Timeout:
        return draft_offline(passage, skill, level, n_questions,
                             note="The assistant timed out, so this is a rule-based draft.")
    except requests.RequestException as exc:
        logger.warning("lesson assistant request failed: %s", exc)
        return draft_offline(passage, skill, level, n_questions,
                             note="The assistant could not be reached, so this is a rule-based draft.")
    except (KeyError, ValueError, TypeError) as exc:
        # Unparseable or malformed model output. This is the case that matters most: a model
        # that returns confident nonsense must not be able to write a broken question into
        # the bank, where a child would eventually be asked it.
        logger.warning("lesson assistant returned unusable output: %s", exc)
        return draft_offline(passage, skill, level, n_questions,
                             note="The assistant's answer could not be used, so this is a rule-based draft.")


def _validate_draft(data, fallback_level):
    """Reject anything structurally wrong BEFORE a tutor sees it.

    A model that returns five choices, or two correct answers, or none, would produce a
    question the quiz engine cannot score. Rather than repairing it silently -- which hides a
    broken model -- we drop the bad question and keep the good ones, and raise only if
    nothing survives.
    """
    if not isinstance(data, dict):
        raise ValueError("draft is not an object")
    questions = []
    for raw in data.get("questions", []):
        choices = raw.get("choices") or []
        if len(choices) != 4:
            continue
        correct = [c for c in choices if c.get("is_correct")]
        if len(correct) != 1:
            continue
        prompt = (raw.get("prompt") or "").strip()
        if not prompt:
            continue
        questions.append({
            "prompt": prompt[:300],
            "choices": [{"text": str(c.get("text", ""))[:120],
                         "is_correct": bool(c.get("is_correct"))} for c in choices],
            "instructions": {k: str(v)[:300] for k, v in (raw.get("instructions") or {}).items()
                             if k in TARGET_LANGUAGES},
        })
    if not questions:
        raise ValueError("no usable questions in draft")
    level = data.get("level")
    if not isinstance(level, int) or not MIN_LEVEL <= level <= MAX_LEVEL:
        level = fallback_level
    return {"title": (data.get("title") or "Untitled lesson")[:120],
            "level": level, "questions": questions}


# ------------------------------------------------------------------ offline fallback
STOPWORDS = {"the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "to", "of",
             "in", "on", "for", "with", "that", "this", "it", "he", "she", "they", "we"}


def draft_offline(passage, skill, level, n_questions, note=""):
    """A deterministic draft with no network and no model.

    Produces real vocabulary questions from the passage's own words: the correct answer is a
    word from the text and the distractors are other words from the text. The questions are
    plain, which is exactly the point -- this path exists so a tutor is never blocked, not to
    match the model's quality.
    """
    words = [w for w in re.findall(r"[A-Za-z']{4,}", passage)
             if w.lower() not in STOPWORDS]
    seen, unique = set(), []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique.append(w)

    questions = []
    for i, word in enumerate(unique[:n_questions]):
        distractors = [w for w in unique if w.lower() != word.lower()][:3]
        while len(distractors) < 3:
            distractors.append(f"word {len(distractors) + 1}")
        choices = [{"text": word, "is_correct": True}] + \
                  [{"text": d, "is_correct": False} for d in distractors]
        questions.append({
            "prompt": f'Which word appears in the passage: "{word}"?',
            "choices": choices,
            "instructions": {code: "" for code in TARGET_LANGUAGES},
        })
    if not questions:
        questions = [{
            "prompt": "Read the passage with your tutor, then choose the word you just read.",
            "choices": [{"text": "yes", "is_correct": True},
                        {"text": "no", "is_correct": False},
                        {"text": "maybe", "is_correct": False},
                        {"text": "later", "is_correct": False}],
            "instructions": {code: "" for code in TARGET_LANGUAGES},
        }]
    title = " ".join(passage.split()[:5])[:120] or "New lesson"
    return {"title": title, "level": level, "questions": questions,
            "source": "offline", "note": note}
