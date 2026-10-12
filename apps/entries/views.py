import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from cv.models import CV
from sections.models import Section
from sections.services import append_entry_to_section, section_entry_kind

from .forms import (
    LANGUAGE_CODE_RE,
    BulletEntryForm,
    EducationEntryForm,
    ExperienceEntryForm,
    NormalEntryForm,
    NumberedEntryForm,
    OneLineEntryForm,
    PublicationEntryForm,
    ReversedNumberedEntryForm,
    TextEntryForm,
    TranslationForm,
)
from .models import *

########################################################################################################################
################################################ ENTRIES ###############################################################
########################################################################################################################

ENTRY_FORMS = {
    "education": EducationEntryForm,
    "experience": ExperienceEntryForm,
    "publication": PublicationEntryForm,
    "normal": NormalEntryForm,
    "one-line": OneLineEntryForm,
    "bullet": BulletEntryForm,
    "numbered": NumberedEntryForm,
    "reversed-numbered": ReversedNumberedEntryForm,
    "text": TextEntryForm,
}

ENTRY_TYPES = ENTRY_FORMS.keys()


class EntryBaseView(LoginRequiredMixin):
    model = BaseEntry

    def get_object(self, queryset=None):
        entry = get_object_or_404(
            BaseEntry.objects.select_subclasses(),
            id=self.kwargs["entry_id"],
            user=self.request.user,
        )
        return entry


################################################# CREATE ###############################################################


class EntryCreateView(EntryBaseView, View):
    """Create an entry in two steps (pick a kind, fill the form).

    With ``?section=<id>&cv=<id>`` (from the Editor) the entry is appended to
    that section and you return to the Editor. A section that already holds
    entries fixes the kind, because rendercv allows one kind per section.
    """

    template_name = "entries/form.html"

    def _owned(self, model, key):
        raw = self.request.GET.get(key, "")
        try:
            return model.objects.filter(user=self.request.user, pk=raw).first() if raw else None
        except (ValueError, ValidationError):  # not a UUID
            return None

    def _context(self):
        section = self._owned(Section, "section")
        cv = self._owned(CV, "cv")
        return {
            "target_section": section,
            "from_cv": cv,
            "locked_type": section_entry_kind(section) if section else None,
        }

    def _back(self):
        """Where to go after saving (or abandoning) an add-to-section flow."""
        ctx = self._context()
        if ctx["from_cv"]:
            return reverse("cv-editor", args=[ctx["from_cv"].id])
        if ctx["target_section"]:
            return reverse("section-detail", args=[ctx["target_section"].id])
        return reverse("entry-create")

    def get(self, request):
        ctx = self._context()
        entry_type = request.GET.get("entry_type") or ctx["locked_type"]

        if not entry_type:  # Step 1: Select Entry Type
            return render(
                request, self.template_name, {"step": 1, "entry_types": ENTRY_TYPES, **ctx}
            )

        # Step 2: Fill in Entry Details
        form_class = ENTRY_FORMS.get(entry_type)
        if not form_class:
            return redirect(request.get_full_path().split("?")[0])  # invalid type

        return render(
            request,
            self.template_name,
            {"step": 2, "form": form_class(), "entry_type": entry_type, **ctx},
        )

    def post(self, request):
        ctx = self._context()
        entry_type = request.POST.get("entry_type")
        form_class = ENTRY_FORMS.get(entry_type)

        if not form_class:
            return redirect(request.get_full_path().split("?")[0])  # invalid type

        section = ctx["target_section"]
        if ctx["locked_type"] and ctx["locked_type"] != entry_type:
            messages.error(
                request,
                f"Section {section.title} holds {ctx['locked_type']} entries; "
                f"a {entry_type} entry can't go in it.",
            )
            return redirect(self._back())

        form = form_class(request.POST)

        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            if section:
                append_entry_to_section(section, entry)
                messages.success(request, f"Added {entry.alias} to {section.title}.")
                return redirect(self._back())
            messages.success(request, f"Saved {entry.alias}. Add another, or open Sections.")
            return redirect(reverse_lazy("entry-create"))  # Redirect to create another entry

        return render(
            request,
            self.template_name,
            {"step": 2, "form": form, "entry_type": entry_type, **ctx},
        )


