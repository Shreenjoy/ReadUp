"""
Tests for the adaptive quiz engine and the session flow.

The engine is the product's one real algorithm, so it is tested as pure functions first --
no database, no requests -- and then through the views that use it.

The authorisation tests matter as much as the engine ones: a tutor reaching another tutor's
student would be a child-privacy failure, not just a bug.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Student, TutorProfile
from lessons.models import Choice, Lesson, Question, Skill

from . import engine
from .models import Attempt, Session

PASSWORD = "readup12345"


def make_lesson(level, skill=Skill.READING, user=None, n=4):
    lesson = Lesson.objects.create(title=f"L{level}", skill=skill, level=level,
                                   created_by=user)
    for i in range(n):
        q = Question.objects.create(lesson=lesson, prompt=f"q{level}-{i}", order=i)
        Choice.objects.create(question=q, text="right", is_correct=True)
        for j in range(3):
            Choice.objects.create(question=q, text=f"wrong{j}", is_correct=False)
    return lesson


class StreakTests(TestCase):
    def test_empty_history_has_no_streaks(self):
        self.assertEqual(engine.streaks([]), (0, 0))

    def test_only_the_run_at_the_end_counts(self):
        # missed, missed, then correct -> a correct streak of one, not two misses carried.
        self.assertEqual(engine.streaks([False, False, True]), (1, 0))

    def test_consecutive_correct(self):
        self.assertEqual(engine.streaks([True, True, True]), (3, 0))

    def test_a_correct_answer_clears_the_miss_streak(self):
        self.assertEqual(engine.streaks([True, False]), (0, 1))


class NextLevelTests(TestCase):
    def test_three_in_a_row_promotes(self):
        self.assertEqual(engine.next_level(2, [True, True, True]), 3)

    def test_two_in_a_row_demotes(self):
        self.assertEqual(engine.next_level(3, [False, False]), 2)

    def test_two_correct_is_not_enough_to_promote(self):
        self.assertEqual(engine.next_level(2, [True, True]), 2)

    def test_one_miss_is_not_enough_to_demote(self):
        self.assertEqual(engine.next_level(2, [False]), 2)

    def test_demotion_is_faster_than_promotion(self):
        """The asymmetry is the pedagogical choice, so it is pinned by a test."""
        self.assertLess(engine.DEMOTE_AFTER, engine.PROMOTE_AFTER)

    def test_level_one_cannot_fall_below_one(self):
        self.assertEqual(engine.next_level(1, [False, False]), 1)

    def test_top_level_cannot_rise_above_the_maximum(self):
        self.assertEqual(engine.next_level(6, [True, True, True]), 6)


class SessionFlowTests(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("asha", password=PASSWORD)
        TutorProfile.objects.create(user=self.tutor)
        self.student = Student.objects.create(first_name="Mitali", tutor=self.tutor)
        for level in range(1, 7):
            make_lesson(level, user=self.tutor)
        self.client.login(username="asha", password=PASSWORD)

    def _answer(self, session, correct):
        question = engine.pick_question(session, engine.decide_level(session))
        choice = question.choices.filter(is_correct=correct).first()
        return self.client.post(reverse("practice:answer", args=[session.pk]),
                                {"choice": choice.pk})

    def test_a_session_records_attempts_and_moves_the_level(self):
        self.client.get(reverse("practice:start", args=[self.student.pk]))
        session = Session.objects.get()
        self.assertEqual(session.started_level, 1)
        for _ in range(3):
            self._answer(session, correct=True)
        self.assertEqual(session.attempts.count(), 3)
        self.assertEqual(session.attempts.last().level_after, 2)

    def test_the_streak_resets_after_a_promotion(self):
        """A fourth correct answer must not immediately promote again."""
        self.client.get(reverse("practice:start", args=[self.student.pk]))
        session = Session.objects.get()
        for _ in range(4):
            self._answer(session, correct=True)
        self.assertEqual(session.attempts.last().level_after, 2)

    def test_two_misses_move_the_student_down(self):
        self.client.get(reverse("practice:start", args=[self.student.pk]))
        session = Session.objects.get()
        session.started_level = 3
        session.save()
        for _ in range(2):
            self._answer(session, correct=False)
        self.assertEqual(session.attempts.last().level_after, 2)

    def test_a_session_ends_after_the_planned_number_of_questions(self):
        self.client.get(reverse("practice:start", args=[self.student.pk]))
        session = Session.objects.get()
        for _ in range(session.planned_questions):
            self._answer(session, correct=True)
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)
        self.assertTrue(session.is_finished)

    def test_answering_a_finished_session_redirects_instead_of_recording(self):
        self.client.get(reverse("practice:start", args=[self.student.pk]))
        session = Session.objects.get()
        for _ in range(session.planned_questions):
            self._answer(session, correct=True)
        before = Attempt.objects.count()
        self._answer(session, correct=True)
        self.assertEqual(Attempt.objects.count(), before)

    def test_the_student_level_comes_from_attempt_history(self):
        self.client.get(reverse("practice:start", args=[self.student.pk]))
        session = Session.objects.get()
        for _ in range(3):
            self._answer(session, correct=True)
        self.assertEqual(self.student.current_level(Skill.READING), 2)

    def test_an_empty_lesson_bank_shows_a_message_not_a_blank_page(self):
        Lesson.objects.all().delete()
        self.client.get(reverse("practice:start", args=[self.student.pk]))
        session = Session.objects.get()
        response = self.client.get(reverse("practice:session", args=[session.pk]))
        self.assertContains(response, "No reading questions in the bank yet")


class AuthorisationTests(TestCase):
    """A tutor must never reach another tutor's student, by any route."""

    def setUp(self):
        self.a = User.objects.create_user("asha", password=PASSWORD)
        self.b = User.objects.create_user("bilal", password=PASSWORD)
        TutorProfile.objects.create(user=self.a)
        TutorProfile.objects.create(user=self.b)
        self.a_student = Student.objects.create(first_name="Mitali", tutor=self.a)

    def test_another_tutor_cannot_open_a_student_profile(self):
        self.client.login(username="bilal", password=PASSWORD)
        response = self.client.get(reverse("students:detail", args=[self.a_student.pk]))
        self.assertEqual(response.status_code, 404)

    def test_another_tutor_cannot_start_a_session_for_that_student(self):
        self.client.login(username="bilal", password=PASSWORD)
        response = self.client.get(reverse("practice:start", args=[self.a_student.pk]))
        self.assertEqual(response.status_code, 404)

    def test_a_signed_out_visitor_is_redirected_to_log_in(self):
        response = self.client.get(reverse("students:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_a_lead_sees_every_student_in_their_program(self):
        lead = User.objects.create_user("priya", password=PASSWORD)
        TutorProfile.objects.create(user=lead, role=TutorProfile.Role.LEAD,
                                    program="Informed Empowerment")
        self.assertIn(self.a_student, Student.visible_to(lead))

    def test_a_lead_does_not_see_another_programs_students(self):
        lead = User.objects.create_user("other", password=PASSWORD)
        TutorProfile.objects.create(user=lead, role=TutorProfile.Role.LEAD,
                                    program="A Different Program")
        self.assertNotIn(self.a_student, Student.visible_to(lead))
