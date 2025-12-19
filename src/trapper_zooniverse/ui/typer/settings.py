"""
Settings management module.

This module provides functionality to manage project-specific configuration files
based on the `Dynaconf` library. It includes utilities for:

- Creating new project settings from a default or custom template.
- Validating settings with type and value constraints.
- Editing settings interactively via a command-line editor.
- Managing multiple configuration environments.
- Accessing and updating individual parameters safely.

The configuration files are stored in TOML format (default location: ``~/.trapper-tools``)
and grouped into logical sections such as ``LOGGER``, ``GENERAL``, and ``WILDINTEL``.

Example:
    .. code-block:: python

        from wildintel_tools.config.settings_manager import SettingsManager

        sm = SettingsManager()
        sm.create_project_settings("my_project")
        settings = sm.load_settings("my_project", validate=True)
        print(settings.GENERAL.host)
"""

import logging
from pydantic import BaseModel, Field, HttpUrl, EmailStr
from typing import Optional

logger = logging.getLogger(__name__)

class LoggerSettings(BaseModel):
    loglevel: int = Field(default=1, ge=0, le=2, description="Logging level (0=ERROR, 1=INFO, 2=DEBUG)")
    filename: str = Field(
        default="",
        description="Empty string or string ending in .log",
        pattern=r"(^$|^.*\.log$)",
    )

class TrapperSettings(BaseModel):
    trapper_username: EmailStr | None = "user@uhu.es"
    trapper_password: str | None = "password"
    trapper_url: HttpUrl | None = "https://wildintel-trap.uhu.es"
    trapper_token: str | None = None

class ZooniverseSettings(BaseModel):
    zooniverse_username: str | None = "myuser"
    zooniverse_password: str | None = "mypassword"
    zooniverse_project_id: str | None = "myprojectid"

class ZooniverseConnectorSettings(BaseModel):
    upload_collection_n_images_seq: int | None = 5
    upload_collection_max_interval: int | None = 120
    upload_collection_attempts: int | None = 5
    upload_collection_delay: int | None = 15
    upload_collection_max_attempts_per_subject: int | None = 5
    upload_collection_delay_seconds_per_subject: int | None = 30

class Settings(BaseModel):
    LOGGER: LoggerSettings = Field(default_factory=LoggerSettings)
    TRAPPER: TrapperSettings = Field(default_factory=TrapperSettings)
    ZOONIVERSE: ZooniverseSettings = Field(default_factory=ZooniverseSettings)
    ZOONIVERSE_CONNECTOR: ZooniverseConnectorSettings = Field(
        default_factory=ZooniverseConnectorSettings
    )