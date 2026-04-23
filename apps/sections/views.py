import uuid

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)

from .forms import SectionForm
from .models import Section


class SectionBaseView(LoginRequiredMixin):
    model = Section
    pk_url_kwarg = 'section_id'

    def get_queryset(self):
        return Section.objects.filter(user=self.request.user)

class SectionDetailView(SectionBaseView, DetailView):
    template_name = 'sections/detail.html'
    context_object_name = 'section'

class SectionListView(SectionBaseView, ListView):
    template_name = "sections/list.html"
    context_object_name = 'sections'

class SectionCreateView(SectionBaseView, CreateView):
    form_class = SectionForm
    template_name = "sections/form.html"

    def form_valid(self, form):
        # Save main section first
        form.instance.user = self.request.user
        response = super().form_valid(form)

        # Create section entries with order
        if form.cleaned_data.get('entries'):
            self.create_section_entries(form.cleaned_data['entries'])

        return response

    def create_section_entries(self, entries):
        for order, entry_key in enumerate(entries):
            ct_id, object_id = entry_key.split('::')
            self.object.section_entries.create(
                content_type_id=int(ct_id),
                object_id=uuid.UUID(object_id),
                order=order
            )

    def get_success_url(self):
        return reverse_lazy('section-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class SectionUpdateView(SectionBaseView, UpdateView):
    form_class = SectionForm
    template_name = "sections/form.html"

    def form_valid(self, form):
        # First save the main form
        response = super().form_valid(form)

        # Clear existing entries and create new ones
        self.object.section_entries.all().delete()
        if form.cleaned_data.get('entries'):
            self.create_section_entries(form.cleaned_data['entries'])

        return response

    def create_section_entries(self, entries):
        for order, entry_key in enumerate(entries):
            ct_id, object_id = entry_key.split('::')
            self.object.section_entries.create(
                content_type_id=int(ct_id),
                object_id=uuid.UUID(object_id),
                order=order
            )

    def get_success_url(self):
        return reverse_lazy('section-detail', kwargs={'section_id': self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class SectionDeleteView(SectionBaseView, DeleteView):
    def get_success_url(self):
        return reverse_lazy('section-list')
