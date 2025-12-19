import random
import string
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional, Any

import typer
from rich.prompt import Confirm
from trapper_client.TrapperClient import TrapperClient

from trapper_zooniverse.TrapperZooniverseConnector import TrapperZooniverseConnector
from trapper_zooniverse.ZooniverseClient import ZooniverseClient
from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils
from trapper_zooniverse.ui.typer.i18n import _

app = typer.Typer(
    help=_("Includes command to upload medias from Trapper to Zooniverse and import Annotations from Zooniverse to Trapper"),
    short_help=_("Utilities for managing and validating WildIntel data"))

def make_dynaconf_callback(override_mapping: dict | None = None):
    def callback(ctx, param: typer.CallbackParam, value: Any):
        return TyperUtils.dynamic_dynaconf_callback(ctx, param, value, override_mapping=override_mapping)
    return callback

override_mapping = {
    "data_path": ("GENERAL", "data_dir"),
    "tolerance_hours": ("WILDINTEL", "tolerance_hours"),
    "output_path": ("WILDINTEL", "output_dir"),
    "owner": ("WILDINTEL", "owner"),
    "publisher": ("WILDINTEL", "publisher"),
    "coverage": ("WILDINTEL", "coverage"),
    "rp_name": ("WILDINTEL", "rp_name"),
    "user": ("GENERAL", "login"),
    "url": ("GENERAL", "host"),
    "trapper_password": ("TRAPPER", "trapper_password"),
    "trapper_user": ("TRAPPER", "trapper_username"),
    "max_interval": ("ZOONIVERSE_CONNECTOR","upload_collection_max_interval"),
    "n_images_seq": ("ZOONIVERSE_CONNECTOR","upload_collection_n_images_seq"),
    "timezone": ("WILDINTEL","timezone"),
    "ignore_dst": ("WILDINTEL","ignore_dst"),
    "convert_to_utc": ("WILDINTEL","convert_to_utc"),
}

callback_with_override = make_dynaconf_callback(override_mapping)

@app.callback()
def main_callback(ctx: typer.Context,
):
    """
    Typer callback executed before any command in this application.

    Use it to initialize or mutate shared values in ``ctx.obj`` such as
    ``settings``, ``setting_manager``, ``logger`` or ``project``.

    :param ctx: Typer context object.
    :type ctx: typer.Context
    :returns: None
    """
    pass

@app.command("collections-upload",
         short_help=_("Upload all media (images) from a Trapper collection to a Zooniverse subject set"),
         help=_("Upload all media (images) from a specific Trapper collection to a designated Zooniverse subject set"))
