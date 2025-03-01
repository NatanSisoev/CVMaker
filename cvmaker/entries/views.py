from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy

from cv.models import Section, SectionEntry
from .models import *
from .forms import EducationEntryForm, ExperienceEntryForm, PublicationEntryForm


########################################################################################################################
################################################ ENTRIES ###############################################################
########################################################################################################################

################################################# CREATE ###############################################################

class EntryCreateView(LoginRequiredMixin, CreateView):
    model = None  # Model will be determined dynamically
    template_name = "entry_form.html"

    def get_form_class(self):
        entry_type = self.kwargs.get("entry_type")
        return {
            "education": EducationEntryForm,
            "experience": ExperienceEntryForm,
            "publication": PublicationEntryForm
        }.get(entry_type, EducationEntryForm)  # Default to Education if not found

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        # Add to section
        section = Section.objects.get(id=self.kwargs["section_id"])
        SectionEntry.objects.create(
            section=section,
            content_object=self.object,
            order=section.section_entries.count() + 1
        )
        return response

    def get_success_url(self):
        return reverse_lazy("cv-structure-edit", kwargs={"cv_id": self.kwargs["cv_id"]})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cv_id"] = self.kwargs["cv_id"]
        return context


################################################## LIST ################################################################


class EntryListView(LoginRequiredMixin, ListView):
    template_name = "entries/list.html"
    context_object_name = "entries"

    def get_queryset(self):
        education_entries = list(EducationEntry.objects.filter(user=self.request.user))
        experience_entries = list(ExperienceEntry.objects.filter(user=self.request.user))
        publication_entries = list(PublicationEntry.objects.filter(user=self.request.user))
        normal_entries = list(NormalEntry.objects.filter(user=self.request.user))
        oneline_entries = list(OneLineEntry.objects.filter(user=self.request.user))
        bullet_entries = list(BulletEntry.objects.filter(user=self.request.user))
        numbered_entries = list(NumberedEntry.objects.filter(user=self.request.user))
        reversed_numbered_entries = list(ReversedNumberedEntry.objects.filter(user=self.request.user))
        text_entries = list(TextEntry.objects.filter(user=self.request.user))

        combined_entries = (
            education_entries
            + experience_entries
            + publication_entries
            + normal_entries
            + oneline_entries
            + bullet_entries
            + numbered_entries
            + reversed_numbered_entries
            + text_entries
        )
        return combined_entries


################################################## VIEW ################################################################


class EntryDetailView(LoginRequiredMixin, DetailView):
    model = CVEntry
    template_name = "entry_detail.html"
    context_object_name = "entry"  # Optional: Rename the context variable

    def get_object(self, queryset=None):
        # Retrieve the object based on the entry_id in the URL and the user
        section_entry = SectionEntry.objects.get(id=self.kwargs["entry_id"])
        if section_entry.content_object.user == self.request.user:
            return section_entry.content_object
        else:
            raise Http404

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add additional context if needed
        return context


################################################## EDIT ################################################################


class EntryUpdateView(LoginRequiredMixin, UpdateView):
    model = CVEntry  # Use your base Entry model or a specific model
    template_name = "entry_edit.html"

    def get_object(self, queryset=None):
        # Retrieve the object based on the entry_id in the URL and the user
        section_entry = SectionEntry.objects.get(id=self.kwargs["entry_id"])
        if section_entry.content_object.user == self.request.user:
            return section_entry.content_object
        else:
            raise Http404

    def get_form_class(self):
        entry = self.get_object()
        return {
            "EducationEntry": EducationEntryForm,
            "ExperienceEntry": ExperienceEntryForm,
            "PublicationEntry": PublicationEntryForm
        }[entry.__class__.__name__]

    def get_success_url(self):
        return reverse_lazy("cv-structure-edit", kwargs={"cv_id": self.kwargs["cv_id"]})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cv_id"] = self.kwargs["cv_id"]
        return context


################################################# DELETE ###############################################################


class EntryDeleteView(LoginRequiredMixin, DeleteView):
    model = CVEntry  # Use your base Entry model or a specific model
    template_name = "entry_delete.html"

    def get_object(self, queryset=None):
        # Retrieve the object based on the entry_id in the URL and the user
        section_entry = SectionEntry.objects.get(id=self.kwargs["entry_id"])
        if section_entry.content_object.user == self.request.user:
            return section_entry.content_object
        else:
            raise Http404

    def get_success_url(self):
        return reverse_lazy("cv-structure-edit", kwargs={"cv_id": self.kwargs["cv_id"]})

    def delete(self, request, *args, **kwargs):
        # Delete the SectionEntry and the content_object
        section_entry = SectionEntry.objects.get(id=self.kwargs["entry_id"])
        content_object = section_entry.content_object
        if content_object.user == self.request.user:
            section_entry.delete()
            content_object.delete()
            return super().delete(request, *args, **kwargs)
        else:
            raise Http404