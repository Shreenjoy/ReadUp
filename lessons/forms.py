"""Forms for the lesson bank and the authoring assistant."""

from django import forms

from .models import Lesson, Skill


class DraftRequestForm(forms.Form):
    """What the tutor gives the assistant."""

    passage = forms.CharField(
        label="Passage or topic",
        widget=forms.Textarea(attrs={"rows": 6, "placeholder":
            "Paste a short reading passage, or describe a topic such as "
            "'adding two numbers under twenty'."}),
        help_text="The assistant drafts questions from this. You review everything before it saves.")
    skill = forms.ChoiceField(choices=Skill.choices, initial=Skill.READING)
    n_questions = forms.IntegerField(label="How many questions", min_value=1, max_value=8,
                                     initial=4)


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title", "skill", "level", "passage"]
        widgets = {"passage": forms.Textarea(attrs={"rows": 4})}
