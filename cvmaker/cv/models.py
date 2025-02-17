from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from rendercv.data import read_a_yaml_file

########################################################################################################################
########################################### LEVEL 1: CV ################################################################
########################################################################################################################


class CV(models.Model):
    # KEYS
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cvs')
    alias = models.CharField(max_length=20, help_text="Alias for the curriculum vitae", default="default")

    # TODO: optionally upload file

    # OTHERS
    info = models.ForeignKey("CVInfo", on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    design = models.ForeignKey("CVDesign", on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    locale = models.ForeignKey("CVLocale", on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    settings = models.ForeignKey("CVSettings", on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    def serialize(self) -> dict:
        return {
            'cv': self.info.serialize() if self.info else None,
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

    # INFO
    name = models.CharField(max_length=20, null=True, blank=True, help_text="Your name")
    location = models.CharField(max_length=255, null=True, blank=True, help_text="The location of the individual")
    email = models.EmailField(null=True, blank=True, help_text="The email address of the individual")
    photo = models.ImageField(upload_to='photos/', null=True, blank=True, help_text="Path to the individual's photo")
    phone = models.CharField(max_length=20, null=True, blank=True, help_text="The phone number, including country code")
    website = models.URLField(null=True, blank=True, help_text="A URL to the individual's personal or professional website")
    social_networks = models.JSONField(null=True, blank=True, help_text="A list of social media profiles in JSON format")

    # FILE
    data_file = models.FileField(
        upload_to="media/cvs/src",
        null=True,
        blank=True,
        help_text="Upload YAML file with complete info"
    )

    # OTHER
    sections: "Section" = models.ManyToManyField("Section", through="CVInfoSection", related_name="cv_infos")

    def _format_social_networks(self):
        # TODO: check if available networks
        if not self.social_networks:
            return None
        return [{"network": k, "username": v} for k, v in self.social_networks.items()]


    def serialize(self) -> dict:
        # TODO: ordering
        if self.data_file and Path(self.data_file.path).exists():
            return read_a_yaml_file(self.data_file.path)

        info = {
            'name': self.name if self.name else None,
            'location': self.location if self.location else None,
            'email': self.email if self.email else None,
            'phone': self.phone if self.phone else None,
            'website': self.website if self.website else None,
            'social_networks': self._format_social_networks(),
            'photo': self.photo.url if self.photo else None,
            'sections': {
                section.title: section.serialize()
                for section in self.sections.all()
            }
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


def months_abbreviations_defaults():
    return ["Jan", "Feb", "Mar", "Apr", "May", "June", "July", "Aug", "Sept", "Oct", "Nov", "Dec"]

def months_full_names_defaults():
    return ["January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"]

class CVLocale(models.Model):
    # DEFAULTS
    phone_number_format_choices = [("national", "National"), ("international", "International"), ("E164", "E164")]

    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_locales')
    alias = models.CharField(max_length=20, help_text="Alias for the locale", default="default")

    # INFO
    language = models.CharField(max_length=2, null=False, blank=False, default='en', help_text="The language as an ISO 639 alpha-2 code")
    phone_number_format = models.CharField(max_length=20, blank=True, choices=phone_number_format_choices, default="national", help_text="The format of phone numbers (national, international, or E164)")
    page_numbering_template = models.CharField(max_length=255, default="NAME - Page PAGE_NUMBER of TOTAL_PAGES", help_text="The template for page numbering in the CV.")
    last_updated_date_template = models.CharField(max_length=255, default="Last updated in TODAY", help_text="The template for the last updated date.")
    date_template = models.CharField(max_length=255, blank=True, default="MONTH_ABBREVIATION YEAR", help_text="The template for dates.")
    month = models.CharField(max_length=100, blank=True, default="month", help_text="Translation of the word 'month' in the locale.")
    months = models.CharField(max_length=100, blank=True, default="months", help_text="Translation of the word 'months' in the locale.")
    year = models.CharField(max_length=100, blank=True, default="year", help_text="Translation of the word 'year' in the locale.")
    years = models.CharField(max_length=100, blank=True, default="years", help_text="Translation of the word 'years' in the locale.")
    present = models.CharField(max_length=100, blank=True, default="present", help_text="Translation of the word 'present' in the locale.")
    to = models.CharField(max_length=10, blank=True, default="–", help_text="The word or character used to indicate a range (e.g., '2020 - 2021').")
    abbreviations_for_months = models.JSONField(blank=True, default=months_abbreviations_defaults, help_text="Abbreviations of the months in the locale.")
    full_names_of_months = models.JSONField(blank=True, default=months_full_names_defaults, help_text="Full names of the months in the locale.")

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

    # INFO
    date = models.DateField(default=timezone.now, help_text="The date that will be used for various computations (default: today)")
    bold_keywords = models.JSONField(default=list, blank=True, help_text="A list of keywords that will be bolded in the output")

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
                "output_folder_name": "RenderCV\output"
            }
        }


########################################################################################################################
######################################## LEVEL 2.5: RELATIONS ##########################################################
########################################################################################################################


class CVInfoSection(models.Model):
    # KEYS
    cv_info = models.ForeignKey("CVInfo", on_delete=models.CASCADE)
    section = models.ForeignKey("Section", on_delete=models.CASCADE)

    # INFO
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']
        unique_together = ('cv_info', 'section')


########################################################################################################################
######################################### LEVEL 3: SECTIONS ############################################################
########################################################################################################################


class Section(models.Model):
    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_sections')
    title = models.CharField(max_length=50, help_text="Name of the section")
    alias = models.CharField(max_length=20, help_text="Alias for the section", default="default")

    def serialize(self) -> list:
        # TODO: not list but dict
        return [
                entry.content_object.serialize()
                for entry in self.section_entries.order_by('order')
            ]


########################################################################################################################
######################################## LEVEL 3.5: RELATIONS ##########################################################
########################################################################################################################


class SectionEntry(models.Model):
    # KEYS
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_section_entry')
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
