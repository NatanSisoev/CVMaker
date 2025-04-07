from django.urls import path

from .views import *

urlpatterns = [
    path('', CVListView.as_view(), name='cv-list'),
    path('create/', CVCreateView.as_view(), name='cv-create'),
    path('upload/', CVUploadView.as_view(), name='cv-upload'),
    path('<uuid:cv_id>/', CVDetailView.as_view(), name='cv-detail'),
    path('<uuid:cv_id>/edit/', CVUpdateView.as_view(), name='cv-edit'),
    path('<uuid:cv_id>/download/', download_cv, name='cv-download'),
    path('<uuid:cv_id>/delete/', CVDeleteView.as_view(), name='cv-delete'),
    path('<uuid:cv_id>/preview/', preview_cv, name='cv-preview'),
]
