from django.contrib import admin
from .models import CV, CVInfo, CVDesign, CVLocale, CVSettings, CVInfoSection, Section, SectionEntry

# Register your models here.

admin.site.register(CV)
admin.site.register(CVInfo)
admin.site.register(CVDesign)
admin.site.register(CVLocale)
admin.site.register(CVSettings)
admin.site.register(CVInfoSection)
admin.site.register(Section)
admin.site.register(SectionEntry)
