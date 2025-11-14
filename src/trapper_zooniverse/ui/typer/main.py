import json
import sys

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from trapper_zooniverse.ZooniverseClient import ZooniverseClient
from trapper_zooniverse.ui.typer.i18n import _, setup_locale
import locale
import os

# --------------------------------------------------------------------------- #
# Localization setup
# --------------------------------------------------------------------------- #

locales_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "locales")
setup_locale(locale.getdefaultlocale()[0] if locale.getdefaultlocale()[0] else "en_GB", locales_dir)

import typer
from typer_config import conf_callback_factory
from trapper_zooniverse.ui.typer.settings import SettingsManager
from trapper_zooniverse.ui.typer.logger import logger, setup_logging
import random
import string
import tempfile
from datetime import datetime
from typing import Annotated, Optional, Any

#
# Typer Subcommands
#

from trapper_zooniverse.ui.typer.commands import config as config_commands
from trapper_zooniverse.ui.typer.commands import logger as logger_commands
from trapper_zooniverse.ui.typer.commands import helpers as helpers_commands
from trapper_zooniverse.ui.typer.commands import reports as reports_commands

def dynaconf_loader(file_path: str) -> dict:
    """
    Load application settings using Dynaconf.

    :param file_path: Full path to the settings file.
    :type file_path: str
    :return: Dictionary containing loaded configuration values.
    :rtype: dict

    Example:
        .. code-block:: python

            settings = dynaconf_loader("/path/to/project.toml")
    """
    try:
        # Check if file_path contains settings
        return json.loads(file_path)
    except (ValueError, TypeError):
        # Read setting file
        settings_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        setting_manager = SettingsManager(settings_dir=Path(settings_dir))
        settings = setting_manager.load_settings(file_name, True, True)
        return settings.as_dict()

# 🔹 Callback base
base_conf_callback = conf_callback_factory(dynaconf_loader)

# 🔹 Callback dinámico que usa otro parámetro (base_path)
def dynamic_dynaconf_callback(ctx: typer.Context, param: typer.CallbackParam, value: Any):
    """
    Typer callback to dynamically load configuration before executing a command.

    This callback loads a Dynaconf configuration based on the current project
    and settings directory, then injects the resulting configuration into
    the Typer context object (`ctx.obj`).

    :param ctx: The current Typer context.
    :type ctx: typer.Context
    :param param: The parameter being processed.
    :type param: typer.CallbackParam
    :param value: The raw parameter value passed to the callback.
    :type value: Any
    :return: Configuration dictionary from Dynaconf.
    :rtype: dict
    """

    if "settings_dir" in ctx.params :
        base_path = ctx.params.get("settings_dir", ".")
        file_path = os.path.join(base_path, ctx.params.get("project", "default"))
    else:
        # Las setting deberían estar ya cargadas
        settings = ctx.obj.get("settings", {}).as_dict()
        file_path = json.dumps(settings, default=str)

    a= base_conf_callback(ctx, param, file_path)

    if ctx.obj is None:
        ctx.obj = {}

    settings = ctx.default_map.copy() if ctx.default_map else {}

    for key, value in ctx.params.items():
        if key == "verbosity":
            if value is None:
                ctx.params[key] = settings["LOGGER"]["loglevel"]

        if key == "log_file":
            if value is None:
                ctx.params[key] = settings["LOGGER"]["filename"]

        if key == "n_images_seq":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE_CONNECTOR"]["upload_collection_n_images_seq"]

        if key == "max_interval":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE_CONNECTOR"]["upload_collection_max_interval"]

        if key == "attempts":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE_CONNECTOR"]["upload_collection_attempts"]

        if key == "delay":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE_CONNECTOR"]["upload_collection_delay"]

        if key == "max_attempts_per_subject":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE_CONNECTOR"]["upload_collection_max_attempts_per_subject"]

        if key == "delay_seconds_per_subject":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE_CONNECTOR"]["upload_collection_delay_seconds_per_subject"]

        if key == "trapper_user":
            if value is None:
                ctx.params[key] = settings["TRAPPER"]["trapper_username"]
        if key == "trapper_url":
            if value is None:
                ctx.params[key] = settings["TRAPPER"]["trapper_url"]

        if key == "trapper_password":
            if value is None:
                ctx.params[key] = settings["TRAPPER"]["trapper_password"]

        if key == "zooniverse_username":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE"]["zooniverse_username"]
        if key == "zooniverse_password":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE"]["zooniverse_password"]
        if key == "zooniverse_project_id":
            if value is None:
                ctx.params[key] = settings["ZOONIVERSE"]["zooniverse_project_id"]

    ctx.obj["settings"] = settings

    return a