#@use_yaml_config(section=["upload_collection"], default_value=config_manager.ensure_config_file())
def upload_collection(
        ctx: typer.Context,
        trapper_url: str = typer.Option(
                    None,
            help=_("Base URL of the Trapper server (e.g., https://trapper.example.org)"),
                ),
                trapper_user: str = typer.Option(
                    None,
                    help=_("Username to authenticate with the Trapper server")
                ),
                trapper_password: str = typer.Option(
                    None,
                    "-p",
                    help=_("Password for the specified user (use only if no access token is provided)")
                ),
                trapper_token: str = typer.Option(
                    None,
                    "--token",
                    "-t",
                    help=_("Access token for the Trapper API (alternative to using a password)"),
                ),

                zooniverse_username: str = typer.Option(
                    None,
                    help=_("Username to authenticate with the Trapper server")
                ),
                zooniverse_password: str = typer.Option(
                    None,
                    help=_("Password for the specified user (use only if no access token is provided)")
                ),

                zooniverse_project_id: str = typer.Option(
                    None,
                    help=_("Password for the specified user (use only if no access token is provided)")
                ),
        collection: Annotated[int, typer.Argument(help=("Collection ID"))] = ...,
        subjectset_name: Annotated[str, typer.Argument(help="Name of the Subject Set to create or use")] = None,
        n_images_seq: Annotated[
            int,
            typer.Option("--n-images-seq", help="Number of images per sequence")
        ] = None,
        max_interval: Annotated[
            int,
            typer.Option("--max-interval", help="Maximum interval between images in a sequence (seconds)")
        ] = None,

        config: Annotated[
            Path,
            typer.Option(
                hidden=True,
                callback=callback_with_override
            )
        ] = None,

) -> None:
    """
    Upload all media collectisubjectson from Trapper to Zooniverse.

    This command uploads media collections from Trapper to a specified Zooniverse project.
    It retrieves collections from Trapper, processes them, and uploads the media files
    to Zooniverse, creating or updating subject sets as necessary.

    Args:
        ctx (typer.Context): The Typer context object, used to share information across commands.

    """
    #trapper_client = ctx.obj["trapper_client"]
    #zooniverse_client = ctx.obj["zooniverse_client"]
    #connector:TrapperZooniverseConnector = ctx.obj["connector"]
    logger = ctx.obj["logger"]
    _ = ctx.obj["_"]

    logger.debug(f"Uploading collection {collection} to Zooniverse project {zooniverse_project_id}")
    logger.debug(locals())

    trapper_client = TrapperClient(access_token=trapper_token,user_password=trapper_password,
                                   base_url=trapper_url, user_name= trapper_user)

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Getting Trapper classification projects by collection {collection}"),
                "func": trapper_client.classification_projects.get_by_collection,
                "args": (collection,),
            },

            {
                "description": _(f"Getting Trapper research projects by collection {collection}"),
                "func": trapper_client.research_projects.get_by_collection,
                "args": (collection,),
            },

        ]
    )

    results_cp = getattr(results[0], "results", [])
    results_rp = getattr(results[1], "results", [])

    if not results_cp:
        TyperUtils.fatal(_(f"No classification projects found for collection {collection}"))
        return None

    if not results_rp:
        TyperUtils.fatal(_(f"No research projects found for collection {collection}"))
        return None

    logger.debug(_(f"Found {len(results[0].results)} classification projects and {len(results[1].results)} research projects for collection {collection}"))

    cp_selected,nothing = TyperUtils.select_from_list(results_cp)
    rp_selected,nothing = TyperUtils.select_from_list(results_rp)
    TyperUtils.success(f"You selected classification project {cp_selected.name} (ID: {cp_selected.pk}) and research project {rp_selected.name} (ID: {rp_selected.pk})")

    medias = trapper_client.media.get_by_collection(cp_selected.pk,collection)

    hay_privados = any(not media.filePublic for media in medias.results)

    if hay_privados:
        continue_process = Confirm.ask(
            f"Collection {collection} contains private items; they will be removed from any selection process."
            f" You can make a collection’s media public by setting the collection to public and enabling the Public "
            f"resources option. After the upload process, you can set the images back to "
            f"private by changing the collection’s visibility to private. Do you want to continue?"
        )

        if not continue_process:
            TyperUtils.warning("Operation canceled by the user.")
            raise typer.Exit(code=1)

    if subjectset_name == None:
        c = trapper_client.collections.get_by_id(collection)
        if len(c.results) == 1:
            c = c.results[0]
            subjectset_name = f"{rp_selected.name}_{rp_selected.pk}_{c.name}_{c.pk}_{datetime.now():%Y-%m}"
        else :
            TyperUtils.fatal(_(f"Collection {collection} not found"))

    logger.debug(f"Using subjectset name: {subjectset_name}")

    zooniverse_client = ZooniverseClient(
        project_id=zooniverse_project_id,
        username=zooniverse_username,
        password=zooniverse_password,
    )

    connector = TrapperZooniverseConnector(zoo=zooniverse_client,trapper=trapper_client)
    import trapper_zooniverse.ui.typer.zooniverse

    try:
        report = trapper_zooniverse.ui.typer.zooniverse.upload_collection(
            tzc = connector,
            subjectset_name=subjectset_name,
            collection=collection,
            cproject=cp_selected.pk,
            n_images_seq=n_images_seq,
            max_interval=max_interval,
            attempts=5,
            delay=15,
            max_attempts_per_subject=5,
            delay_seconds_per_subject=15,
        )

        TyperUtils.success(f"Collection {collection} uploaded to Zooniverse subject set '{subjectset_name}'")
        report_file = TyperUtils.report_save(report)
        TyperUtils.console.print("\n")
        TyperUtils.report_display(report)
        TyperUtils.success(_(f"Report saved at: {report_file}"))

    except Exception as e:
        raise e
        TyperUtils.error(f"Error uploading collection {collection}: {str(e)}")

