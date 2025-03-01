from django import forms
from .models import (
    EducationEntry, ExperienceEntry, PublicationEntry,
    NormalEntry, OneLineEntry, BulletEntry,
    NumberedEntry, ReversedNumberedEntry, TextEntry
)

class EducationEntryForm(forms.ModelForm):
    class Meta:
        model = EducationEntry
        fields = [
            'alias',
            'institution',
            'area',
            'degree',
            'location',
            'start_date',
            'end_date',
            'date',
            'summary',
            'highlights',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

class ExperienceEntryForm(forms.ModelForm):
    class Meta:
        model = ExperienceEntry
        fields = [
            'alias',
            'company',
            'position',
            'location',
            'start_date',
            'end_date',
            'date',
            'summary',
            'highlights',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

class PublicationEntryForm(forms.ModelForm):
    class Meta:
        model = PublicationEntry
        fields = [
            'alias',
            'title',
            'authors',
            'doi',
            'url',
            'journal',
            'date',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

class NormalEntryForm(forms.ModelForm):
    class Meta:
        model = NormalEntry
        fields = ['alias', 'name', 'location', 'start_date', 'end_date', 'date', 'summary', 'highlights']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

class OneLineEntryForm(forms.ModelForm):
    class Meta:
        model = OneLineEntry
        fields = ['alias','label', 'details']

class BulletEntryForm(forms.ModelForm):
    class Meta:
        model = BulletEntry
        fields = ['alias','bullet']

class NumberedEntryForm(forms.ModelForm):
    class Meta:
        model = NumberedEntry
        fields = ['alias','number']

class ReversedNumberedEntryForm(forms.ModelForm):
    class Meta:
        model = ReversedNumberedEntry
        fields = ['alias','reversed_number']

class TextEntryForm(forms.ModelForm):
    class Meta:
        model = TextEntry
        fields = ['alias','text']
