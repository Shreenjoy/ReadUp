"""
ReadUp URL map.

    /                     home              landing page (screen 1)
    /accounts/signup/     signup            tutor sign-up (screen 2)
    /accounts/login/      login             Django auth
    /students/            students:*        My students, profiles (screens 3 and 4)
    /practice/            practice:*        the adaptive session and summary (screens 5 and 6)
    /lessons/             lessons:*         the lesson bank and AI assistant (screen 7)
    /progress/            progress:*        dashboard, JSON API and CSV export (screen 8)
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts import views as account_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", account_views.home, name="home"),
    path("accounts/signup/", account_views.signup, name="signup"),
    path("accounts/login/",
         auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("students/", include("accounts.urls")),
    path("practice/", include("practice.urls")),
    path("lessons/", include("lessons.urls")),
    path("progress/", include("progress.urls")),
]
