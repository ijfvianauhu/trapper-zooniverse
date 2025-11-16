# python
"""
Helpers CLI commands module for Typer.

Provides utilities to test connections and retrieve information from a
Trapper instance and Zooniverse projects.

Functions
---------
dynaconf_loader(file_path: str) -> dict
    Load configuration from a JSON string.
dynamic_dynaconf_callback(ctx, param, value)
    Dynamic callback that loads runtime configuration and fills context params.
main_callback(ctx: typer.Context)
    Callback executed before any Typer command.
test_connection(...)
    Test connection to a Trapper server (API).
classification_projects(...)
    Retrieve classification projects from a Trapper instance and display them.
research_projects(...)
    Retrieve research projects from a Trapper instance and display them.
locations(...)
    Retrieve locations from a Trapper instance and display them.
"""
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue, Empty
from typing import Annotated

from rich.progress import Progress, TimeElapsedColumn, BarColumn, TimeRemainingColumn
from typer_config import conf_callback_factory

from trapper_zooniverse.ZooniverseClient import ZooniverseClient
from trapper_zooniverse.helpers import check_trapper_connection, check_zooniverse_connection, \
    zooniverse_get_workflows, zooniverse_get_subject_sets, trapper_collections, zooniverse_get_subjects, \
    trapper_deployments
from trapper_zooniverse.reports import Report
from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils
from trapper_zooniverse.ui.typer.ZooUtils import ZooUtils
from trapper_zooniverse.ui.typer.i18n import _
#from wildintel_tools.ui.typer.TyperUtils import TyperUtils
from trapper_zooniverse.ui.typer.settings import SettingsManager

#from wildintel_tools.helpers import (
#    check_ffmpeg,
#    check_exiftool,
#    check_trapper_connection,
#    get_trapper_classification_projects,
#    get_trapper_research_projects,
#    get_trapper_locations, get_trapper_deployments
#)

import typer

app = typer.Typer(
    help=_("Helpers"),
    short_help=_("Helpers")
)

def dynaconf_loader(file_path: str) -> dict:
    """
    Load configuration from a JSON string.

    Note:
        Despite the name, this function calls ``json.loads`` on ``file_path``,
        so it expects a JSON string containing the configuration, not a file path.

    :param file_path: JSON string with the configuration.
    :type file_path: str
    :return: Deserialized configuration dictionary.
    :rtype: dict
    :raises json.JSONDecodeError: If the string is not valid JSON.
    """
    return json.loads(file_path)

# Base callback
base_conf_callback = conf_callback_factory(dynaconf_loader)

def dynamic_dynaconf_callback(ctx, param, value):
    """
    Dynamic callback to load configuration values at runtime.

    This callback obtains configuration from ``ctx.obj["settings"]`` and
    serializes it to pass it to ``base_conf_callback``. It also fills
    context parameters (``user``, ``url``, ``password``) if they were not
    provided explicitly.

    :param ctx: Typer/Click context.
    :type ctx: typer.Context
    :param param: Parameter associated with the callback.
    :type param: click.Parameter
    :param value: Current parameter value.
    :type value: Any
    :return: Result of applying ``base_conf_callback``.
    :rtype: Any
    """
    settings = ctx.obj.get("settings", {}).as_dict()
    json_str = json.dumps(settings, default=str)
    results = base_conf_callback(ctx, param, json_str)

    mapping = {
        "trapper_user": ("TRAPPER", "trapper_username"),
        "trapper_url": ("TRAPPER", "trapper_url"),
        "trapper_password": ("TRAPPER", "trapper_password"),
        "zooniverse_username": ("ZOONIVERSE", "zooniverse_username"),
        "zooniverse_password": ("ZOONIVERSE", "zooniverse_password"),
        "zooniverse_project_id": ("ZOONIVERSE", "zooniverse_project_id"),
    }

    for param_name in ctx.params:
        if ctx.params[param_name] is None and param_name in mapping:
            section, key = mapping[param_name]
            ctx.params[param_name] = settings[section][key]

    return results

