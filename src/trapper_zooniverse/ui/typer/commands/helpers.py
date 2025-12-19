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
from types import SimpleNamespace
from typing import Annotated, List, Any

from rich.progress import Progress, TimeElapsedColumn, BarColumn, TimeRemainingColumn
from trapper_client.TrapperClient import TrapperClient
from typer_config import conf_callback_factory

from trapper_zooniverse.Schemas import Zoo2TrapperObservation
from trapper_zooniverse.ZooniverseClient import ZooniverseClient
from trapper_zooniverse.helpers import check_trapper_connection, check_zooniverse_connection, \
    zooniverse_get_workflows, zooniverse_get_subject_sets, trapper_collections, zooniverse_get_subjects, \
    trapper_deployments
from trapper_zooniverse.reports import Report
from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils
from trapper_zooniverse.ui.typer.ZooUtils import ZooUtils
from trapper_zooniverse.ui.typer.i18n import _


import typer

from trapper_zooniverse.ui.typer.settings import Settings

app = typer.Typer(
    help=_("Helpers"),
    short_help=_("Helpers")
)

def make_dynaconf_callback(override_mapping: dict | None = None):
    def callback(ctx, param: typer.CallbackParam, value: Any):
        return TyperUtils.dynamic_dynaconf_callback(ctx, param, value, override_mapping=override_mapping)
    return callback

override_mapping = {
    "user": ("GENERAL", "login"),
    "url": ("GENERAL", "host"),
    "password": ("GENERAL", "password"),
}

callback_with_override = make_dynaconf_callback(override_mapping)

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

@app.command(help=_("This command allows users to fetch all annotations from Zooniverse." + " (alias: ann)"),
             short_help=_("Retrieve annotations from Zooniverse ") + " (alias: ann)")
