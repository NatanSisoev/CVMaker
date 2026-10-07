import re

from django import forms
from django.db import models

from .models import (
    BulletEntry,
    EducationEntry,
    ExperienceEntry,
    NormalEntry,
    NumberedEntry,
    OneLineEntry,
    PublicationEntry,
    ReversedNumberedEntry,
    TextEntry,
)


class EducationEntryForm(forms.ModelForm):
    class Meta:
        model = EducationEntry
        fields = [
            "alias",
            "institution",
            "area",
            "degree",
            "location",
            "start_date",
            "end_date",
            "date",
            "summary",
            "highlights",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class ExperienceEntryForm(forms.ModelForm):
    class Meta:
        model = ExperienceEntry
        fields = [
            "alias",
            "company",
            "position",
            "location",
            "start_date",
            "end_date",
            "date",
            "summary",
            "highlights",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class PublicationEntryForm(forms.ModelForm):
    class Meta:
        model = PublicationEntry
        fields = [
            "alias",
            "title",
            "authors",
            "doi",
            "url",
            "journal",
            "date",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class NormalEntryForm(forms.ModelForm):
    class Meta:
        model = NormalEntry
        fields = [
            "alias",
            "name",
            "location",
            "start_date",
            "end_date",
            "date",
            "summary",
            "highlights",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class OneLineEntryForm(forms.ModelForm):
    class Meta:
        model = OneLineEntry
        fields = ["alias", "label", "details"]


class BulletEntryForm(forms.ModelForm):
    class Meta:
        model = BulletEntry
        fields = ["alias", "bullet"]


class NumberedEntryForm(forms.ModelForm):
    class Meta:
        model = NumberedEntry
        fields = ["alias", "number"]


class ReversedNumberedEntryForm(forms.ModelForm):
    class Meta:
        model = ReversedNumberedEntry
        fields = ["alias", "reversed_number"]


class TextEntryForm(forms.ModelForm):
    class Meta:
        model = TextEntry
        fields = ["alias", "text"]


LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2}$")


class TranslationForm(forms.Form):
    """One field per ``TRANSLATABLE_FIELDS`` entry, for a single language.

    Blank means "no translation, fall back to canonical", so ``save`` drops
    blank keys (and the whole language once nothing is left) rather than
    storing "" -- which would read as a deliberate empty translation.
    """

    def __init__(self, entry, language: str, *args, **kwargs):
        self.entry = entry
        self.language = language
        bag = (entry.translations or {}).get(language) or {}
        kwargs.setdefault(
            "initial", {name: bag.get(name, "") for name in entry.TRANSLATABLE_FIELDS}
        )
        super().__init__(*args, **kwargs)
        for name in entry.TRANSLATABLE_FIELDS:
            model_field = entry._meta.get_field(name)
            is_long = isinstance(model_field, models.TextField)
            self.fields[name] = forms.CharField(
                label=str(model_field.verbose_name).capitalize(),
                required=False,
                widget=forms.Textarea(attrs={"rows": 3}) if is_long else None,
                max_length=getattr(model_field, "max_length", None),
            )

    def rows(self):
        """(bound field, canonical value) pairs for the side-by-side layout."""
        return [
            (self[name], getattr(self.entry, name, "") or "")
            for name in self.entry.TRANSLATABLE_FIELDS
        ]

    def save(self):
        bag = {name: value for name, value in self.cleaned_data.items() if value.strip()}
        translations = dict(self.entry.translations or {})
        if bag:
            translations[self.language] = bag
        else:
            translations.pop(self.language, None)
        self.entry.translations = translations
        self.entry.clean()  # validates the translations shape
        self.entry.save(update_fields=["translations"])
        return self.entry