@app.callback()
def main_callback(ctx: typer.Context):
    """
    Callback executed before any Typer command.

    Use this to initialize or modify the global context.

    :param ctx: Typer context.
    :type ctx: typer.Context
    """
    # ctx.obj = {"config": "global value"}
    # typer.echo("Callback executed")
    pass


@app.command(help=_("Test connection to Trapper server instance and Zooniverse"),
             short_help=_("Test connection to Trapper server instance and Zooniverse"))
def test_connection(ctx: typer.Context,
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
                            help=_("File to save the report"),
                            callback=dynamic_dynaconf_callback
                        )
                    ] = None,
    ):
    """
    Test the connection to a Trapper server (API).

    Performs a check using ``check_trapper_connection`` and reports the result
    to the console.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param url: Base URL of the Trapper server.
    :type url: str
    :param user: Username for authentication.
    :type user: str
    :param password: Password for the user (optional).
    :type password: str
    :param token: Access token (optional).
    :type token: str
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If the connection fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})

    try:
        TyperUtils.info(_("Testing Trapper API connection..."))
        check_trapper_connection(trapper_url, trapper_user, trapper_password, None)
        TyperUtils.success(_("Trapper API connection successful!"))
    except Exception as e:
        TyperUtils.fatal(_(f"Failed to connect to Trapper API. Check your settings: {str(e)}"))

    try:
        TyperUtils.info(_("Testing Zooniverse API connection..."))
        check_zooniverse_connection(zooniverse_username, zooniverse_password, zooniverse_project_id)
        TyperUtils.success(_("Zooniverse API connection successful!"))
    except Exception as e:
        TyperUtils.fatal(_(f"Failed to connect to Trapper API. Check your settings: {str(e)}"))

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Login to trapper {trapper_url}"),
                "func" : check_trapper_connection,
                "args": (trapper_url, trapper_user, trapper_password, None),
            },

            {
                "description": _(f"Login to Zooniverse {zooniverse_project_id}"),
                "func": check_zooniverse_connection,
                "args": (zooniverse_username, zooniverse_password, zooniverse_project_id),
            }

        ]
    )


@app.command(
    help=_("Retrieve workflows from a Zooniverse project."
            "If a project ID is provided, only workflows for that project will be retrieved (alias: wf)."
            ),
    short_help=_("Retrieve workflows from a Zooniverse project") + " (alias: wf)")
def workflows(ctx: typer.Context,
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

              id: Annotated[int, typer.Argument(help=("Workflow ID"))] = None,

              raw: Annotated[
                  bool,
                  typer.Option(help=_("Display raw JSON output instead of formatted table"))
              ] = False,

              config: Annotated[
                  Path,
                  typer.Option(
                      hidden=True,
                      help=_("File to save the report"),
                      callback=dynamic_dynaconf_callback
                  )
              ] = None,
  ):
    """
    Check availability of external tools: ffmpeg and exiftool.

    Loads the current project settings and runs the corresponding checks.

    :param ctx: Typer context (must contain ``project`` and ``setting_manager``).
    :type ctx: typer.Context
    :raises Exception: If any check raises, the error is logged.
    """

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(
                    f"Retrieving workflows from Zooniverse project {zooniverse_project_id} with id {id}"),
                "func": zooniverse_get_workflows,
                "args": (zooniverse_username, zooniverse_password, zooniverse_project_id, id),
            },
        ]
    )

    workflows = results[0]

    if not id:
        ZooUtils.show_workflows(workflows)
    else:
        ZooUtils.show_workflow(workflows,raw)

app.command(name="wf", hidden=True) (workflows)


@app.command(help=_(
        "Retrieve subject sets from a Zooniverse project. "
        "If a workflow ID is provided, only the subject sets linked to that workflow will be retrieved."
    ) + "(alias: ss)",
    short_help=_("Retrieve all or workflow-specific subject sets from a Zooniverse project" + " (alias: ss)")
)
def subjectsets(ctx: typer.Context,
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

            id: Annotated[int, typer.Argument(help=("Workflow ID"))] = None,

    exports: Annotated[
        bool,
        typer.Option(help="Only print subjectsets with exports")
    ] = False,

    wf_id: Annotated[
        int,
        typer.Option(help="Workflow id")
    ] = None,

    config: Annotated[
        Path,
        typer.Option(
            hidden=True,
            help=_("File to save the report"),
            callback=dynamic_dynaconf_callback
        )
    ] = None,
):
    """
    Retrieve classification projects from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param url: Base URL of the Trapper server.
    :type url: str
    :param user: Username for authentication.
    :type user: str
    :param password: Password for the user (optional).
    :type password: str
    :param token: Access token (optional).
    :type token: str
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """

    tasks = []

    tasks.append(
            {
                "description": _(f"Getting subjectsset {id} Zooniverse {zooniverse_project_id}"),
                "func": zooniverse_get_subject_sets,
                "args": (zooniverse_username, zooniverse_password, zooniverse_project_id,
                                id, exports,wf_id),
            }
        )

    results = TyperUtils.run_tasks_with_progress(tasks)
    if not id:
        ZooUtils.show_subject_sets(results[0])
    else:
        ZooUtils.show_subject_set(results[0])

app.command(name="ss", hidden=True) (subjectsets)

@app.command(help=_("This command allows users to fetch all collections from trapper instance.") + "(alias: col)",
             short_help=_("Retrieve all collections from Trapper instance ") + "(alias: col)")
def collections(ctx: typer.Context,

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
            "--password",
            "-p",
            help=_("Password for the specified user (use only if no access token is provided)")
        ),
        trapper_token: str = typer.Option(
            None,
            "--token",
            "-t",
            help=_("Access token for the Trapper API (alternative to using a password)"),
        ),
        config: Annotated[
              Path,
              typer.Option(
                  hidden=True,
                  help=_("File to save the report"),
                  callback=dynamic_dynaconf_callback
              )
          ] = None,
):
    """
    Retrieve research projects from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param url: Base URL of the Trapper server.
    :type url: str
    :param user: Username for authentication.
    :type user: str
    :param password: Password for the user (optional).
    :type password: str
    :param token: Access token (optional).
    :type token: str
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Retrieving collection from Trapper"),
                "func": trapper_collections,
                "args": (trapper_url,trapper_user, trapper_password, trapper_token),
            },
        ]
    )

    #logger.info(f"Retrieved {len(results[0].results)} collections")
    TyperUtils.json2Table(results[0], title="Collections", columns=["pk", "name", "description", "owner"])

