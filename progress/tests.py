"""Tests for the dashboard, the JSON API and the CSV export."""

import csv
import io

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Student, TutorProfile
from lessons.models import Choice, Lesson, Question, Skill
from practice.models import Attempt, Session

PASSWORD = "readup12345"


class ProgressTests(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("asha", password=PASSWORD)
        TutorProfile.objects.create(user=self.tutor)
        self.student = Student.objects.create(first_name="Mitali", tutor=self.tutor)
        lesson = Lesson.objects.create(title="L1", skill=Skill.READING, level=1,
                                       created_by=self.tutor)
        self.question = Question.objects.create(lesson=lesson, prompt="=2+2 is a formula")
        Choice.objects.create(question=self.question, text="4", is_correct=True)
        self.session = Session.objects.create(student=self.student, tutor=self.tutor)
        for i in range(6):
            Attempt.objects.create(session=self.session, student=self.student,
                                   question=self.question, chosen_text="4",
                                   is_correct=(i % 2 == 0), level_before=1, level_after=1)
        self.client.login(username="asha", password=PASSWORD)

    def test_the_dashboard_renders(self):
        response = self.client.get(reverse("progress:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Progress")

    def test_the_json_api_matches_the_attempt_history(self):
        data = self.client.get(reverse("progress:api")).json()
        self.assertEqual(data["attempts"], 6)
        self.assertAlmostEqual(data["overall_accuracy"], 0.5)

    def test_the_api_requires_a_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("progress:api")).status_code, 302)

    def test_the_api_never_shows_another_tutors_students(self):
        other = User.objects.create_user("bilal", password=PASSWORD)
        TutorProfile.objects.create(user=other)
        self.client.login(username="bilal", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("progress:api")).json()["attempts"], 0)

    def test_the_csv_export_has_a_row_per_attempt(self):
        response = self.client.get(reverse("progress:export"))
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(len(rows), 7)               # header + 6 attempts
        self.assertIn("attachment;", response["Content-Disposition"])

    def test_a_question_that_looks_like_a_formula_is_escaped_in_the_csv(self):
        """A tutor-written '=...' prompt must not execute when a lead opens the report."""
        response = self.client.get(reverse("progress:export"))
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertTrue(rows[1][5].startswith("'="))

    def test_small_samples_are_flagged_rather_than_presented_as_a_trend(self):
        Attempt.objects.all().delete()
        Attempt.objects.create(session=self.session, student=self.student,
                               question=self.question, is_correct=True,
                               level_before=1, level_after=1)
        response = self.client.get(reverse("progress:dashboard"))
        self.assertContains(response, "first look rather than a trend")
