from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from .models import Section
from .forms import SectionForm
from cv.models import CV

class SectionDetailView(DetailView):
    model = Section
    template_name = 'section_detail.html'

class SectionListView(LoginRequiredMixin, ListView):
    model = Section
    template_name = "sections/list.html"
    context_object_name = 'sections'

class SectionCreateView(CreateView):
    model = Section
    form_class = SectionForm
    template_name = "sections/section_form.html"

    def form_valid(self, form):
        cv = get_object_or_404(CV, pk=self.kwargs['cv_id'])
        form.instance.cv = cv
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('section-list', kwargs={'cv_id': self.kwargs['cv_id']})

class SectionUpdateView(UpdateView):
    model = Section
    form_class = SectionForm
    template_name = "sections/section_form.html"

    def get_success_url(self):
        return reverse_lazy('section-list', kwargs={'cv_id': self.object.cv.id})

class SectionDeleteView(DeleteView):
    model = Section
    template_name = "sections/section_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy('section-list', kwargs={'cv_id': self.object.cv.id})