app.command(name="col", hidden=True) (collections)

@app.command(
    help=_("Retrieve a specific subject (image) from a Zooniverse project" + "(alias: sbj)"),
    short_help=_("Retrieve a subject" + "(alias: sbj)"))
def subjects(ctx: typer.Context,
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

    id: Annotated[int, typer.Argument(help=("Collection ID"))] = None,
    subjectset_id: Annotated[int, typer.Option(help=("Collection ID"))] = None,

    raw: bool = typer.Option(
         False,
         help=_("Password for the specified user (use only if no access token is provided)")
     ),

             config: Annotated[
              Path,
              typer.Option(
                  hidden=True,
                  help=_("File to save the report"),
                  callback=dynamic_dynaconf_callback
              )
          ] = None,
):
    """
    Retrieve locations from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param url: Base URL of the Trapper server.
    :type url: str
    :param user: Username for authentication.
    :type user: str
    :param password: Password for the user (optional).
    :type password: str
    :param token: Access token (optional).
    :type token: str
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})

    if id is None and subjectset_id is None:
        TyperUtils.fatal(_("Dede indicar el identificador del sujeto, o el subjectset_id, no ambos."))

    try:
        results = TyperUtils.run_tasks_with_progress(
            [
                {
                    "description": _(
                        f"Getting subject from Zooniverse {zooniverse_project_id}, subjectset {id}"),
                    "func": zooniverse_get_subjects,
                    "args": (zooniverse_username, zooniverse_password,zooniverse_project_id,id,subjectset_id),
                }

            ]
        )

        if raw:
            TyperUtils.print_as_json([results[1]])
        else:
            ZooUtils.show_subject(results[1], title="Subjects")
    except Exception as e:
        TyperUtils.error(str(e))
app.command(name="sbj", hidden=True) (subjects)

@app.command(
    help=_("Download subjects (images) from a Zooniverse subjetset (alias: dl_ss)."),
    short_help=_("Download a subjectset (alias: dl_ss)"))
def download_ss(ctx: typer.Context,
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

    id: Annotated[int, typer.Argument(help=("Subjectset ID"))] = ...,
    out_put_dir: Annotated[Path, typer.Argument(help=("Subjectset ID"))] = None,

                config: Annotated[
              Path,
              typer.Option(
                  hidden=True,
                  help=_("File to save the report"),
                  callback=dynamic_dynaconf_callback
              )
          ] = None,
):
    """
    Retrieve locations from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param url: Base URL of the Trapper server.
    :type url: str
    :param user: Username for authentication.
    :type user: str
    :param password: Password for the user (optional).
    :type password: str
    :param token: Access token (optional).
    :type token: str
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})

    try:
        if out_put_dir is None:
            temp_dir = tempfile.mkdtemp(prefix="bulk_download_")

        zooniverse_client = ZooniverseClient(zooniverse_project_id,zooniverse_username, zooniverse_password)
        TyperUtils.info(f"Retrieving subjects from {zooniverse_project_id}...")
        ss = zooniverse_client.subjectsets.get_by_id(id)
        num_subjects= getattr(ss, "set_member_subjects_count", "-")

        if out_put_dir is None:
            out_put_dir = tempfile.mkdtemp(prefix="bulk_download_")

        report: Report = Report(f"Bulk Download Report for subjectset {id}")

        event_queue = Queue()

        def callback(status, subject_id, name):
            event_queue.put((status, subject_id, name))

        with Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                transient=False
        ) as progress:

            task = progress.add_task(
                f"[cyan]Downloading subjects from subjectset {id}...",
                total=num_subjects
            )

            # Lanzamos download() en segundo plano
            future = ThreadPoolExecutor(1).submit(
                zooniverse_client.subjectsets.download,
                id, Path(out_put_dir),
                callback, 8, event_queue
            )

            # Procesamos eventos
            while True:
                try:
                    status, subject_id, name = event_queue.get(timeout=0.1)

                    if status == "start":
                        progress.log(f"[yellow]→ Starting {name}")

                    elif status == "end":
                        progress.advance(task, 1)
                        report.add_success(name, "downloaded")
                        progress.log(f"[green]✓ Finished {name}")

                    elif status == "fail":
                        report.add_error(subject_id, "error")
                        progress.log(f"[red]✗ Failed {subject_id}")

                except Empty:
                    pass

                if future.done() and event_queue.empty():
                    break

            report.finish()

        TyperUtils.success(f"Subjects downloaded successfully in {out_put_dir}!")
        report_output_file = TyperUtils.report_save(report)
        TyperUtils.success(f"Report saved in  {report_output_file}!")

    except Exception as e:
        TyperUtils.error(str(e))

