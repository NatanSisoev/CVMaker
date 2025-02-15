import copy
from django.http import FileResponse, HttpResponse
import os
from rendercv import data
from rendercv.cli.utilities import read_and_construct_the_input, get_default_render_command_cli_arguments
from rendercv.renderer import renderer
from cvmaker import settings

def render_to_pdf(request):
    file = settings.MEDIA_ROOT / "cvs" / "test_dynamic"

    cli_render_arguments = get_default_render_command_cli_arguments()
    input_file_as_a_dict = read_and_construct_the_input(file.with_suffix(".yaml"), cli_render_arguments)

    # DEBUG: Check input data before validation
    print("INPUT FILE AS A DICT:", input_file_as_a_dict)

    del input_file_as_a_dict["rendercv_settings"]["render_command"]["_"]
    del input_file_as_a_dict["rendercv_settings"]["render_command"]["extra_data_model_override_arguments"]

    # Validate input
    data_model = data.validate_input_dictionary_and_return_the_data_model(
        input_file_as_a_dict,
        context={"input_file_directory": file.parent},
    )

    render_command_settings: data.models.RenderCommandSettings = data_model.rendercv_settings.render_command  # type: ignore


    # Ensure render_command_settings is valid
    if not render_command_settings or not render_command_settings.output_folder_name:
        return HttpResponse("Invalid render command settings", status=400)

    output_directory = file.parent / render_command_settings.output_folder_name

    # Generate Typst file and render PDF
    typst_file_path_in_output_folder = renderer.create_a_typst_file_and_copy_theme_files(
        data_model, output_directory
    )
    pdf_file_path_in_output_folder = renderer.render_a_pdf_from_typst(typst_file_path_in_output_folder)

    # DEBUG: Print file paths
    print("PDF FILE PATH:", pdf_file_path_in_output_folder)

    if os.path.exists(pdf_file_path_in_output_folder):
        return FileResponse(open(pdf_file_path_in_output_folder, "rb"), content_type="application/pdf")
    else:
        return HttpResponse("File not found", status=404)
