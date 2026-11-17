from django.urls import path

from . import views

app_name = "practice"

urlpatterns = [
    path("start/<int:student_pk>/", views.start_session, name="start"),
    path("session/<int:pk>/", views.session_view, name="session"),
    path("session/<int:pk>/answer/", views.answer, name="answer"),
    path("session/<int:pk>/end/", views.end_session, name="end"),
    path("session/<int:pk>/summary/", views.summary, name="summary"),
]
