from datetime import datetime
from typing import Annotated, Optional, Dict, Tuple, Any

import typer
import logging
import gettext
from pathlib import Path, PosixPath

from rich.text import Text
from rich.prompt import Prompt

import yaml
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn, ProgressColumn
from rich.table import Table
from rich.console import Console
from typer_config import use_yaml_config
import time

from trapper_zooniverse.TrapperZooniverseConnector import TrapperZooniverseConnector
from trapper_zooniverse.TyperUtils import TyperUtils
from trapper_client.TrapperClient import TrapperClient
from trapper_zooniverse.ZooniverseClient import ZooniverseClient, UploadReport
from trapper_zooniverse.TrapperZooniverseConnector import MediaObservationEntry

console = Console()
TyperUtils.console = console
logger = logging.getLogger(__name__)
_ = gettext.gettext


APP_NAME="trapper-zooniverse"

app = typer.Typer(help=_("CLI for uploading images from Trapper to Zooniverse and upload Zooniverse results to Trapper"), rich_markup_mode='markdown')

def get_default_config_file() -> Path:
    """Obtiene la ruta al fichero de configuración por defecto."""
    app_dir = Path(typer.get_app_dir(APP_NAME))
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "config.yaml"

def get_default_upload_reports_dir() -> Path:
    """Obtiene la ruta al fichero de contable.add_row(
            str(getattr(export_obj, "export_type", "N/A")),
            str(getattr(export_obj, "id", "N/A")),
            str(getattr(export_obj, "state", "unknown")),
            str(getattr(export_obj, "created_at", "N/A")),
            str(getattr(export_obj, "updated_at", "N/A")),
            str(getattr(export_obj, "url", "N/A")),
        )figuración por defecto."""
    app_dir = Path(typer.get_app_dir(APP_NAME))
    results_dir = app_dir / "upload_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir

def ensure_config_file() -> Path:
    """Crea el fichero de configuración con valores por defecto si no existe
    y asegura que el fichero de log también exista."""
    config_file = get_default_config_file()

    if not config_file.exists():
        default_config = {
            "login": {
                "trapper_username": "myuser",
                "trapper_password": "mypassword",
                "trapper_url": "https://wildintel-trap.uhu.es",
                "trapper_access_token" : "mi_token_secreto",
                "zooniverse_project_id" : "tu_id_de_proyecto",
                "zooniverse_username" : "tu_usuario",
                "zooniverse_password" : "tu_password",
            },
            "logger": {
                "lang": "en",
                "loglevel": "INFO",
                "logfilename": str(config_file.parent / "app.log"),
            },
            "upload_collection" : {
                "n_images_seq": 5,  # images per sequence
                "max_interval": 120,  # max seconds between sequence images
                "attempts": 5,  # global upload attempts
                "delay": 15, # seconds between retries
                "max_attempts_per_subject": 5,
                "delay_seconds_per_subject": 30
            },
            "download_classifications" : {
            }
        }

        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)

    # Asegurarse de que el fichero de log exista
    with open(yaml.safe_load(open(config_file))["logger"]["logfilename"], "a") as f:
        pass

    return config_file

def init_logger(logfilename: Path, loglevel:str):
    """Inicializa el logger y la configuración de i18n."""
    global logger, _

    print(logfilename, loglevel)

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

def init_locale(lang:str):
    global  _

    locale_dir = Path(__file__).parent / "locales"

    try:
        translation = gettext.translation(
    # media, observations = (results[0], results[1])

            "messages", localedir=locale_dir, languages=[lang]
        )

        logger.debug(f"Locale set to: {lang}")

        _ = translation.gettext
    except FileNotFoundError as e:
        print(e)
        _ = gettext.gettext

    return _

