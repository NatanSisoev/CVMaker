import uuid

from django import forms
from django.contrib.contenttypes.models import ContentType

from .models import Section, SectionEntry


class SectionForm(forms.ModelForm):
    entries = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select entries to include in this section"
    )

    class Meta:
        model = Section
        fields = ['title', 'alias']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Get all entry types that can be linked to sections
        entry_models = ContentType.objects.filter(
            app_label='entries',
            model__in=[
                'educationentry', 'experienceentry', 'publicationentry',
                'normalentry', 'onelineentry', 'bulletentry',
                'numberedentry', 'reversednumberedentry', 'textentry'
            ]
        )

        # Build choices list: (content_type_id-object_id, entry_title)
        choices = []
        for ct in entry_models:
            model_class = ct.model_class()
            for entry in model_class.objects.filter(user=self.user):
                value = f"{ct.id}::{entry.id}"
                label = f"{ct.name}: {entry.alias}"
                choices.append((value, label))

        self.fields['entries'].choices = choices

        # Set initial values when editing
        if self.instance.pk:
            current_entries = self.instance.section_entries.values_list(
                'content_type', 'object_id'
            )
            initial = [f"{ct}::{oid}" for ct, oid in current_entries]
            self.fields['entries'].initial = initial

    def save(self, commit=True):
        section = super().save(commit=False)
        section.user = self.user
        if commit:
            section.save()
            self.save_m2m()
        return section

    def save_m2m(self):
        # Clear existing entries
        self.instance.section_entries.all().delete()

        # Create new entries with order
        entries = self.cleaned_data.get('entries', [])
        for order, entry_key in enumerate(entries):
            ct_id, object_id = entry_key.split('-')

            SectionEntry.objects.create(
                section=self.instance,
                content_type_id=int(ct_id),
                object_id=uuid.UUID(object_id),
                order=order
            )