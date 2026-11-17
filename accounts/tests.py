"""Tests for sign-up, student profiles and the privacy rules."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Language, Student, TutorProfile

PASSWORD = "readup12345"


class SignUpTests(TestCase):
    def test_a_tutor_can_sign_up_and_lands_on_my_students(self):
        response = self.client.post(reverse("signup"), {
            "username": "asha", "full_name": "Asha Rahman", "email": "a@example.com",
            "program": "Informed Empowerment", "role": "tutor",
            "password1": "a-strong-passphrase-42", "password2": "a-strong-passphrase-42",
        })
        self.assertRedirects(response, reverse("students:list"))
        self.assertEqual(TutorProfile.objects.get().role, "tutor")

    def test_sign_up_rejects_mismatched_passwords(self):
        self.client.post(reverse("signup"), {
            "username": "asha", "full_name": "Asha", "email": "a@example.com",
            "program": "X", "role": "tutor",
            "password1": "a-strong-passphrase-42", "password2": "different-passphrase-43",
        })
        self.assertEqual(User.objects.count(), 0)


class StudentTests(TestCase):
    def setUp(self):
        self.tutor = User.objects.create_user("asha", password=PASSWORD)
        TutorProfile.objects.create(user=self.tutor)
        self.client.login(username="asha", password=PASSWORD)

    def test_a_tutor_can_add_a_student_and_see_them_listed(self):
        self.client.post(reverse("students:add"), {
            "first_name": "Mitali", "grade": 3, "home_language": Language.BENGALI,
            "notes": "",
        })
        student = Student.objects.get()
        self.assertEqual(student.tutor, self.tutor)
        self.assertContains(self.client.get(reverse("students:list")), "Mitali")

    def test_a_one_letter_name_is_rejected_with_a_message(self):
        response = self.client.post(reverse("students:add"), {
            "first_name": "M", "grade": 3, "home_language": Language.BENGALI, "notes": ""})
        self.assertEqual(Student.objects.count(), 0)
        self.assertContains(response, "first name")

    def test_a_new_student_starts_at_level_one(self):
        student = Student.objects.create(first_name="Zara", tutor=self.tutor)
        self.assertEqual(student.current_level("reading"), 1)

    def test_search_filters_the_student_list(self):
        Student.objects.create(first_name="Mitali", tutor=self.tutor)
        Student.objects.create(first_name="Arjun", tutor=self.tutor)
        response = self.client.get(reverse("students:list"), {"q": "Mit"})
        self.assertContains(response, "Mitali")
        self.assertNotContains(response, "Arjun")

    def test_the_student_model_stores_no_surname_field(self):
        """Privacy by design, pinned so a later migration cannot quietly add one."""
        fields = {f.name for f in Student._meta.get_fields()}
        for forbidden in ("last_name", "surname", "date_of_birth", "address", "email", "phone"):
            self.assertNotIn(forbidden, fields)
