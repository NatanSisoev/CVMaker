import json
import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from sections.models import CVSection, Section

from .forms import (
    CVDesignForm,
    CVForm,
    CVInfoForm,
    CVInfoQuickForm,
    CVLocaleForm,
    CVSettingsForm,
    QuickCVForm,
)
from .importer import CVImportError, import_cv_from_yaml
from .models import CV, CVDesign, CVInfo, CVLocale, CVSettings
from .services import clone_cv, create_starter_cv, language_status

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
    """Import a rendercv YAML file as a new CV, then open it in the editor.

    Problems (bad YAML, rendercv validation errors, values our columns can't
    hold) come back as an error toast on the dashboard; nothing is saved.
    """

    MAX_BYTES = 512 * 1024

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get("yaml_file")
        if upload is None:
            messages.error(request, "Choose a rendercv YAML file to import.")
            return redirect("cv-list")
        if upload.size > self.MAX_BYTES:
            messages.error(request, "That file is too large to be a CV (512 KB max).")
            return redirect("cv-list")
        try:
            text = upload.read().decode("utf-8")
        except UnicodeDecodeError:
            messages.error(request, "That file isn't UTF-8 text. Export it as YAML and retry.")
            return redirect("cv-list")

        alias = upload.name.rsplit(".", 1)[0]
        try:
            cv = import_cv_from_yaml(request.user, text, alias)
        except CVImportError as exc:
            messages.error(request, str(exc))
            return redirect("cv-list")

        messages.success(request, f"Imported {cv.alias}.")
        return redirect("cv-editor", cv_id=cv.id)


################################################### VIEW ###############################################################


class CVDetailView(LoginRequiredMixin, DetailView):
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


class CVQuickCreateView(LoginRequiredMixin, View):
    """Start a CV by naming it, then land in the Editor."""

    template_name = "cv/new.html"

    def get(self, request):
        initial = {"style": request.GET.get("style", "classic")}
        return render(request, self.template_name, {"form": QuickCVForm(initial=initial)})

    def post(self, request):
        form = QuickCVForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        cv = create_starter_cv(
            request.user, form.cleaned_data["alias"], form.cleaned_data["style"] or "classic"
        )
        messages.success(
            request, f"Created {cv.alias}. Fill in your details, then add your first section."
        )
        return redirect("cv-editor", cv_id=cv.id)


class CVInfoInlineView(LoginRequiredMixin, View):
    """HTMX fragment: the CV's personal details, edited inside the Editor.

    Creates the record (and attaches it) if the CV has none. A save re-renders
    the form, fires a toast, and refreshes the summary line out of band.
    """

    template_name = "cv/_info_inline.html"

    def _cv(self, request, cv_id):
        return get_object_or_404(CV.objects.select_related("info"), pk=cv_id, user=request.user)

    def _render(self, request, cv, form, saved=False):
        response = render(request, self.template_name, {"cv": cv, "form": form, "saved": saved})
        if saved:
            response["HX-Trigger"] = json.dumps(
                {"toast": {"message": "Personal details saved.", "variant": "success"}}
            )
        return response

    def get(self, request, cv_id):
        cv = self._cv(request, cv_id)
        return self._render(request, cv, CVInfoQuickForm(instance=cv.info))

    def post(self, request, cv_id):
        cv = self._cv(request, cv_id)
        form = CVInfoQuickForm(request.POST, instance=cv.info)
        if not form.is_valid():
            return self._render(request, cv, form)
        info = form.save(commit=False)
        info.user = request.user
        if cv.info_id is None:  # a brand-new record: name it after the CV
            info.alias = cv.alias
        info.save()
        if cv.info_id != info.id:
            cv.info = info
            cv.save(update_fields=["info"])
        return self._render(request, cv, CVInfoQuickForm(instance=info), saved=True)


class CVDuplicateView(LoginRequiredMixin, View):
    """POST: copy a CV (own details/design, shared sections) and open the copy."""

    def post(self, request, cv_id):
        cv = get_object_or_404(CV, pk=cv_id, user=request.user)
        suffix = " copy"
        copy = clone_cv(cv, f"{cv.alias[: 20 - len(suffix)]}{suffix}")
        messages.success(request, f"Duplicated {cv.alias}. Edit the copy freely.")
        return redirect("cv-editor", cv_id=copy.id)


class CVEditorView(LoginRequiredMixin, DetailView):
    """Split-pane editor: outline on the left, live PDF preview on the right."""

    model = CV
    template_name = "cv/editor.html"
    context_object_name = "cv"

    def get_object(self, queryset=None):
        return get_object_or_404(
            CV.objects.select_related("info", "locale", "design"),
            pk=self.kwargs["cv_id"],
            user=self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cv = self.object
        context["language_status"] = language_status(cv)
        context["needs_info"] = not (cv.info_id and cv.info.name)
        # ?render=1 (dashboard "Render PDF"): start rendering as soon as the page loads.
        context["autorender"] = self.request.GET.get("render") == "1"
        context["styles"] = [c for c in CVDesign.THEME_CHOICES if c[0] != "custom"]
        context["current_style"] = cv.design.theme if cv.design_id else "classic"
        context["sections"] = cv.sections.prefetch_related("section_entries__entry").order_by(
            "cvsection__order"
        )
        return context


################################################# DELETE ###############################################################


class CVDeleteView(LoginRequiredMixin, DeleteView):
    model = CV

    def get_object(self, queryset=None):
        return get_object_or_404(CV, id=self.kwargs["cv_id"], user=self.request.user)

    def get_success_url(self):
        return reverse_lazy("cv-list")


################################################ MODULES ###############################################################


class UserIsOwnerMixin(UserPassesTestMixin):
    def test_func(self):
        obj = self.get_object()
        return obj.user == self.request.user


# Helper Mixin to assign user & alias automatically. Requires login, and
# scopes object lookups to the current user so an update can never reach (and,
# via the user assignment below, take over) someone else's row -- 404 instead.
class AssignUserAndAliasMixin(LoginRequiredMixin):
    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

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
