from django.shortcuts import render
from entries.models import EducationEntry, ExperienceEntry

def homepage(request):
    context = {
        'education_entries': EducationEntry.objects.filter(user=request.user),  # or .all() if no user relation
        'experience_entries': ExperienceEntry.objects.filter(user=request.user),
    }
    return render(request, "home.html", context)
