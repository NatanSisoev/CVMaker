from django.contrib.auth import views as auth_views
from django.urls import path
from django_ratelimit.decorators import ratelimit

from .views import AccountSettingsView, ExportDataView, SignUpView

urlpatterns = [
    path(
        "signup/",
        ratelimit(key="ip", rate="5/h", method="POST")(SignUpView.as_view()),
        name="signup",
    ),
    path("profile/", AccountSettingsView.as_view(), name="profile"),
    path("profile/export/", ExportDataView.as_view(), name="account-export"),
    # Brute-force guard: per IP, and per targeted account.
    path(
        "login/",
        ratelimit(key="ip", rate="10/m", method="POST")(
            ratelimit(key="post:username", rate="5/m", method="POST")(
                auth_views.LoginView.as_view(template_name="accounts/login.html")
            )
        ),
        name="login",
    ),
]
