from django.contrib import admin

from sections.models import CVSection, Section, SectionEntry

from .models import CV, CVDesign, CVInfo, CVLocale, CVSettings

# Register your models here.

admin.site.register(CV)
admin.site.register(CVInfo)
admin.site.register(CVDesign)
admin.site.register(CVLocale)
admin.site.register(CVSettings)
admin.site.register(CVSection)
admin.site.register(Section)
admin.site.register(SectionEntry)