################################################## LIST ################################################################


class EntryListView(EntryBaseView, ListView):
    template_name = "entries/list.html"
    context_object_name = "entries"

    def get_queryset(self):
        return (
            BaseEntry.objects.filter(user=self.request.user)
            .select_subclasses()
            .annotate(uses=Count("section_entries", distinct=True))
        )


################################################## VIEW ################################################################


class EntryDetailView(EntryBaseView, DetailView):
    template_name = "entries/detail.html"
    context_object_name = "entry"


################################################## EDIT ################################################################


class EntryUpdateView(EntryBaseView, UpdateView):
    template_name = "entries/update.html"

    def get_form_class(self):
        entry = self.get_object()
        return ENTRY_FORMS[entry.type]

    def get_success_url(self):
        return reverse_lazy("entry-detail", kwargs={"entry_id": self.kwargs["entry_id"]})

    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        entry = self.get_object()  # Retrieve the entry object
        context["entry"] = entry  # Add the entry object to context
        context["entry_type"] = entry.__class__.__name__  # Set entry type
        return context


class EntryInlineEditView(EntryBaseView, View):
    """HTMX fragment: the entry's form, edited in place inside the Editor.

    GET returns the form; POST saves it. Invalid input re-renders the form with
    errors at 200 (HTMX doesn't swap 4xx bodies by default). A successful save
    re-renders the form and fires a toast via the ``HX-Trigger`` header.
    """

    template_name = "entries/_inline_form.html"

    def _render(self, request, entry, form, saved=False):
        response = render(request, self.template_name, {"entry": entry, "form": form})
        if saved:
            response["HX-Trigger"] = json.dumps(
                {"toast": {"message": f"Saved {entry.alias}.", "variant": "success"}}
            )
        return response

    def get(self, request, entry_id):
        entry = self.get_object()
        return self._render(request, entry, ENTRY_FORMS[entry.type](instance=entry))

    def post(self, request, entry_id):
        entry = self.get_object()
        form = ENTRY_FORMS[entry.type](request.POST, instance=entry)
        if not form.is_valid():
            return self._render(request, entry, form)
        entry = form.save()
        return self._render(request, entry, ENTRY_FORMS[entry.type](instance=entry), saved=True)


class EntryTranslateView(EntryBaseView, View):
    """HTMX fragment: edit one language's translation beside the canonical text.

    ``?lang=xx`` on GET, ``lang`` in the body on POST. The canonical language
    and malformed codes get an inline message rather than a 4xx, so the
    fragment always swaps.
    """

    template_name = "entries/_translate_form.html"

    def _language(self, raw, entry):
        code = (raw or "").strip().lower()
        if not LANGUAGE_CODE_RE.match(code):
            return code, "Use a 2-letter ISO 639-1 code, e.g. es or fr."
        if code == entry.canonical_language:
            return code, f"{code.upper()} is the original language of this entry; edit it above."
        return code, None

    def _render(self, request, entry, code, form=None, error=None, saved=False):
        response = render(
            request,
            self.template_name,
            {"entry": entry, "language": code, "form": form, "error": error},
        )
        if saved:
            response["HX-Trigger"] = json.dumps(
                {"toast": {"message": f"Saved {code.upper()} translation.", "variant": "success"}}
            )
        return response

    def get(self, request, entry_id):
        entry = self.get_object()
        code, error = self._language(request.GET.get("lang"), entry)
        form = None if error else TranslationForm(entry, code)
        return self._render(request, entry, code, form, error)

    def post(self, request, entry_id):
        entry = self.get_object()
        code, error = self._language(request.POST.get("lang"), entry)
        if error:
            return self._render(request, entry, code, error=error)
        form = TranslationForm(entry, code, request.POST)
        if not form.is_valid():
            return self._render(request, entry, code, form)
        entry = form.save()
        return self._render(request, entry, code, TranslationForm(entry, code), saved=True)


################################################# DELETE ###############################################################


class EntryDeleteView(EntryBaseView, DeleteView):
    def get_success_url(self):
        return reverse_lazy("entry-list")
