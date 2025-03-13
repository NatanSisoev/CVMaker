from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from cv.views import HomePageView  # change the import

urlpatterns = [
    path('', HomePageView.as_view(), name='homepage'),

    path('admin/', admin.site.urls),
    path('cv/', include('cv.urls')),
    path('section/', include('sections.urls')),
    path('entry/', include('entries.urls')),

    path('accounts/', include('accounts.urls')),
    path('accounts/', include('django.contrib.auth.urls')),

    path('templates/', lambda: None, name='templates'),  # TODO
    path('import/', lambda: None, name='import'),  # TODO
    path('help/', lambda: None, name='help'),  # TODO
    path('contact/', lambda: None, name='contact'),  # TODO
    path('status/', lambda: None, name='status'),  # TODO
    path('about/', lambda: None, name='about'),  # TODO

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
