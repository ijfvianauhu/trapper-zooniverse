import gzip
import random
import shutil
import string
import tempfile
import time

from datetime import datetime
from typing import Annotated, Optional, Any

import typer
import logging
import gettext
from pathlib import Path, PosixPath

import yaml
from rich.table import Table
from rich.console import Console
from typer_config import use_yaml_config

from trapper_zooniverse.ui.typer.ZooUtils import ZooUtils


def typer_base_path() -> Path:
    return Path(typer.get_app_dir(APP_NAME))

from trapper_zooniverse.i18n import setup_i18n, _

# Asignamos nuestra versión
import trapper_zooniverse.ui.typer.ConfigManager
trapper_zooniverse.ui.typer.ConfigManager.get_base_path = typer_base_path

from trapper_zooniverse.ui.typer.ConfigManager import ConfigManager, AppConfig
from trapper_zooniverse.Reports import Report
from trapper_zooniverse.Schemas import UploadAnnotationsReport
from trapper_zooniverse.TrapperZooniverseConnector import TrapperZooniverseConnector
from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils
from trapper_client.TrapperClient import TrapperClient
from trapper_zooniverse.ZooniverseClient import ZooniverseClient

console = Console()
TyperUtils.console = console
logger = logging.getLogger(__name__)
_ = gettext.gettext


APP_NAME="trapper-zooniverse"
# Inicializar el gestor de configuración
config_manager = ConfigManager(Path(typer.get_app_dir(APP_NAME)) / "config.yaml")

app = typer.Typer(help=_("CLI for uploading images from Trapper to Zooniverse and upload Zooniverse results to Trapper"), rich_markup_mode='markdown')

def get_default_upload_reports_dir() -> Path:
    app_dir = Path(typer.get_app_dir(APP_NAME))
    results_dir = app_dir / "upload_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir

def get_default_annotations_upload_reports_dir() -> Path:
    app_dir = Path(typer.get_app_dir(APP_NAME))
    results_dir = app_dir / "annotations_upload_reports"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir

