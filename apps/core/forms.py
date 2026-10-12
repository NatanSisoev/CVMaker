from __future__ import annotations

from typing import ClassVar

from django import forms

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    # Honeypot: hidden from people via CSS in the template.
    website = forms.CharField(required=False, label="Leave empty")

    class Meta:
        model = ContactMessage
        fields = ("name", "email", "message")
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "message": forms.Textarea(attrs={"rows": 6, "maxlength": 4000})
        }