@app.callback()
@use_yaml_config(default_value=ensure_config_file())
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
    # Cargar config YAML entera
    import yaml
    config_file = ensure_config_file()
    with open(config_file) as f:
        config = yaml.safe_load(f)

    logger_cfg = config.get("logger", {})

    # Logger
    logfilename = logfilename or Path(logger_cfg.get("logfilename", "app.log"))
    loglevel = loglevel or logger_cfg.get("loglevel", "INFO")
    init_logger(logfilename, loglevel)

    # Lang
    lang = lang or logger_cfg.get("lang", "en")
    init_locale(lang)

    login_cfg = config.get("login", {})

    trapper_username = trapper_username or login_cfg.get("trapper_username")
    trapper_password = trapper_password or login_cfg.get("trapper_password")
    trapper_url = trapper_url or login_cfg.get("trapper_url")
    trapper_token = trapper_token or login_cfg.get("token")

    zooniverse_username = zooniverse_username or login_cfg.get("zooniverse_username")
    zooniverse_password = zooniverse_password or login_cfg.get("zooniverse_password")
    zooniverse_project_id = zooniverse_project_id or login_cfg.get("zooniverse_project_id")

    trapper_client=TrapperClient(
        access_token= trapper_token if trapper_token else None,
        base_url=trapper_url,
        user_name=trapper_username if trapper_username else None,
        user_password=trapper_password if trapper_password else None,
    )

    zooniverse_client=ZooniverseClient(
        project_id= zooniverse_project_id if zooniverse_project_id else None,
        username= zooniverse_username if zooniverse_username else None,
        password= zooniverse_password if zooniverse_password else None,
    )

    connector = TrapperZooniverseConnector(zooniverse_client, trapper_client)

    ctx.obj = {
        "logger": logging.getLogger(__name__),
        "_": _,
        "trapper_client": trapper_client,
        "zooniverse_client": zooniverse_client,
        "connector":connector
    }

@app.command("show-logger", help=_("Show log file content"), short_help=_("Show log file content"))
def show_logger():

    config_file = ensure_config_file()
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)  # Devuelve un diccionario de Python

    log_path = Path(config.get("logger", {}).get("logfilename", "app.log"))

    if log_path.exists():
        with log_path.open("r") as f:
            content = f.read()
        print(content)
    else:
        TyperUtils.fatal(_(f"Log file not found: {log_path}"))

@app.command("show-config", help=_("Show current configuration"), short_help=_("Show current configuration"))
def show_config():
    config_file = ensure_config_file()
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)  # Devuelve un diccionario de Python

    table = Table(title=_("Configuration"))
    table.add_column(_("Section"), style="cyan")
    table.add_column(_("Key"), style="green")
    table.add_column(_("Value"), style="magenta")

    for section, values in config.items():
        if isinstance(values, dict):
            for key, value in values.items():
                table.add_row(section, key, str(value))
        else:
            # Para claves de nivel superior que no pertenezcan a ninguna sección
            table.add_row("None", section, str(values))

    console.print(table)

@app.command("set-config", help=_("Set a configuration parameter"), short_help=_("Set a configuration parameter"))
def set_config(key: str, value: str):
    """Modifica un parámetro Archivos procesados conde la configuración"""
    config_file = ensure_config_file()

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    found = False
    for section, values in config.items():
        if isinstance(values, dict) and key in values:
            values[key] = value
            found = True
            break

    if not found:
        TyperUtils.fatal(_(f"'{key}' is not a valid parameter"))

    # Guardar la configuración YAML actualizada
    with open(config_file, "w") as f:
        yaml.dump(config, f, sort_keys=False)

    TyperUtils.success(_(f"Configuration updated in {config_file}"))

