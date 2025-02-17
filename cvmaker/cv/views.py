from django.http import FileResponse, HttpResponse
import os
from rendercv import data
from rendercv.cli.utilities import read_and_construct_the_input, get_default_render_command_cli_arguments
from rendercv.data import validate_input_dictionary_and_return_the_data_model
from rendercv.renderer import renderer

from cv.models import CV
from cvmaker import settings


def render_to_pdf(request):
    log = open(settings.MEDIA_ROOT / "rendering.log", "w")

    ############################################

    # TODO: cv.photo location

    cv = CV.objects.get(user=request.user)
    print(cv.entries.all(), file=log)
    data_model = data.validate_input_dictionary_and_return_the_data_model(cv.asdict())

    print(f"{data_model.cv.photo.name}", file=log)

    ############################################

    render_command_settings: data.models.RenderCommandSettings = data_model.rendercv_settings.render_command
    if not render_command_settings or not render_command_settings.output_folder_name:
        return HttpResponse("Invalid render command settings", status=400)
    # print(f"{render_command_settings=}", file=log)

    output_directory = settings.MEDIA_ROOT / render_command_settings.output_folder_name
    print(f"{output_directory=}", file=log)

    # Generate Typst file and render PDF
    typst_file_path_in_output_folder = renderer.create_a_typst_file_and_copy_theme_files(
        data_model, output_directory
    )
    pdf_file_path_in_output_folder = renderer.render_a_pdf_from_typst(typst_file_path_in_output_folder)

    # print(f"{pdf_file_path_in_output_folder=}", file=log)

    if os.path.exists(pdf_file_path_in_output_folder):
        return FileResponse(open(pdf_file_path_in_output_folder, "rb"), content_type="application/pdf")
    else:
        return HttpResponse("File not found", status=404)
