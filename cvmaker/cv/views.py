import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, HttpResponse, Http404
import os

from rendercv import data
from rendercv.renderer import renderer
from django.shortcuts import get_object_or_404, render

from cv.models import CV, SectionEntry
from cvmaker import settings
from .forms import EducationEntryForm, ExperienceEntryForm, PublicationEntryForm

from django.views.generic import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import CV

from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView


class CVCreateView(CreateView):
    model = CV
    fields = ['alias', 'info', 'design', 'locale', 'settings']
    template_name = 'cv_form.html'

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)

        # Check which button was clicked
        if 'add_sections' in self.request.POST:
            return redirect('cv-section-order', pk=self.object.id)
        return redirect('cv-detail', pk=self.object.id)


class CVUpdateView(UpdateView):
    model = CV
    fields = ['alias', 'info', 'design', 'locale', 'settings']
    template_name = 'cv_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)

        if 'add_sections' in self.request.POST:
            return redirect('cv-section-order', pk=self.object.id)
        return redirect('cv-detail', pk=self.object.id)

from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from .models import CV

class CVDetailView(DetailView):
    model = CV
    template_name = 'cv_detail.html'
    context_object_name = 'cv'

    def get_object(self, queryset=None):
        # Ensure the user can only access their own CV
        return get_object_or_404(CV, pk=self.kwargs['cv_id'], user=self.request.user)


class EditCVView(LoginRequiredMixin, UpdateView):
    model = CV
    template_name = 'cv_form.html'
    fields = ['alias', 'info', 'design', 'locale']

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_success_url(self):
        return reverse_lazy('cv-detail', kwargs={'cv_id': self.object.id})

    def get_object(self, queryset=None):
        # Ensure the object is fetched by its ID from the kwargs and filtered by user
        return get_object_or_404(CV, id=self.kwargs["cv_id"], user=self.request.user)

########################################################################################################################
########################################################################################################################
########################################################################################################################

class CreateCVView(LoginRequiredMixin, CreateView):
    model = CV
    template_name = 'cv_form.html'
    fields = ['title', 'description']

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('cv-edit', kwargs={'cv_id': self.object.id})


from django.shortcuts import get_object_or_404



class DeleteCVView(LoginRequiredMixin, DeleteView):
    model = CV
    template_name = 'cv_confirm_delete.html'
    success_url = reverse_lazy('dashboard')

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


def preview_cv(request, cv_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    return render(request, 'cv_detail.html', {'cv': cv})

def download_cv(request, cv_id):
    # TODO: cv.photo location
    cv = CV.objects.get(id=cv_id, user=request.user)
    data_model = data.validate_input_dictionary_and_return_the_data_model(cv.serialize())

    render_command_settings: data.models.RenderCommandSettings = data_model.rendercv_settings.render_command
    if not render_command_settings or not render_command_settings.output_folder_name:
        return HttpResponse("Invalid render command settings", status=400)

    output_directory = settings.MEDIA_ROOT / render_command_settings.output_folder_name

    typst_file_path_in_output_folder = renderer.create_a_typst_file_and_copy_theme_files(
        data_model, output_directory
    )
    pdf_file_path_in_output_folder = renderer.render_a_pdf_from_typst(typst_file_path_in_output_folder)

    if os.path.exists(pdf_file_path_in_output_folder):
        return FileResponse(open(pdf_file_path_in_output_folder, "rb"), content_type="application/pdf")
    else:
        return HttpResponse("File not found", status=404)


from django.views.generic import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from .models import CV, Section, CVInfoSection
from entries.models import EducationEntry, ExperienceEntry, PublicationEntry


# views.py
class SectionOrderView(LoginRequiredMixin, UpdateView):
    model = CV
    template_name = 'templates/section_order.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sections'] = self.object.info.cvinfosection_set.order_by('order')
        return context

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)


