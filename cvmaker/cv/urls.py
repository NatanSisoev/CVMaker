from django.urls import path

from cv.views import render_to_pdf

urlpatterns = [
    # TODO: finish
    # path("new/", ..., name="new-cv"),
    # path("view/", ..., name="view-cv"),
    path("render/", render_to_pdf, name="render-cv"),
    # path("edit/", ..., name="edit-cv"),
    # path("delete/", ..., name="delete-cv"),
]
