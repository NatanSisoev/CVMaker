import uuid
from pathlib import Path

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from rendercv.data import read_a_yaml_file
from rendercv.data.models.curriculum_vitae import available_social_networks


def months_abbreviations_defaults():
    return ["Jan", "Feb", "Mar", "Apr", "May", "June", "July", "Aug", "Sept", "Oct", "Nov", "Dec"]


def months_full_names_defaults():
    return ["January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"]


# TODO: create a generator class that accepts file upload and creates all entries, info, design, etc.

########################################################################################################################
########################################### LEVEL 1: CV ################################################################
########################################################################################################################


class CV(models.Model):
    # KEYS
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cvs', default=1, null=True)
    alias = models.CharField(max_length=20, null=False, blank=False, help_text="Alias for the curriculum vitae",
                             default="CV")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    info = models.ForeignKey("CVInfo", on_delete=models.SET_NULL, null=True, blank=True, related_name='cv')
    design = models.ForeignKey("CVDesign", on_delete=models.SET_NULL, null=True, blank=True, related_name='cv')
    locale = models.ForeignKey("CVLocale", on_delete=models.SET_NULL, null=True, blank=True, related_name='cv')
    settings = models.ForeignKey("CVSettings", on_delete=models.SET_NULL, null=True, blank=True, related_name='cv')

    sections = models.ManyToManyField(
        "sections.Section",
        through="sections.CVSection",
        related_name="cvs",
        blank=True
    )

    # EXTRA
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def serialize(self) -> dict:
        cv = self.info.serialize() if self.info else None
        for section in self.sections.all():
            if "sections" not in cv:
                cv["sections"] = {}
            cv["sections"][section.title] = section.serialize()

        return {
            'cv': cv if cv else None,
            'design': self.design.serialize() if self.design else None,
            'locale': self.locale.serialize() if self.locale else None,
            'rendercv_settings': self.settings.serialize() if self.settings else None
        }


########################################################################################################################
######################################### LEVEL 2: MODULES #############################################################
########################################################################################################################


class CVInfo(models.Model):
    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name="cv_info")
    alias = models.CharField(max_length=20, help_text="Alias for the information", default="default")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    # INFO
    name = models.CharField(max_length=20, null=True, blank=True, help_text="Your name")
    location = models.CharField(max_length=255, null=True, blank=True, help_text="The location of the individual")
    email = models.EmailField(null=True, blank=True, help_text="The email address of the individual")
    photo = models.ImageField(upload_to='photos/', null=True, blank=True, help_text="Path to the individual's photo")
    phone = models.CharField(max_length=20, null=True, blank=True, help_text="The phone number, including country code")
    website = models.URLField(null=True, blank=True,
                              help_text="A URL to the individual's personal or professional website")
    social_networks = models.JSONField(null=True, blank=True,
                                       help_text="A list of social media profiles in JSON format")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.social_networks:
            for social_network in self.social_networks:
                if social_network not in available_social_networks:
                    raise ValidationError("Network currently unavailable")

    def _format_social_networks(self):
        if not self.social_networks:
            return None
        return [{"network": k, "username": v} for k, v in self.social_networks.items()]

    def serialize(self) -> dict:
        if hasattr(self, "data_file") and self.data_file and Path(self.data_file.path).exists():
            return read_a_yaml_file(self.data_file.path)

        info = {
            'name': self.name if self.name else None,
            'location': self.location if self.location else None,
            'email': self.email if self.email else None,
            'phone': self.phone if self.phone else None,
            'website': self.website if self.website else None,
            'social_networks': self._format_social_networks(),
            'photo': self.photo.url if self.photo else None
        }

        return {k: v for k, v in info.items() if v is not None}


class CVDesign(models.Model):
    # DEFAULTS
    THEME_CHOICES = [
        ('classic', 'Classic'),
        ('sb2nov', 'Sb2Nov'),
        ('engineeringresumes', 'EngineeringResumes'),
        ('engineeringclassic', 'EngineeringClassic'),
        ('moderncv', 'ModernCV')
    ]

    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_designs')
    alias = models.CharField(max_length=20, help_text="Alias for the design", default="default")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    # INFO
    theme = models.CharField(max_length=100, null=False, blank=False, choices=THEME_CHOICES, help_text="The theme name")

    # FILE
    design_file = models.FileField(
        upload_to="media/cvs/src",
        null=True,
        blank=True,
        help_text="Upload YAML file with complete design specs"
    )

    def serialize(self) -> dict:
        if self.design_file and Path(self.design_file.path).exists():
            return read_a_yaml_file(self.design_file.path)

        return {'theme': self.theme}