def annotations(
    ctx: typer.Context,
    workflow_id: Annotated[int, typer.Argument(help=("Filter annotations by workflow"))] = None,
    subjectset: Annotated[int, typer.Option(help=("Filter annotations by workflow"))] = None,
    config: Annotated[
        Path, typer.Option(hidden=True, help=_("File to save the report"), callback=callback_with_override)
    ] = None,
):
    """
    Retrieve research projects from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param url: Base URL of the Trapper server.
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})
    zoo:ZooniverseClient = ctx.obj.get("zooniverse_client")

    if workflow_id == None:
        workflows = zoo.workflows.get_all()
        simplified_list = [SimpleNamespace(pk=ss.raw["id"], name=ss.raw["display_name"]) for ss in workflows]
        wf_selected,index = TyperUtils.select_from_list(simplified_list, "Select a Workflow")
        wf_selected = workflows[index]
    else:
        wf_selected = zoo.workflows.get_by_id(workflow_id)

    TyperUtils.info(f"Retrieving annotations from Zooniverse {wf_selected.id } workflow...")

    if subjectset == None:
        a= zoo.annotations.get_by_workflow(wf_selected.id)
    else:
        a= zoo.annotations.get_by_subjectset(wf_selected.id, subjectset)

    ZooUtils.show_annotations(a)
    """try:
        TyperUtils.info(f"Retrieving deployments from Trapper Instance {trapper_client.base_url}...")
        results = trapper_deployments(trapper_client)
        #logger.info(f"Retrieved {len(results[0].results)} collections")
        TyperUtils.json2Table(results, title="Deployments", columns=["pk", "name", "deployment_id", "description", "owner"])
    except Exception as e:
        TyperUtils.fatal(f"Failed retrieving Trapper deployments: {str(e)}")
    """
app.command(name="ann", hidden=True, help=_("Alias for annotations")) (annotations)


@app.command(help=_("Test connection to Trapper server instance and Zooniverse") + " (alias: tc)",
             short_help=_("Test connection to Trapper server instance and Zooniverse") + " (alias: tc)")
def test_connection(ctx: typer.Context,

                    config: Annotated[
                        Path,
                        typer.Option(
                            hidden=True,
                            help=_("File to save the report"),
                            callback=callback_with_override
                        )
                    ] = None,
    ):
    """
    Test the connection to a Trapper server (API).

    Performs a check using ``check_trapper_connection`` and reports the result
    to the console.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If the connection fails a fatal message is logged.
    """
    # settings:Settings = ctx.obj.get("settings", {})
    trapper_client = ctx.obj.get("trapper_client")
    zooniverse_client = ctx.obj.get("zooniverse_client")

    try:
        TyperUtils.info(_("Testing Trapper API connection..."))
        check_trapper_connection(trapper_client)
        TyperUtils.success(_("Trapper API connection successful!"))
    except Exception as e:
        TyperUtils.fatal(_(f"Failed to connect to Trapper API. Check your settings: {str(e)}"))

    try:
        TyperUtils.info(_("Testing Zooniverse API connection..."))
        check_zooniverse_connection(zooniverse_client)
        TyperUtils.success(_("Zooniverse API connection successful!"))
    except Exception as e:
        TyperUtils.fatal(_(f"Failed to connect to Zooniverse API. Check your settings: {str(e)}"))

app.command(name="tc", hidden=True) (test_connection)

@app.command(
    help=_("Retrieve workflows from a Zooniverse project."
            "If a project ID is provided, only workflows for that project will be retrieved."
            ) + " (alias: wf)",
    short_help=_("Retrieve workflows from a Zooniverse project") + " (alias: wf)")
def workflows(ctx: typer.Context,
              wf_id: Annotated[int, typer.Argument(help=("Workflow ID"))] = None,
              raw: Annotated[
                  bool,
                  typer.Option(help=_("Display raw JSON output instead of formatted table"))
              ] = False,

              config: Annotated[
                  Path,
                  typer.Option(
                      hidden=True,
                      help=_("File to save the report"),
                      callback=callback_with_override
                  )
              ] = None,
  ):
    """
    Display Zooniverse workflows.

    :param ctx: Typer context (must contain ``project`` and ``setting_manager``).
    :type ctx: typer.Context
    :param wf_id: Workflow ID to retrieve (optional).
    :type wf_id: int | None
    :param raw: Whether to display raw JSON output instead of a formatted table.
    :type raw: bool
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If any check raises, the error is logged.

    """

    zooniverse_client = ctx.obj.get("zooniverse_client")
    TyperUtils.info(_(f"Retrieving workflows from Zooniverse project {zooniverse_client.project_id} with id {wf_id}"))
    wfs = zooniverse_get_workflows(zooniverse_client, wf_id)

    ZooUtils.show_workflow(wfs, raw) if wf_id else ZooUtils.show_workflows(wfs)

app.command(name="wf", hidden=True, help=_("Alias for workflows")) (workflows)

@app.command(help=_(
        "Retrieve subject sets from a Zooniverse project. "
        "If a workflow ID is provided, only the subject sets linked to that workflow will be retrieved."
    ) + " (alias: ss)",
    short_help=_("Retrieve all or workflow-specific subject sets from a Zooniverse project" + " (alias: ss)"),
)
def subjectsets(ctx: typer.Context,
    ss_id: Annotated[int, typer.Argument(help=("Workflow ID"))] = None,

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
            callback=callback_with_override
        )
    ] = None,
):
    """
    Retrieve subject sets from a Zooniverse project

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param ss_id: SubjectSet ID to filter subject sets (optional).
    :type ss_id: int | None
    :param exports: Whether to filter subject sets with exports only.
    :type exports: bool
    :param wf_id: Workflow ID to filter subject sets (optional).
    :type wf_id: int | None
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """

    try:
        zooniverse_client = ctx.obj.get("zooniverse_client")
        TyperUtils.info(_(f"Retrieving Zoooniverse subjectset {ss_id} from project  {zooniverse_client.project_id}"))
        results = zooniverse_get_subject_sets(zooniverse_client, ss_id, exports, wf_id)
        TyperUtils.debug(results)
        ZooUtils.show_subject_sets(results) if not ss_id else ZooUtils.show_subject_set(results)
    except Exception as e:
        TyperUtils.fatal(_(f"Failed retrieving Zoooniverse subjectset info: {str(e)}"))

app.command(name="ss", hidden=True, help="Alias for subjectsets") (subjectsets)

@app.command(help=_("This command allows users to fetch all collections from trapper instance.") + "(alias: col)",
             short_help=_("Retrieve all collections from Trapper instance ") + "(alias: col)")
def collections(ctx: typer.Context,
        config: Annotated[
              Path,
              typer.Option(
                  hidden=True,
                  help=_("File to save the report"),
                  callback=callback_with_override
              )
          ] = None,
):
    """
    Retrieve collections from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})
    trapper_client = ctx.obj.get("trapper_client")

    try:
        TyperUtils.info(_(f"Retrieving collection from Trapper instance"))
        results = trapper_collections(trapper_client)
        TyperUtils.json2Table(results, title="Collections", columns=["pk", "name", "description", "owner"])
    except Exception as e:
        TyperUtils.fatal(_(f"Failed retrieving Trapper collections: {str(e)}"))

app.command(name="col", hidden=True, help=_("Alias for collections")) (collections)

@app.command(help=_("This command allows users to fetch all classification projects from trapper instance.") + " (alias: cp)",
             short_help=_("Retrieve all classification projects from Trapper instance ") + "(alias: cp)")
