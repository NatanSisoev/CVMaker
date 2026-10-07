import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView, UpdateView

from .forms import (
    BulletEntryForm,
    EducationEntryForm,
    ExperienceEntryForm,
    NormalEntryForm,
    NumberedEntryForm,
    OneLineEntryForm,
    PublicationEntryForm,
    ReversedNumberedEntryForm,
    TextEntryForm,
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
    template_name = "entries/form.html"

    def get(self, request):
        entry_type = request.GET.get("entry_type")

        if not entry_type:  # Step 1: Select Entry Type
            return render(request, self.template_name, {"step": 1, "entry_types": ENTRY_TYPES})

        # Step 2: Fill in Entry Details
        form_class = ENTRY_FORMS.get(entry_type)
        if not form_class:
            return redirect(reverse_lazy("entry-create"))  # Redirect if invalid type

        form = form_class()
        return render(
            request, self.template_name, {"step": 2, "form": form, "entry_type": entry_type}
        )

    def post(self, request):
        entry_type = request.POST.get("entry_type")
        form_class = ENTRY_FORMS.get(entry_type)

        if not form_class:
            return redirect(reverse_lazy("entry-create"))  # Redirect if invalid type

        form = form_class(request.POST)

        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            return redirect(reverse_lazy("entry-create"))  # Redirect to create another entry

        return render(
            request, self.template_name, {"step": 2, "form": form, "entry_type": entry_type}
        )


################################################## LIST ################################################################


class EntryListView(EntryBaseView, ListView):
    template_name = "entries/list.html"
    context_object_name = "entries"

    def get_queryset(self):
        return BaseEntry.objects.filter(user=self.request.user).select_subclasses()


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


################################################# DELETE ###############################################################


class EntryDeleteView(EntryBaseView, DeleteView):
    def get_success_url(self):
        return reverse_lazy("entry-list")
