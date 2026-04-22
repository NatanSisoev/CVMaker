from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import TemplateView

from .views import SignUpView

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    # Placeholder — Phase 6 (allauth migration) replaces this with a real
    # account page.
    path(
        "profile/",
        TemplateView.as_view(
            template_name="placeholder.html",
            extra_context={
                "page_title": "Account",
                "page_description": "Account settings land in Phase 6.",
            },
        ),
        name="profile",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
]
