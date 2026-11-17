"""
Seed a demo program: one tutor, one lead, six students and a lesson bank at every level.

Run after migrate so the app is usable immediately:

    python manage.py seed_demo

Idempotent -- running it twice does not duplicate anything. The students are the six from the
wireframes so the screens match the design document.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import Language, Student, TutorProfile
from lessons.models import Choice, Lesson, Question, Skill

STUDENTS = [
    ("Arjun", 2, Language.HINDI), ("Mitali", 3, Language.BENGALI),
    ("Zara", 1, Language.URDU), ("Dev", 4, Language.GUJARATI),
    ("Riya", 2, Language.BENGALI), ("Sami", 3, Language.URDU),
]

# (skill, level, title, [(prompt, [choices], correct_index, {instructions})])
BANK = [
    (Skill.READING, 1, "First words", [
        ("Which word means a small animal you keep at home?",
         ["pet", "car", "tree", "cup"], 0, {"bn": "সঠিক শব্দটি বেছে নাও।", "hi": "सही शब्द चुनो।"}),
        ("Which word rhymes with 'cat'?", ["hat", "dog", "sun", "book"], 0,
         {"bn": "যে শব্দটি মিল আছে সেটি বেছে নাও।", "hi": "जो शब्द तुक मिलाता है उसे चुनो।"}),
    ]),
    (Skill.READING, 2, "Opposites", [
        ("Which word means the same as 'big'?", ["large", "small", "quick", "soft"], 0,
         {"bn": "একই অর্থের শব্দটি বেছে নাও।", "hi": "समान अर्थ वाला शब्द चुनो।"}),
        ("Which word is the opposite of 'hot'?", ["cold", "warm", "fast", "loud"], 0,
         {"bn": "বিপরীত শব্দটি বেছে নাও।", "hi": "विपरीत शब्द चुनो।"}),
    ]),
    (Skill.READING, 3, "Sentence meaning", [
        ("'The sun set behind the hills.' What time of day is it?",
         ["evening", "morning", "noon", "midnight"], 0, {"bn": "দিনের কোন সময়?"}),
        ("'She was soaked.' What happened to her?",
         ["she got wet", "she ran fast", "she laughed", "she slept"], 0, {"bn": "তার কী হয়েছিল?"}),
    ]),
    (Skill.READING, 4, "Inference", [
        ("'He packed a towel and sunscreen.' Where is he going?",
         ["the beach", "school", "the library", "bed"], 0, {}),
        ("'The plates were empty and everyone smiled.' What just happened?",
         ["they finished a meal", "they went out", "they slept", "they argued"], 0, {}),
    ]),
    (Skill.MATH, 1, "Counting to ten", [
        ("What is 2 + 3?", ["5", "4", "6", "7"], 0, {"bn": "যোগ করো।", "hi": "जोड़ो।"}),
        ("What is 7 - 2?", ["5", "6", "4", "9"], 0, {"bn": "বিয়োগ করো।"}),
    ]),
    (Skill.MATH, 2, "Teen numbers", [
        ("What is 8 + 6?", ["14", "12", "15", "16"], 0, {"bn": "যোগ করো।"}),
        ("What is 15 - 7?", ["8", "7", "9", "6"], 0, {}),
    ]),
    (Skill.MATH, 3, "Times tables", [
        ("What is 4 x 3?", ["12", "7", "16", "9"], 0, {}),
        ("What is 6 x 5?", ["30", "25", "35", "11"], 0, {}),
    ]),
    (Skill.MATH, 4, "Two steps", [
        ("A pencil costs 3. You buy 4. How much?", ["12", "7", "9", "16"], 0, {}),
        ("You have 20 and spend 6 twice. What is left?", ["8", "14", "10", "6"], 0, {}),
    ]),
]


class Command(BaseCommand):
    help = "Create a demo tutor, students and lesson bank."

    def handle(self, *args, **options):
        tutor, made = User.objects.get_or_create(
            username="tutor", defaults={"first_name": "Asha", "email": "tutor@example.com"})
        if made:
            tutor.set_password("readup12345")
            tutor.save()
        TutorProfile.objects.get_or_create(
            user=tutor, defaults={"role": TutorProfile.Role.TUTOR})

        lead, made = User.objects.get_or_create(
            username="lead", defaults={"first_name": "Priya", "email": "lead@example.com"})
        if made:
            lead.set_password("readup12345")
            lead.save()
        TutorProfile.objects.get_or_create(
            user=lead, defaults={"role": TutorProfile.Role.LEAD})

        for name, grade, language in STUDENTS:
            Student.objects.get_or_create(
                first_name=name, tutor=tutor,
                defaults={"grade": grade, "home_language": language})

        created = 0
        for skill, level, title, questions in BANK:
            lesson, made = Lesson.objects.get_or_create(
                title=title, skill=skill, level=level,
                defaults={"created_by": tutor})
            if not made:
                continue
            for order, (prompt, choices, correct, instructions) in enumerate(questions):
                question = Question.objects.create(
                    lesson=lesson, prompt=prompt, order=order,
                    instruction_translations=instructions)
                for i, text in enumerate(choices):
                    Choice.objects.create(question=question, text=text,
                                          is_correct=(i == correct))
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Demo ready: {Student.objects.count()} students, "
            f"{Lesson.objects.count()} lessons, {created} new questions.\n"
            f"Sign in as 'tutor' or 'lead' with password readup12345."))
