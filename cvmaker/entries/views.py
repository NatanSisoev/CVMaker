from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, DeleteView

from .forms import (
    EducationEntryForm, ExperienceEntryForm, PublicationEntryForm,
    NormalEntryForm, OneLineEntryForm, BulletEntryForm,
    NumberedEntryForm, ReversedNumberedEntryForm, TextEntryForm
)
from .models import *


########################################################################################################################
################################################ ENTRIES ###############################################################
########################################################################################################################

ENTRY_FORMS = {
    'education': EducationEntryForm,
    'experience': ExperienceEntryForm,
    'publication': PublicationEntryForm,
    'normal': NormalEntryForm,
    'one_line': OneLineEntryForm,
    'bullet': BulletEntryForm,
    'numbered': NumberedEntryForm,
    'reversed_numbered': ReversedNumberedEntryForm,
    'text': TextEntryForm,
}

ENTRY_TYPES = ENTRY_FORMS.keys()

class EntryBaseView(LoginRequiredMixin):
    def get_entry(self):
        entry = get_object_or_404(
            BaseEntry.objects.select_subclasses(),
            id=self.kwargs['entry_id'],
            user=self.request.user
        )
        return entry

################################################# CREATE ###############################################################

class EntryCreateView(View):
    template_name = "entries/form.html"

    def get(self, request):
        entry_type = request.GET.get("entry_type")

        if not entry_type:  # Step 1: Select Entry Type
            return render(request, self.template_name, {"step": 1, "entry_types": ENTRY_FORMS.keys()})

        # Step 2: Fill in Entry Details
        form_class = ENTRY_FORMS.get(entry_type)
        if not form_class:
            return redirect(reverse_lazy("entry-create"))  # Redirect if invalid type

        form = form_class()
        return render(request, self.template_name, {
            "step": 2,
            "form": form,
            "entry_type": entry_type
        })

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

        return render(request, self.template_name, {
            "step": 2,
            "form": form,
            "entry_type": entry_type
        })


################################################## LIST ################################################################


class EntryListView(LoginRequiredMixin, ListView):
    template_name = "entries/list.html"
    context_object_name = "entries"

    def get_queryset(self):
        # Dynamically collect entries from all entry types
        entry_models = [
            EducationEntry, ExperienceEntry, PublicationEntry,
            NormalEntry, OneLineEntry, BulletEntry,
            NumberedEntry, ReversedNumberedEntry, TextEntry
        ]

        # Collect all entries for the current user
        entries = []
        for model in entry_models:
            entries += list(model.objects.filter(user=self.request.user))
        return entries


################################################## VIEW ################################################################


class EntryDetailView(LoginRequiredMixin, DetailView):
    template_name = "entries/detail.html"
    context_object_name = "entry"

    def get_object(self, queryset=None):
        try:
            return BaseEntry.objects.select_subclasses().get(
                id=self.kwargs["entry_id"],
                user=self.request.user
            )
        except BaseEntry.DoesNotExist:
            raise Http404("Entry not found or access denied")


################################################## EDIT ################################################################

class EntryUpdateView(LoginRequiredMixin, UpdateView):
    template_name = "entries/update.html"

    def get_object(self, queryset=None):
        """Retrieve the entry instance and ensure the user owns it."""
        # Get the entry ID from the URL
        entry_id = self.kwargs["entry_id"]

        # Attempt to find the entry in one of the concrete models (subclasses of BaseEntry)
        for model in [EducationEntry, ExperienceEntry, PublicationEntry, NormalEntry,
                      OneLineEntry, BulletEntry, NumberedEntry, ReversedNumberedEntry, TextEntry]:
            entry = model.objects.filter(id=entry_id).first()
            if entry:
                # If the entry exists in this model, check if the user owns it
                if entry.user != self.request.user:
                    raise Http404("You do not have permission to edit this entry.")
                return entry

        # If no entry is found in any of the models, raise a 404 error
        raise Http404("Entry not found.")

    def get_form_class(self):
        """Return the correct form class based on the entry type."""
        entry = self.get_object()  # Retrieve the entry object
        form_mapping = {
            EducationEntry: EducationEntryForm,
            ExperienceEntry: ExperienceEntryForm,
            PublicationEntry: PublicationEntryForm,
            NormalEntry: NormalEntryForm,
            BulletEntry: BulletEntryForm,
            NumberedEntry: NumberedEntryForm,
            ReversedNumberedEntry: ReversedNumberedEntryForm,
            TextEntry: TextEntryForm,
            OneLineEntry: OneLineEntryForm,
        }

        # Dynamically return the appropriate form class based on entry type
        return form_mapping.get(type(entry), NormalEntryForm)

    def get_success_url(self):
        """Redirect to the entry detail page upon successful update."""
        return reverse_lazy("entry-detail", kwargs={"entry_id": self.kwargs["entry_id"]})

    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        entry = self.get_object()  # Retrieve the entry object
        context["entry"] = entry  # Add the entry object to context
        context["entry_type"] = entry.__class__.__name__  # Set entry type
        return context


################################################# DELETE ###############################################################

class EntryDeleteView(LoginRequiredMixin, DeleteView):
    model = BaseEntry  # Use BaseEntry as base class for all entry types

    def get_object(self, queryset=None):
        """Retrieve the entry instance and ensure the user owns it."""
        # Get the entry ID from the URL
        entry_id = self.kwargs["entry_id"]

        # Attempt to find the entry in one of the concrete models (subclasses of BaseEntry)
        for model in [EducationEntry, ExperienceEntry, PublicationEntry, NormalEntry,
                      OneLineEntry, BulletEntry, NumberedEntry, ReversedNumberedEntry, TextEntry]:
            entry = model.objects.filter(id=entry_id).first()
            if entry:
                # If the entry exists in this model, check if the user owns it
                if entry.user != self.request.user:
                    raise Http404("You do not have permission to edit this entry.")
                return entry

        # If no entry is found in any of the models, raise a 404 error
        raise Http404("Entry not found.")

    def get_success_url(self):
        # Redirect to the entry list after deletion
        return reverse_lazy("entry-list")

    def delete(self, request, *args, **kwargs):
        # Get the entry object to delete
        entry = self.get_object()
        if entry.user == self.request.user:
            try:
                # Delete the entry
                entry.delete()
            except Exception as e:
                raise Http404(f"Error occurred while deleting: {str(e)}")

            return super().delete(request, *args, **kwargs)
        else:
            raise Http404("You do not have permission to delete this entry.")
