import copy

from django.contrib.auth import user_logged_in
from django.http import FileResponse, HttpResponse
import os
from rendercv import data
from rendercv.cli.utilities import read_and_construct_the_input, get_default_render_command_cli_arguments
from rendercv.renderer import renderer

from cv.models import CV
from cvmaker import settings
from entries.models import CVEntry


def render_to_pdf(request):
    file = settings.MEDIA_ROOT / "cvs" / "test_dynamic"
    log = open(settings.MEDIA_ROOT / "rendering.log", "w")

    ############################################

    cv = CV.objects.get(user=request.user)
    print(f"{cv.asdict()}", file=log)
    # print(f"{cv=}", file=log)
    # print(f"{cv.__dict__}", file=log)
    # print(f"{cv.entries.all()}", file=log)
    # print(f"{CVEntry.objects.filter(user=request.user)}", file=log)

    ############################################

    cli_render_arguments = get_default_render_command_cli_arguments()
    # print(f"{cli_render_arguments=}", file=log)
    input_file_as_a_dict = read_and_construct_the_input(file.with_suffix(".yaml"), cli_render_arguments)
    print(f"{input_file_as_a_dict=}", file=log)

    data_model_dict = {"cv": "kjn"}

    del input_file_as_a_dict["rendercv_settings"]["render_command"]["_"]
    del input_file_as_a_dict["rendercv_settings"]["render_command"]["extra_data_model_override_arguments"]

    # TODO: generate DataModel directly

    # Validate input
    data_model = data.validate_input_dictionary_and_return_the_data_model(
        input_file_as_a_dict,
        context={"input_file_directory": file.parent},
    )
    # print(f"{data_model=}", file=log)

    render_command_settings: data.models.RenderCommandSettings = data_model.rendercv_settings.render_command
    if not render_command_settings or not render_command_settings.output_folder_name:
        return HttpResponse("Invalid render command settings", status=400)
    # print(f"{render_command_settings=}", file=log)

    output_directory = file.parent / render_command_settings.output_folder_name
    # print(f"{output_directory=}", file=log)

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