def choose_report_file(results_dir:Path, filename:str = None) -> Path:

    # Si el usuario no pasa ningún archivo → mostrar el último
    if filename is None:
        yaml_files = sorted(
            results_dir.glob("*.yaml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if not yaml_files:
            TyperUtils.fatal(f"No reports found in: {results_dir}")

        target_file = yaml_files[0]
        TyperUtils.info(_(f"Showing latest report: {target_file.name}"))
    else:
        target_file = results_dir / filename
        if not target_file.exists():
            TyperUtils.fatal(f"Report file not found:{target_file}")

    return target_file

def init_logger(logfilename: Path, loglevel:str):
    """Inicializa el logger y la configuración de i18n."""
    global logger

    logging.basicConfig(
        level=loglevel.upper(),
        filename=logfilename,
        filemode="a",
        format="%(asctime)s [%(levelname)s] %(message)s",
        force=True,
    )

    logger = logging.getLogger(__name__)
    logger.debug(f"Logging level: {loglevel}")

    return logger

def init_locale(lang:str, dir:Path):
    locale_dir = Path(__file__).resolve().parents[2] / "locales"
    setup_i18n(lang,locale_dir)

@app.callback()
@use_yaml_config(default_value=config_manager.ensure_config_file())
def common_setup(
        ctx: typer.Context,
        logfilename: Annotated[Path, typer.Option()] = None,
        loglevel: Annotated[str, typer.Option()] = None,
        lang: Annotated[str, typer.Option()] = None,
        trapper_username: Annotated[str, typer.Option()] = None,
        trapper_password: Annotated[str, typer.Option()] = None,
        trapper_url: Annotated[str, typer.Option()] = None,
        trapper_token: Annotated[str, typer.Option()] = None,
        zooniverse_username: Annotated[str, typer.Option()] = None,
        zooniverse_password: Annotated[str, typer.Option()] = None,
        zooniverse_project_id: Annotated[str, typer.Option()] = None,
):
    config:AppConfig= config_manager.load_config()
    init_logger(config.logger.logfilename, config.logger.loglevel)
    init_locale(config.i18n.language, config.i18n.locale_dir)

    trapper_client=TrapperClient(
        access_token= config.login.trapper_access_token.get_secret_value(),
        base_url=str(config.login.trapper_url),
        user_name=config.login.trapper_username,
        user_password=config.login.trapper_password.get_secret_value(),
    )

    zooniverse_client=ZooniverseClient(
        project_id= config.login.zooniverse_project_id,
        username= config.login.zooniverse_username,
        password= config.login.zooniverse_password.get_secret_value(),
    )

    connector = TrapperZooniverseConnector(zooniverse_client, trapper_client)

    ctx.obj = {
        "logger": logging.getLogger(__name__),
        "_": _,
        "trapper_client": trapper_client,
        "zooniverse_client": zooniverse_client,
        "connector":connector,
        "config":config
    }

@app.command("logger", help=_("Show log file content"), short_help=_("Show log file content"))
def show_logger(
    follow: bool = typer.Option(False, help=_("Follow file content (like tail -f)")),
):
    config:AppConfig= config_manager.load_config()
    log_path = config.logger.logfilename

    if log_path.exists():
        with log_path.open("r") as f:
            if follow:
                # Ir al final del archivo
                f.seek(0, 2)
            else:
                # Mostrar todo el contenido existente
                for line in f:
                    print(line, end="")
                exit()
            try:
                while True:
                    line = f.readline()
                    if line:
                        print(line, end="")  # `end=""` para no duplicar saltos de línea
                    else:
                        time.sleep(0.5)  # Espera antes de volver a leer
            except KeyboardInterrupt:
                TyperUtils.info(_("\nStopped following the log."))
    else:
        TyperUtils.fatal(_(f"Log file not found: {log_path}"))

@app.command("logger-archive", help=_("Compress the log file and remove the original"), short_help=_("Compress and archive log"))
def logger_archive():
    # Cargar configuración

    config: AppConfig = config_manager.load_config()
    log_path = config.logger.logfilename

    if not log_path.exists():
        TyperUtils.fatal(_(f"Log file not found: {log_path}"))

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = log_path.with_name(f"{log_path.stem}_{timestamp}{log_path.suffix}.gz")

    with log_path.open("rb") as f_in, gzip.open(archive_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    log_path.unlink()

    TyperUtils.success(_(f"Log archived to: {archive_path}"))

@app.command("config", help=_("Show current configuration"), short_help=_("Show current configuration"))
def show_config():
    try:
        config = config_manager.load_config()
        TyperUtils.display_config_table(config)
    except Exception as e:
        TyperUtils.fatal(str(e))

@app.command("config-set", help=_("Set a configuration parameter"), short_help=_("Set a configuration parameter"))
def set_config(key: str, value: str):
    # Permite acceder a claves anidadas tipo "login.trapper_password"
    keys = key.split(".")
    update_dict: dict[str, Any] = value

    # Construimos el diccionario anidado recursivamente
    for k in reversed(keys):
        update_dict = {k: update_dict}

    config_manager.update_config(**update_dict)

    TyperUtils.success(_(f"Configuration updated in {config_manager.config_file}"))

@app.command(help=_("Test the login form"), short_help=_("Test the login form"))
@use_yaml_config(section=["login"], default_value=config_manager.ensure_config_file())
def login(
        ctx: typer.Context,
        trapper_username: Annotated[str, typer.Option(help=("Usernane"))] = ...,
        trapper_password: Annotated[str, typer.Option(help=("User passwod"))] = ...,
        trapper_url: Annotated[str, typer.Option(help="Trapper url.")] = ...,
        zooniverse_username: Annotated[str, typer.Option(help=("Zooniverse Usernane"))] = ...,
        zooniverse_password: Annotated[str, typer.Option(help=("Zooniverse User passwod"))] = ...,
        zooniverse_project_id: Annotated[str, typer.Option(help="Zooniverse project ID")] = ...,
):
    TyperUtils.info(_("Starting login test"))
    trapper_client = ctx.obj["trapper_client"]
    zooniverse_client = ctx.obj["zooniverse_client"]
    logger.debug(locals())

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Login to trapper {trapper_url}"),
                "func" : trapper_client.collections.get_all,
                "args": (),
            },

            {
                "description": _(f"Login to Zooniverse {zooniverse_project_id}"),
                "func": zooniverse_client.connect,
                "args": (),
            }

        ]
    )

