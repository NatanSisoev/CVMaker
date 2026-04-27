"""
Class-based views for the Section CRUD surface.

Phase 2.1: ``create_section_entries`` no longer parses
``content_type_id::object_id`` keys; the form now hands us plain
``BaseEntry`` UUIDs.

Phase 2.3 will collapse the duplicate ``create_section_entries`` between
``SectionCreateView`` and ``SectionUpdateView`` into a single
``apps/sections/services.py`` helper.
"""

from __future__ import annotations

import uuid

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


class _SectionEntryWriter:
    """Mixin: write SectionEntry rows for a list of BaseEntry UUIDs.

    Saves duplicating the same loop in Create + Update. Phase 2.3 lifts
    this into ``services.reorder_entries`` once the service module exists.
    """

    def _write_section_entries(self, entry_ids: list[str]) -> None:
        for order, entry_id in enumerate(entry_ids):
            self.object.section_entries.create(
                entry_id=uuid.UUID(entry_id),
                order=order,
            )


class SectionCreateView(SectionBaseView, _SectionEntryWriter, CreateView):
    form_class = SectionForm
    template_name = "sections/form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        if form.cleaned_data.get("entries"):
            self._write_section_entries(form.cleaned_data["entries"])
        return response

    def get_success_url(self):
        return reverse_lazy("section-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class SectionUpdateView(SectionBaseView, _SectionEntryWriter, UpdateView):
    form_class = SectionForm
    template_name = "sections/form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        # Replace, don't merge -- the form already represents the desired
        # final ordering of entries, including removals.
        self.object.section_entries.all().delete()
        if form.cleaned_data.get("entries"):
            self._write_section_entries(form.cleaned_data["entries"])
        return response

    def get_success_url(self):
        return reverse_lazy("section-detail", kwargs={"section_id": self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class SectionDeleteView(SectionBaseView, DeleteView):
    def get_success_url(self):
        return reverse_lazy("section-list")
