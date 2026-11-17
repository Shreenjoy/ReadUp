"""
Tests for the lesson bank and the authoring assistant.

The assistant's failure paths get more attention than its happy path, because the happy path
is the one we will notice in testing and the failure paths are the ones a volunteer tutor
will hit at 9pm with no one to ask. The rule being tested throughout: the feature degrades,
it never errors, and it never writes an unusable question into the bank.
"""

from unittest import mock

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import TutorProfile

from . import ai
from .models import Choice, Lesson, Question, Skill

PASSWORD = "readup12345"
PASSAGE = ("The old bus stopped at the corner. Rina climbed on and found a seat by the "
           "window. She watched the market go past.")

GOOD_DRAFT = {
    "title": "The bus",
    "level": 2,
    "questions": [{
        "prompt": "Where did Rina sit?",
        "choices": [{"text": "by the window", "is_correct": True},
                    {"text": "on the floor", "is_correct": False},
                    {"text": "near the driver", "is_correct": False},
                    {"text": "at the market", "is_correct": False}],
        "instructions": {"bn": "সঠিক উত্তর বেছে নাও।", "hi": "सही उत्तर चुनो।"},
    }],
}


def fake_response(payload):
    response = mock.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"content": __import__("json").dumps(payload)}}]}
    return response


class PassageValidationTests(TestCase):
    def test_a_too_short_passage_is_rejected_with_a_usable_message(self):
        with self.assertRaises(ai.DraftError) as cm:
            ai.validate_passage("hi")
        self.assertIn("at least a sentence", str(cm.exception))

    def test_an_enormous_passage_is_rejected(self):
        with self.assertRaises(ai.DraftError):
            ai.validate_passage("word " * 5000)

    def test_a_normal_passage_passes(self):
        self.assertEqual(ai.validate_passage(f"  {PASSAGE} "), PASSAGE)


class LevelEstimateTests(TestCase):
    def test_simple_text_scores_low(self):
        self.assertLessEqual(ai.estimate_level("The cat sat. The dog ran. I am here."), 2)

    def test_dense_text_scores_higher_than_simple_text(self):
        simple = ai.estimate_level("The cat sat. The dog ran.")
        dense = ai.estimate_level(
            "Consequently, the administration's deliberations concerning environmental "
            "legislation demonstrated considerable institutional complexity.")
        self.assertGreater(dense, simple)

    def test_empty_text_does_not_crash(self):
        self.assertEqual(ai.estimate_level(""), 1)


@override_settings(AI_ENABLED=True, AI_API_KEY="test-key")
class AssistantReliabilityTests(TestCase):
    """Every one of these must return a usable draft rather than raising."""

    def test_a_good_response_is_used(self):
        with mock.patch("requests.post", return_value=fake_response(GOOD_DRAFT)):
            draft = ai.draft_lesson(PASSAGE)
        self.assertEqual(draft["source"], "ai")
        self.assertEqual(len(draft["questions"]), 1)

    def test_a_timeout_falls_back_instead_of_failing(self):
        with mock.patch("requests.post", side_effect=requests.Timeout()):
            draft = ai.draft_lesson(PASSAGE)
        self.assertEqual(draft["source"], "offline")
        self.assertIn("timed out", draft["note"])
        self.assertTrue(draft["questions"])

    def test_a_network_error_falls_back(self):
        with mock.patch("requests.post", side_effect=requests.ConnectionError()):
            draft = ai.draft_lesson(PASSAGE)
        self.assertEqual(draft["source"], "offline")

    def test_unparseable_output_falls_back(self):
        bad = mock.Mock()
        bad.raise_for_status.return_value = None
        bad.json.return_value = {"choices": [{"message": {"content": "not json at all"}}]}
        with mock.patch("requests.post", return_value=bad):
            draft = ai.draft_lesson(PASSAGE)
        self.assertEqual(draft["source"], "offline")

    def test_a_question_with_two_correct_answers_is_dropped(self):
        broken = {"title": "x", "level": 2, "questions": [
            {"prompt": "bad", "choices": [{"text": "a", "is_correct": True},
                                          {"text": "b", "is_correct": True},
                                          {"text": "c", "is_correct": False},
                                          {"text": "d", "is_correct": False}],
             "instructions": {}},
            GOOD_DRAFT["questions"][0],
        ]}
        with mock.patch("requests.post", return_value=fake_response(broken)):
            draft = ai.draft_lesson(PASSAGE)
        self.assertEqual(len(draft["questions"]), 1)
        self.assertEqual(draft["questions"][0]["prompt"], "Where did Rina sit?")

    def test_a_question_with_the_wrong_number_of_choices_is_dropped(self):
        broken = {"title": "x", "level": 2, "questions": [
            {"prompt": "bad", "choices": [{"text": "a", "is_correct": True}],
             "instructions": {}}]}
        with mock.patch("requests.post", return_value=fake_response(broken)):
            draft = ai.draft_lesson(PASSAGE)
        self.assertEqual(draft["source"], "offline")   # nothing usable survived

    def test_an_out_of_range_level_is_replaced_not_trusted(self):
        odd = dict(GOOD_DRAFT, level=99)
        with mock.patch("requests.post", return_value=fake_response(odd)):
            draft = ai.draft_lesson(PASSAGE)
        self.assertTrue(1 <= draft["level"] <= 6)


