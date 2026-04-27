import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import pre_delete

from entries.models import (
    BaseEntry,
    BulletEntry,
    EducationEntry,
    ExperienceEntry,
    NormalEntry,
    NumberedEntry,
    OneLineEntry,
    PublicationEntry,
    ReversedNumberedEntry,
    TextEntry,
    get_entry_model,
)

# Models whose deletion should cascade to section_entries via the GenericForeignKey.
# (Phase 2 replaces this GFK with a real FK to BaseEntry and removes the signal.)
_ENTRY_MODELS = (
    BaseEntry,
    BulletEntry,
    EducationEntry,
    ExperienceEntry,
    NormalEntry,
    NumberedEntry,
    OneLineEntry,
    PublicationEntry,
    ReversedNumberedEntry,
    TextEntry,
)


def _delete_dangling_section_entries(sender, instance, **kwargs):
    content_type = ContentType.objects.get_for_model(sender)
    SectionEntry.objects.filter(content_type=content_type, object_id=instance.pk).delete()


for _model in _ENTRY_MODELS:
    pre_delete.connect(
        _delete_dangling_section_entries,
        sender=_model,
        dispatch_uid=f"delete_section_entries_for_{_model.__name__}",
    )


class CVSection(models.Model):
    # KEYS
    cv = models.ForeignKey("cv.CV", on_delete=models.CASCADE)
    section = models.ForeignKey("sections.Section", on_delete=models.CASCADE)

    # INFO
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        unique_together = ("cv", "section")


class Section(models.Model):
    # KEYS
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name="cv_sections",
    )
    title = models.CharField(max_length=50, help_text="Name of the section")
    alias = models.CharField(max_length=20, help_text="Alias for the section", default="default")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    def serialize(self) -> list:
        return [
            entry.content_object.serialize() for entry in self.section_entries.order_by("order")
        ]


class SectionEntry(models.Model):
    # KEYS
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="section_entries")

    # INFO
    order = models.PositiveIntegerField()

    # OTHER
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["order"]

    def serialize(self) -> dict:
        return self.content_object.serialize()


class SectionManager:
    """Helper class to create sections and their entries from a RenderCVDataModel"""

    def __init__(self, user, cv, data_model, alias):
        self.user = user
        self.cv = cv
        self.data_model = data_model
        self.alias = alias

    def create_all_sections(self):
        """Create all sections from the data model"""
        if not hasattr(self.data_model.cv, "sections"):
            return

        section_order = 1
        for section in self.data_model.cv.sections:
            self._create_section(section, section_order)
            section_order += 1

    def _create_section(self, section_data, order):
        """Create a single section and its entries"""
        # Create Section object
        section = Section.objects.create(user=self.user, title=section_data.title, alias=self.alias)

        # Create relation between CV and section
        CVSection.objects.create(cv=self.cv, section=section, order=order)

        # Process entries
        self._create_entries(section, section_data)

    def _create_entries(self, section, section_data):
        """Create entries for a section"""
        if not hasattr(section_data, "entries") or not section_data.entries:
            return

        entry_type = get_entry_model(section_data.entry_type)
        entry_order = 1

        for entry_data in section_data.entries:
            # Create entry
            data = {key: value for key, value in entry_data.dict().items() if value is not None}
            entry_instance = entry_type.objects.create(user=self.user, **data, alias=self.alias)

            # Create relation between section and entry
            SectionEntry.objects.create(
                section=section, order=entry_order, content_object=entry_instance
            )

            entry_order += 1