@app.command("upload-reports", help=_("List all upload reports"), short_help=_("List upload reports"))
def upload_reports():
    """
    List all YAML upload reports saved in the same directory as the configuration file.
    """
    results_dir = get_default_upload_reports_dir()

    yaml_files = sorted(results_dir.glob("upload_report_*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not yaml_files:
        console.print(f"[yellow]⚠️ No upload reports found in:[/yellow] {results_dir}")
        raise typer.Exit()

    table = Table(title=_("Upload Reports"))
    table.add_column(_("File name"), style="cyan", no_wrap=True)
    table.add_column(_("SubjectSet"), style="green")
    table.add_column(_("Start time"), style="magenta")
    table.add_column(_("End time"), style="white")
    table.add_column(_("Saved at"), style="bright_black")

    for yaml_file in yaml_files:
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            subjectset = data.get("subjectset_name", "—")
            start_time = data.get("start_time", "—")
            end_time = data.get("end_time", "—")
        except Exception as e:
            subjectset = "⚠️ Error"
            start_time = end_time = str(e)

        modified_time = datetime.fromtimestamp(yaml_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

        table.add_row(yaml_file.name, subjectset, start_time, end_time, modified_time)

    console.print(table)

@app.command("upload-report", help=_("Show details of an upload report"), short_help=_("Show an upload report"))
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
    target_file = None

    # Si el usuario no pasa ningún archivo → mostrar el último
    if filename is None:
        yaml_files = sorted(
            results_dir.glob("upload_report_*.yaml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if not yaml_files:
            TyperUtils.fatal(f"No upload reports found in: {results_dir}")

        target_file = yaml_files[0]
        TyperUtils.info(_(f"Showing latest report: {target_file.name}"))
    else:
        target_file = results_dir / filename
        if not target_file.exists():
            TyperUtils.fatal(f"Report file not found:{target_file}")

    # Cargar el YAML y mostrar el informe con Rich
    try:
        report = TyperUtils.load_yaml(target_file)
        TyperUtils.display_report(report)
        TyperUtils.success(f"Report loaded from: {target_file}\n")
    except Exception as e:
        TyperUtils.fatal(f"Failed to load report {e}")

@app.command(help=_("Test the login form"), short_help=_("Test the login form"))
@use_yaml_config(section=["login"], default_value=ensure_config_file())
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
    TyperUtils.show_subject_sets_table(results[1])

@app.command("subjects",
    help=_("Retrieve all subjects from Zooniverse"),
    short_help=_("Retrieve all subset_sets from Zooniverse"))
def subjects(
        ctx: typer.Context,
        subjectset_id: Annotated[int, typer.Argument(help=("Collection ID"))] = ...,
):
    # TyperUtils.info(_("Starting login test"))
    zooniverse_client = ctx.obj["zooniverse_client"]

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

    TyperUtils.show_subjects_table(results[1], title= "Subjects")

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
    #logger.debug(results.model_dump_json(indent=4) )
    TyperUtils.json2Table(results[0], title="Collections")

@app.command("upload-collection",
    short_help=_("Upload all media collection from Trapper to Zooniverse"),
    help=_("Upload all media collection from Trapper to Zooniverse")
)
@use_yaml_config(section=["upload_collection"], default_value=ensure_config_file())
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
                "description": _(f"Uploading collection {collection} to Zooniverse {zooniverse_client.project_id} in subjectset {subjectset_name}"),
                "func": connector.upload_collection,
                "args": (subjectset_name,collection,cp_selected.pk, None, n_images_seq, max_interval, attempts, delay, max_attempts_per_subject, delay_seconds_per_subject),
            }
        ]
    )

    logger.debug(_(f"Upload results: {results[1]}"))

    report=results[1]
    app_dir = Path(typer.get_app_dir(APP_NAME))
    results_dir = app_dir / "upload_results"
    results_dir.mkdir(parents=True, exist_ok=True)
    report_file = results_dir / f"upload_report_{collection}_{cp_selected.pk}_{datetime.now():%Y%m%d_%H%M%S}.yaml"

    TyperUtils.save_yaml(results[1], PosixPath(report_file))
    TyperUtils.display_report(results[1])
    TyperUtils.success(_(f"Report saved at: {report_file}"))

@app.command("annotations",
    short_help=_("Upload all media collection from Trapper to Zooniverse"),
    help=_("Upload all media collection from Trapper to Zooniverse")
)
#@use_yaml_config(section=["download_subject"], default_value=ensure_config_file())
def annotations(
        ctx: typer.Context,
        subjectset_id: Annotated[int, typer.Argument(help=("Collection ID"))] = None,
):
    trapper_client = ctx.obj["trapper_client"]
    zooniverse_client = ctx.obj["zooniverse_client"]
    connector:TrapperZooniverseConnector = ctx.obj["connector"]
    logger = ctx.obj["logger"]
    _ = ctx.obj["_"]

    tasks = []

    tasks.append(
        {
            "description": _(f"Login to Zooniverse {zooniverse_client.project_id}"),
            "func" : zooniverse_client.connect,
            "args": (),
        }
    )

    if not subjectset_id:
        tasks.append(
            {
                "description": _(f"Getting all anotations from Zooniverse {zooniverse_client.project_id}"),
                "func": zooniverse_client.annotations.get_all,
                "args": (),
            }
        )
    else:
        tasks.append(
                {
                    "description": _(f"Getting annotations for {subjectset_id} from Zooniverse {zooniverse_client.project_id}"),
                    "func": zooniverse_client.annotations.get_by_subjectset,
                    "args": (subjectset_id),
                }
            )
    results = TyperUtils.run_tasks_with_progress(tasks)

    pass


if __name__ == "__main__":
    app()