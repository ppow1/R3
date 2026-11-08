"""Compatibility import for the Engineering workspace capability module.

New installations register ``r3a_plugins.engineering_workspace`` through its
external capability operation manifest. Existing Engineering callers retain
this import path while that migration proceeds.
"""
from r3a_plugins.engineering_workspace.provider import (IsolatedWorkspaceProvider,
                                                       create_provider)

__all__ = ["IsolatedWorkspaceProvider", "create_provider"]