app.command(name="dl_ss", hidden=True) (download_ss)

@app.command(help=_("This command allows users to fetch all deployments from trapper instance."),
             short_help=_("Retrieve all deployments from Trapper instance "))
def deployments(ctx: typer.Context,

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
            "--password",
            "-p",
            help=_("Password for the specified user (use only if no access token is provided)")
        ),
        trapper_token: str = typer.Option(
            None,
            "--token",
            "-t",
            help=_("Access token for the Trapper API (alternative to using a password)"),
        ),
        config: Annotated[
              Path,
              typer.Option(
                  hidden=True,
                  help=_("File to save the report"),
                  callback=dynamic_dynaconf_callback
              )
          ] = None,
):
    """
    Retrieve research projects from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param url: Base URL of the Trapper server.
    :type url: str
    :param user: Username for authentication.
    :type user: str
    :param password: Password for the user (optional).
    :type password: str
    :param token: Access token (optional).
    :type token: str
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})

    results = TyperUtils.run_tasks_with_progress(
        [
            {
                "description": _(f"Retrieving deployments from Trapper"),
                "func": trapper_deployments,
                "args": (trapper_url,trapper_user, trapper_password, trapper_token),
            },
        ]
    )

    #logger.info(f"Retrieved {len(results[0].results)} collections")
    TyperUtils.json2Table(results[0], title="Deployments", columns=["pk", "name", "deployment_id", "description", "owner"])