@app.command("annotations-upload",
    short_help=_("Upload all annotations from a Zooniverse subject set to a Trapper classification project"),
    help=_("Upload all annotations from a specific Zooniverse subject set into a designated Trapper classification project")
)
def public_annotations(
        ctx: typer.Context,
        collection_id: Annotated[int, typer.Argument(help=("Collection ID"))] = None,
        subjectset_id: Annotated[int, typer.Argument(help=("Subjectset_ID"))] = None,
        wf_id: Annotated[int, typer.Argument(help=("Workflow id"))] = None,
        observations_file: Annotated[
            Optional[Path],
            typer.Argument(help="Optional path to a CSV file where observations will be saved.")
        ] = None,

        observation_mapping: Annotated[typer.FileText, typer.Option(help=_("CSV File containing mapping observations"))] = None,
        species_mapping: Annotated[typer.FileText, typer.Option(help=_("CSV file containing mapping species"))] = None,
):

    trapper_client = ctx.obj["trapper_client"]
    zooniverse_client = ctx.obj["zooniverse_client"]
    connector:TrapperZooniverseConnector = ctx.obj["connector"]
    logger = ctx.obj["logger"]
    _ = ctx.obj["_"]

    if collection_id == None:
        collections = trapper_client.collections.get_all()
        col_selected,sel_index = TyperUtils.select_from_list(collections.results,
                                            title=_("Select a Collection"),
                                            prompt_msg=_("Please select the index of the Trapper collection whose images "
                                                         "you want to classify"))
    else:
        col_selected = trapper_client.collections.get_by_id(collection_id).results[0]

    from types import SimpleNamespace

    if subjectset_id == None:
        subjectsets = zooniverse_client.subjectsets.get_all()
        simplified_list = [SimpleNamespace(pk=ss.raw["id"], name=ss.raw["display_name"]) for ss in subjectsets]
        ss_selected,sel_index = TyperUtils.select_from_list(simplified_list,
                                    title="Select a Subject Set",
                                    prompt_msg="Please select the index of the Zooniverse subject set used to upload the "
                                                 "collection selected in the previous step"
                            )
        ss_selected = subjectsets[sel_index]
    else:
        ss_selected = zooniverse_client.subjectsets.get_by_id(subjectset_id)

    if wf_id == None:
        workflows = zooniverse_client.workflows.get_all()
        simplified_list = [SimpleNamespace(pk=ss.raw["id"], name=ss.raw["display_name"]) for ss in workflows]
        wf_selected,sel_index = TyperUtils.select_from_list(simplified_list,
                                                        title="Select a Workflow",
                                                        prompt_msg="Please select the index of the Zooniverse workflow "
                                                                     "that contains annotations for the subjects in the"
                                                                     " subject set selected in the previous step")
        wf_selected = workflows[sel_index]
    else:
        wf_selected = zooniverse_client.workflows.get_by_id(wf_id)

    cps = trapper_client.classification_projects.get_by_collection(col_selected.pk)

    if not cps or len(cps.results) == 0:
        TyperUtils.fatal(_(f"No classification projects found for collection {col_selected.name} {col_selected.pk}"))

    cp_selected,sel_index = TyperUtils.select_from_list(cps.results, "Select a Classification Project")

    TyperUtils.success(f"You selected classification project {cp_selected.name} (ID: {cp_selected.pk}) "
                        f", collection {col_selected.name} (ID: {col_selected.pk})"
                       f", subject set {ss_selected.raw['display_name']} (ID: {ss_selected.id})"
                       f" and workflow {wf_selected.raw["display_name"]} (ID: {wf_selected.raw["id"]})")

    ### connector

    if observations_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        temp_file = tempfile.NamedTemporaryFile(
            prefix=f"annotations_{timestamp}_",
            suffix=f"_{suffix}.csv",
            delete=False  # <- clave: no se borra al cerrar
        )
        observations_file = Path(temp_file.name)

    try:
        import trapper_zooniverse.ui.typer.zooniverse

        results = trapper_zooniverse.ui.typer.zooniverse.public_annotations(connector,
            cp_id=cp_selected.pk,
            collection_id=col_selected.pk,
            subjectset_id=ss_selected.id,
            wf_id=wf_selected.id,
            observations_file=observations_file
        )
        url = f"{connector.trapper.base_url}media_classification/classification/import/"
        TyperUtils.success(f"Annotations file saved in {observations_file}. Uppload it to Trapper using {url}")
        report_dir=TyperUtils.report_save(results)
        TyperUtils.success(_(f"Report saved at: {report_dir}"))
        TyperUtils.report_display(results)

    except Exception as e:
        TyperUtils.fatal(str(e))
