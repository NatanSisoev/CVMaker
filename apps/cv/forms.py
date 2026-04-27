from django import forms

from cv.models import CV
from sections.models import Section

from .models import CVDesign, CVInfo, CVLocale, CVSettings


class CVForm(forms.ModelForm):
    sections = forms.ModelMultipleChoiceField(
        queryset=Section.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Select Sections to Include",
    )

    class Meta:
        model = CV
        fields = ["alias", "info", "locale", "settings", "design", "sections"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields["sections"].queryset = Section.objects.filter(user=user)
            self.fields["info"].queryset = CVInfo.objects.filter(user=user)
            self.fields["locale"].queryset = CVLocale.objects.filter(user=user)
            self.fields["settings"].queryset = CVSettings.objects.filter(user=user)
            self.fields["design"].queryset = CVDesign.objects.filter(user=user)


class CVInfoForm(forms.ModelForm):
    class Meta:
        model = CVInfo
        exclude = ("user", "alias", "id", "cv")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "website": forms.URLInput(attrs={"class": "form-control"}),
            "photo": forms.FileInput(attrs={"class": "form-control-file"}),
        }


class CVDesignForm(forms.ModelForm):
    class Meta:
        model = CVDesign
        exclude = ("user", "alias", "id")
        widgets = {
            "theme": forms.Select(attrs={"class": "form-select"}),
            "design_file": forms.FileInput(attrs={"class": "form-control-file"}),
        }


class CVLocaleForm(forms.ModelForm):
    class Meta:
        model = CVLocale
        exclude = ("user", "alias", "id")
        widgets = {
            "language": forms.TextInput(attrs={"class": "form-control"}),
            "phone_number_format": forms.Select(attrs={"class": "form-select"}),
            "page_numbering_template": forms.TextInput(attrs={"class": "form-control"}),
            "last_updated_date_template": forms.TextInput(attrs={"class": "form-control"}),
            "date_template": forms.TextInput(attrs={"class": "form-control"}),
            "month": forms.TextInput(attrs={"class": "form-control"}),
            "months": forms.TextInput(attrs={"class": "form-control"}),
            "year": forms.TextInput(attrs={"class": "form-control"}),
            "years": forms.TextInput(attrs={"class": "form-control"}),
            "present": forms.TextInput(attrs={"class": "form-control"}),
            "to": forms.TextInput(attrs={"class": "form-control"}),
            "abbreviations_for_months": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "full_names_of_months": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "locale_file": forms.FileInput(attrs={"class": "form-control-file"}),
        }


class CVSettingsForm(forms.ModelForm):
    class Meta:
        model = CVSettings
        exclude = ("user", "alias", "id")
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "bold_keywords": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "settings_file": forms.FileInput(attrs={"class": "form-control-file"}),
        }
