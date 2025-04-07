import os

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)
from rendercv import data
from rendercv.renderer import renderer

from cvmaker import settings
from entries.forms import (EducationEntryForm, ExperienceEntryForm,
                           PublicationEntryForm)
from entries.models import EducationEntry, ExperienceEntry, PublicationEntry

from .forms import CVInfoForm
from .models import CV, CVInfo


################################################## HOME ################################################################

class HomePageView(View):
    template_name = 'homepage.html'

    def get(self, request, *args, **kwargs):
        context = {}

        if request.user.is_authenticated:
            cv_list = CV.objects.filter(user=request.user)
            context['cv_list'] = cv_list

        return render(request, self.template_name, context)


########################################################################################################################
################################################### CV #################################################################
########################################################################################################################


################################################## LIST ################################################################


class CVListView(LoginRequiredMixin, ListView):
    model = CV
    template_name = "cv/list.html"
    context_object_name = "cvs"

    def get_queryset(self):
        return CV.objects.filter(user=self.request.user)


################################################# CREATE ###############################################################


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


################################################### VIEW ###############################################################

class CVDetailView(DetailView):
    model = CV
    template_name = 'cv/detail.html'
    context_object_name = 'cv'

    def get_object(self, queryset=None):
        return get_object_or_404(CV, pk=self.kwargs['cv_id'], user=self.request.user)


################################################### EDIT ###############################################################


class CVUpdateView(LoginRequiredMixin, UpdateView):
    model = CV
    template_name = 'cv/edit.html'
    fields = ['alias', 'design', 'locale']

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_success_url(self):
        return reverse_lazy('cv-detail', kwargs={'cv_id': self.object.id})

    def get_object(self, queryset=None):
        return get_object_or_404(CV, id=self.kwargs["cv_id"], user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cv = self.get_object()
        cv_info, created = CVInfo.objects.get_or_create(cv=cv)

        if self.request.POST:
            context['cv_info_form'] = CVInfoForm(self.request.POST, self.request.FILES, instance=cv_info)
        else:
            context['cv_info_form'] = CVInfoForm(instance=cv_info)

        education_forms = {}
        experience_forms = {}
        publication_forms = {}

        for section in cv.sections.all():
            for section_entry in section.section_entries.all():
                if isinstance(section_entry.content_object, EducationEntry):
                    if self.request.POST:
                        education_forms[section_entry.id] = EducationEntryForm(self.request.POST,
                                                                               instance=section_entry.content_object)
                    else:
                        education_forms[section_entry.id] = EducationEntryForm(instance=section_entry.content_object)
                elif isinstance(section_entry.content_object, ExperienceEntry):
                    if self.request.POST:
                        experience_forms[section_entry.id] = ExperienceEntryForm(self.request.POST,
                                                                                 instance=section_entry.content_object)
                    else:
                        experience_forms[section_entry.id] = ExperienceEntryForm(instance=section_entry.content_object)
                elif isinstance(section_entry.content_object, PublicationEntry):
                    if self.request.POST:
                        publication_forms[section_entry.id] = PublicationEntryForm(self.request.POST,
                                                                                   instance=section_entry.content_object)
                    else:
                        publication_forms[section_entry.id] = PublicationEntryForm(
                            instance=section_entry.content_object)

        context['education_forms'] = education_forms
        context['experience_forms'] = experience_forms
        context['publication_forms'] = publication_forms

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        cv_info_form = context['cv_info_form']
        education_forms = context['education_forms']
        experience_forms = context['experience_forms']
        publication_forms = context['publication_forms']

        if cv_info_form.is_valid():
            cv_info_form.save()

        for form_dict in [education_forms, experience_forms, publication_forms]:
            for form in form_dict.values():
                if form.is_valid():
                    form.save()

        return super().form_valid(form)


################################################# DELETE ###############################################################


class CVDeleteView(DeleteView):
    model = CV
    template_name = 'cv_delete.html'


################################################ PREVIEW ###############################################################

def preview_cv(request, cv_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    return render(request, 'cv_detail.html', {'cv': cv})


############################################### DOWNLOAD ###############################################################

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
