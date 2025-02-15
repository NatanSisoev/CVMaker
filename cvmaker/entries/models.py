from django.contrib.auth.models import User
from django.db import models


class CVEntry(models.Model):
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='%(class)s')
    start_date = models.DateField(null=True, blank=True, help_text="The start date")
    end_date = models.DateField(null=True, blank=True, help_text="The end date")
    date = models.DateField(null=True, blank=True, help_text="Custom date (overrides start_date and end_date)")
    summary = models.CharField(max_length=500, blank=True, help_text="Summary of the entry")
    highlights = models.CharField(max_length=500, blank=True, help_text="List of highlights separated by ;")

    def __str__(self) -> str:
        return f"[{self.__class__.__name__}]"


class EducationEntry(CVEntry):
    institution = models.CharField(max_length=100, null=False, blank=False, help_text="The name of the institution")
    area = models.CharField(max_length=100, null=False, blank=False, help_text="The area of study")
    degree = models.CharField(max_length=100, blank=True, help_text="The type of degree (e.g., BS, MS, PhD)")
    location = models.CharField(max_length=100, blank=True, help_text="The location")

    def __str__(self) -> str:
        return f"[{self.institution}({self.area})]"


class ExperienceEntry(CVEntry):
    company = models.CharField(max_length=100, null=False, blank=False, help_text="The name of the company")
    position = models.CharField(max_length=100, null=False, blank=False, help_text="The position")
    location = models.CharField(max_length=100, blank=True, help_text="The location")

    def __str__(self) -> str:
        return f"[{self.company}({self.position})]"


class NormalEntry(CVEntry):
    name = models.CharField(max_length=100, null=False, blank=False, help_text="The name of the entry")
    location = models.CharField(max_length=100, blank=True, help_text="The location")

    def __str__(self) -> str:
        return f"[{self.name}]"


class PublicationEntry(CVEntry):
    title = models.CharField(max_length=200, null=False, blank=False, help_text="The title of the publication")
    authors = models.CharField(max_length=300, null=False, blank=False, help_text="The authors (separated by commas)")
    doi = models.CharField(max_length=100, blank=True, help_text="The DOI of the publication")
    url = models.URLField(blank=True, help_text="The URL of the publication")
    journal = models.CharField(max_length=200, blank=True, help_text="The journal of the publication")

    def __str__(self) -> str:
        return f"[{self.title}]"


class OneLineEntry(CVEntry):
    label = models.CharField(max_length=100, null=False, blank=False, help_text="The label of the entry")
    details = models.CharField(max_length=300, null=False, blank=False, help_text="The details of the entry")

    def __str__(self) -> str:
        return f"[{self.label}({self.details})]"


class BulletEntry(CVEntry):
    bullet = models.CharField(max_length=300, null=False, blank=False, help_text="The bullet point")

    def __str__(self) -> str:
        return f"[Bulleted({self.bullet})]"


class NumberedEntry(CVEntry):
    number = models.CharField(max_length=300, null=False, blank=False, help_text="The numbered entry content")

    def __str__(self) -> str:
        return f"[Numbered({self.number})]"


class ReversedNumberedEntry(CVEntry):
    reversed_number = models.CharField(max_length=300, null=False, blank=False,
                                       help_text="The reversed numbered entry content")

    def __str__(self) -> str:
        return f"[ReversedNumbered({self.reversed_number})]"


class TextEntry(CVEntry):
    text = models.TextField(null=False, blank=False, help_text="The text content for the entry")

    def __str__(self) -> str:
        return f"[Text({self.text})]"
