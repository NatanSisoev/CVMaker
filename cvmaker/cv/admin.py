from django.contrib import admin

from .models import CV, CVDesign, CVInfo, CVLocale, CVSettings
from sections.models import Section, CVSection, SectionEntry

# Register your models here.

admin.site.register(CV)
admin.site.register(CVInfo)
admin.site.register(CVDesign)
admin.site.register(CVLocale)
admin.site.register(CVSettings)
admin.site.register(CVSection)
admin.site.register(Section)
admin.site.register(SectionEntry)