def classification_projects(ctx: typer.Context,
        config: Annotated[
              Path,
              typer.Option(
                  hidden=True,
                  help=_("File to save the report"),
                  callback=callback_with_override
              )
          ] = None,
):
    """
    Retrieve collections from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})
    trapper_client = ctx.obj.get("trapper_client")

    try:
        TyperUtils.info(_(f"Retrieving classification projects from Trapper instance"))
        results = trapper_client.classification_projects.get_all()
        TyperUtils.json2Table(results, title="Classification Projects", columns=["pk", "name", "description", "owner"])
    except Exception as e:
        TyperUtils.fatal(_(f"Failed retrieving Trapper collections: {str(e)}"))

app.command(name="cp", hidden=True, help=_("Alias for classification_projects")) (classification_projects)

@app.command(
    help=_("Retrieve a specific subject (image) from a Zooniverse project" + "(alias: sbj)"),
    short_help=_("Retrieve a subject" + "(alias: sbj)"))
def subjects(ctx: typer.Context,
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
              callback=callback_with_override
          )
      ] = None,
):
    """
    Retrieve locations from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})
    trapper_client = ctx.obj.get("trapper_client")
    zooniverse_client = ctx.obj.get("zooniverse_client")

    if id is None and subjectset_id is None:
        TyperUtils.fatal(_("Dede indicar el identificador del sujeto, o el subjectset_id, no ambos."))

    try:
        TyperUtils.info(_(f"Getting subject from Zooniverse {zooniverse_client.project_id}, subjectset {subjectset_id}"))
        results = zooniverse_get_subjects(zooniverse_client, id, subjectset_id)

        if raw:
            TyperUtils.print_as_json([results])
        else:
            ZooUtils.show_subject(results, title="Subjects")
    except Exception as e:
        TyperUtils.error(str(e))
#app.command(name="sbj", hidden=True) (subjects)

@app.command(
    help=_("Download subjects (images) from a Zooniverse subjetset (alias: dl_ss)."),
    short_help=_("Download a subjectset (alias: dl_ss)"))
