"""
Auth forms.

Uses ``get_user_model()`` rather than importing ``User`` directly so the
forms stay correct if ``AUTH_USER_MODEL`` ever changes again.
"""

from __future__ import annotations

import re
from typing import ClassVar

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


_LANGUAGE_TAG_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class ProfileForm(forms.ModelForm):
    """The editable part of the account: name, email, preferred language."""

    class Meta:
        model = User
        fields = ("display_name", "email", "preferred_language")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "preferred_language": forms.TextInput(attrs={"maxlength": 5, "placeholder": "en"}),
        }

    def clean_email(self) -> str:
        email = User.objects.normalize_email(self.cleaned_data["email"])
        # The DB constraint is case-sensitive; addresses aren't, so check iexact.
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists()
        if taken:
            raise forms.ValidationError("Another account already uses this email address.")
        return email

    def clean_preferred_language(self) -> str:
        tag = (self.cleaned_data.get("preferred_language") or "").strip()
        if not tag:
            return "en"
        parts = tag.replace("_", "-").split("-")
        tag = "-".join([parts[0].lower(), *(p.upper() for p in parts[1:])])
        if not _LANGUAGE_TAG_RE.match(tag):
            raise forms.ValidationError("Use a language code like en, es or pt-BR.")
        return tag


class DeleteAccountForm(forms.Form):
    """Deletion is irreversible: require the password and the typed email."""

    password = forms.CharField(
        label="Current password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    confirm_email = forms.EmailField(
        label="Type your email to confirm",
        widget=forms.EmailInput(attrs={"autocomplete": "off"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("That password is not correct.")
        return password

    def clean_confirm_email(self) -> str:
        email = self.cleaned_data["confirm_email"]
        if email.strip().lower() != self.user.email.lower():
            raise forms.ValidationError("That doesn't match your account's email.")
        return email


class WaitlistForm(forms.Form):
    email = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()