class CVLocale(models.Model):
    # DEFAULTS
    phone_number_format_choices = [("national", "National"), ("international", "International"), ("E164", "E164")]

    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_locales')
    alias = models.CharField(max_length=20, help_text="Alias for the locale", default="default")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    # INFO
    language = models.CharField(max_length=2, null=False, blank=False, default='en',
                                help_text="The language as an ISO 639 alpha-2 code")
    phone_number_format = models.CharField(max_length=20, blank=True, choices=phone_number_format_choices,
                                           default="national",
                                           help_text="The format of phone numbers (national, international, or E164)")
    page_numbering_template = models.CharField(max_length=255, default="NAME - Page PAGE_NUMBER of TOTAL_PAGES",
                                               help_text="The template for page numbering in the CV.")
    last_updated_date_template = models.CharField(max_length=255, default="Last updated in TODAY",
                                                  help_text="The template for the last updated date.")
    date_template = models.CharField(max_length=255, blank=True, default="MONTH_ABBREVIATION YEAR",
                                     help_text="The template for dates.")
    month = models.CharField(max_length=100, blank=True, default="month",
                             help_text="Translation of the word 'month' in the locale.")
    months = models.CharField(max_length=100, blank=True, default="months",
                              help_text="Translation of the word 'months' in the locale.")
    year = models.CharField(max_length=100, blank=True, default="year",
                            help_text="Translation of the word 'year' in the locale.")
    years = models.CharField(max_length=100, blank=True, default="years",
                             help_text="Translation of the word 'years' in the locale.")
    present = models.CharField(max_length=100, blank=True, default="present",
                               help_text="Translation of the word 'present' in the locale.")
    to = models.CharField(max_length=10, blank=True, default="–",
                          help_text="The word or character used to indicate a range (e.g., '2020 - 2021').")
    abbreviations_for_months = models.JSONField(blank=True, default=months_abbreviations_defaults,
                                                help_text="Abbreviations of the months in the locale.")
    full_names_of_months = models.JSONField(blank=True, default=months_full_names_defaults,
                                            help_text="Full names of the months in the locale.")

    # FILE
    locale_file = models.FileField(
        upload_to="media/cvs/src",
        null=True,
        blank=True,
        help_text="Upload YAML file with complete locale settings"
    )

    def serialize(self) -> dict:
        if self.locale_file and Path(self.locale_file.path).exists():
            return read_a_yaml_file(self.locale_file.path)

        return {
            'language': self.language,
            'phone_number_format': self.phone_number_format,
            'page_numbering_template': self.page_numbering_template,
            'last_updated_date_template': self.last_updated_date_template,
            'date_template': self.date_template,
            'month': self.month,
            'months': self.months,
            'year': self.year,
            'years': self.years,
            'present': self.present,
            'to': self.to,
            'abbreviations_for_months': self.abbreviations_for_months,
            'full_names_of_months': self.full_names_of_months,
        }


class CVSettings(models.Model):
    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_settings')
    alias = models.CharField(max_length=20, help_text="Alias for the settings", default="default")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    # INFO
    date = models.DateField(default=timezone.now,
                            help_text="The date that will be used for various computations (default: today)")
    bold_keywords = models.JSONField(default=list, blank=True,
                                     help_text="A list of keywords that will be bolded in the output")

    # FILE
    settings_file = models.FileField(
        upload_to="media/cvs/src",
        null=True,
        blank=True,
        help_text="Upload YAML file with complete settings"
    )

    def serialize(self) -> dict:
        # TODO: finish render_command
        if self.settings_file and Path(self.settings_file.path).exists():
            return read_a_yaml_file(self.settings_file.path)

        return {
            'date': self.date.isoformat(),
            'bold_keywords': self.bold_keywords,
            'render_command': {
                "output_folder_name": r"RenderCV\output",
                "pdf_path": "NAME_IN_SNAKE_CASE_CV.pdf",
                "typst_path": "NAME_IN_LOWER_SNAKE_CASE_cv.typ",
                "html_path": "NAME_IN_KEBAB_CASE_CV.html",
                "markdown_path": "NAME.md",
                "dont_generate_html": "true",
                "dont_generate_markdown": "true",
                "dont_generate_png": "true"
            }
        }
