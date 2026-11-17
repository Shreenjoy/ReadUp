"""
The lesson bank: the questions the quiz engine draws from.

Shape is Lesson -> Question -> Choice. A Lesson is a themed set at one skill and level
("Opposites, Reading L2"); a Question is one thing asked; a Choice is one of its four
answers, exactly one of which is correct.

Why three models rather than one wide table: the quiz engine selects at QUESTION level, not
lesson level, because a session mixes questions from several lessons as the student's level
moves. Choices are rows rather than four columns so the count can change later without a
migration, and so "exactly one correct answer" can be validated and queried.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from accounts.models import Language

MIN_LEVEL, MAX_LEVEL = 1, 6


class Skill(models.TextChoices):
    READING = "reading", "Reading"
    MATH = "math", "Math"


class Lesson(models.Model):
    """A set of questions at one skill and level, added by a tutor."""

    title = models.CharField(max_length=120)
    skill = models.CharField(max_length=10, choices=Skill.choices, default=Skill.READING)
    level = models.PositiveSmallIntegerField(
        default=1, choices=[(i, f"Level {i}") for i in range(MIN_LEVEL, MAX_LEVEL + 1)])
    passage = models.TextField(blank=True,
                               help_text="Optional reading passage the questions refer to.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="lessons")
    created_at = models.DateTimeField(auto_now_add=True)
    # Set when the lesson authoring assistant drafted this lesson. Kept so the dashboard can
    # report how much of the bank is AI-drafted, and so a reviewer can tell the difference.
    ai_generated = models.BooleanField(default=False)

    class Meta:
        ordering = ["skill", "level", "title"]

    def __str__(self):
        return f"{self.title} ({self.get_skill_display()} L{self.level})"

    def get_absolute_url(self):
        return reverse("lessons:detail", args=[self.pk])


class Question(models.Model):
    """One question. The instruction line is stored per language, not translated at render time.

    Translating on every page view would put a network call (or a model) on the critical path
    of a child waiting for the next question. Storing the translation once, when the lesson is
    created, keeps the session fast and keeps the app usable when the AI service is down.
    """

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="questions")
    prompt = models.CharField(max_length=300, help_text="The question, in English.")
    instruction_translations = models.JSONField(
        default=dict, blank=True,
        help_text='Home-language instruction lines, e.g. {"bn": "...", "hi": "..."}.')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["lesson", "order", "id"]

    def __str__(self):
        return self.prompt[:60]

    def instruction_for(self, language_code):
        """The home-language line, or empty if we do not have one.

        Returns empty rather than falling back to English on purpose: the template shows the
        English prompt already, and a duplicated English line pretending to be a translation
        would be worse than no second line at all.
        """
        if language_code == Language.ENGLISH:
            return ""
        return (self.instruction_translations or {}).get(language_code, "")

    @property
    def correct_choice(self):
        return self.choices.filter(is_correct=True).first()

    def clean(self):
        """A question with no single correct answer would break scoring, so refuse it."""
        if self.pk and self.choices.filter(is_correct=True).count() != 1:
            raise ValidationError("A question must have exactly one correct answer.")


class Choice(models.Model):
    """One answer button. Exactly one choice per question has is_correct=True."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=120)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.text}{' *' if self.is_correct else ''}"
