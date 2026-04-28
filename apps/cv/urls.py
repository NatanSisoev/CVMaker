from django.urls import path

from .views import (
    CVCreateView,
    CVDeleteView,
    CVDesignCreateView,
    CVDesignDeleteView,
    CVDesignDetailView,
    CVDesignListView,
    CVDesignUpdateView,
    CVDetailView,
    CVInfoCreateView,
    CVInfoDeleteView,
    CVInfoDetailView,
    CVInfoListView,
    CVInfoUpdateView,
    CVListView,
    CVLocaleCreateView,
    CVLocaleDeleteView,
    CVLocaleDetailView,
    CVLocaleListView,
    CVLocaleUpdateView,
    CVSettingsCreateView,
    CVSettingsDeleteView,
    CVSettingsDetailView,
    CVSettingsListView,
    CVSettingsUpdateView,
    CVUpdateView,
    CVUploadView,
    download_cv,
    preview_cv,
)

urlpatterns = [
    path("", CVListView.as_view(), name="cv-list"),
    path("create/", CVCreateView.as_view(), name="cv-create"),
    path("upload/", CVUploadView.as_view(), name="cv-upload"),
    path("<uuid:cv_id>/", CVDetailView.as_view(), name="cv-detail"),
    path("<uuid:cv_id>/edit/", CVUpdateView.as_view(), name="cv-edit"),
    path("<uuid:cv_id>/download/", download_cv, name="cv-download"),
    path("<uuid:cv_id>/delete/", CVDeleteView.as_view(), name="cv-delete"),
    path("<uuid:cv_id>/preview/", preview_cv, name="cv-preview"),
]

urlpatterns += [
    # CVInfo URLs
    path("info/create/", CVInfoCreateView.as_view(), name="cvinfo-create"),
    path("info/", CVInfoListView.as_view(), name="cvinfo-list"),
    path("info/<uuid:info_id>/", CVInfoDetailView.as_view(), name="cvinfo-detail"),
    path("info/<uuid:info_id>/edit/", CVInfoUpdateView.as_view(), name="cvinfo-edit"),
    path("info/<uuid:info_id>/delete/", CVInfoDeleteView.as_view(), name="cvinfo-delete"),
    # CVDesign URLs
    path("design/create/", CVDesignCreateView.as_view(), name="cvdesign-create"),
    path("design/", CVDesignListView.as_view(), name="cvdesign-list"),
    path("design/<uuid:design_id>/", CVDesignDetailView.as_view(), name="cvdesign-detail"),
    path("design/<uuid:design_id>/edit/", CVDesignUpdateView.as_view(), name="cvdesign-edit"),
    path("design/<uuid:design_id>/delete/", CVDesignDeleteView.as_view(), name="cvdesign-delete"),
    # CVLocale URLs
    path("locale/create/", CVLocaleCreateView.as_view(), name="cvlocale-create"),
    path("locale/", CVLocaleListView.as_view(), name="cvlocale-list"),
    path("locale/<uuid:locale_id>/", CVLocaleDetailView.as_view(), name="cvlocale-detail"),
    path("locale/<uuid:locale_id>/edit/", CVLocaleUpdateView.as_view(), name="cvlocale-edit"),
    path("locale/<uuid:locale_id>/delete/", CVLocaleDeleteView.as_view(), name="cvlocale-delete"),
    # CVSettings URLs
    path("settings/create/", CVSettingsCreateView.as_view(), name="cvsettings-create"),
    path("settings/", CVSettingsListView.as_view(), name="cvsettings-list"),
    path("settings/<uuid:settings_id>/", CVSettingsDetailView.as_view(), name="cvsettings-detail"),
    path(
        "settings/<uuid:settings_id>/edit/", CVSettingsUpdateView.as_view(), name="cvsettings-edit"
    ),
    path(
        "settings/<uuid:settings_id>/delete/",
        CVSettingsDeleteView.as_view(),
        name="cvsettings-delete",
    ),
]
