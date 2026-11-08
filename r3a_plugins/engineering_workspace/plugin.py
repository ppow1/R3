"""Manifest package entrypoint for the canonical isolated workspace provider."""
from r3a_runtime.providers.isolated_workspace import create_provider

__all__ = ["create_provider"]
