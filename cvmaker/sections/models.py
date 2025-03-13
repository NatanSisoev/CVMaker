import uuid

from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class CVSection(models.Model):
    # KEYS
    cv = models.ForeignKey("cv.CV", on_delete=models.CASCADE)
    section = models.ForeignKey("sections.Section", on_delete=models.CASCADE)

    # INFO
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']
        unique_together = ('cv', 'section')


class Section(models.Model):
    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_sections')
    title = models.CharField(max_length=50, help_text="Name of the section")
    alias = models.CharField(max_length=20, help_text="Alias for the section", default="default")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    def serialize(self) -> list:
        return [entry.content_object.serialize() for entry in self.section_entries.order_by('order')]


class SectionEntry(models.Model):
    # KEYS
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='section_entries')

    # INFO
    order = models.PositiveIntegerField()

    # OTHER
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ['order']

    def serialize(self) -> dict:
        return self.content_object.serialize()
