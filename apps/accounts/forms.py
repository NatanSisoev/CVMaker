"""
Auth forms.

Uses ``get_user_model()`` rather than importing ``User`` directly so the
forms stay correct if ``AUTH_USER_MODEL`` ever changes again.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class SignUpForm(UserCreationForm):
    """Email-first signup. Username is hidden and defaulted on save."""

    email = forms.EmailField(
        required=True, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )

    class Meta:
        model = User
        fields = ("email", "password1", "password2")

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        # Pre-fill username from the email's local part to satisfy the
        # AbstractUser uniqueness constraint. Users can change it later.
        user.username = self.cleaned_data["email"].split("@", 1)[0]
        if commit:
            user.save()
        return user
