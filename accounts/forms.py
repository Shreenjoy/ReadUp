"""Sign-up and student forms."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Student, TutorProfile


class TutorSignUpForm(UserCreationForm):
    """Sign-up for an adult. The role chosen here decides what they can see."""

    full_name = forms.CharField(max_length=120, label="Full name")
    email = forms.EmailField()
    program = forms.CharField(max_length=120, initial="Informed Empowerment",
                              help_text="The tutoring program you volunteer with.")
    role = forms.ChoiceField(choices=TutorProfile.Role.choices,
                             initial=TutorProfile.Role.TUTOR,
                             widget=forms.RadioSelect)

    class Meta:
        model = User
        fields = ["username", "full_name", "email"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["full_name"][:150]
        if commit:
            user.save()
            TutorProfile.objects.create(user=user, role=self.cleaned_data["role"],
                                        program=self.cleaned_data["program"])
        return user


class StudentForm(forms.ModelForm):
    """A tutor creates a child's profile. First name only -- see Student's docstring."""

    class Meta:
        model = Student
        fields = ["first_name", "grade", "home_language", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
        labels = {"first_name": "First name", "notes": "Notes for the next tutor"}
        help_texts = {"first_name": "First name only. ReadUp never stores a child's surname."}

    def clean_first_name(self):
        name = self.cleaned_data["first_name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("Please enter the child's first name.")
        return name
