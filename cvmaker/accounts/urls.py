from django.urls import path

from .views import SignUpView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path("profile/", lambda: None, name="profile"),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
]