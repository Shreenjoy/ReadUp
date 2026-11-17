"""
Accounts and student profiles.

Two ideas carry the product's privacy promise, and both are enforced here rather than in the
templates:

1. **Children never have accounts.** A Student is a row created and owned by a tutor, not a
   Django user. There is no password, no email and no login for a child. The practice screen
   is reached from a tutor's session, so a child never authenticates and never types personal
   information.
2. **A tutor sees only their own students; a program lead sees their whole program.** That is
   a queryset rule (`visible_to`), not a template check, so a hand-typed URL cannot reach
   another tutor's student.
"""

from django.conf import settings
from django.db import models
from django.urls import reverse


class Language(models.TextChoices):
    """Home languages our pilot partner actually serves, plus English."""

    ENGLISH = "en", "English"
    BENGALI = "bn", "Bengali"
    HINDI = "hi", "Hindi"
    URDU = "ur", "Urdu"
    GUJARATI = "gu", "Gujarati"


class TutorProfile(models.Model):
    """The adult behind a Django user: their role and which program they belong to."""

    class Role(models.TextChoices):
        TUTOR = "tutor", "Tutor"
        LEAD = "lead", "Program lead"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="tutor_profile")
    role = models.CharField(max_length=8, choices=Role.choices, default=Role.TUTOR)
    program = models.CharField(max_length=120, default="Informed Empowerment",
                               help_text="The tutoring program this account belongs to.")

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def is_lead(self):
        return self.role == self.Role.LEAD


class Student(models.Model):
    """A child in the program. Deliberately thin.

    First name, grade and home language are everything the product needs to pick the right
    question and print the right instruction line. We do not store surnames, dates of birth,
    contact details or anything else about a child, because none of it would be used and all
    of it would be a liability.
    """

    GRADES = [(i, f"Grade {i}") for i in range(1, 9)]

    first_name = models.CharField(max_length=40)
    grade = models.PositiveSmallIntegerField(choices=GRADES, default=2)
    home_language = models.CharField(max_length=2, choices=Language.choices,
                                     default=Language.BENGALI)
    program = models.CharField(max_length=120, default="Informed Empowerment")
    tutor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="students")
    notes = models.TextField(blank=True,
                             help_text="Carried between tutors so nothing is lost when a "
                                       "student changes tutor.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["first_name"]

    def __str__(self):
        return f"{self.first_name} (Grade {self.grade})"

    def get_absolute_url(self):
        return reverse("students:detail", args=[self.pk])

    @classmethod
    def visible_to(cls, user):
        """The authorisation rule, in one place.

        A lead sees every student in their program; a tutor sees only their own. Every view
        that touches students starts from this queryset, so there is no route -- including a
        hand-typed primary key -- that reaches someone else's student.
        """
        if not user.is_authenticated:
            return cls.objects.none()
        profile = getattr(user, "tutor_profile", None)
        if profile and profile.is_lead:
            return cls.objects.filter(program=profile.program)
        return cls.objects.filter(tutor=user)

    def current_level(self, skill):
        """Where this student is now in one skill, from their own history.

        Level is derived from the last recorded attempt rather than stored on the student,
        so there is exactly one source of truth: the attempt history. A stored column could
        drift away from the attempts that produced it, and then the dashboard and the quiz
        engine would disagree about the same child.
        """
        last = (self.attempts.filter(question__lesson__skill=skill)
                .order_by("-created_at").values_list("level_after", flat=True).first())
        return last or 1