def download_ss(ctx: typer.Context,
    ss_ids: Annotated[List[int], typer.Argument(help=_("Subjectset ID"))] = ...,
    out_put_dir: Annotated[Path, typer.Option(help=_("Directory where the downloaded images will be saved"))] = None,
    max_workers: Annotated[int, typer.Option(help=_("Maximum number of threads to use"))] = 2,

    config: Annotated[
      Path,
      typer.Option(
          hidden=True,
          help=_("File to save the report"),
          callback=callback_with_override
      )
    ] = None,
):
    """
    Download subjects from a Zooniverse subject set.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param ss_id: Subjectset ID to download subjects from.
    :type ss_id: int
    :param out_put_dir: Directory to save downloaded subjects. If not provided, a temporary directory is used.
    :type out_put_dir: pathlib.Path | None
    :param max_workers: Maximum number of threads to use for downloading subjects.
    :type max_workers: int
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})
    trapper_client = ctx.obj.get("trapper_client")
    zooniverse_client = ctx.obj.get("zooniverse_client")
    reports_files = []

    TyperUtils.debug(f"Downloading subjectsets {ss_ids} from Zooniverse project {zooniverse_client.project_id}")

    if out_put_dir is None:
        out_put_dir = tempfile.mkdtemp(prefix="bulk_download_")
    else:
        out_put_dir.mkdir(parents=True, exist_ok=True)

    for ss_id in ss_ids:
        try:
            TyperUtils.info(_(f"Retrieving subjects from {zooniverse_client.project_id}, subject set {ss_id}..."))
            ss = zooniverse_client.subjectsets.get_by_id(ss_id)

            try:
                num_subjects = int(getattr(ss, "set_member_subjects_count", 0) or 0)
                total = num_subjects if num_subjects > 0 else None
            except Exception:
                total = None

            TyperUtils.info(_(f"Subjectset {ss_id} has {total} subjects."))

            report = TyperUtils.progress_bar(
                zooniverse_client.subjectsets.download,
                (ss_id, Path(out_put_dir), max_workers),
                None,
                _(f"[cyan]Downloading subjects from subjectset {ss_id}..."),
                total=total,
                use_subtasks=True,
            )

            TyperUtils.success(_(f"Subjects downloaded successfully in {out_put_dir}!"))
            report_output_file = TyperUtils.report_save(report)
            reports_files.append(report_output_file)
        except Exception as e:
            TyperUtils.error(str(e))

        TyperUtils.success(_(f"Reports saved in  {', '.join(map(str, reports_files))}!"))

app.command(name="dl_ss", hidden=True, help=_("Alias for download_ss")) (download_ss)


@app.command(
    help=_("Download medias from Trapper (alias: dl_m)."),
    short_help=_("Download medias (alias: dl_m)"))
def download_medias(ctx: typer.Context,
    cp_ids: Annotated[List[int], typer.Argument(help=_("Clasification Project ID"))] = ...,
    out_put_dir: Annotated[Path, typer.Option(help=_("Directory where the downloaded images will be saved"))] = None,
    max_workers: Annotated[int, typer.Option(help=_("Maximum number of threads to use"))] = 2,
    collection_id: Annotated[int, typer.Option(help=_("Collection_id"))] = None,
    compress: Annotated[bool, typer.Option(help=_("Whether to compress the downloaded files into a zip archive"))] = False,

    config: Annotated[
      Path,
      typer.Option(
          hidden=True,
          help=_("File to save the report"),
          callback=callback_with_override
      )
    ] = None,
):
    """
    Download subjects from a Zooniverse subject set.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param ss_id: Subjectset ID to download subjects from.
    :type ss_id: int
    :param out_put_dir: Directory to save downloaded subjects. If not provided, a temporary directory is used.
    :type out_put_dir: pathlib.Path | None
    :param max_workers: Maximum number of threads to use for downloading subjects.
    :type max_workers: int
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})
    trapper_client : TrapperClient= ctx.obj.get("trapper_client")
    reports_files = []

    #TyperUtils.debug(f"Downloading medias from Trapper classification  project {cp_ids} and collection {collection_id}")

    if out_put_dir is None:
        out_put_dir = tempfile.mkdtemp(prefix="bulk_download_")
    else:
        out_put_dir.mkdir(parents=True, exist_ok=True)

    out, report = (None, None)

    def progress_callback(event: str, sid: int, name, total=None, step=None):
        #TyperUtils.info(_(f"Downloaded {event} of {sid} medias {name} {total} {step}. "))
        return (event, sid, name, total, step,)

    for cp_id in cp_ids:
        try:
            TyperUtils.info(_(f"Retrieving medias from {cp_id}, subject set {collection_id}..."))

            if not collection_id:
                (out, report) = TyperUtils.progress_bar2(trapper_client.media.download_by_classification_project,
                                        (cp_id, {}
                                        , Path(out_put_dir), compress,
                                        2),
                                        None, _(f"Retrieving medias from {cp_id}...")
                                        , total=None, use_subtasks=False, custom_callback=progress_callback)

                #out=trapper_client.media.download_by_classification_project(cp_id, query={}
                #                        , destination_folder=Path(out_put_dir) , compress=compress,
                #                                                            workers=2, callback=progress_callback)
            else:
                (out,report)=trapper_client.media.download_by_collection(cp_id, collection_id, query={}, destination_folder=out_put_dir
                                                                   , compress=compress)

            TyperUtils.success(_(f"Medias  downloaded successfully in {out}!"))
            report_output_file = TyperUtils.report_save(report)
            reports_files.append(report_output_file)
        except Exception as e:
            TyperUtils.error(str(e))
            raise e

        TyperUtils.success(_(f"Reports saved in  {', '.join(map(str, reports_files))}!"))

app.command(name="dl_m", hidden=True, help=_("Alias for download_medias")) (download_medias)

@app.command(help=_("This command allows users to fetch all deployments from trapper instance." + " (alias: dpl)"),
             short_help=_("Retrieve all deployments from Trapper instance ") + " (alias: dpl)")
def deployments(ctx: typer.Context,
        config: Annotated[
              Path,
              typer.Option(
                  hidden=True,
                  help=_("File to save the report"),
                  callback=callback_with_override
              )
          ] = None,
):
    """
    Retrieve research projects from a Trapper instance and display them.

    :param ctx: Typer context.
    :type ctx: typer.Context
    :param url: Base URL of the Trapper server.
    :param config: Internal configuration option (dynamic callback).
    :type config: pathlib.Path | None
    :raises Exception: If retrieval fails a fatal message is logged.
    """
    settings = ctx.obj.get("settings", {})
    trapper_client:TrapperClient = ctx.obj.get("trapper_client")

    try:
        TyperUtils.info(f"Retrieving deployments from Trapper Instance {trapper_client.base_url}...")
        results = trapper_deployments(trapper_client)
        #logger.info(f"Retrieved {len(results[0].results)} collections")
        TyperUtils.json2Table(results, title="Deployments", columns=["pk", "name", "deployment_id", "description", "owner"])
    except Exception as e:
        TyperUtils.fatal(f"Failed retrieving Trapper deployments: {str(e)}")

app.command(name="dpl", hidden=True, help=_("Alias for deployments")) (download_ss)

