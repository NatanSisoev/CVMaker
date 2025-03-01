from django.contrib.auth.models import User
from django.db import models


class CVEntry(models.Model):
    # KEY
    user: models.ForeignKey = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='%(class)s')
    alias: models.CharField = models.CharField(max_length=20, null=False, blank=False, help_text="Alias for the CV entry")

    # TYPE-HINTING FOR METHODS
    start_date: models.DateField
    end_date: models.DateField
    date: models.DateField
    summary: models.CharField
    highlights: models.CharField

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"[{self.__class__.__name__}({self.alias})]"

    def _format_dates(self) -> dict:
        if self.date:
            return {'date': self.date.isoformat()}

        dates = {}
        if self.start_date:
            dates['start_date'] = self.start_date.isoformat()
        if self.end_date:
            dates['end_date'] = self.end_date.isoformat()

        return dates

    def _parse_highlights(self) -> list | None:
        if not self.highlights:
            return None

        return [highlight.strip()
                for highlight in self.highlights.split(';')
                if highlight.strip()]


class EducationEntry(CVEntry):
    # MANDATORY
    institution = models.CharField(max_length=100, null=False, blank=False, help_text="The name of the institution")
    area = models.CharField(max_length=100, null=False, blank=False, help_text="The area of study")

    # OPTIONAL
    degree = models.CharField(max_length=100, blank=True, help_text="The type of degree (e.g., BS, MS, PhD)")
    location = models.CharField(max_length=100, blank=True, help_text="The location")
    start_date = models.DateField(null=True, blank=True, help_text="The start date")
    end_date = models.DateField(null=True, blank=True, help_text="The end date")
    date = models.DateField(null=True, blank=True, help_text="Custom date (overrides start_date and end_date)")
    summary = models.CharField(max_length=500, blank=True, help_text="Summary of the entry")
    highlights = models.CharField(max_length=500, blank=True, help_text="List of highlights separated by ;")

    def __str__(self) -> str:
        return f"[{self.institution}({self.area})]"

    def serialize(self) -> dict:
        info = {
            'institution': self.institution,
            'area': self.area,
            'degree': self.degree if self.degree else None,
            'location': self.location if self.location else None,
            **self._format_dates(),
            'summary': self.summary if self.summary else None,
            'highlights': self._parse_highlights()
        }

        return {k: v for k, v in info.items() if v is not None}


class ExperienceEntry(CVEntry):
    # MANDATORY
    company = models.CharField(max_length=100, null=False, blank=False, help_text="The name of the company")
    position = models.CharField(max_length=100, null=False, blank=False, help_text="The position")

    # OPTIONAL
    location = models.CharField(max_length=100, blank=True, help_text="The location")
    start_date = models.DateField(null=True, blank=True, help_text="The start date")
    end_date = models.DateField(null=True, blank=True, help_text="The end date")
    date = models.DateField(null=True, blank=True, help_text="Custom date (overrides start_date and end_date)")
    summary = models.CharField(max_length=500, blank=True, help_text="Summary of the entry")
    highlights = models.CharField(max_length=500, blank=True, help_text="List of highlights separated by ;")

    def __str__(self) -> str:
        return f"[{self.company}({self.position})]"

    def serialize(self) -> dict:
        info = {
            'company': self.company,
            'position': self.position,
            'location': self.location if self.location else None,
            **self._format_dates(),
            'summary': self.summary if self.summary else None,
            'highlights': self._parse_highlights()
        }
        return {k: v for k, v in info.items() if v is not None}


class NormalEntry(CVEntry):
    # MANDATORY
    name = models.CharField(max_length=100, null=False, blank=False, help_text="The name of the entry")

    # OPTIONAL
    location = models.CharField(max_length=100, blank=True, help_text="The location")
    start_date = models.DateField(null=True, blank=True, help_text="The start date")
    end_date = models.DateField(null=True, blank=True, help_text="The end date")
    date = models.DateField(null=True, blank=True, help_text="Custom date (overrides start_date and end_date)")
    summary = models.CharField(max_length=500, blank=True, help_text="Summary of the entry")
    highlights = models.CharField(max_length=500, blank=True, help_text="List of highlights separated by ;")

    def __str__(self) -> str:
        return f"[{self.name}]"

    def serialize(self) -> dict:
        info = {
            'name': self.name,
            'location': self.location if self.location else None,
            **self._format_dates(),
            'summary': self.summary if self.summary else None,
            'highlights': self._parse_highlights()
        }
        return {k: v for k, v in info.items() if v is not None}

class PublicationEntry(CVEntry):
    # MANDATORY
    title = models.CharField(max_length=200, null=False, blank=False, help_text="The title of the publication")
    authors = models.CharField(max_length=300, null=False, blank=False, help_text="The authors (separated by commas)")

    # OPTIONAL
    doi = models.CharField(max_length=100, blank=True, help_text="The DOI of the publication")
    url = models.URLField(blank=True, help_text="The URL of the publication")
    journal = models.CharField(max_length=200, blank=True, help_text="The journal of the publication")
    date = models.DateField(null=True, blank=True, help_text="Custom date (overrides start_date and end_date)")

    def __str__(self) -> str:
        return f"[{self.title}]"

    def serialize(self) -> dict:
        info = {
            'title': self.title,
            'authors': self.authors,
            'doi': self.doi if self.doi else None,
            'url': self.url if self.url else None,
            'journal': self.journal if self.journal else None,
            **self._format_dates()
        }
        return {k: v for k, v in info.items() if v is not None}


class OneLineEntry(CVEntry):
    # MANDATORY
    label = models.CharField(max_length=100, null=False, blank=False, help_text="The label of the entry")
    details = models.CharField(max_length=300, null=False, blank=False, help_text="The details of the entry")

    def __str__(self) -> str:
        return f"[{self.label}({self.details})]"

    def serialize(self) -> dict:
        return {
            'label': self.label,
            'details': self.details
        }


class BulletEntry(CVEntry):
    # MANDATORY
    bullet = models.CharField(max_length=300, null=False, blank=False, help_text="The bullet point")

    def __str__(self) -> str:
        return f"[Bulleted({self.bullet})]"

    def serialize(self) -> dict:
        return {'bullet': self.bullet}


class NumberedEntry(CVEntry):
    # MANDATORY
    number = models.CharField(max_length=300, null=False, blank=False, help_text="The numbered entry content")

    def __str__(self) -> str:
        return f"[Numbered({self.number})]"

    def serialize(self) -> dict:
        return {'number': self.number}


class ReversedNumberedEntry(CVEntry):
    # MANDATORY
    reversed_number = models.CharField(max_length=300, null=False, blank=False,
                                       help_text="The reversed numbered entry content")

    def __str__(self) -> str:
        return f"[ReversedNumbered({self.reversed_number})]"

    def serialize(self) -> dict:
        return {'reversed_number': self.reversed_number}


class TextEntry(CVEntry):
    # MANDATORY
    text = models.TextField(null=False, blank=False, help_text="The text content for the entry")

    def __str__(self) -> str:
        return f"[Text({self.text})]"

    def serialize(self) -> dict:
        return {'text': self.text}

