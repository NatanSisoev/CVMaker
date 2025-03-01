from django.urls import path
from . import views

urlpatterns = [
    path('', views.SectionListView.as_view(), name='section-list'),
    path('<int:section_id>/', views.SectionDetailView.as_view(), name='section-detail'),
    path('<int:section_id>/edit/', views.SectionUpdateView.as_view(), name='section-edit'),
    path('<int:section_id>/delete/', views.SectionDeleteView.as_view(), name='section-delete'),
    path('create/', views.SectionCreateView.as_view(), name='section-create'),
]