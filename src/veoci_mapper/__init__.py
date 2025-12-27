"""Veoci Solution Mapper - CLI tool to map Veoci solution structure and dependencies."""

from veoci_mapper.client import (
    AuthenticationError,
    NotFoundError,
    VeociClient,
    VeociClientError,
)

__version__ = "0.1.0"

__all__ = [
    "VeociClient",
    "VeociClientError",
    "AuthenticationError",
    "NotFoundError",
]
