from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from entries.views import home

urlpatterns = [
    # Home
    path('', home, name='home'),

    # Admin
    path('admin/', admin.site.urls),

    # CV App
    path('cv/', include('cv.urls')),

    # Accounts
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
