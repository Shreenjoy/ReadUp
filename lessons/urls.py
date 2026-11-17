from django.urls import path

from . import views

app_name = "lessons"

urlpatterns = [
    path("", views.lesson_list, name="list"),
    path("new/", views.lesson_create, name="create"),
    path("draft/", views.lesson_draft, name="draft"),
    path("draft/save/", views.lesson_save_draft, name="save-draft"),
    path("<int:pk>/", views.lesson_detail, name="detail"),
]