@app.command("collections",
    short_help=_("Retrieve all collections from trapper"),
    help=_("This command allows users to fetch collections from trapper.")
)
def collections_get_all(
        ctx: typer.Context
) -> None:
    """
    Retrieve all collections based on optional query parameters.

    This command allows users to fetch collections from the database.
    Query parameters can be provided to filter results, and the output can
    optionally be exported to a CSV file.

    Args:
        ctx (typer.Context): The Typer context object, used to share information across commands.

    Returns:
        None: Prints the collections  details to the CLI output
    """

    trapper_client = ctx.obj["trapper_client"]
    logger = ctx.obj["logger"]
    _ = ctx.obj["_"]

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Retrieving collection from Trapper"),
                "func": trapper_client.collections.get_all,
                "args": (),
            },
        ]
    )

    logger.info(f"Retrieved {len(results[0].results)} collections")
    TyperUtils.json2Table(results[0], title="Collections", columns=["pk","name","description","owner"])

@app.command("collections-upload",
    short_help=_("Upload all media collection from Trapper to Zooniverse"),
    help=_("Upload all media collection from Trapper to Zooniverse")
)
@use_yaml_config(section=["upload_collection"], default_value=config_manager.ensure_config_file())
def upload_collection(
        ctx: typer.Context,
        collection: Annotated[int, typer.Argument(help=("Collection ID"))] = ...,
        subjectset_name: Annotated[str, typer.Argument(help="Name of the Subject Set to create or use")] = None,
        n_images_seq: Annotated[
            int,
            typer.Option("--n-images-seq", help="Number of images per sequence")
        ] = ...,
        max_interval: Annotated[
            int,
            typer.Option("--max-interval", help="Maximum interval between images in a sequence (seconds)")
        ] = ...,
        attempts: Annotated[
            int,
            typer.Option("--attempts", help="Number of attempts for upload retries")
        ] = None,
        delay: Annotated[
            int,
            typer.Option("--delay", help="Delay in seconds between retries")
        ] = ...,
        max_attempts_per_subject: Annotated[
            int,
            typer.Option("--max-attempts-per-subject", help="Maximum upload attempts per subject")
        ] = ...,
        delay_seconds_per_subject: Annotated[
            int,
            typer.Option("--delay-seconds-per-subject", help="Delay between subject uploads (seconds)")
        ] = ...,
) -> None:
    """
    Upload all media collectisubjectson from Trapper to Zooniverse.

    This command uploads media collections from Trapper to a specified Zooniverse project.
    It retrieves collections from Trapper, processes them, and uploads the media files
    to Zooniverse, creating or updating subject sets as necessary.

    Args:
        ctx (typer.Context): The Typer context object, used to share information across commands.

    """
    trapper_client = ctx.obj["trapper_client"]
    zooniverse_client = ctx.obj["zooniverse_client"]
    connector:TrapperZooniverseConnector = ctx.obj["connector"]
    logger = ctx.obj["logger"]
    _ = ctx.obj["_"]

    logger.debug(f"Uploading collection {collection} to Zooniverse project {zooniverse_client.project_id}")
    logger.debug(locals())

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

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
                "func": zooniverse_client.connect,
                "args": (),
            },

            {
                "description": _(f"Uploading Trapper collection {collection} to Zooniverse {zooniverse_client.project_id} in subjectset {subjectset_name}"),
                "func": connector.upload_collection,
                "args": (subjectset_name,collection,cp_selected.pk, None, n_images_seq, max_interval, attempts, delay, max_attempts_per_subject, delay_seconds_per_subject),
            }
        ]
    )

    logger.debug(_(f"Upload results: {results[1]}"))

    report = results[1]
    results_dir=get_default_upload_reports_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    report_file = results_dir / f"upload_report_{collection}_{cp_selected.pk}_{datetime.now():%Y%m%d_%H%M%S}.yaml"
    report.to_yaml(report_file)
    TyperUtils.display_report2(report)
    TyperUtils.success(_(f"Report saved at: {report_file}"))

