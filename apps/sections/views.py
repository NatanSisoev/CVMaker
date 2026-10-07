"""
Class-based views for the Section CRUD surface.

Phase 2.3: views are thin -- parse input, call service, render template.
The actual entry-write loop lives in ``apps/sections/services.py``
where it's testable without an HTTP round-trip.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from cv.models import CV

from .forms import SectionForm
from .models import Section
from .services import reorder_entries, reorder_sections


class SectionBaseView(LoginRequiredMixin):
    model = Section
    pk_url_kwarg = "section_id"

    def get_queryset(self):
        return Section.objects.filter(user=self.request.user)


class SectionDetailView(SectionBaseView, DetailView):
    template_name = "sections/detail.html"
    context_object_name = "section"


class SectionListView(SectionBaseView, ListView):
    template_name = "sections/list.html"
    context_object_name = "sections"


class SectionCreateView(SectionBaseView, CreateView):
    form_class = SectionForm
    template_name = "sections/form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        # SectionForm.save_m2m handles entry creation + ordering; this view
        # just stamps the user and lets Django's standard ModelForm flow run.
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("section-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class SectionUpdateView(SectionBaseView, UpdateView):
    form_class = SectionForm
    template_name = "sections/form.html"

    def get_success_url(self):
        return reverse_lazy("section-detail", kwargs={"section_id": self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class SectionDeleteView(SectionBaseView, DeleteView):
    def get_success_url(self):
        return reverse_lazy("section-list")


# ---------------------------------------------------------------------------
# Drag-reorder endpoints (Editor screen). POST `ids` repeated, top first.
# 204 on success; 400 if any id isn't attached to the CV/section.
# ---------------------------------------------------------------------------
def _apply_order(reorder, parent, ids) -> HttpResponse:
    if not ids:
        return HttpResponseBadRequest("No ids given.")
    try:
        with transaction.atomic():
            reorder(parent, ids)
    except (ObjectDoesNotExist, ValueError):
        return HttpResponseBadRequest("Unknown id in ordering.")
    return HttpResponse(status=204)


@login_required
@require_POST
def reorder_cv_sections_view(request, cv_id):
    cv = get_object_or_404(CV, pk=cv_id, user=request.user)
    return _apply_order(reorder_sections, cv, request.POST.getlist("ids"))


@login_required
@require_POST
def reorder_section_entries_view(request, section_id):
    section = get_object_or_404(Section, pk=section_id, user=request.user)
    return _apply_order(reorder_entries, section, request.POST.getlist("ids"))
