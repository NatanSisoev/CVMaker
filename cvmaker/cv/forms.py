from django import forms
from .models import CVInfo

class CVInfoForm(forms.ModelForm):
    class Meta:
        model = CVInfo
        fields = '__all__'
        exclude = ('cv',)  # Exclude 'cv' as it's a related field and should be handled in the view
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control-file'}),
        }