@app.command("collections-upload-reports", help=_("List all upload reports"), short_help=_("List upload reports"))
def upload_reports():
    """
    List all YAML upload reports saved in the same directory as the configuration file.
    """
    results_dir = get_default_upload_reports_dir()
    TyperUtils.print_reports_in_directory(results_dir)

@app.command("collections-upload-report", help=_("Show details of an upload report"), short_help=_("Show an upload report"))
def upload_report(
    filename: Annotated[
        str,
        typer.Argument(help=_("Name of the YAML report file to display (optional)"))
    ] = None,
):
    """
    Show details of an upload report stored in the results/ directory.
    If no filename is given, the most recent report will be shown.
    """
    results_dir = get_default_upload_reports_dir()
    target_file = choose_report_file(results_dir, filename)
    report = Report.from_yaml(target_file)
    TyperUtils.display_report2(report, True)

@app.command("subjectsets",
    help=_("Retrieve all subset_sets from Zooniverse"),
    short_help=_("Retrieve all subset_sets from Zooniverse"))
def subset_sets(
        ctx: typer.Context,
        with_exports: Annotated[bool, typer.Option(help="Only show subjetsts with exports")] = False,
):
    # TyperUtils.info(_("Starting login test"))
    zooniverse_client = ctx.obj["zooniverse_client"]

    tasks = []

    tasks.append(
        {
            "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
            "func" : zooniverse_client.connect,
            "args": (),
        }
    )

    if not with_exports:
        tasks.append(
            {
                "description": _(f"Getting subjectsets from Zooniverse {zooniverse_client.project_id}"),
                "func": zooniverse_client.subjectsets.get_all,
                "args": (),
            }
        )
    else:
        tasks.append(
                {
                    "description": _(f"Getting subjectssets with exports from Zooniverse {zooniverse_client.project_id}"),
                    "func": zooniverse_client.subjectsets.with_exports,
                    "args": (),
                }
            )
    results = TyperUtils.run_tasks_with_progress(tasks)
    ZooUtils.show_subject_sets(results[1])

@app.command("subjectsets-get",
    help=_("Retrieve one subset_set from Zooniverse"),
    short_help=_("Retrieve one subset_set from Zooniverse"))
def subset_sets_get_by_id(
        ctx: typer.Context,
        id: Annotated[int, typer.Argument(help=_("Subject Set  ID"))] = ...,
        raw: Annotated[bool, typer.Option(help="Only show subjetsts with exports")] = False,
):
    zooniverse_client = ctx.obj["zooniverse_client"]

    tasks = []

    tasks.append(
        {
            "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
            "func" : zooniverse_client.connect,
            "args": (),
        }
    )
    tasks.append(
            {
                "description": _(f"Getting subjectsset {id} Zooniverse {zooniverse_client.project_id}"),
                "func": zooniverse_client.subjectsets.get_by_id,
                "args": (id,),
            }
        )
    results = TyperUtils.run_tasks_with_progress(tasks)

    if raw:
        TyperUtils.print_as_json([results[1]])
    else:
        ZooUtils.show_subject_set(results[1])

@app.command("subjectsets-get-by-workflow",
    help=_("Retrieve subset sets linked to a workflow"),
    short_help=_("Retrieve subset sets linked to a workflow"))
def subset_sets_get_by_workflow(
        ctx: typer.Context,
        id: Annotated[int, typer.Argument(help=_("Work flow ID"))] = ...,
):
    zooniverse_client = ctx.obj["zooniverse_client"]

    tasks = []

    tasks.append(
        {
            "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
            "func" : zooniverse_client.connect,
            "args": (),
        }
    )
    tasks.append(
            {
                "description": _(f"Getting subjectsset {id} Zooniverse {zooniverse_client.project_id}"),
                "func": zooniverse_client.subjectsets.get_subject_sets_from_workflow,
                "args": (id,),
            }
        )

    results = TyperUtils.run_tasks_with_progress(tasks)
    ZooUtils.show_subject_sets(results[1])

@app.command("subjects-get",
    help=_("Retrieve subject"),
    short_help=_("Retrieve subject"))
