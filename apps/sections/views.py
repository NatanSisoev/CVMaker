"""
Class-based views for the Section CRUD surface.

Phase 2.3: views are thin -- parse input, call service, render template.
The actual entry-write loop lives in ``apps/sections/services.py``
where it's testable without an HTTP round-trip.
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import SectionForm
from .models import Section


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
