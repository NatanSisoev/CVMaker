import os
import uuid

import yaml
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from entries.forms import EducationEntryForm, ExperienceEntryForm, PublicationEntryForm
from entries.models import EducationEntry, ExperienceEntry, PublicationEntry
from sections.models import CVSection, Section
from sections.services import import_sections_from_data_model

from .forms import CVDesignForm, CVForm, CVInfoForm, CVLocaleForm, CVSettingsForm
from .models import CV, CVDesign, CVInfo, CVLocale, CVSettings

################################################## HOME ################################################################


class HomePageView(View):
    template_name = "homepage.html"

    def get(self, request, *args, **kwargs):
        context = {}

        if request.user.is_authenticated:
            cv_list = CV.objects.filter(user=request.user)
            context["cv_list"] = cv_list

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
    form_class = CVForm
    template_name = "cv/form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["sections"].queryset = Section.objects.filter(user=self.request.user)
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        self.object = form.save(commit=False)
        self.object.save()

        # Clear existing M2M relations (if update; for create it's safe too)
        self.object.sections.clear()

        # Add sections with order in the through model
        section_ids = self.request.POST.get("section_order", "")
        section_ids = [uuid.UUID(id_str) for id_str in section_ids.split(",") if id_str]
        sections = Section.objects.filter(id__in=section_ids)
        self.object.sections.clear()

        for order, section in enumerate(section_ids, 1):
            CVSection.objects.create(cv=self.object, section_id=section, order=order)

        return redirect("cv-detail", cv_id=self.object.id)


################################################# UPLOAD ###############################################################


class CVUploadView(LoginRequiredMixin, View):
    """Handle YAML file uploads and convert them to CV instances"""

    # TODO: finish

    def post(self, request, *args, **kwargs):
        if "yaml_file" not in request.FILES:
            return redirect("cv-list")

        yaml_file = request.FILES["yaml_file"]
        yaml_data = yaml.safe_load(yaml_file.read().decode("utf-8"))

        # Use the rendercv function to validate and parse the YAML
        data_model = data.validate_input_dictionary_and_return_the_data_model(yaml_data)

        # Create CV from data model
        cv = self.create_cv_from_data(request.user, data_model, yaml_file)

        return redirect("cv-detail", cv_id=cv.id)

    def create_cv_from_data(self, user, data_model, file):
        """
        Create a CV and all related objects from a RenderCVDataModel instance.

        Args:
            user: The user who owns the CV
            data_model: An instance of RenderCVDataModel containing parsed YAML data
            file: The uploaded file object

        Returns:
            CV: The created CV instance
        """
        filename = "uploaded"  # you might derive this from the file if needed

        # Create main CV pieces using their custom managers
        # Each manager extracts what it needs from the data_model
        cv_info = CVInfo.objects.create_from_data_model(user, data_model, alias=filename)
        # cv_design = CVDesign.objects.create_from_data_model(user, data_model, file, alias=filename)
        cv_design = CVDesign.objects.all()[0]
        cv_locale = CVLocale.objects.create_from_data_model(user, data_model, alias=filename)
        cv_settings = CVSettings.objects.create_from_data_model(user, data_model, alias=filename)

        # Create the main CV object
        cv = CV.objects.create(
            user=user,
            alias=filename,
            design=cv_design,
            locale=cv_locale,
            info=cv_info,
            settings=cv_settings,
        )

        # Process sections via the import service.
        import_sections_from_data_model(user=user, cv=cv, data_model=data_model, alias=filename)

        return cv


################################################### VIEW ###############################################################


class CVDetailView(DetailView):
    model = CV
    template_name = "cv/detail.html"
    context_object_name = "cv"

    def get_object(self, queryset=None):
        return get_object_or_404(CV, pk=self.kwargs["cv_id"], user=self.request.user)


################################################### EDIT ###############################################################


