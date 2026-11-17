"""Sign-up, and the My students hub."""

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render

from lessons.models import Skill

from .forms import StudentForm, TutorSignUpForm
from .models import Student


def home(request):
    """Screen 1. The only page a signed-out visitor sees."""
    if request.user.is_authenticated:
        return redirect("students:list")
    return render(request, "home.html")


def signup(request):
    """Screen 2."""
    form = TutorSignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("students:list")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def student_list(request):
    """Screen 3: the hub. Search filters the cards server-side."""
    query = request.GET.get("q", "").strip()
    students = Student.visible_to(request.user)
    if query:
        students = students.filter(first_name__icontains=query)
    students = students.annotate(session_count=Count("sessions", distinct=True),
                                 last_seen=Max("sessions__started_at"))
    cards = [{"student": s,
              "reading_level": s.current_level(Skill.READING),
              "math_level": s.current_level(Skill.MATH),
              "last_seen": s.last_seen,
              "session_count": s.session_count} for s in students]
    return render(request, "accounts/student_list.html",
                  {"cards": cards, "query": query})


@login_required
def student_detail(request, pk):
    """Screen 4."""
    student = get_object_or_404(Student.visible_to(request.user), pk=pk)
    return render(request, "accounts/student_detail.html", {
        "student": student,
        "reading_level": student.current_level(Skill.READING),
        "math_level": student.current_level(Skill.MATH),
        "sessions": student.sessions.all()[:10],
    })


@login_required
def student_create(request):
    form = StudentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student = form.save(commit=False)
        student.tutor = request.user
        profile = getattr(request.user, "tutor_profile", None)
        student.program = profile.program if profile else "Informed Empowerment"
        student.save()
        return redirect(student)
    return render(request, "accounts/student_form.html", {"form": form, "mode": "Add"})


@login_required
def student_edit(request, pk):
    student = get_object_or_404(Student.visible_to(request.user), pk=pk)
    form = StudentForm(request.POST or None, instance=student)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(student)
    return render(request, "accounts/student_form.html",
                  {"form": form, "mode": "Edit", "student": student})
