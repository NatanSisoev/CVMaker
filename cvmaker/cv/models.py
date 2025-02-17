from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from rendercv.data import read_a_yaml_file

from cvmaker import settings
from entries.models import CVEntry

# convert { CV, CVDesign, CVLocale } -> python asdict (method for each one, where cv is recursive)
# convert python asdict ->  rendercv.data.RenderCVDataModel (using rendercv.api.read_a_python_dictionary_and_return_a_data_model)
# convert RenderCVDataModel -> typst file (using rendercv.api.create_a_typst_file)
#                                         -> pdf file (using rendercv.api.render_a_pdf_from_typst)
#                                         -> pdf file (using rendercv.api.render_pngs_from_typst)
# convert RenderCVDataModel -> markdown file (using rendercv.api.create_a_markdown_file)
#                                            -> html file (using rendercv.api.render_an_html_from_markdown)

def ABBREVIATIONSSFORMONTHS_DEFAULT():
    return ["Jan", "Feb", "Mar", "Apr", "May", "June", "July", "Aug", "Sept", "Oct", "Nov", "Dec"]

def FULLNAMESOFMONTHS_DEFAULT():
    return ["January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"]


class CVDesign(models.Model):
    THEME_CHOICES = [
        ('classic', 'Classic'),
        ('modern', 'Modern'),
        ('professional', 'Professional'),
        ('minimalist', 'Minimalist'),
        ('custom', 'Custom')
    ]

    # Mandatory
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_designs')
    theme = models.CharField(max_length=100, null=False, blank=False,
                             choices=THEME_CHOICES, help_text="The theme name")

    # Optional
    custom_design = models.FileField(null=True, blank=True, help_text="Upload a custom design file")

    def __str__(self) -> str:
        return f"[{self.__class__.__name__}({self.theme})]"

    def asdict(self):
        return {"theme": self.theme} if not self.custom_design else read_a_yaml_file(settings.MEDIA_ROOT / self.custom_design.name)["design"]

    
class CVLocale(models.Model):
    PHONENUMBERFORMAT_CHOICES =  [("national", "National"), ("international", "International"), ("E164", "E164")]

    # Mandatory
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='cv_locales')
    language = models.CharField(max_length=2, null=False, blank=False, default='en',
                                help_text="The language as an ISO 639 alpha-2 code")

    # Optional
    phone_number_format = models.CharField(max_length=20, blank=True, choices=PHONENUMBERFORMAT_CHOICES,
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
    abbreviations_for_months = models.JSONField(blank=True, default=ABBREVIATIONSSFORMONTHS_DEFAULT,
                                                help_text="Abbreviations of the months in the locale.")
    full_names_of_months = models.JSONField(blank=True, default=FULLNAMESOFMONTHS_DEFAULT,
                                            help_text="Full names of the months in the locale.")

    def asdict(self):
        return {"language": self.language,
                "phone_number_format": self.phone_number_format,
                "page_numbering_template": self.page_numbering_template,
                "last_updated_date_template": self.last_updated_date_template,
                "date_template": self.date_template,
                "month": self.month,
                "months": self.months,
                "year": self.year,
                "years": self.years,
                "present": self.present,
                "to": self.to,
                "abbreviations_for_months": self.abbreviations_for_months,
                "full_names_of_months": self.full_names_of_months}

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.language})"


class CV(models.Model):
    # Mandatory
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cvs')
    name = models.CharField(max_length=255, null=False, blank=False, help_text="The full name of the individual")

    # Optional
    location = models.CharField(max_length=255, null=True, blank=True, help_text="The location of the individual")
    email = models.EmailField(null=True, blank=True, help_text="The email address of the individual")
    photo = models.ImageField(upload_to='photos/', null=True, blank=True, help_text="Path to the individual's photo")
    phone = models.CharField(max_length=20, null=True, blank=True, help_text="The phone number, including country code")
    website = models.URLField(null=True, blank=True,
                              help_text="A URL to the individual's personal or professional website")
    social_networks = models.JSONField(null=True, blank=True,
                                       help_text="A list of social media profiles in JSON format")

    date = models.DateField(default=timezone.now,
                            help_text="The date that will be used for various computations (default: today)")
    bold_keywords = models.JSONField(default=list, blank=True,
                                     help_text="A list of keywords that will be bolded in the output")

    design = models.ForeignKey(CVDesign, on_delete=models.SET_NULL, null=True, blank=True)
    locale = models.ForeignKey(CVLocale, on_delete=models.SET_NULL, null=True, blank=True)
    entries = models.ManyToManyField("entries.CVEntry", through="CVEntryOrder")

    def __str__(self) -> str:
        return f"[{self.__class__.__name__}({self.name})]"

    @property
    def _social_networks(self):
        return [{"network": network, "username": username} for network, username in self.social_networks.items()]

    @property
    def _cv(self):
        # TODO: finish sections (get all related entries)
        # problem: used as CVEntry not specific entries
        entries = self.entries.all()
        sections = {entry.alias: [entry.asdict()] for entry in entries}
        print(sections)
        return {"name": self.name,
                "location": self.location,
                "email": self.email,
                "photo": self.photo.name,
                "phone": f"tel:{self.phone}",
                "website": self.website,
                "social_networks": self._social_networks,
                "sections": None}

    @property
    def _design(self):
        return self.design.asdict()

    @property
    def _settings(self):
        return {"date": self.date,
                "bold_keywords": self.bold_keywords,
                "render_command": {"output_folder_name": "out"}}

    @property
    def _locale(self):
        return self.locale.asdict()
    
    def asdict(self):
        return {"cv": self._cv,
                "design": self._design,
                "rendercv_settings": self._settings,
                "locale": self._locale}


class CVEntryOrder(models.Model):
    cv = models.ForeignKey(CV, on_delete=models.CASCADE)
    entry = models.ForeignKey(CVEntry, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']
        constraints = [models.UniqueConstraint(fields=['cv', 'order'], name='unique_cv_order')]

    def __str__(self) -> str:
        return f"[{self.cv}-{self.order}->{self.entry}]"
