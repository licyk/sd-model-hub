"""version, env."""

import os
import platform
from importlib import metadata
from typing import Annotated

import typer

from sd_model_hub.cli.output import print_json, print_table
from sd_model_hub.version import VERSION

COMPONENTS = ("fastapi", "uvicorn", "python-socketio", "httpx", "pydantic", "typer", "huggingface_hub", "modelscope")

ENV_VARS = {
    "SD_MODEL_HUB_DATA_DIR": "Data directory holding settings.toml, the database and caches",
    "SD_MODEL_HUB_LOG_LEVEL": "Log level: DEBUG, INFO, WARNING or ERROR",
    "SD_MODEL_HUB_<GROUP>__<FIELD>": "Override one setting, e.g. SD_MODEL_HUB_SERVER__PORT=8000 or SD_MODEL_HUB_SOURCES__CIVITAI__TOKEN=...",
}


def version(
    json_output: Annotated[bool, typer.Option("--json", help="Print JSON")] = False,
) -> None:
    """Show the version of SD Model Hub and its main components."""
    components: dict[str, str | None] = {}
    for name in COMPONENTS:
        try:
            components[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            components[name] = None
    if json_output:
        print_json({"sd_model_hub": VERSION, "python": platform.python_version(), "components": components})
        return
    print_table(None, ["Component", "Version"], [("sd-model-hub", VERSION), ("python", platform.python_version()), *((k, v or "not installed") for k, v in components.items())])


def env(
    json_output: Annotated[bool, typer.Option("--json", help="Print JSON")] = False,
) -> None:
    """List the environment variables SD Model Hub reads, and those currently set."""
    in_use = {k: ("***" if "TOKEN" in k else v) for k, v in sorted(os.environ.items()) if k.startswith("SD_MODEL_HUB_")}
    if json_output:
        print_json({"known": ENV_VARS, "set": in_use})
        return
    print_table("Environment variables", ["Name", "Meaning"], ENV_VARS.items())
    if in_use:
        print_table("Set now", ["Name", "Value"], in_use.items())