class SectionCreateView(CreateView):
    model = Section
    template_name = 'section_form.html'
    fields = ['title', 'alias']

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('cv-structure-edit', kwargs={'cv_id': self.kwargs['cv_id']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cv_id'] = self.kwargs['cv_id']  # Ensure cv_id is passed to template
        return context


class EntryCreateView(CreateView):
    model = None  # Will be set dynamically
    template_name = 'entry_form.html'

    def get_form_class(self):
        entry_type = self.kwargs.get('entry_type')
        return {
            'education': EducationEntryForm,
            'experience': ExperienceEntryForm,
            'publication': PublicationEntryForm
        }.get(entry_type, EducationEntryForm)

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        # Add to section
        section = Section.objects.get(id=self.kwargs['section_id'])
        SectionEntry.objects.create(
            section=section,
            content_object=self.object,
            order=section.section_entries.count() + 1
        )
        return response

    def get_success_url(self):
        return reverse_lazy('cv-structure-edit', kwargs={'cv_id': self.kwargs['cv_id']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cv_id'] = self.kwargs['cv_id']
        return context


class EntryUpdateView(UpdateView):
    model = None  # Dynamic
    template_name = 'entry_form.html'

    def get_object(self, queryset=None):
        return SectionEntry.objects.get(id=self.kwargs['entry_id']).content_object

    def get_form_class(self):
        entry = self.get_object()
        return {
            'EducationEntry': EducationEntryForm,
            'ExperienceEntry': ExperienceEntryForm,
            'PublicationEntry': PublicationEntryForm
        }[entry.__class__.__name__]

    def get_success_url(self):
        return reverse_lazy('cv-structure-edit', kwargs={'cv_id': self.kwargs['cv_id']})


class EntryDeleteView(DeleteView):
    model = SectionEntry
    template_name = 'entry_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('cv-structure-edit', kwargs={'cv_id': self.kwargs['cv_id']})


# views.py
from django.http import JsonResponse
import json
from django.http import JsonResponse
from django.views import View
from .models import CVInfoSection

class UpdateSectionOrderView(View):
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        for item in data['sections']:
            CVInfoSection.objects.filter(
                section_id=item['id'],
                cv_info__cv__user=request.user
            ).update(order=item['order'])
        return JsonResponse({'status': 'success'})

    def handle_exception(self, exc):
        # You can handle the exception if necessary
        return JsonResponse({'status': 'error'}, status=400)

import json
from django.http import JsonResponse
from django.views import View
from .models import SectionEntry

class UpdateEntryOrderView(View):
    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        for item in data['entries']:
            SectionEntry.objects.filter(
                id=item['id'],
                section__user=request.user
            ).update(order=item['order'])
        return JsonResponse({'status': 'success'})

    def handle_exception(self, exc):
        # Handle the exception if necessary
        return JsonResponse({'status': 'error'}, status=400)


# views.py
class SectionUpdateView(UpdateView):
    model = Section
    template_name = 'section_form.html'
    fields = ['title', 'alias']

    def get_success_url(self):
        return reverse_lazy('cv-structure-edit', kwargs={'cv_id': self.kwargs['cv_id']})


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from .models import CV, Section

from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import CV


class EditCVStructureView(LoginRequiredMixin, DetailView):
    model = CV
    template_name = 'edit_cv_structure.html'
    context_object_name = 'cv'
    cv_id_url_kwarg = 'cv_id'  # This allows the URL to pass 'cv_id' for the object.

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cv = self.get_object()  # Get the CV object
        sections = cv.info.sections.all()  # Fetch sections for the CV (could be ordered if necessary)

        # Debugging: Check if the CV object and sections are fetched properly
        if not cv:
            print(f"CV with ID {self.kwargs.get(self.cv_id_url_kwarg)} not found.")
        if not sections:
            print(f"No sections found for CV ID {self.kwargs.get(self.cv_id_url_kwarg)}.")

        context['sections'] = sections
        return context

    def get_object(self, queryset=None):
        # Ensure that the CV is fetched for the current user
        try:
            return get_object_or_404(CV, id=self.kwargs[self.cv_id_url_kwarg], user=self.request.user)
        except Http404:
            # Add debugging: Print which cv_id is being requested
            print(f"CV with ID {self.kwargs.get(self.cv_id_url_kwarg)} was not found for this user.")
            raise

    def get_success_url(self):
        # Redirect after success (if applicable, like after a form save)
        return reverse_lazy('cv-edit', kwargs={'cv_id': self.object.id})

    def post(self, request, *args, **kwargs):
        # Handle POST requests (e.g., updating section order or content)
        cv = self.get_object()
        # Logic to handle section editing or saving goes here
        # After processing the form or data, redirect to success URL
        return redirect(self.get_success_url())


from django.shortcuts import get_object_or_404, redirect
from django.views import View
from .models import Section

class SectionDeleteView(View):
    def post(self, request, cv_id):
        section = get_object_or_404(Section, cv_id=cv_id)
        section.delete()
        return redirect('cv-structure-edit', cv_id=cv_id)