class CVUpdateView(LoginRequiredMixin, UpdateView):
    model = CV
    template_name = "cv/form.html"
    form_class = CVForm

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse_lazy("cv-detail", kwargs={"cv_id": self.object.id})

    def get_object(self, queryset=None):
        return get_object_or_404(CV, id=self.kwargs["cv_id"], user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cv = self.get_object()
        cv_info, created = CVInfo.objects.get_or_create(cv=cv)

        if self.request.POST:
            context["cv_info_form"] = CVInfoForm(
                self.request.POST, self.request.FILES, instance=cv_info
            )
        else:
            context["cv_info_form"] = CVInfoForm(instance=cv_info)

        # Phase 2.1 (ADR-0005): SectionEntry.entry is now a real FK to
        # BaseEntry. Promote to the concrete subclass via select_subclasses
        # so the isinstance dispatch + ModelForm binding still works.
        # Phase 2.3 lifts this branchy dispatch into a service that maps
        # subclass -> form_class, dropping the if/elif tower entirely.
        from entries.models import BaseEntry  # local import to avoid cv→entries cycle

        education_forms = {}
        experience_forms = {}
        publication_forms = {}

        for section in cv.sections.all():
            section_entries = list(section.section_entries.all())
            entry_ids = [se.entry_id for se in section_entries]
            promoted = {
                e.pk: e for e in BaseEntry.objects.filter(pk__in=entry_ids).select_subclasses()
            }

            for section_entry in section_entries:
                real_entry = promoted.get(section_entry.entry_id)
                if isinstance(real_entry, EducationEntry):
                    if self.request.POST:
                        education_forms[section_entry.id] = EducationEntryForm(
                            self.request.POST, instance=real_entry
                        )
                    else:
                        education_forms[section_entry.id] = EducationEntryForm(instance=real_entry)
                elif isinstance(real_entry, ExperienceEntry):
                    if self.request.POST:
                        experience_forms[section_entry.id] = ExperienceEntryForm(
                            self.request.POST, instance=real_entry
                        )
                    else:
                        experience_forms[section_entry.id] = ExperienceEntryForm(
                            instance=real_entry
                        )
                elif isinstance(real_entry, PublicationEntry):
                    if self.request.POST:
                        publication_forms[section_entry.id] = PublicationEntryForm(
                            self.request.POST, instance=real_entry
                        )
                    else:
                        publication_forms[section_entry.id] = PublicationEntryForm(
                            instance=real_entry
                        )

        context["education_forms"] = education_forms
        context["experience_forms"] = experience_forms
        context["publication_forms"] = publication_forms

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        # Bind related forms manually
        cv_info, _ = CVInfo.objects.get_or_create(cv=self.object)
        cv_info_form = CVInfoForm(self.request.POST, self.request.FILES, instance=cv_info)

        # Bind other forms similarly if needed...

        if form.is_valid() and cv_info_form.is_valid():
            # Also validate other related forms if needed here

            return self.forms_valid(form, cv_info_form)
        else:
            return self.forms_invalid(form, cv_info_form)

    def forms_valid(self, form, cv_info_form):
        self.object = form.save()

        # TODO: CVInfo gets deleted on cv edit

        # Save related forms after main form saved
        cv_info_form.save()

        # Save sections (your logic)
        self.object.sections.clear()
        section_ids = self.request.POST.get("section_order", "")
        section_ids = [uuid.UUID(id_str) for id_str in section_ids.split(",") if id_str]
        for order, section_id in enumerate(section_ids, 1):
            CVSection.objects.create(cv=self.object, section_id=section_id, order=order)

        # Save other related forms here if any

        return redirect(self.get_success_url())

    def forms_invalid(self, form, cv_info_form):
        context = self.get_context_data(form=form)
        context["cv_info_form"] = cv_info_form
        # Add other forms to context too
        return self.render_to_response(context)

    def form_valid(self, form):
        response = super().form_valid(form)

        # Clear existing CVSection relations
        self.object.sections.clear()

        # Add selected sections back with new order
        section_ids = self.request.POST.get("section_order", "")
        section_ids = [uuid.UUID(id_str) for id_str in section_ids.split(",") if id_str]
        sections = Section.objects.filter(id__in=section_ids)
        self.object.sections.clear()

        for order, section in enumerate(section_ids, 1):
            CVSection.objects.create(cv=self.object, section_id=section, order=order)

        # Handle CVInfo and entry forms
        context = self.get_context_data()
        cv_info_form = context["cv_info_form"]
        education_forms = context["education_forms"]
        experience_forms = context["experience_forms"]
        publication_forms = context["publication_forms"]

        if cv_info_form.is_valid():
            cv_info_form.save()

        for form_dict in [education_forms, experience_forms, publication_forms]:
            for entry_form in form_dict.values():
                if entry_form.is_valid():
                    entry_form.save()

        return response


################################################# DELETE ###############################################################


class CVDeleteView(DeleteView):
    model = CV

    def get_object(self, queryset=None):
        return get_object_or_404(CV, id=self.kwargs["cv_id"])

    def get_success_url(self):
        return reverse_lazy("cv-list")


################################################ PREVIEW ###############################################################


def preview_cv(request, cv_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    return render(request, "cv_detail.html", {"cv": cv})


############################################### DOWNLOAD ###############################################################


def download_cv(request, cv_id):
    # TODO: cv.photo location
    cv = CV.objects.get(id=cv_id, user=request.user)
    data_model = data.validate_input_dictionary_and_return_the_data_model(cv.serialize())

    render_command_settings: data.models.RenderCommandSettings = (
        data_model.rendercv_settings.render_command
    )
    if not render_command_settings or not render_command_settings.output_folder_name:
        return HttpResponse("Invalid render command settings", status=400)

    output_directory = settings.MEDIA_ROOT / render_command_settings.output_folder_name

    typst_file_path_in_output_folder = renderer.create_a_typst_file_and_copy_theme_files(
        data_model, output_directory
    )
    pdf_file_path_in_output_folder = renderer.render_a_pdf_from_typst(
        typst_file_path_in_output_folder
    )

    if os.path.exists(pdf_file_path_in_output_folder):
        return FileResponse(
            open(pdf_file_path_in_output_folder, "rb"), content_type="application/pdf"
        )
    else:
        return HttpResponse("File not found", status=404)


################################################ MODULES ###############################################################


class UserIsOwnerMixin(UserPassesTestMixin):
    def test_func(self):
        obj = self.get_object()
        return obj.user == self.request.user


# Helper Mixin to assign user & alias automatically
class AssignUserAndAliasMixin:
    def form_valid(self, form):
        form.instance.user = self.request.user
        if not form.instance.alias:
            form.instance.alias = "default"
        return super().form_valid(form)


# CVInfo Views
class CVInfoCreateView(AssignUserAndAliasMixin, CreateView):
    model = CVInfo
    form_class = CVInfoForm
    template_name = "cv/cvinfo_form.html"
    pk_url_kwarg = "info_id"

    def get_success_url(self):
        return reverse_lazy("cvinfo-list")


class CVInfoUpdateView(AssignUserAndAliasMixin, UpdateView):
    model = CVInfo
    form_class = CVInfoForm
    template_name = "cv/cvinfo_form.html"
    pk_url_kwarg = "info_id"

    def get_success_url(self):
        return reverse_lazy("cvinfo-list")


class CVInfoListView(LoginRequiredMixin, ListView):
    model = CVInfo
    template_name = "cv/cvinfo_list.html"  # your list template
    context_object_name = "cvinfos"
    pk_url_kwarg = "info_id"

    def get_queryset(self):
        return CVInfo.objects.filter(user=self.request.user)


class CVInfoDetailView(LoginRequiredMixin, UserIsOwnerMixin, DetailView):
    model = CVInfo
    template_name = "cv/cvinfo_detail.html"
    context_object_name = "cvinfo"
    pk_url_kwarg = "info_id"


class CVInfoDeleteView(LoginRequiredMixin, UserIsOwnerMixin, DeleteView):
    model = CVInfo
    template_name = "cv/cvinfo_confirm_delete.html"
    success_url = reverse_lazy("cvinfo-list")
    pk_url_kwarg = "info_id"


# CVDesign Views
class CVDesignCreateView(AssignUserAndAliasMixin, CreateView):
    model = CVDesign
    form_class = CVDesignForm
    template_name = "cv/cvdesign_form.html"
    pk_url_kwarg = "design_id"

    def get_success_url(self):
        return reverse_lazy("cvdesign-list")


class CVDesignUpdateView(AssignUserAndAliasMixin, UpdateView):
    model = CVDesign
    form_class = CVDesignForm
    template_name = "cv/cvdesign_form.html"
    pk_url_kwarg = "design_id"

    def get_success_url(self):
        return reverse_lazy("cvdesign-list")


class CVDesignListView(LoginRequiredMixin, ListView):
    model = CVDesign
    template_name = "cv/cvdesign_list.html"
    context_object_name = "cvdesigns"
    pk_url_kwarg = "design_id"

    def get_queryset(self):
        return CVDesign.objects.filter(user=self.request.user)


class CVDesignDetailView(LoginRequiredMixin, UserIsOwnerMixin, DetailView):
    model = CVDesign
    template_name = "cv/cvdesign_detail.html"
    context_object_name = "cvdesign"
    pk_url_kwarg = "design_id"


class CVDesignDeleteView(LoginRequiredMixin, UserIsOwnerMixin, DeleteView):
    model = CVDesign
    template_name = "cv/cvdesign_confirm_delete.html"
    success_url = reverse_lazy("cvdesign-list")
    pk_url_kwarg = "design_id"


# CVLocale Views
class CVLocaleCreateView(AssignUserAndAliasMixin, CreateView):
    model = CVLocale
    form_class = CVLocaleForm
    template_name = "cv/cvlocale_form.html"
    pk_url_kwarg = "locale_id"

    def get_success_url(self):
        return reverse_lazy("cvlocale-list")


class CVLocaleUpdateView(AssignUserAndAliasMixin, UpdateView):
    model = CVLocale
    form_class = CVLocaleForm
    template_name = "cv/cvlocale_form.html"
    pk_url_kwarg = "locale_id"

    def get_success_url(self):
        return reverse_lazy("cvlocale-list")


class CVLocaleListView(LoginRequiredMixin, ListView):
    model = CVLocale
    template_name = "cv/cvlocale_list.html"
    context_object_name = "cvlocales"
    pk_url_kwarg = "locale_id"

    def get_queryset(self):
        return CVLocale.objects.filter(user=self.request.user)


class CVLocaleDetailView(LoginRequiredMixin, UserIsOwnerMixin, DetailView):
    model = CVLocale
    template_name = "cv/cvlocale_detail.html"
    context_object_name = "cvlocale"
    pk_url_kwarg = "locale_id"


class CVLocaleDeleteView(LoginRequiredMixin, UserIsOwnerMixin, DeleteView):
    model = CVLocale
    template_name = "cv/cvlocale_confirm_delete.html"
    success_url = reverse_lazy("cvlocale-list")
    pk_url_kwarg = "locale_id"


# CVSettings Views
class CVSettingsCreateView(AssignUserAndAliasMixin, CreateView):
    model = CVSettings
    form_class = CVSettingsForm
    template_name = "cv/cvsettings_form.html"
    pk_url_kwarg = "settings_id"

    def get_success_url(self):
        return reverse_lazy("cvsettings-list")


class CVSettingsUpdateView(AssignUserAndAliasMixin, UpdateView):
    model = CVSettings
    form_class = CVSettingsForm
    template_name = "cv/cvsettings_form.html"
    pk_url_kwarg = "settings_id"

    def get_success_url(self):
        return reverse_lazy("cvsettings-list")


class CVSettingsListView(LoginRequiredMixin, ListView):
    model = CVSettings
    template_name = "cv/cvsettings_list.html"
    context_object_name = "cvsettings"
    pk_url_kwarg = "settings_id"

    def get_queryset(self):
        return CVSettings.objects.filter(user=self.request.user)


class CVSettingsDetailView(LoginRequiredMixin, UserIsOwnerMixin, DetailView):
    model = CVSettings
    template_name = "cv/cvsettings_detail.html"
    context_object_name = "cvsettings"
    pk_url_kwarg = "settings_id"


class CVSettingsDeleteView(LoginRequiredMixin, UserIsOwnerMixin, DeleteView):
    model = CVSettings
    template_name = "cv/cvsettings_confirm_delete.html"
    success_url = reverse_lazy("cvsettings-list")
    pk_url_kwarg = "settings_id"


# --- rendercv 2.x stopgap (Phase 1, see scripts/fix_rendercv_imports.py) ---
# rendercv 2.x removed the ``data`` module and reorganized ``renderer``.
# The views in this file were written against the 1.x private-ish API and
# will be rewritten in Phase 3 when PDF rendering is wired up for real.
# Until then, keep the module importable so makemigrations / reverse() work,
# and fail loudly if anyone actually tries to render a CV.
class _RendercvUnavailable:
    def __init__(self, what):
        self._what = what

    def _boom(self):
        raise NotImplementedError(
            "rendercv." + self._what + " is not wired up yet. "
            "PDF rendering is deferred to Phase 3 -- see ROADMAP.md."
        )

    def __getattr__(self, name):
        self._boom()

    def __call__(self, *args, **kwargs):
        self._boom()


data = _RendercvUnavailable("data")
renderer = _RendercvUnavailable("renderer")
# --- end rendercv 2.x stopgap ---
