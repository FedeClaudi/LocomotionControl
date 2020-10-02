import logging
from rich.logging import RichHandler

# supress warnings
import pandas as pd
import warnings

from loguru import logger


warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

# Set up RICH logger
logger.configure(
    handlers=[
        {
            "sink": RichHandler(rich_tracebacks=True, markup=True),
            "format": "{message}",
        }
    ]
)


# Disable logging some packages
for module in [
    "matplotlib",
    "pandas",
    "numpy",
    "tensorflow",
    "pandas",
    "tables",
]:
    logger = logging.getLogger(module)
    logger.setLevel(logging.ERROR)


def make_header(msg):
    bar = "#" * 100

    return bar + "\n" + msg + "\n" + bar + "\n\n"