"""
Practice sessions and the attempts inside them.

A Session is one sitting with one child in one skill. An Attempt is one question answered.
Every Attempt stores the level the question was asked at AND the level the engine moved to
afterwards, which is what makes the adaptive decisions auditable: a tutor (or we) can replay
exactly why the difficulty changed, instead of trusting a number on a profile.

The student's current level is derived from `level_after` on their most recent attempt rather
than stored on Student, so the attempt history is the single source of truth.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse

from accounts.models import Student
from lessons.models import Question, Skill


class Session(models.Model):
    """One practice sitting."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="sessions")
    tutor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="sessions")
    skill = models.CharField(max_length=10, choices=Skill.choices, default=Skill.READING)
    planned_questions = models.PositiveSmallIntegerField(default=8)
    started_level = models.PositiveSmallIntegerField(default=1)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Notes for the next tutor.")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.student.first_name} {self.get_skill_display()} {self.started_at:%Y-%m-%d}"

    def get_absolute_url(self):
        return reverse("practice:session", args=[self.pk])

    @property
    def is_finished(self):
        return self.ended_at is not None or self.attempts.count() >= self.planned_questions

    @property
    def answered(self):
        return self.attempts.count()

    @property
    def correct_count(self):
        return self.attempts.filter(is_correct=True).count()

    @property
    def accuracy(self):
        total = self.answered
        return (self.correct_count / total) if total else None

    @property
    def coverage_gaps(self):
        """Levels this session asked for and the bank could not supply.

        Surfaced on the summary so a tutor learns the bank has a hole, instead of quietly
        watching a child practise below their level for weeks.
        """
        gaps = {}
        for attempt in self.attempts.select_related("question__lesson"):
            if attempt.level_mismatch:
                gaps.setdefault(attempt.level_before, set()).add(attempt.served_level)
        return [{"asked": asked, "served": sorted(served)} for asked, served in sorted(gaps.items())]

    @property
    def ended_level(self):
        last = self.attempts.order_by("-created_at").first()
        return last.level_after if last else self.started_level


class Attempt(models.Model):
    """One answered question, and the engine's decision about what it meant.

    `level_before` / `level_after` are both stored. Storing only the result and recomputing
    the level later would mean the history could be re-interpreted by a future version of the
    rules, and a tutor looking at an old session would see something that never happened.
    """

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attempts")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="attempts")
    chosen_text = models.CharField(max_length=120, blank=True)
    is_correct = models.BooleanField(default=False)
    level_before = models.PositiveSmallIntegerField(default=1)
    level_after = models.PositiveSmallIntegerField(default=1)
    seconds = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.student.first_name} {'right' if self.is_correct else 'missed'}"

    @property
    def level_changed(self):
        return self.level_after != self.level_before

    @property
    def served_level(self):
        """The level of the question the child was ACTUALLY given.

        Not always the level the engine asked for: when the bank has no question at the
        requested level, `pick_question` falls outward to the nearest level that does. That
        is the right behaviour -- a gap in the bank should not end a child's session -- but
        it has to be visible, which is what `level_mismatch` is for.
        """
        return self.question.lesson.level

    @property
    def level_mismatch(self):
        """True when the bank could not serve the level the engine asked for."""
        return self.served_level != self.level_before
