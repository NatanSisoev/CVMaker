from django.urls import path
from .views import *

urlpatterns = [
    path('', CVListView.as_view(), name='cv-list'),
    path('create/', CVCreateView.as_view(), name='cv-create'),
    path('<int:cv_id>/', CVDetailView.as_view(), name='cv-detail'),
    path('<int:cv_id>/edit/', CVUpdateView.as_view(), name='cv-edit'),
    path('<int:cv_id>/download/', download_cv, name='cv-download'),
    path('<int:cv_id>/delete/', CVDeleteView.as_view(), name='cv-delete'),
    path('<int:cv_id>/preview/', preview_cv, name='cv-preview'),
]