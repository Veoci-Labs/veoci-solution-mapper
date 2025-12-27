"""Veoci Solution Mapper - CLI tool to map Veoci solution structure and dependencies."""

from veoci_mapper.client import (
    AuthenticationError,
    NotFoundError,
    VeociClient,
    VeociClientError,
)
from veoci_mapper.fetcher import (
    fetch_forms_list,
    fetch_solution,
    fetch_workflows_list,
)

__version__ = "0.1.0"

__all__ = [
    "VeociClient",
    "VeociClientError",
    "AuthenticationError",
    "NotFoundError",
    "fetch_solution",
    "fetch_forms_list",
    "fetch_workflows_list",
]
