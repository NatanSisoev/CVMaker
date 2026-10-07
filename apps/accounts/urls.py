from django.contrib.auth import views as auth_views
from django.urls import path

from .views import AccountSettingsView, SignUpView

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path("profile/", AccountSettingsView.as_view(), name="profile"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
]