# --------------------------------------------------------------------------- #
# App metadata
# --------------------------------------------------------------------------- #

APP_NAME = "trapper-zooniverse"
__version__ = "0.1.0"


import logging
import gettext
from pathlib import Path, PosixPath

from rich.console import Console

def typer_base_path() -> Path:
    return Path(typer.get_app_dir(APP_NAME))

# Asignamos nuestra versión
import trapper_zooniverse.ui.typer.ConfigManager
trapper_zooniverse.ui.typer.ConfigManager.get_base_path = typer_base_path

from trapper_zooniverse.TrapperZooniverseConnector import TrapperZooniverseConnector
from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils
from trapper_client.TrapperClient import TrapperClient

console = Console()
TyperUtils.console = console
logger = logging.getLogger(__name__)
_ = gettext.gettext

# --------------------------------------------------------------------------- #
# Typer CLI definition
# --------------------------------------------------------------------------- #

app = typer.Typer(
    help=_("CLI for uploading images from Trapper to Zooniverse and upload Zooniverse results to Trapper"),
    rich_markup_mode='markdown')

app.add_typer(config_commands.app, name="config")
app.add_typer(logger_commands.app, name="logger")
app.add_typer(helpers_commands.app, name="helpers")
app.add_typer(reports_commands.app, name="reports")

