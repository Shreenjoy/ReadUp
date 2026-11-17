"""
The practice session: Joy's adaptive quiz engine, as Django views.

The loop is deliberately one question per request:

    GET  /practice/session/<pk>/   -> engine decides the level, picks a question, renders it
    POST /practice/session/<pk>/   -> records the attempt, recomputes the level, redirects

A redirect after the POST (rather than rendering the next question directly) means a child
hammering refresh cannot record the same answer twice, which on a shared classroom laptop is
not a hypothetical.
"""

import time

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Student
from lessons.models import Choice, Skill

from . import engine
from .models import Attempt, Session


@login_required
def start_session(request, student_pk):
    """Create a session and send the tutor straight into the first question."""
    student = get_object_or_404(Student.visible_to(request.user), pk=student_pk)
    skill = request.GET.get("skill", Skill.READING)
    if skill not in Skill.values:
        skill = Skill.READING
    session = Session.objects.create(
        student=student, tutor=request.user, skill=skill,
        started_level=student.current_level(skill))
    return redirect(session)


@login_required
def session_view(request, pk):
    """Screen 5: one question, four big answers, no score shown to the child."""
    session = get_object_or_404(
        Session.objects.select_related("student"),
        pk=pk, student__in=Student.visible_to(request.user))

    if session.is_finished:
        return redirect("practice:summary", pk=session.pk)

    level = engine.decide_level(session)
    question = engine.pick_question(session, level)
    if question is None:
        # The bank has nothing in this skill. Say so plainly instead of showing a blank page.
        return render(request, "practice/no_questions.html", {"session": session})

    request.session[f"q_start_{session.pk}"] = time.time()
    # Display the level of the question actually being asked, not the one the engine wanted.
    # These differ when the bank has a gap, and showing the requested level made the header
    # state something untrue -- "Level 5" above a level 4 question.
    return render(request, "practice/session.html", {
        "session": session,
        "question": question,
        "level": question.lesson.level,
        "requested_level": level,
        "level_mismatch": question.lesson.level != level,
        "instruction": question.instruction_for(session.student.home_language),
        "answered": session.answered,
        "progress": range(session.planned_questions),
    })


@login_required
@require_POST
def answer(request, pk):
    """Record one answer, let the engine move the level, and move on."""
    session = get_object_or_404(Session, pk=pk, student__in=Student.visible_to(request.user))
    if session.is_finished:
        return redirect("practice:summary", pk=session.pk)

    choice = get_object_or_404(Choice, pk=request.POST.get("choice"))
    question = choice.question
    level_before = engine.decide_level(session)

    started = request.session.pop(f"q_start_{session.pk}", None)
    seconds = max(0.0, time.time() - started) if started else 0.0

    attempt = Attempt.objects.create(
        session=session, student=session.student, question=question,
        chosen_text=choice.text, is_correct=choice.is_correct,
        level_before=level_before, level_after=level_before, seconds=seconds)

    # The level for the NEXT question is decided from history that now includes this attempt,
    # then written back onto it, so every attempt records the decision it caused.
    attempt.level_after = engine.next_level(level_before,
                                            engine.results_since_last_change(session))
    attempt.save(update_fields=["level_after"])

    if session.answered >= session.planned_questions:
        session.ended_at = timezone.now()
        session.save(update_fields=["ended_at"])
        return redirect("practice:summary", pk=session.pk)
    return redirect(session)


@login_required
def end_session(request, pk):
    session = get_object_or_404(Session, pk=pk, student__in=Student.visible_to(request.user))
    if session.ended_at is None:
        session.ended_at = timezone.now()
        session.save(update_fields=["ended_at"])
    return redirect("practice:summary", pk=session.pk)


@login_required
def summary(request, pk):
    """Screen 6: tutor-only wrap-up, and where notes for the next tutor are saved."""
    session = get_object_or_404(
        Session.objects.select_related("student"),
        pk=pk, student__in=Student.visible_to(request.user))

    if request.method == "POST":
        session.notes = request.POST.get("notes", "")[:2000]
        session.save(update_fields=["notes"])
        if session.notes:
            session.student.notes = session.notes
            session.student.save(update_fields=["notes"])
        return redirect("students:list")

    attempts = session.attempts.select_related("question")
    best = 0
    streak = 0
    for a in attempts:
        streak = streak + 1 if a.is_correct else 0
        best = max(best, streak)
    return render(request, "practice/summary.html", {
        "session": session, "attempts": attempts, "best_streak": best,
        "minutes": round(((session.ended_at or timezone.now())
                          - session.started_at).total_seconds() / 60),
    })
