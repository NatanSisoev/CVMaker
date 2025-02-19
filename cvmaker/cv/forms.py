from django import forms
from entries.models import EducationEntry, ExperienceEntry, PublicationEntry

class EducationEntryForm(forms.ModelForm):
    class Meta:
        model = EducationEntry
        fields = ['alias', 'institution', 'area', 'degree', 'location',
                 'start_date', 'end_date', 'summary', 'highlights']

class ExperienceEntryForm(forms.ModelForm):
    class Meta:
        model = ExperienceEntry
        fields = ['alias', 'company', 'position', 'location',
                 'start_date', 'end_date', 'summary', 'highlights']

class PublicationEntryForm(forms.ModelForm):
    class Meta:
        model = PublicationEntry
        fields = ['alias', 'title', 'authors', 'doi', 'url', 'journal', 'date']