@app.callback()
#@use_yaml_config(default_value=config_manager.ensure_config_file())
def common_setup(
        ctx: typer.Context,
        version: Annotated[Optional[bool], typer.Option(help=_("Show program's version number and exit"))] = None,
        verbosity: Annotated[Optional[int], typer.Option( help=_("Logger level: 0 (error), 1 (info), 2 (debug).")) ] = None,
        log_file: Annotated[Optional[Path], typer.Option( "--logfile",
                help="Path to the log file")] = Path(typer.get_app_dir(APP_NAME))/ "app.log",
        env_file: Annotated[Optional[bool], typer.Option("--env-file", help=_("Load .env file with dotenv"))] = False,

        settings_dir: Annotated[Optional[Path], typer.Option("--settings-dir",
                                help=_("Directory containing settings files"), )] = Path(typer.get_app_dir(APP_NAME)),

        config: Annotated[
            Path,
            typer.Option(
                hidden=True,
                callback=dynamic_dynaconf_callback
            )
        ] = None,

):
    if (version):
        prog = os.path.basename(sys.argv[0])
        TyperUtils.console.print(f"{prog}s {__version__}")
        exit(1)

    ## Load settings --> in project param callback
    settings = ctx.obj["settings"]
    settings_dyn = SettingsManager.load_from_array(settings)
    setup_logging(APP_NAME, verbosity, log_file)

    TyperUtils.home = Path(typer.get_app_dir(APP_NAME))

    ctx.obj = {
        "setting_manager": SettingsManager(settings_dir=Path(settings_dir)),
        "settings": settings_dyn,
        "logger": logger,
        "_": _,
    }

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
        attempts: Annotated[
            int,
            typer.Option("--attempts", help="Number of attempts for upload retries")
        ] = None,
        delay: Annotated[
            int,
            typer.Option("--delay", help="Delay in seconds between retries")
        ] = None,
        max_attempts_per_subject: Annotated[
            int,
            typer.Option("--max-attempts-per-subject", help="Maximum upload attempts per subject")
        ] = None,
        delay_seconds_per_subject: Annotated[
            int,
            typer.Option("--delay-seconds-per-subject", help="Delay between subject uploads (seconds)")
        ] = None,

        config: Annotated[
            Path,
            typer.Option(
                hidden=True,
                callback=dynamic_dynaconf_callback
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

    cp_selected = TyperUtils.select_from_list(results_cp)
    rp_selected = TyperUtils.select_from_list(results_rp)
    TyperUtils.success(f"You selected classification project {cp_selected.name} (ID: {cp_selected.pk}) and research project {rp_selected.name} (ID: {rp_selected.pk})")

    if subjectset_name == None:
        c = trapper_client.collections.get_by_id(collection)
        if len(c.results) == 1:
            c = c.results[0]
            subjectset_name = f"{rp_selected.name}_{rp_selected.pk}_{c.name}_{c.pk}_{datetime.now():%Y-%m}"
        else :
            TyperUtils.fatal(_(f"Collection {collection} not found"))

    logger.debug(_(f"Using subjectset name: {subjectset_name}"))

    zooniverse_client = ZooniverseClient(
        project_id=zooniverse_project_id,
        username=zooniverse_username,
        password=zooniverse_password,
    )

    connector = TrapperZooniverseConnector(zoo=zooniverse_client,trapper=trapper_client)

    connector.upload_collection(subjectset_name, collection, cp_selected.pk, None, n_images_seq,
                                max_interval, attempts, delay,
             max_attempts_per_subject, delay_seconds_per_subject)

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
    ) as progress:

        # Crear tareas "indeterminadas"
        get_media_task = progress.add_task("[cyan]Getting media...", total=None)
        get_observations_task = progress.add_task("[magenta]Getting observations...", total=None)

        def progress_callback(task_name: str, advance: int = 1):
            if task_name == "get_media":
                progress.advance(get_media_task, advance)
            elif task_name == "get_observations":
                progress.advance(get_observations_task, advance)
            # otras tareas como download, upload, etc.

        # Llamas a tu función pasándole el callback
        report = connector.upload_collection(
            subjectset_name,
            collection,
            cp_selected.pk,
            None,
            progress_callback=progress_callback
        )
    """
    results = TyperUtils.run_tasks_with_progress(
        [
            #{
            #    "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
            #    "func": zooniverse_client.connect,
            #    "args": (),
            #},

            {
                "description": _(f"Uploading Trapper collection {collection} to Zooniverse {zooniverse_client.project_id} in subjectset {subjectset_name}"),
                "func": connector.upload_collection,
                "args": (subjectset_name,collection,cp_selected.pk, None, n_images_seq, max_interval, attempts, delay, max_attempts_per_subject, delay_seconds_per_subject),
            }
        ]
    )

    logger.debug(_(f"Upload results: {results[1]}"))

    report = results[1]"""
    results_dir=TyperUtils.get_default_report_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    report_file = results_dir / f"upload_report_{collection}_{cp_selected.pk}_{datetime.now():%Y%m%d_%H%M%S}.yaml"
    report.to_yaml(report_file)
    TyperUtils.display_report2(report)
    TyperUtils.success(_(f"Report saved at: {report_file}"))

@app.command("annotations-upload",
    short_help=_("Upload all annotations from a Zooniverse subject set to a Trapper classification project"),
    help=_("Upload all annotations from a specific Zooniverse subject set into a designated Trapper classification project")
)
def public_annotations(
        ctx: typer.Context,
        collection_id: Annotated[int, typer.Argument(help=("Collection ID"))] = ...,
        subjectset_id: Annotated[int, typer.Argument(help=("Subjectset_ID"))] = ...,
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

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Getting Trapper classification projects by collection {collection_id}"),
                "func": trapper_client.classification_projects.get_by_collection,
                "args": (collection_id,),
            },

            {
                "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
                "func": zooniverse_client.connect,
                "args": (),
            },

            {
                "description": _(f"Getting Zooniverse workflows for subjectset {subjectset_id}"),
                "func": zooniverse_client.workflows.get_by_subjectset,
                "args": (subjectset_id,),
            },
        ]
    )

    results_cp = getattr(results[0], "results", [])
    results_workflows = results[2]

    if not results_cp:
        TyperUtils.fatal(_(f"No classification projects found for collection {collection_id}"))

    cp_selected = TyperUtils.select_from_list(results_cp)

    from types import SimpleNamespace
    wf_selected = TyperUtils.select_from_list([ SimpleNamespace({"id":wf.id, "name": wf.display_name}) for wf in results_workflows ])

    TyperUtils.success(f"You selected classification project {cp_selected.name} (ID: {cp_selected.pk}) and workflow {wf_selected.name} (ID: {wf_selected.id})")

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
        results = TyperUtils.run_tasks_with_progress(
            [
                {
                    "description": _(f"Uploading Zooniverse Annotations to Trapper"),
                    "func": connector.upload_annotations,
                    "args": (subjectset_id, wf_selected.id, collection_id, cp_selected.pk, observations_file, observation_mapping, species_mapping),
                },
            ]
        )
        TyperUtils.success(f"Annotations uploaded to Trapper and saved in {observations_file}")
        report = results[0]
        report_dir=get_default_annotations_upload_reports_dir()
        report_dir.mkdir(parents=True, exist_ok=True)
        report_dir = report_dir / f"annotations_upload_report_{collection_id}_{subjectset_id}_{datetime.now():%Y%m%d_%H%M%S}.yaml"
        TyperUtils.save_yaml(report, PosixPath(report_dir))
        TyperUtils.success(_(f"Report saved at: {report_dir}"))

    except Exception as e:
        TyperUtils.fatal(str(e))

if __name__ == "__main__":
    app()