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

LANGUAGE_CODE_RE = re.compile(r"^[a-z]{2}$")


class _EntryForm(forms.ModelForm):
    """Shared behaviour for every entry form: the entry's original language.

    Blank keeps the current value (``en`` for new entries), so posts that omit
    the field don't reset it. Switching to a language that already has a
    translation is refused: ``get_field`` would start ignoring that translation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["canonical_language"]
        field.required = False
        field.label = "Original language"
        field.help_text = "2-letter ISO 639-1 code the fields below are written in, e.g. en, es."
        field.widget.attrs.update({"maxlength": 2, "placeholder": "en", "autocomplete": "off"})

    def clean_canonical_language(self):
        code = (self.cleaned_data.get("canonical_language") or "").strip().lower()
        if not code:
            return self.instance.canonical_language or "en"
        if not LANGUAGE_CODE_RE.match(code):
            raise forms.ValidationError("Use a 2-letter ISO 639-1 code, e.g. en or es.")
        if code != self.instance.canonical_language and code in (self.instance.translations or {}):
            raise forms.ValidationError(
                "This entry already has a %(code)s translation. Remove it first, "
                "or the translation would stop being used.",
                params={"code": code.upper()},
            )
        return code


class EducationEntryForm(_EntryForm):
    class Meta:
        model = EducationEntry
        fields = [
            "alias",
            "canonical_language",
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


class ExperienceEntryForm(_EntryForm):
    class Meta:
        model = ExperienceEntry
        fields = [
            "alias",
            "canonical_language",
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


class PublicationEntryForm(_EntryForm):
    class Meta:
        model = PublicationEntry
        fields = [
            "alias",
            "canonical_language",
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


class NormalEntryForm(_EntryForm):
    class Meta:
        model = NormalEntry
        fields = [
            "alias",
            "canonical_language",
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


class OneLineEntryForm(_EntryForm):
    class Meta:
        model = OneLineEntry
        fields = ["alias", "canonical_language", "label", "details"]


class BulletEntryForm(_EntryForm):
    class Meta:
        model = BulletEntry
        fields = ["alias", "canonical_language", "bullet"]


class NumberedEntryForm(_EntryForm):
    class Meta:
        model = NumberedEntry
        fields = ["alias", "canonical_language", "number"]


class ReversedNumberedEntryForm(_EntryForm):
    class Meta:
        model = ReversedNumberedEntry
        fields = ["alias", "canonical_language", "reversed_number"]


class TextEntryForm(_EntryForm):
    class Meta:
        model = TextEntry
        fields = ["alias", "canonical_language", "text"]


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
