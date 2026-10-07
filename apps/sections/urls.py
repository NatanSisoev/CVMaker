from django.urls import path

from . import views

urlpatterns = [
    path("", views.SectionListView.as_view(), name="section-list"),
    path("<uuid:section_id>/", views.SectionDetailView.as_view(), name="section-detail"),
    path("<uuid:section_id>/edit/", views.SectionUpdateView.as_view(), name="section-edit"),
    path("<uuid:section_id>/delete/", views.SectionDeleteView.as_view(), name="section-delete"),
    path("create/", views.SectionCreateView.as_view(), name="section-create"),
    path(
        "<uuid:section_id>/entries/order/",
        views.reorder_section_entries_view,
        name="section-reorder-entries",
    ),
    path("cv/<uuid:cv_id>/order/", views.reorder_cv_sections_view, name="cv-reorder-sections"),
]
