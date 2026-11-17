"""
The adaptive quiz engine: what level comes next, and which question to ask.

The rule, from the product proposal: a student moves UP a level after three correct answers
in a row, and DOWN a level after two misses in a row. The asymmetry is deliberate and is the
whole pedagogical idea -- dropping a struggling seven-year-old quickly costs almost nothing,
while promoting them too eagerly produces the exact experience the product exists to prevent.
Being wrong downward is cheap; being wrong upward makes a child give up.

Two properties this module guarantees, both tested:

* **Streaks reset on every level change.** Without that, a student who gets three right is
  promoted, and then a single further correct answer at the harder level would promote them
  again off the back of answers given at the easier one. Each level has to be earned on its
  own evidence.
* **Levels are clamped.** A child at level 1 who misses twice stays at level 1 rather than
  falling off the bottom of the lesson bank, where no question exists and the session would
  simply end.
"""

import random

from lessons.models import MAX_LEVEL, MIN_LEVEL, Question

PROMOTE_AFTER = 3     # consecutive correct answers needed to move up
DEMOTE_AFTER = 2      # consecutive misses that move a student down


def streaks(results):
    """(current correct streak, current miss streak) from a list of booleans, oldest first.

    Only the run at the END of the list counts: a student who missed two and then answered
    correctly is on a correct streak of one, not still carrying the misses.
    """
    correct = miss = 0
    for ok in reversed(results):
        if ok and miss == 0:
            correct += 1
        elif not ok and correct == 0:
            miss += 1
        else:
            break
    return correct, miss


def next_level(current_level, results_since_change):
    """The level for the NEXT question.

    `results_since_change` is the run of results at the current level only -- the caller
    resets it whenever the level moves, which is what keeps each level independently earned.
    """
    correct, miss = streaks(results_since_change)
    if correct >= PROMOTE_AFTER:
        return min(MAX_LEVEL, current_level + 1)
    if miss >= DEMOTE_AFTER:
        return max(MIN_LEVEL, current_level - 1)
    return current_level


def results_since_last_change(session):
    """The results the student has produced AT their current level.

    Walks backwards and stops at the last level change, so a promotion wipes the slate.
    """
    out = []
    for attempt in session.attempts.order_by("-created_at"):
        out.append(attempt.is_correct)
        if attempt.level_changed:
            break
    return list(reversed(out))


def decide_level(session):
    """The level the next question should be asked at."""
    last = session.attempts.order_by("-created_at").first()
    if last is None:
        return session.started_level
    return next_level(last.level_after, results_since_last_change(session))


def pick_question(session, level, rng=None):
    """Choose a question at `level` in this session's skill that the student has not just seen.

    Falls back outward to the nearest level with any question, because a bank with a gap at
    level 4 should not end a child's session -- it should ask something close and let the
    tutor notice the gap later. Returns None only when the bank has nothing in this skill at
    all, which the view turns into a clear message rather than an empty screen.
    """
    rng = rng or random
    asked = set(session.attempts.values_list("question_id", flat=True))
    base = Question.objects.filter(lesson__skill=session.skill).select_related("lesson")

    for candidate_level in _levels_outward_from(level):
        pool = list(base.filter(lesson__level=candidate_level).exclude(id__in=asked))
        if pool:
            return rng.choice(pool)
    # Everything at every level has been asked already: allow a repeat rather than stopping.
    pool = list(base.filter(lesson__level=level)) or list(base)
    return rng.choice(pool) if pool else None


def _levels_outward_from(level):
    """`level` first, then its nearest neighbours, closest first."""
    yield level
    for distance in range(1, MAX_LEVEL):
        for candidate in (level - distance, level + distance):
            if MIN_LEVEL <= candidate <= MAX_LEVEL:
                yield candidate
