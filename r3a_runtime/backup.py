"""
R3 CONTROLLED SOURCE
File: r3a_runtime/backup.py
Component: R3A-ISOLATED-BACKUP
File Revision: 1.0.0
Created: 2026-11-06T15:30:00Z
Created By: Codex GPT-6
Purpose: Create consistent AP0 PostgreSQL backups and restore into a new R3A-only database.
Execution Model: pg_dump/pg_restore subprocess with isolated Unix-socket connection.
Observability: Artifact checksums, config/schema revision, row counts and restore verification.
Dependencies: PostgreSQL client tools; r3a_runtime.config/db.
Authority: AP0-M1 implementation authorized by Steward in GitHub Issue #42; isolated R3A database only.
Changed: 2026-11-06T15:30:00Z | R3A-AP0-M1 | Codex GPT-6 | Add protected basic backup and separate-target restore.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Verify checksummed restore, apply forward migrations, and validate restored lineage.
Supersedes: None.
Contracts: AP0-013; AP0-M1 D9; STM-003/007.
Tests: tests/test_r3a_backup.py; actual disposable DB restore evidence.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.conninfo import make_conninfo
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import Settings
from .db import Store


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _run(command: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode("utf-8", "replace")[-4000:]
        raise RuntimeError(f"{Path(command[0]).name} failed ({process.returncode}): {message}")


async def create_backup(settings: Settings, output: Path | None = None) -> dict[str, Any]:
    backup_dir = settings.data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = output.resolve() if output else backup_dir / f"{settings.instance_id}-{stamp}.dump"
    if target.exists():
        raise FileExistsError(f"Backup output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.touch(mode=0o600, exist_ok=False)
    conn = settings.connection_info
    await _run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--no-password",
                "--host", conn["host"], "--port", str(conn["port"]), "--username", conn["user"],
                "--file", str(target), conn["dbname"]])
    target.chmod(0o600)
    store = Store(settings)
    await store.open()
    try:
        counts = await store.rows(
            "SELECT (SELECT count(*) FROM r3a.institution_events) AS events,"
            "(SELECT count(*) FROM r3a.activities) AS activities,"
            "(SELECT count(*) FROM r3a.config_revisions) AS config_revisions,"
            "(SELECT max(version) FROM r3a.schema_migrations) AS latest_migration"
        )
    finally:
        await store.close()
    config_copy = target.with_suffix(target.suffix + ".bootstrap.json")
    config_copy.write_bytes(settings.source_path.read_bytes())
    config_copy.chmod(0o600)
    manifest = {"format_version": 1, "instance_id": settings.instance_id,
                "database": settings.database, "created_at": datetime.now(timezone.utc).isoformat(),
                "config_revision": settings.source_digest,
                "schema_migration": counts[0]["latest_migration"],
                "counts": counts[0], "dump_file": target.name,
                "dump_sha256": digest_file(target),
                "bootstrap_file": config_copy.name,
                "bootstrap_sha256": digest_file(config_copy),
                "contains_secret_values": False}
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)
    return {"artifact": str(target), "manifest": str(manifest_path),
            "sha256": manifest["dump_sha256"], "counts": counts[0],
            "config_revision": settings.source_digest}


async def restore_backup(settings: Settings, backup: Path, target_database: str) -> dict[str, Any]:
    backup = backup.expanduser().resolve()
    if not backup.is_file():
        raise FileNotFoundError(backup)
    if not re.fullmatch(r"r3a_[a-z0-9_]{1,50}", target_database):
        raise ValueError("restore target database must use the isolated r3a_<name> form")
    if target_database == settings.database:
        raise ValueError("restore target must be a separate database")
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if digest_file(backup) != manifest.get("dump_sha256"):
        raise RuntimeError("Backup checksum does not match its manifest")
    if manifest.get("instance_id") != settings.instance_id or manifest.get("database") != settings.database:
        raise RuntimeError("Backup manifest does not identify this isolated source instance")
    admin = {"dbname": "postgres", "user": "admin1", "host": str(settings.database_socket_dir),
             "port": settings.database_port, "connect_timeout": 3}
    admin_dsn = make_conninfo(**admin)
    async with await AsyncConnection.connect(admin_dsn, autocommit=True,
                                             row_factory=dict_row) as conn:
        found = await (await conn.execute("SELECT 1 FROM pg_database WHERE datname=%s",
                                          (target_database,))).fetchone()
        if found:
            raise FileExistsError(f"Restore target already exists: {target_database}")
        await conn.execute(f'CREATE DATABASE "{target_database}" OWNER r3a_runtime')
    await _run(["pg_restore", "--no-owner", "--no-acl", "--exit-on-error", "--role=r3a_runtime",
                "--host", str(settings.database_socket_dir), "--port", str(settings.database_port),
                "--username", "admin1", "--dbname", target_database, str(backup)])
    target_settings = replace(settings, database=target_database)
    restored_store = Store(target_settings)
    await restored_store.open()
    try:
        await restored_store.migrate()
        await restored_store.seed_machines()
    finally:
        await restored_store.close()
    restored_conn = target_settings.connection_info
    restored_pool = AsyncConnectionPool(make_conninfo(**restored_conn), min_size=1, max_size=1,
                                        open=False, kwargs={"row_factory": dict_row})
    await restored_pool.open()
    await restored_pool.wait()
    try:
        async with restored_pool.connection() as conn:
            counts = await (await conn.execute(
                "SELECT (SELECT count(*) FROM r3a.institution_events) AS events,"
                "(SELECT count(*) FROM r3a.activities) AS activities,"
                "(SELECT count(*) FROM r3a.config_revisions) AS config_revisions,"
                "(SELECT count(*) FROM r3a.state_machine_definitions) AS state_machines,"
                "(SELECT version FROM r3a.schema_migrations ORDER BY version DESC LIMIT 1) AS latest_migration"
            )).fetchone()
            current = await (await conn.execute("SELECT revision_id FROM r3a.config_current WHERE singleton=true")).fetchone()
            if counts["events"] < manifest["counts"]["events"] or counts["activities"] < manifest["counts"]["activities"]:
                raise RuntimeError("Restored event or activity lineage is incomplete")
            if not current or current["revision_id"] != manifest["config_revision"]:
                raise RuntimeError("Restored effective configuration revision does not match backup manifest")
    finally:
        await restored_pool.close()
    return {"target_database": target_database, "counts": counts,
            "config_revision": current["revision_id"], "status": "restored_and_verified",
            "diagnostic_projection": "available from restored PostgreSQL records; process freshness is evaluated on query"}
