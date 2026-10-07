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


class _SectionOrderMixin:
    """Save a CV and rewrite its CVSection rows from the posted `section_order`.

    The `sections` M2M uses an explicit through table with a required `order`,
    so we save with commit=False (skipping `save_m2m`) and write the rows by hand.
    """

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["sections"].queryset = Section.objects.filter(user=self.request.user)
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        self.object = form.save(commit=False)
        self.object.save()

        raw = self.request.POST.get("section_order", "")
        ordered = [uuid.UUID(part) for part in raw.split(",") if part]
        owned = set(
            Section.objects.filter(user=self.request.user, id__in=ordered).values_list(
                "id", flat=True
            )
        )
        self.object.sections.clear()
        CVSection.objects.bulk_create(
            CVSection(cv=self.object, section_id=section_id, order=order)
            for order, section_id in enumerate((i for i in ordered if i in owned), 1)
        )
        return redirect("cv-detail", cv_id=self.object.id)


class CVCreateView(LoginRequiredMixin, _SectionOrderMixin, CreateView):
    model = CV
    form_class = CVForm
    template_name = "cv/form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


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


class CVUpdateView(LoginRequiredMixin, _SectionOrderMixin, UpdateView):
    """Edit a CV's own fields (alias, info/locale/settings/design, section order).

    Entry content is edited on the entries pages; the split-pane Editor screen
    (Phase 4.3) will bring both onto one page.
    """

    model = CV
    template_name = "cv/form.html"
    form_class = CVForm

    def get_object(self, queryset=None):
        return get_object_or_404(CV, id=self.kwargs["cv_id"], user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


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
