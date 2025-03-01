from django.urls import path
from .views import *

urlpatterns = [
    path('', EntryListView.as_view(), name='entry-list'),
    path('<int:entry_id>/', EntryDetailView.as_view(), name='entry-detail'),
    path('<int:entry_id>/edit/', EntryUpdateView.as_view(), name='entry-edit'),
    path('<int:entry_id>/delete/', EntryDeleteView.as_view(), name='entry-delete'),
    path('create/', EntryCreateView.as_view(), name='entry-create'),
]
