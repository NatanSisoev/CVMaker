from django.urls import path
from cv.views import (
    CreateCVView,
    EditCVView,
    preview_cv,
    download_cv,
    DeleteCVView,
    SectionOrderView,
    SectionCreateView,
    SectionUpdateView,
    EntryCreateView,
    EntryUpdateView,
    EntryDeleteView, EditCVStructureView, UpdateSectionOrderView, UpdateEntryOrderView, SectionDeleteView, CVCreateView,
    CVDetailView,
)


urlpatterns = [
    # CV CRUD
    path("aa", CVCreateView.as_view(), name="aa"),
    path("create/", CreateCVView.as_view(), name="cv-create"),
    path("<int:cv_id>/", CVDetailView.as_view(),name="cv-detail"),
    path("<int:cv_id>/edit/", EditCVView.as_view(), name="cv-edit"),
    path("<int:cv_id>/download/", download_cv, name="cv-download"),
    path("<int:cv_id>/delete/", DeleteCVView.as_view(), name="cv-delete"),

    # CV Structure Edit
    path("<int:cv_id>/structure/edit/", EditCVStructureView.as_view(), name="cv-structure-edit"),

    # Section Management
    path("<int:cv_id>/sections/order/", SectionOrderView.as_view(), name="cv-section-order"),
    path("<int:cv_id>/sections/add/", SectionCreateView.as_view(), name="cv-section-add"),
    path("<int:cv_id>/sections/<int:pk>/edit/", SectionUpdateView.as_view(), name="cv-section-edit"),
    path("cv/<int:cv_id>/sections/<int:pk>/delete/", SectionDeleteView.as_view(), name="cv-section-delete"),

    # Entry Management
    path("<int:cv_id>/sections/<int:section_id>/entries/add/<str:entry_type>/", EntryCreateView.as_view(), name="cv-entry-add"),
    path("<int:cv_id>/entries/<int:entry_id>/edit/", EntryUpdateView.as_view(), name="cv-entry-edit"),
    path("<int:cv_id>/entries/<int:pk>/delete/", EntryDeleteView.as_view(), name="cv-entry-delete"),

    # Update Order Endpoints
    path("<int:cv_id>/sections/update-order/", UpdateSectionOrderView.as_view(), name="cv-section-update-order"),
    path("<int:cv_id>/entries/update-order/", UpdateEntryOrderView.as_view(), name="cv-entry-update-order"),
]

