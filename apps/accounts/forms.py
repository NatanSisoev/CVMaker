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
from django.contrib.auth.forms import PasswordChangeForm

User = get_user_model()


class QuietPasswordChangeForm(PasswordChangeForm):
    """Django's form autofocuses ``old_password``; on the Settings page that scrolls
    the whole page down to it on every load, so drop the autofocus."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs.pop("autofocus", None)


_HANDLE_RE = re.compile(r"^[a-z0-9_-]{3,30}$")
_LANGUAGE_TAG_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class ProfileForm(forms.ModelForm):
    """Display name and preferred language. Email changes go through allauth
    (``account_email``) so the new address is verified first."""

    class Meta:
        model = User
        fields = (
            "display_name",
            "preferred_language",
            "notify_on_render",
            "public_handle",
            "public_cv",
            "public_show_contact",
        )
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "preferred_language": forms.TextInput(attrs={"maxlength": 5, "placeholder": "en"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["public_cv"].queryset = self.instance.cvs.all() if self.instance.pk else []
        self.fields["public_cv"].empty_label = "(none)"

    def clean_public_handle(self) -> str | None:
        handle = (self.cleaned_data.get("public_handle") or "").strip().lower()
        if not handle:
            return None  # NULL, so many users can stay private despite the unique index
        if not _HANDLE_RE.match(handle):
            raise forms.ValidationError("3-30 characters: letters, digits, '-' or '_'.")
        return handle

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("public_handle") and not cleaned.get("public_cv"):
            self.add_error("public_cv", "Pick the CV to show on your public page.")
        return cleaned

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
