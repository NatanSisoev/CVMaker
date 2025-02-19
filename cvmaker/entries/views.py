import pathlib

from django.shortcuts import render, redirect

from cv.models import CV
from entries.models import EducationEntry, ExperienceEntry, PublicationEntry, OneLineEntry, BulletEntry, NormalEntry, \
    NumberedEntry, ReversedNumberedEntry, TextEntry


def homeOLD(request):
    if request.user.is_authenticated:
        context = {
            # TODO: pass CV/ CVInfo not entries
            'education_entries': EducationEntry.objects.filter(user=request.user),
            'experience_entries': ExperienceEntry.objects.filter(user=request.user),
            'normal_entries': NormalEntry.objects.filter(user=request.user),
            'publication_entries': PublicationEntry.objects.filter(user=request.user),
            'oneline_entries': OneLineEntry.objects.filter(user=request.user),
            'bullet_entries': BulletEntry.objects.filter(user=request.user),
            'numbered_entries': NumberedEntry.objects.filter(user=request.user),
            'reversed_numbered_entries': ReversedNumberedEntry.objects.filter(user=request.user),
            'text_entries': TextEntry.objects.filter(user=request.user),
            'user': request.user,
            'cv_id': 1  # TODO: get user cvs
        }
        return render(request, "homeOLD.html", context)
    else:
        return redirect("login")

def home(request):
    cvs = CV.objects.filter(user=request.user) if request.user.is_authenticated else []
    return render(request, 'home.html', {'cvs': cvs})