def subjects(
        ctx: typer.Context,
        id: Annotated[int, typer.Argument(help=("Collection ID"))] = ...,
        raw: Annotated[bool, typer.Option(help="Only show subjetsts with exports")] = False,
):
    # TyperUtils.info(_("Starting login test"))
    zooniverse_client = ctx.obj["zooniverse_client"]

    try:
        results = TyperUtils.run_tasks_with_progress(
            [
                {
                    "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
                    "func" : zooniverse_client.connect,
                    "args": (),
                },

                {
                    "description": _(f"Getting subject from Zooniverse {zooniverse_client.project_id}, subjectset {id}"),
                    "func": zooniverse_client.subjects.get_by_id,
                    "args": (id,),
                }

            ]
        )

        if raw:
            TyperUtils.print_as_json([results[1]])
        else:
            ZooUtils.show_subject(results[1], title="Subjects")
    except Exception as e:
        TyperUtils.error(str(e))

@app.command("subjects-by-subjectset",
    help=_("Retrieve all subjects from Zooniverse"),
    short_help=_("Retrieve all subset_sets from Zooniverse"))
def subjects_by_subjectset(
        ctx: typer.Context,
        subjectset_id: Annotated[int, typer.Argument(help=("Collection ID"))] = ...,
):
    # TyperUtils.info(_("Starting login test"))
    zooniverse_client = ctx.obj["zooniverse_client"]

    try:
        results = TyperUtils.run_tasks_with_progress(
            [
                {
                    "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
                    "func" : zooniverse_client.connect,
                    "args": (),
                },

                {
                    "description": _(f"Getting subjects from Zooniverse {zooniverse_client.project_id}, subjectset {subjectset_id}"),
                    "func": zooniverse_client.subjects.get_by_subjectset,
                    "args": (subjectset_id,),
                }

            ]
        )

        ZooUtils.show_subjects(results[1], title="Subjects")
    except Exception as e:
        TyperUtils.error(str(e))

@app.command("workflows",
    short_help=_("Retrieve all workflows for a project from Zooniverse"),
    help=_("Retrieve all workflows for a project from Zooniverse")
)
def workflows_get_all(
        ctx: typer.Context,
):
    """
    Retrieve all collections based on optional query parameters.

    This command allows users to fetch collections from the database.
    Query parameters can be provided to filter results, and the output can
    optionally be exported to a CSV file.

    Args:
        ctx (typer.Context): The Typer context object, used to share information across commands.

    Returns:
        None: Prints the collections  details to the CLI output
    """

    zooniverse_client = ctx.obj["zooniverse_client"]
    logger = ctx.obj["logger"]
    _ = ctx.obj["_"]

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Retrieving workflows from Zooniverse project {zooniverse_client.project_id}"),
                "func": zooniverse_client.workflows.get_all,
                "args": (),
            },
        ]
    )
    logger.info(f"Retrieved {len(results[0])} workflows")
    ZooUtils.show_workflows(results[0])

@app.command("workflows-get",
    short_help=_("Retrieve all workflows for a project from Zooniverse"),
    help=_("Retrieve all workflows for a project from Zooniverse")
)
def workflows_by_id(
        ctx: typer.Context,
        id: Annotated[int, typer.Argument(help=("Workflow ID"))] = ...,
        raw: Annotated[
            bool,
            typer.Option(help="Print raw output instead of table")
        ] = False,
) -> None:
    """
    Retrieve all collections based on optional query parameters.

    This command allows users to fetch collections from the database.
    Query parameters can be provided to filter results, and the output can
    optionally be exported to a CSV file.

    Args:
        ctx (typer.Context): The Typer context object, used to share information across commands.

    Returns:
        None: Prints the collections  details to the CLI output
    """

    zooniverse_client = ctx.obj["zooniverse_client"]
    logger = ctx.obj["logger"]
    _ = ctx.obj["_"]

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Retrieving workflows from Zooniverse project {zooniverse_client.project_id} with id {id}"),
                "func": zooniverse_client.workflows.get_by_id,
                "args": (id,),
            },
        ]
    )

    workflow = results[0]
    if raw:
        TyperUtils.print_as_json([workflow])
    else:
        ZooUtils.show_workflow(workflow)

