"""
Forms for the sections app.

Phase 2.1 (ADR-0005) replaces the ``content_type::object_id`` choice values
with plain ``BaseEntry.id`` UUIDs -- now that ``SectionEntry.entry`` is a
real FK to ``BaseEntry``, we don't need the content type to disambiguate.

The choice list is still built per-subclass so labels read naturally
("educationentry: alias-foo"); subclass resolution at save time happens
automatically via MTI (the ``BaseEntry`` row is the parent of the
subclass row, sharing its primary key).
"""

from __future__ import annotations

import uuid

from django import forms

from entries.models import (
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

from .models import Section, SectionEntry

# Subclasses we offer in the entry picker. Order = display order in the form.
_ENTRY_SUBCLASSES = (
    EducationEntry,
    ExperienceEntry,
    PublicationEntry,
    NormalEntry,
    OneLineEntry,
    BulletEntry,
    NumberedEntry,
    ReversedNumberedEntry,
    TextEntry,
)


class SectionForm(forms.ModelForm):
    entries = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select entries to include in this section",
    )

    class Meta:
        model = Section
        fields = ["title", "alias"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Build (entry-uuid, label) choices grouped by subclass.
        choices: list[tuple[str, str]] = []
        for model_cls in _ENTRY_SUBCLASSES:
            for entry in model_cls.objects.filter(user=self.user):
                # The label includes the subclass name so "Education: foo"
                # and "Experience: foo" are distinguishable in the form.
                kind = model_cls.__name__.replace("Entry", "").lower()
                choices.append((str(entry.id), f"{kind}: {entry.alias}"))

        self.fields["entries"].choices = choices

        # Pre-select on edit. ``entry_id`` on SectionEntry already carries
        # the BaseEntry UUID -- no content-type lookup needed.
        if self.instance.pk:
            current_ids = self.instance.section_entries.values_list("entry_id", flat=True)
            self.fields["entries"].initial = [str(eid) for eid in current_ids]

    def save(self, commit=True):
        section = super().save(commit=False)
        section.user = self.user
        if commit:
            section.save()
            self.save_m2m()
        return section

    def save_m2m(self):
        # Reset and re-add. Cheap because each user has at most a few
        # entries per section; Phase 4 swaps this for an HTMX reorder UI.
        self.instance.section_entries.all().delete()

        entry_ids = self.cleaned_data.get("entries", [])
        for order, entry_id in enumerate(entry_ids):
            SectionEntry.objects.create(
                section=self.instance,
                entry_id=uuid.UUID(entry_id),
                order=order,
            )
