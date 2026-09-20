"""Application logging."""

import logging
import os

from rich.console import Console
from rich.logging import RichHandler

LOGGER_NAME = "sd_model_hub"


def setup_logging(level: int | str | None = None) -> logging.Logger:
    """Configure the ``sd_model_hub`` logger once, writing to stderr through Rich."""
    logger = logging.getLogger(LOGGER_NAME)
    if level is None:
        level = os.environ.get("SD_MODEL_HUB_LOG_LEVEL", "INFO").upper()
    logger.setLevel(level)
    if not any(getattr(h, "_sd_model_hub", False) for h in logger.handlers):
        handler = RichHandler(console=Console(stderr=True), show_time=False, show_path=False, markup=False, rich_tracebacks=False)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._sd_model_hub = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
        logger.propagate = False
    return logger