@app.command("annotations-upload",
    short_help=_("Upload all subjetset annotation from Zooniverse to Trapper Classification Project"),
    help=_("Upload all subjetset annotation from Zooniverse to Trapper Classification Project")
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

@app.command("annotations-upload-reports",
    help=_("List all upload reports related to data transferred from Zooniverse (annotations) to Trapper."),
    short_help=_("List upload reports from Zooniverse to Trapper.")
)
def trapper_reports():
    """
    ## trapper_reports

    Displays a summary table of **annotation upload reports** found in the default reports directory.
    Each YAML report file is parsed to extract metadata such as subject set, start and end times, and upload status.

    ### 🧩 Behavior
    - Scans the directory returned by `get_default_annotations_upload_reports_dir()` for `.yaml` files.
    - Parses each YAML file and extracts:
      - `subjectset_name`
      - `start_time`
      - `end_time`
      - `errors`
    - Builds a Rich table showing the following columns:
      - **File name** — report filename
      - **SubjectSet** — subject set name in Zooniverse
      - **Start time** — when the upload started
      - **End time** — when the upload finished
      - **Status** — ✅ if no errors were found, ❌ if the `errors` field is not empty

    ### ⚠️ Notes
    - If no report files are found, the function stops execution with a fatal message.
    - If a report file cannot be parsed, its row shows a warning symbol (`⚠️ Error`) and the status is marked as ❌.
    - Output is printed directly to the console using `TyperUtils.console.print()`.

    ### 🧾 Example
    ```python
    trapper_reports()
    ```
    Displays something like:

    ```
    ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┓
    ┃ File name    ┃ SubjectSet ┃ Start time ┃ End time   ┃ Status  ┃
    ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━┩
    │ report1.yaml │ Project A  │ 10:00:00   │ 10:05:00   │ ✅      │
    │ report2.yaml │ Project B  │ 11:00:00   │ 11:02:00   │ ❌      │
    └──────────────┴────────────┴────────────┴────────────┴─────────┘
    ```

    ---
    """

    report_dir = get_default_annotations_upload_reports_dir()
    yaml_files = sorted(report_dir.glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not yaml_files:
        TyperUtils.fatal(f"No annotations upload reports found in:[/yellow] {report_dir}")

    table = Table(title=_("Annotations upload reports"))
    table.add_column(_("File name"), style="cyan", no_wrap=True)
    table.add_column(_("SubjectSet"), style="green")
    table.add_column(_("Start time"), style="magenta")
    table.add_column(_("End time"), style="white")
    table.add_column(_("Status"), style="bold")

    for yaml_file in yaml_files:
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            subjectset = data.get("subjectset_name", "—")
            start_time = str(data.get("start_time", "—"))
            end_time = str(data.get("end_time", "—"))

            errors = data.get("errors", {})
            status = "❌" if errors else "✅"

        except Exception as e:
            subjectset = "⚠️ Error"
            start_time = end_time = str(e)
            status = "❌"

        table.add_row(yaml_file.name, subjectset, start_time, end_time, status)

    TyperUtils.console.print(table)

@app.command("annotations-upload-report",
             help=_("Show detailed information from a specific upload report"),
             short_help=_("Show details of an upload report.")
)
def trapper_report(
    filename: Annotated[
        str,
        typer.Argument(help=_("Name of the YAML report file to display (optional)"))
    ] = None,
):
    """"
    Show detailed information from a specific upload report.

    ## Parameters
    - **filename** (`str`, optional): Name of the YAML report file to display. If not provided, the command may use a default or prompt for input.

    ## Behavior
    - Displays comprehensive details of an upload report in a formatted manner
    - Parses and presents information from the specified YAML report file
    - Provides insights into upload statistics, errors, warnings, and processing results

    ## Usage
    ```bash
    trapper-report <filename.yaml>
    """
    report_dir = get_default_annotations_upload_reports_dir()
    target_file = choose_report_file(report_dir, filename)

    try:
        report = UploadAnnotationsReport.from_yaml(target_file)
        TyperUtils.display_upload_annotations_report(report)
        TyperUtils.success(f"Report loaded from: {target_file}\n")
    except Exception as e:
        TyperUtils.fatal(f"Failed to load report {e}")

if __name__ == "__main__":
    app()