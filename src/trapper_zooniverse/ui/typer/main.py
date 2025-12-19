import sys
from pathlib import Path

import requests
from trapper_client.TrapperClient import TrapperClient
from trapper_zooniverse.TrapperZooniverseConnector import TrapperZooniverseConnector
from trapper_zooniverse.ZooniverseClient import ZooniverseClient
from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils
from trapper_zooniverse.ui.typer.i18n import _, setup_locale
import locale
import os

# --------------------------------------------------------------------------- #
# Localization setup
# --------------------------------------------------------------------------- #

locales_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "locales")
setup_locale(locale.getdefaultlocale()[0] if locale.getdefaultlocale()[0] else "en_GB", locales_dir)

import typer
from trapper_zooniverse.ui.typer.settings import Settings
from trapper_zooniverse.ui.typer.settings_manager import SettingsManager
from trapper_zooniverse.ui.typer.logger import logger, setup_logging
from typing import Annotated, Optional, Any, Literal

#
# Typer Subcommands
#

from trapper_zooniverse.ui.typer.commands import config as config_commands
from trapper_zooniverse.ui.typer.commands import logger as logger_commands
from trapper_zooniverse.ui.typer.commands import helpers as helpers_commands
from trapper_zooniverse.ui.typer.commands import reports as reports_commands
from trapper_zooniverse.ui.typer.commands import zooniverse as zooniverse_commands

# --------------------------------------------------------------------------- #
# App metadata
# --------------------------------------------------------------------------- #

APP_NAME = "trapper-zooniverse"
__version__ = "0.1.0"

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
app.add_typer(zooniverse_commands.app, name="zooniverse")

def make_dynaconf_callback(override_mapping: dict | None = None):
    def callback(ctx, param: typer.CallbackParam, value: Any):
        return TyperUtils.dynamic_dynaconf_callback(ctx, param, value, override_mapping=override_mapping)
    return callback

override_mapping = {
    "verbosity": ("LOGGER", "loglevel"),
    "log_file": ("LOGGER", "filename"),
    "trapper_url": ("TRAPPER", "trapper_url"),
    "trapper_user": ("TRAPPER", "trapper_username"),
    "trapper_password": ("TRAPPER", "trapper_password"),
    "trapper_token": ("TRAPPER", "trapper_token"),
}

callback_with_override = make_dynaconf_callback(override_mapping)


def typer_base_path() -> Path:
    return Path(typer.get_app_dir(APP_NAME))

# Asignamos nuestra versión
#import trapper_zooniverse.ui.typer.ConfigManager
#trapper_zooniverse.ui.typer.ConfigManager.get_base_path = typer_base_path

#from trapper_zooniverse.TrapperZooniverseConnector import TrapperZooniverseConnector
#from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils
#from trapper_client.TrapperClient import TrapperClient

#console = Console()
#TyperUtils.console = console
#logger = logging.getLogger(__name__)
#_ = gettext.gettext

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
                callback=callback_with_override
            )
        ] = None,

):
    if (version):
        prog = os.path.basename(sys.argv[0])
        TyperUtils.console.print(f"{prog}s {__version__}")
        exit(1)

    ## Load settings --> in project param callback
    settings:Settings = ctx.obj["settings"]
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

if __name__ == "__main__":
    app()