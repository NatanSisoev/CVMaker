from django.db import models
from django.contrib.auth.models import User

class Section(models.Model):
    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_sections')
    title = models.CharField(max_length=50, help_text="Name of the section")
    alias = models.CharField(max_length=20, help_text="Alias for the section", default="default")
    cv = models.ForeignKey("cv.CV", on_delete=models.CASCADE, related_name='sections') #Add the cv foreign key

    def serialize(self) -> list:
        # TODO: not list but dict
        return [
            entry.content_object.serialize()
            for entry in self.section_entries.order_by('order')
        ]