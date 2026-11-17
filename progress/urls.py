from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/", views.api_progress, name="api"),
    path("export.csv", views.export_csv, name="export"),
]
