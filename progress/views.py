"""
Screen 8: the progress dashboard, the JSON API and the CSV report.

These satisfy requirement 2.5 (one internal JSON API plus one data-oriented feature) and are
the reason attempts store `level_after`: every chart here is a straight aggregation over
attempt history, with no second source of truth to drift.
"""

import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from accounts.models import Student
from lessons.models import Skill
from practice.models import Attempt


def _window(request):
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    return max(1, min(days, 365))


def _attempts_for(request):
    """Every attempt the signed-in user is allowed to see, honouring the student rule."""
    qs = Attempt.objects.filter(student__in=Student.visible_to(request.user))
    student_id = request.GET.get("student", "")
    if student_id.isdigit():
        qs = qs.filter(student_id=int(student_id))
    days = _window(request)
    return qs.filter(created_at__gte=timezone.now() - timezone.timedelta(days=days)), days


def _series(attempts):
    """Level over time, accuracy by skill, and the weakest skills -- the three widgets."""
    level_over_time = {}
    for created, level in attempts.values_list("created_at", "level_after"):
        day = timezone.localtime(created).date().isoformat()
        level_over_time.setdefault(day, []).append(level)
    level_points = [{"date": d, "level": round(sum(v) / len(v), 2)}
                    for d, v in sorted(level_over_time.items())]

    by_skill = (attempts.values("question__lesson__skill")
                .annotate(n=Count("id"), correct=Count("id", filter=Q(is_correct=True)))
                .order_by())
    labels = dict(Skill.choices)
    accuracy = [{"skill": labels.get(r["question__lesson__skill"], "—"),
                 "attempts": r["n"],
                 "accuracy": round(r["correct"] / r["n"], 3) if r["n"] else 0}
                for r in by_skill]

    # "Needs practice": lowest accuracy first, but only where there is enough evidence to
    # say anything. Three attempts is not a weakness, it is a small sample.
    needs = sorted([a for a in accuracy if a["attempts"] >= 4], key=lambda a: a["accuracy"])[:3]
    return level_points, accuracy, needs


@login_required
def dashboard(request):
    attempts, days = _attempts_for(request)
    level_points, accuracy, needs = _series(attempts)
    total = attempts.count()
    return render(request, "progress/dashboard.html", {
        "students": Student.visible_to(request.user),
        "selected": request.GET.get("student", ""),
        "days": days,
        "total_attempts": total,
        "overall_accuracy": (attempts.filter(is_correct=True).count() / total) if total else None,
        "level_points": level_points,
        "accuracy": accuracy,
        "needs": needs,
        "enough_data": total >= 10,
    })


@login_required
def api_progress(request):
    """The internal JSON API. Same numbers as the dashboard, same permission rule."""
    attempts, days = _attempts_for(request)
    level_points, accuracy, needs = _series(attempts)
    total = attempts.count()
    return JsonResponse({
        "window_days": days,
        "attempts": total,
        "overall_accuracy": round(attempts.filter(is_correct=True).count() / total, 3)
        if total else None,
        "level_over_time": level_points,
        "accuracy_by_skill": accuracy,
        "needs_practice": needs,
    })


@login_required
def export_csv(request):
    """The downloadable report a tutor shares with a program lead or parent."""
    attempts, days = _attempts_for(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = \
        f'attachment; filename="readup-progress-{timezone.now():%Y-%m-%d}.csv"'
    writer = csv.writer(response)
    writer.writerow(["date", "student", "skill", "level_before", "level_after",
                     "question", "answered", "correct", "seconds"])
    for a in attempts.select_related("student", "question__lesson").order_by("created_at"):
        writer.writerow([
            timezone.localtime(a.created_at).strftime("%Y-%m-%d %H:%M"),
            a.student.first_name,
            a.question.lesson.get_skill_display(),
            a.level_before, a.level_after,
            _csv_safe(a.question.prompt),
            _csv_safe(a.chosen_text),
            "yes" if a.is_correct else "no",
            round(a.seconds, 1),
        ])
    return response


FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value):
    """Prefix anything a spreadsheet would execute as a formula.

    A tutor-written question beginning with "=" would otherwise run as a formula when the
    program lead opens the report in Excel.
    """
    if isinstance(value, str) and value.startswith(FORMULA_TRIGGERS):
        return "'" + value
    return value
