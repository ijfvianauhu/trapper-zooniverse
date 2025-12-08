import json
import sys

import requests
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
from trapper_zooniverse.ui.typer.settings import SettingsManager, Settings
from trapper_zooniverse.ui.typer.logger import logger, setup_logging
import random
import string
import tempfile
from datetime import datetime
from typing import Annotated, Optional, Any, Literal

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
        #settings = setting_manager.load_settings(file_name, True, True)
        settings:Settings = setting_manager.load_settings_pydantic(file_name, True, True)

        return settings.model_dump()

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
        file_path = os.path.join(base_path, ctx.params.get("configuration", "default"))
    else:
        settings = ctx.obj.get("settings", {}).model_dump() if ctx.obj and "settings" in ctx.obj else {}
        file_path = json.dumps(settings, default=str)

    results= base_conf_callback(ctx, param, file_path)

    if ctx.obj is None:
        ctx.obj = {}

    settings = ctx.default_map.copy() if ctx.default_map else {}

    mapping = {
        "verbosity" : ("LOGGER", "loglevel"),
        "log_file" : ("LOGGER", "filename"),
        "trapper_user": ("TRAPPER", "trapper_username"),
        "trapper_url": ("TRAPPER", "trapper_url"),
        "trapper_token": ("TRAPPER", "trapper_token"),
        "trapper_password": ("TRAPPER", "trapper_password"),
        "zooniverse_username": ("ZOONIVERSE", "zooniverse_username"),
        "zooniverse_password": ("ZOONIVERSE", "zooniverse_password"),
        "zooniverse_project_id": ("ZOONIVERSE", "zooniverse_project_id"),
        "n_images_seq": ("ZOONIVERSE_CONNECTOR", "upload_collection_n_images_seq"),
        "max_interval": ("ZOONIVERSE_CONNECTOR", "upload_collection_max_interval"),
        "attempts": ("ZOONIVERSE_CONNECTOR", "upload_collection_attempts"),
        "delay": ("ZOONIVERSE_CONNECTOR", "upload_collection_delay"),
        "max_attempts_per_subject": ("ZOONIVERSE_CONNECTOR", "upload_collection_max_attempts_per_subject"),
        "delay_seconds_per_subject": ("ZOONIVERSE_CONNECTOR", "upload_collection_delay_seconds_per_subject"),
    }

    for param_name in ctx.params:
        if ctx.params[param_name] is None and param_name in mapping:
            section, key = mapping[param_name]
            ctx.params[param_name] = settings[section][key]

    ctx.obj["settings"] =  Settings(**settings)

    return results

# --------------------------------------------------------------------------- #
# App metadata
# --------------------------------------------------------------------------- #

APP_NAME = "trapper-zooniverse"
__version__ = "0.1.0"

import logging
import gettext
from pathlib import Path

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

