"""
Screen 7: the lesson bank, plus the AI authoring assistant.

The assistant is a two-step flow on purpose -- draft, then review and save. A one-click
"generate and save" would put model output in front of a child with no adult in between,
which is the thing we are least willing to do.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from . import ai
from .forms import DraftRequestForm, LessonForm
from .models import Choice, Lesson, Question, Skill


@login_required
def lesson_list(request):
    """Browse and filter the bank. Filters are querystring-driven so a view is shareable."""
    lessons = Lesson.objects.select_related("created_by").prefetch_related("questions")
    skill = request.GET.get("skill", "")
    level = request.GET.get("level", "")
    if skill in Skill.values:
        lessons = lessons.filter(skill=skill)
    if level.isdigit():
        lessons = lessons.filter(level=int(level))
    # Coverage matrix. A gap here is the cause of the "asked L5, served L4" warning tutors
    # see on the session summary, so the bank page is where it belongs.
    from .models import Question
    coverage = []
    for value, label in Skill.choices:
        row = {"skill": label, "levels": []}
        for lvl in range(1, 7):
            row["levels"].append({
                "level": lvl,
                "count": Question.objects.filter(lesson__skill=value, lesson__level=lvl).count(),
            })
        coverage.append(row)
    return render(request, "lessons/lesson_list.html", {
        "lessons": lessons, "skill": skill, "level": level,
        "skills": Skill.choices, "levels": range(1, 7),
        "coverage": coverage,
        "has_gaps": any(c["count"] == 0 for row in coverage for c in row["levels"]),
        "ai_configured": ai.is_configured(),
    })


@login_required
def lesson_detail(request, pk):
    lesson = get_object_or_404(Lesson.objects.prefetch_related("questions__choices"), pk=pk)
    return render(request, "lessons/lesson_detail.html", {"lesson": lesson})


@login_required
def lesson_draft(request):
    """Step 1: ask the assistant for a draft. Never saves anything."""
    form = DraftRequestForm(request.POST or None)
    draft = None
    if request.method == "POST" and form.is_valid():
        try:
            draft = ai.draft_lesson(
                form.cleaned_data["passage"],
                skill=form.cleaned_data["skill"],
                n_questions=form.cleaned_data["n_questions"])
        except ai.DraftError as exc:
            form.add_error("passage", str(exc))
    return render(request, "lessons/lesson_draft.html", {
        "form": form, "draft": draft,
        "passage": request.POST.get("passage", ""),
        "skill": request.POST.get("skill", Skill.READING),
        "ai_configured": ai.is_configured(),
    })


@login_required
@transaction.atomic
def lesson_save_draft(request):
    """Step 2: save the draft the tutor reviewed, with any edits they made.

    Runs in a transaction: a lesson whose questions half-saved would sit in the bank looking
    complete and then hand a child a question with no answers.
    """
    if request.method != "POST":
        return redirect("lessons:draft")

    titles = request.POST.get("title", "").strip() or "Untitled lesson"
    skill = request.POST.get("skill", Skill.READING)
    level = int(request.POST.get("level", 1) or 1)
    lesson = Lesson.objects.create(
        title=titles[:120], skill=skill if skill in Skill.values else Skill.READING,
        level=max(1, min(6, level)), passage=request.POST.get("passage", "")[:4000],
        created_by=request.user, ai_generated=request.POST.get("source") == "ai")

    saved = 0
    for i in range(int(request.POST.get("question_count", 0) or 0)):
        prompt = request.POST.get(f"q{i}_prompt", "").strip()
        if not prompt:
            continue
        correct = request.POST.get(f"q{i}_correct")
        texts = [request.POST.get(f"q{i}_c{j}", "").strip() for j in range(4)]
        if correct is None or not all(texts):
            continue                       # refuse an incomplete question rather than save it
        question = Question.objects.create(
            lesson=lesson, prompt=prompt[:300], order=i,
            instruction_translations={
                code: request.POST.get(f"q{i}_i_{code}", "").strip()
                for code in ai.TARGET_LANGUAGES
                if request.POST.get(f"q{i}_i_{code}", "").strip()})
        for j, text in enumerate(texts):
            Choice.objects.create(question=question, text=text[:120],
                                  is_correct=(str(j) == str(correct)))
        saved += 1

    if not saved:
        transaction.set_rollback(True)
        messages.error(request, "Nothing was saved: every question needs four answers and "
                                "one marked correct.")
        return redirect("lessons:draft")

    messages.success(request, f"Saved “{lesson.title}” with {saved} question"
                              f"{'s' if saved != 1 else ''}.")
    return redirect(lesson)


@login_required
def lesson_create(request):
    """Write a lesson by hand, with no assistant involved."""
    form = LessonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        lesson = form.save(commit=False)
        lesson.created_by = request.user
        lesson.save()
        messages.success(request, "Lesson created. Add questions to it below.")
        return redirect(lesson)
    return render(request, "lessons/lesson_form.html", {"form": form})
