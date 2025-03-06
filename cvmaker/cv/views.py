import datetime
import os

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)
from rendercv import data
from rendercv.renderer import renderer

from cvmaker import settings
from .models import CV


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
    template_name = 'cv_detail.html'
    context_object_name = 'cv'

    def get_object(self, queryset=None):
        # Ensure the user can only access their own CV
        return get_object_or_404(CV, pk=self.kwargs['cv_id'], user=self.request.user)


################################################### EDIT ###############################################################

class CVUpdateView(LoginRequiredMixin, UpdateView):
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
