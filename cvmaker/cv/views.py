from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
import os

from rendercv import data
from rendercv.renderer import renderer

from cv.models import CV
from cvmaker import settings


@login_required
def render_to_pdf(request, cv_id):
    # TODO: cv.photo location
    cv = CV.objects.get(id=cv_id, user=request.user)
    data_model = data.validate_input_dictionary_and_return_the_data_model(cv.serialize())

    render_command_settings: data.models.RenderCommandSettings = data_model.rendercv_settings.render_command
    if not render_command_settings or not render_command_settings.output_folder_name:
        return HttpResponse("Invalid render command settings", status=400)

    output_directory = settings.MEDIA_ROOT / render_command_settings.output_folder_name

    typst_file_path_in_output_folder = renderer.create_a_typst_file_and_copy_theme_files(
        data_model, output_directory
    )
    pdf_file_path_in_output_folder = renderer.render_a_pdf_from_typst(typst_file_path_in_output_folder)

    if os.path.exists(pdf_file_path_in_output_folder):
        return FileResponse(open(pdf_file_path_in_output_folder, "rb"), content_type="application/pdf")
    else:
        return HttpResponse("File not found", status=404)