@override_settings(AI_ENABLED=False, AI_API_KEY="")
class OfflineModeTests(TestCase):
    def test_without_a_key_the_feature_still_produces_a_lesson(self):
        draft = ai.draft_lesson(PASSAGE)
        self.assertEqual(draft["source"], "offline")
        self.assertTrue(draft["questions"])
        for q in draft["questions"]:
            self.assertEqual(len(q["choices"]), 4)
            self.assertEqual(sum(1 for c in q["choices"] if c["is_correct"]), 1)

    def test_no_api_call_is_made_without_a_key(self):
        with mock.patch("requests.post") as post:
            ai.draft_lesson(PASSAGE)
        post.assert_not_called()


class SaveDraftTests(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("asha", password=PASSWORD)
        TutorProfile.objects.create(user=self.tutor)
        self.client.login(username="asha", password=PASSWORD)

    def _post(self, **overrides):
        data = {
            "title": "The bus", "skill": Skill.READING, "level": "2",
            "source": "ai", "question_count": "1", "passage": PASSAGE,
            "q0_prompt": "Where did Rina sit?", "q0_correct": "0",
            "q0_c0": "by the window", "q0_c1": "on the floor",
            "q0_c2": "near the driver", "q0_c3": "at the market",
            "q0_i_bn": "সঠিক উত্তর বেছে নাও।",
        }
        data.update(overrides)
        return self.client.post(reverse("lessons:save-draft"), data)

    def test_a_reviewed_draft_saves_with_its_questions_and_translations(self):
        self._post()
        lesson = Lesson.objects.get()
        self.assertTrue(lesson.ai_generated)
        question = lesson.questions.get()
        self.assertEqual(question.choices.filter(is_correct=True).count(), 1)
        self.assertEqual(question.instruction_for("bn"), "সঠিক উত্তর বেছে নাও।")

    def test_a_question_missing_an_answer_saves_nothing_at_all(self):
        """Half a lesson in the bank is worse than none: a child would hit the gap."""
        self._post(q0_c3="")
        self.assertEqual(Lesson.objects.count(), 0)
        self.assertEqual(Question.objects.count(), 0)

    def test_a_question_with_no_correct_answer_marked_saves_nothing(self):
        data = {"title": "x", "skill": Skill.READING, "level": "1", "question_count": "1",
                "q0_prompt": "p", "q0_c0": "a", "q0_c1": "b", "q0_c2": "c", "q0_c3": "d"}
        self.client.post(reverse("lessons:save-draft"), data)
        self.assertEqual(Lesson.objects.count(), 0)

    def test_the_english_instruction_line_is_never_stored_as_a_translation(self):
        self._post()
        self.assertEqual(Question.objects.get().instruction_for("en"), "")


class LessonBankTests(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("asha", password=PASSWORD)
        TutorProfile.objects.create(user=self.tutor)
        for level in (1, 3):
            lesson = Lesson.objects.create(title=f"L{level}", skill=Skill.READING,
                                           level=level, created_by=self.tutor)
            q = Question.objects.create(lesson=lesson, prompt="p")
            Choice.objects.create(question=q, text="a", is_correct=True)
        self.client.login(username="asha", password=PASSWORD)

    def test_the_bank_requires_a_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("lessons:list")).status_code, 302)

    def test_filtering_by_level_narrows_the_list(self):
        response = self.client.get(reverse("lessons:list"), {"level": "3"})
        self.assertContains(response, "L3")
        self.assertNotContains(response, ">L1<")