def get_latest_github_release(owner: str, repo: str) -> str:
    """
    Returns the tag name of the latest GitHub release.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    response = requests.get(url)
    if response.status_code != 200:
        TyperUtils.error(f"GitHub API request failed with status {response.status_code}")
        return None
    data = response.json()
    return data["tag_name"]


def is_newer_version(current_version: str, latest_version: str) -> bool:
    """
    Returns True if latest_version is newer than current_version.
    Assumes versions are in semantic versioning format: vMAJOR.MINOR.PATCH
    """

    def parse_version(v: str):
        return tuple(int(x) for x in v.lstrip("v").split("."))

    return parse_version(latest_version) > parse_version(current_version)


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
        configuration: Annotated[Optional[str], typer.Option(
            help=_("Configuration name to use (without extension). E.g., 'development', 'production', etc.") )
        ] = "default",
        trapper_url: str = typer.Option(
            None,
            help=_("Base URL of the Trapper server (e.g., https://trapper.example.org)"),
        ),
        trapper_user: str = typer.Option(
            None,
            help=_("Username for Trapper authentication. Required unless an access token is provided")
        ),
        trapper_password: str = typer.Option(
            None,
            help=_("Password for the specified Trapper user. Only needed if no access token is used.")
        ),
        trapper_token: str = typer.Option(
            None,
            help=_("Access token for the Trapper API. Can be used instead of username/password."),
        ),

        zooniverse_username: str = typer.Option(
            None,
            help=_("Username to authenticate with Zooniverse.")
        ),
        zooniverse_password: str = typer.Option(
            None,
            help=_("Password for the specified Zooniverse user")
        ),

        zooniverse_project_id: str = typer.Option(
            None,
            help=_("ID of the Zooniverse project to connect to.")
        ),

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
    settings:Settings = ctx.obj["settings"]
    #settings_dyn = SettingsManager.load_from_array(settings)
    setup_logging(APP_NAME, verbosity, log_file)

    TyperUtils.home = Path(typer.get_app_dir(APP_NAME))
    TyperUtils.logger = logger

    zoo_client = ZooniverseClient(
        project_id=zooniverse_project_id,
        username=zooniverse_username,
        password=zooniverse_password,
    )
    trapper_client = TrapperClient(
        access_token=trapper_token,
        user_password=trapper_password,
        base_url=str(trapper_url),
        user_name=trapper_user,
    )

    connector = TrapperZooniverseConnector(zoo=zoo_client,trapper=trapper_client)

    ctx.obj = {
        "setting_manager": SettingsManager(settings_dir=Path(settings_dir)),
        "settings": settings,
        "configuration": configuration,
        "logger": logger,
        "trapper_client": trapper_client,
        "zooniverse_client": zoo_client,
        "connector": connector,
        "_": _,
    }

    latest_version = get_latest_github_release("ijfvianauhu", APP_NAME)
    if latest_version and  is_newer_version(__version__, latest_version):
        TyperUtils.warning(
            _(
                f"A newer version is available: {latest_version}. You can download it from "
                f"https://github.com/ijfvianauhu/trapper-zooniverse"
            )
        )
    else:
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

    cp_selected,_ = TyperUtils.select_from_list(results_cp)
    rp_selected,_ = TyperUtils.select_from_list(results_rp)
    TyperUtils.success(f"You selected classification project {cp_selected.name} (ID: {cp_selected.pk}) and research project {rp_selected.name} (ID: {rp_selected.pk})")

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

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
    ) as progress:

        # Registro dinámico de tareas
        task_registry = {}

        def get_or_create_task(task_name: str, total=None, description=None):
            """
            Crea la tarea si no existe. Si existe, la devuelve.
            """
            if task_name not in task_registry:
                desc = description or task_name.replace("_", " ").title()
                task_id = progress.add_task(desc, total=total)
                task_registry[task_name] = task_id
            return task_registry[task_name]

        def progress_callback(
            task_name: str,
            state: str,
            advance: int = 1,
            total: int | None = None,
            description: str | None = None,
            set_total: bool = False,
            item_name:str = None,
            item_status: Literal["start", "end", "fail"] | None = None,
        ):
            """
            Callback flexible que soporta:
            - tareas determinadas   (con total)
            - tareas indeterminadas (total=None)
            - cambio de total a posteriori
            - añadir descripciones personalizadas
            """
            task_id = get_or_create_task(task_name, total, description)

            # --- Estados ---
            if state == "start":
                new_desc = f"🟢  {description or task_name.replace('_', ' ').title()}"
                progress.update(task_id, description=new_desc)

            elif state == "end":
                new_desc = f"✔️  {description or task_name.replace('_', ' ').title()}"
                progress.update(task_id, completed=progress.tasks[task_id].total or 1,
                                description=new_desc)
                progress.stop_task(task_id)

            elif state == "fail":
                new_desc = f"❌  {description or task_name.replace('_', ' ').title()}"
                progress.update(task_id, description=new_desc)
                return  # no seguir avanzando

            if set_total and total is not None:
                progress.update(task_id, total=total)

            if item_name is not None:
                if item_status == "start":
                    progress.log(f"[yellow]→ Starting processing item {item_name}")
                elif item_status == "end":
                    progress.log(f"[green]✓ Finished processing item {item_name}")
                elif item_status == "fail":
                    progress.log(f"[red]✗ Failed processing {item_name}")

            progress.advance(task_id, advance)

        # Ejecuta tu función pasándole el callback
        report = connector.upload_collection(
            subjectset_name=subjectset_name,
            collection=collection,
            classification_project=cp_selected.pk,
            uploaded_file=None,
            n_images_seq=n_images_seq,
            max_interval=max_interval,
            attempts=attempts,
            delay=delay,
            max_attempts_per_subject=max_attempts_per_subject,
            delay_seconds_per_subject=delay_seconds_per_subject,
            progress_callback=progress_callback
        )

    report_file = TyperUtils.report_save(report)
    TyperUtils.console.print("\n")
    TyperUtils.report_display(report)
    TyperUtils.success(_(f"Report saved at: {report_file}"))

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
        results = connector.upload_annotations(ss_selected.id, wf_selected.id, col_selected.pk, cp_selected.pk, observations_file,
                                                None, None)
        #results = TyperUtils.run_tasks_with_progress(
        #    [
        #        {
        #            "description": _(f"Uploading Zooniverse Annotations to Trapper"),
        #            "func": connector.upload_annotations,
        #            "args": (subjectset_id, wf.id, collection_id, cp_selected.pk, observations_file, observation_mapping, species_mapping),
        #        },
        #    ]
        #)
        TyperUtils.success(f"Annotations uploaded to Trapper and saved in {observations_file}")
        report = results
        report_dir=TyperUtils.report_save(report)
        TyperUtils.success(_(f"Report saved at: {report_dir}"))

    except Exception as e:
        TyperUtils.fatal(str(e))


if __name__ == "__main__":
    app()