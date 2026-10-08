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

    def clean_entries(self):
        """rendercv needs one entry type per section; reject mixes up front."""
        from entries.models import BaseEntry

        ids = self.cleaned_data.get("entries", [])
        kinds = {
            type(entry).__name__.replace("Entry", "")
            for entry in BaseEntry.objects.filter(pk__in=ids).select_subclasses()
        }
        if len(kinds) > 1:
            raise forms.ValidationError(
                "A section can hold only one kind of entry (found %(kinds)s). "
                "Create a separate section for each kind.",
                params={"kinds": ", ".join(sorted(kinds))},
            )
        return ids

    def save(self, commit=True):
        # super().save(commit=False) sets ``self.save_m2m = self._save_m2m``,
        # so the entry write must live in ``_save_m2m`` (an override of a
        # ``save_m2m`` method would be shadowed by that instance attribute).
        section = super().save(commit=False)
        section.user = self.user
        if commit:
            section.save()
            self._save_m2m()
        return section

    def _save_m2m(self):
        super()._save_m2m()
        self._sync_entries()

    def _sync_entries(self):
        """Make the section hold exactly the checked entries.

        Entries that stay keep their row and their order (set by drag-reorder
        in the Editor); newly checked ones are appended; unchecked ones go.
        """
        wanted = [uuid.UUID(entry_id) for entry_id in self.cleaned_data.get("entries", [])]
        current = {se.entry_id: se for se in self.instance.section_entries.all()}

        for entry_id, section_entry in current.items():
            if entry_id not in wanted:
                section_entry.delete()

        kept_orders = [se.order for eid, se in current.items() if eid in wanted]
        next_order = max(kept_orders, default=-1) + 1
        for entry_id in wanted:
            if entry_id not in current:
                SectionEntry.objects.create(
                    section=self.instance, entry_id=entry_id, order=next_order
                )
                next_order += 1
