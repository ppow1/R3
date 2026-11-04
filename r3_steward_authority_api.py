from pathlib import Path
from fastapi import APIRouter, HTTPException
import os
import json
import subprocess

def build_steward_authority_router(root):
    router = APIRouter(prefix="/api/v1/steward-authority")

    @router.get("/capabilities")
    def capabilities():
        return {
            "component": "Steward Authority",
            "contract": "r3.steward-authority.v1",
            "operations": {
                "inventory": "discovery",
                "pending": "requires authoritative provider",
                "active": "requires authoritative provider",
                "history": "requires authoritative provider",
                "request": "not enabled",
                "approve": "not enabled",
                "deny": "not enabled",
                "renew": "not enabled",
                "revoke": "not enabled"
            },
            "mutations_enabled": False,
            "authority": "existing Riverview grant lifecycle",
            "note": "No local grant registry or implicit authorization."
        }

    @router.get("/inventory")
    def inventory():
        # Fail closed until the authoritative grant lifecycle is bound
        # to authenticated R3 sessions.
        raise HTTPException(
            status_code=503,
            detail="Authoritative grant inventory is not connected"
        )

    @router.get("/pending")
    def pending():
        raise HTTPException(
            status_code=503,
            detail="Authoritative pending requests are not connected"
        )

    @router.get("/active")
    def active():
        raise HTTPException(
            status_code=503,
            detail="Authoritative active grants are not connected"
        )

    @router.get("/history")
    def history():
        raise HTTPException(
            status_code=503,
            detail="Authoritative grant history is not connected"
        )

    return router
