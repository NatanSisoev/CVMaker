from django.contrib.auth.models import User
from django.db import models


class EducationEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#educationentry

    Mandatory Fields:
        institution: The name of the institution.
        area: The area of study.
    Optional Fields:
        degree: The type of degree (e.g., BS, MS, PhD)
        location: The location
        start_date: The start date in YYYY-MM-DD, YYYY-MM, or YYYY format
        end_date: The end date in YYYY-MM-DD, YYYY-MM, or YYYY format or "present"
        date: A custom date string or in date format (overrides start_date and end_date)
        summary: The summary
        highlights: A list of bullet points (use <;> as separator)
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='education_entries'
    )
    institution = models.CharField(
        max_length=100, null=False, blank=False, help_text="The name of the institution"
    )
    area = models.CharField(
        max_length=100, null=False, blank=False, help_text="The area of study"
    )
    degree = models.CharField(
        max_length=100, blank=True, help_text="The type of degree (e.g., BS, MS, PhD)"
    )
    location = models.CharField(
        max_length=100, blank=True, help_text="The location"
    )
    start_date = models.DateField(
        null=True, blank=True, help_text="The start date"
    )
    end_date = models.DateField(
        null=True, blank=True, help_text="The end date"
    )
    date = models.DateField(
        null=True, blank=True, help_text="Custom date (overrides start_date and end_date)"
    )
    summary = models.CharField(
        max_length=500, blank=True, help_text="Summary of the entry"
    )
    highlights = models.CharField(
        max_length=500, blank=True, help_text="List of highlights separated by <;>"
    )

    def __str__(self):
        return f"[{self.institution} ({self.area})]"


class ExperienceEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#experienceentry

    Mandatory Fields:
        company: The name of the company.
        position: The position.
    Optional Fields:
        location: The location.
        start_date: The start date.
        end_date: The end date (or 'present').
        date: A custom date string (overrides start_date and end_date).
        summary: The summary.
        highlights: A list of bullet points (use <;> as separator).
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='experience_entries'
    )
    company = models.CharField(
        max_length=100, null=False, blank=False, help_text="The name of the company"
    )
    position = models.CharField(
        max_length=100, null=False, blank=False, help_text="The position"
    )
    location = models.CharField(
        max_length=100, blank=True, help_text="The location"
    )
    start_date = models.DateField(
        null=True, blank=True, help_text="The start date"
    )
    end_date = models.DateField(
        null=True, blank=True, help_text="The end date"
    )
    date = models.DateField(
        null=True, blank=True, help_text="Custom date (overrides start_date and end_date)"
    )
    summary = models.CharField(
        max_length=500, blank=True, help_text="Summary of the entry"
    )
    highlights = models.CharField(
        max_length=500, blank=True, help_text="List of highlights separated by <;>"
    )

    def __str__(self):
        return f"[{self.company} - {self.position}]"


class NormalEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#normalentry

    Mandatory Fields:
        name: The name of the entry.
    Optional Fields:
        location: The location.
        start_date: The start date.
        end_date: The end date (or 'present').
        date: A custom date string (overrides start_date and end_date).
        summary: The summary.
        highlights: A list of bullet points (use <;> as separator).
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='normal_entries'
    )
    name = models.CharField(
        max_length=100, null=False, blank=False, help_text="The name of the entry"
    )
    location = models.CharField(
        max_length=100, blank=True, help_text="The location"
    )
    start_date = models.DateField(
        null=True, blank=True, help_text="The start date"
    )
    end_date = models.DateField(
        null=True, blank=True, help_text="The end date"
    )
    date = models.DateField(
        null=True, blank=True, help_text="Custom date (overrides start_date and end_date)"
    )
    summary = models.CharField(
        max_length=500, blank=True, help_text="Summary of the entry"
    )
    highlights = models.CharField(
        max_length=500, blank=True, help_text="List of highlights separated by <;>"
    )

    def __str__(self):
        return f"[{self.name}]"


class PublicationEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#publicationentry

    Mandatory Fields:
        title: The title of the publication.
        authors: The authors of the publication.
    Optional Fields:
        doi: The DOI of the publication.
        url: The URL of the publication.
        journal: The journal of the publication.
        date: The publication date (custom string or in date format).
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='publication_entries'
    )
    title = models.CharField(
        max_length=200, null=False, blank=False, help_text="The title of the publication"
    )
    authors = models.CharField(
        max_length=300, null=False, blank=False,
        help_text="The authors (separated by commas)"
    )
    doi = models.CharField(
        max_length=100, blank=True, help_text="The DOI of the publication"
    )
    url = models.URLField(
        blank=True, help_text="The URL of the publication"
    )
    journal = models.CharField(
        max_length=200, blank=True, help_text="The journal of the publication"
    )
    date = models.DateField(
        null=True, blank=True, help_text="The publication date"
    )

    def __str__(self):
        return f"[{self.title}]"


class OneLineEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#onelineentry

    Mandatory Fields:
        label: The label of the entry.
        details: The details of the entry.
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='oneline_entries'
    )
    label = models.CharField(
        max_length=100, null=False, blank=False, help_text="The label of the entry"
    )
    details = models.CharField(
        max_length=300, null=False, blank=False, help_text="The details of the entry"
    )

    def __str__(self):
        return f"[{self.label}: {self.details}]"


class BulletEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#bullettentry

    Mandatory Fields:
        bullet: The bullet point.
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='bullet_entries'
    )
    bullet = models.CharField(
        max_length=300, null=False, blank=False, help_text="The bullet point"
    )

    def __str__(self):
        return f"[Bullet: {self.bullet}]"


class NumberedEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#numberedentry

    Mandatory Fields:
        number: The content of the numbered entry.
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='numbered_entries'
    )
    number = models.CharField(
        max_length=300, null=False, blank=False, help_text="The numbered entry content"
    )

    def __str__(self):
        return f"[Numbered: {self.number}]"


class ReversedNumberedEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#reversednumberedentry

    Mandatory Fields:
        reversed_number: The content of the reversed numbered entry.
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='reversenumbered_entries'
    )
    reversed_number = models.CharField(
        max_length=300, null=False, blank=False,
        help_text="The reversed numbered entry content"
    )

    def __str__(self):
        return f"[Reversed Numbered: {self.reversed_number}]"


class TextEntry(models.Model):
    """
    RenderCV: https://docs.rendercv.com/user_guide/structure_of_the_yaml_input_file/#textentry

    Mandatory Fields:
        text: The text content.
    """
    user = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='text_entries'
    )
    text = models.TextField(
        null=False, blank=False, help_text="The text content for the entry"
    )

    def __str__(self):
        # Show only the first 50 characters for brevity.
        return f"[TextEntry: {self.text[:50]}...]"
