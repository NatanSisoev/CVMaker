"""Our account pages. Login, signup, logout, verification, password reset and
2FA come from allauth (mounted at /accounts/ in the root urlconf)."""

from django.urls import path

from .views import AccountSettingsView, ExportDataView, WaitlistView

urlpatterns = [
    path("profile/", AccountSettingsView.as_view(), name="profile"),
    path("profile/export/", ExportDataView.as_view(), name="account-export"),
    path("waitlist/", WaitlistView.as_view(), name="waitlist"),
]
