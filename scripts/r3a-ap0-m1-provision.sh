#!/usr/bin/env bash
# R3 CONTROLLED SOURCE
# File: scripts/r3a-ap0-m1-provision.sh
# Component: R3A-AP0-ISOLATED-PROVISIONING
# File Revision: 1.0.0
# Created: 2026-11-06T15:24:00Z
# Created By: Codex GPT-6
# Purpose: Provision a private local AP0 PostgreSQL cluster and user services without touching R/3.
# Execution Model: Run as the unprivileged development owner from the R3A checkout.
# Observability: Dedicated paths, Unix socket, PostgreSQL identity, unit status and CLI diagnostics.
# Dependencies: Python venv already installed; PostgreSQL 16 server/client; systemd user manager.
# Authority: AP0-M1 implementation authorization in GitHub Issue #42; isolated R3A resources only.
# Changed: 2026-11-06T15:24:00Z | R3A-AP0-M1 | Codex GPT-6 | Add safe local provisioner.
# Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Allow local peer-authenticated restore targets within the isolated cluster.
# Supersedes: None.
# Contracts: AP0-001/002/004/009/011/013; AP0-M1 D1/D2/D3/D7/D9.
# Tests: Fresh isolated cluster start, role/DB identity query, user unit launch.
# History/Predecessor: New file; initial publication recorded in Git.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/r3a-ap0-m1"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}/r3a-ap0-m1"
unit_root="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
postgres_bin="/usr/lib/postgresql/16/bin"
socket_dir="$state_root/run"
config_file="$config_root/bootstrap.json"
port=55492

if [[ "$(id -un)" == "postgres" || "$(id -u)" == 0 ]]; then
  echo "Run this as the isolated development owner, not root or postgres." >&2
  exit 2
fi
if ! systemctl --user is-active --quiet default.target; then
  echo "The user systemd manager is not active." >&2
  exit 2
fi
if systemctl is-active --quiet r3-institution.service; then
  echo "Production r3-institution.service is active and will not be modified." >&2
fi
if [[ ! -x "$postgres_bin/initdb" || ! -x "$postgres_bin/postgres" ]]; then
  echo "PostgreSQL 16 server binaries are required at $postgres_bin." >&2
  exit 2
fi
if [[ -e "$state_root/PG_VERSION" ]]; then
  echo "Refusing to reinitialize existing isolated cluster at $state_root." >&2
  exit 2
fi

install -d -m 0700 "$state_root" "$config_root" "$unit_root"
"$postgres_bin/initdb" -D "$state_root" --username="$(id -un)" --no-locale --encoding=UTF8 \
  --auth-local=peer --auth-host=reject
install -d -m 0700 "$socket_dir"

cat >"$state_root/postgresql.conf" <<EOF
data_directory = '$state_root'
hba_file = '$state_root/pg_hba.conf'
ident_file = '$state_root/pg_ident.conf'
listen_addresses = ''
port = $port
unix_socket_directories = '$socket_dir'
unix_socket_permissions = 0700
password_encryption = 'scram-sha-256'
max_connections = 30
EOF
cat >"$state_root/pg_hba.conf" <<'EOF'
local all admin1 peer
local all r3a_runtime peer map=r3a_local
local all all reject
host all all 127.0.0.1/32 reject
host all all ::1/128 reject
EOF
cat >"$state_root/pg_ident.conf" <<'EOF'
# MAPNAME       SYSTEM-USERNAME   PG-USERNAME
r3a_local       admin1            r3a_runtime
EOF
chmod 0600 "$state_root/postgresql.conf" "$state_root/pg_hba.conf" "$state_root/pg_ident.conf"

cat >"$unit_root/r3a-ap0-m1-postgres.service" <<EOF
[Unit]
Description=Isolated R3A AP0-M1 PostgreSQL cluster
After=basic.target

[Service]
Type=simple
ExecStart=$postgres_bin/postgres -D $state_root
Restart=on-failure
RestartSec=2s
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$state_root

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now r3a-ap0-m1-postgres.service
for _ in $(seq 1 30); do
  if "$postgres_bin/pg_isready" -h "$socket_dir" -p "$port" -d postgres -U "$(id -un)" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
"$postgres_bin/pg_isready" -h "$socket_dir" -p "$port" -d postgres -U "$(id -un)"

psql -X -v ON_ERROR_STOP=1 -h "$socket_dir" -p "$port" -U "$(id -un)" -d postgres \
  -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='r3a_runtime') THEN CREATE ROLE r3a_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION; END IF; END \$\$;"
if ! psql -X -At -h "$socket_dir" -p "$port" -U "$(id -un)" -d postgres \
     -c "SELECT 1 FROM pg_database WHERE datname='r3a_ap0_m1'" | grep -qx 1; then
  createdb -h "$socket_dir" -p "$port" -U "$(id -un)" -O r3a_runtime r3a_ap0_m1
fi

module_sha="$(sha256sum "$repo_root/r3a_runtime/observer_module.py" | cut -d' ' -f1)"
python3 - "$config_file" "$state_root" "$socket_dir" "$repo_root" "$module_sha" "$port" <<'PY'
import json, pathlib, sys
path, state, sock, repo, digest, port = sys.argv[1:]
state = pathlib.Path(state)
repo = pathlib.Path(repo)
value = {
  "schema_version": 1,
  "instance_id": "r3a_ap0_m1",
  "paths": {
    "data_dir": str(state),
    "postgres_socket_dir": sock,
    "control_socket": str(state / "run" / "cme-control.sock"),
    "diagnostics_socket": str(state / "run" / "diagnostics.sock"),
    "module_socket": str(state / "run" / "module.sock"),
    "machine_catalog_dir": str(repo / "r3a_runtime" / "state_machines")
  },
  "postgres": {"database": "r3a_ap0_m1", "user": "r3a_runtime", "socket_dir": sock, "port": int(port)},
  "module": {
    "module_id": "foundation.observer", "version": "1.0.0", "contract_id": "r3a.module.v1",
    "protocol_major": 1, "protocol_minor": 0,
    "capabilities": ["host.process.read", "postgres.readiness"], "owner": "R3A-CME",
    "entrypoint": "r3a_runtime.observer_module", "source": str(repo / "r3a_runtime" / "observer_module.py"),
    "sha256": digest
  },
  "timing": {
    "observer_interval_seconds": 2, "scheduler_interval_seconds": 0.25, "lease_seconds": 15,
    "heartbeat_interval_seconds": 2, "heartbeat_stale_after_seconds": 8,
    "diagnostic_stale_after_seconds": 8, "restart_initial_seconds": 0.5,
    "restart_max_seconds": 5, "worker_concurrency": 1
  }
}
target = pathlib.Path(path)
target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
target.chmod(0o600)
PY

cat >"$unit_root/r3a-ap0-m1-ring0.service" <<EOF
[Unit]
Description=Isolated R3A AP0-M1 Ring 0 supervisor
Requires=r3a-ap0-m1-postgres.service
After=r3a-ap0-m1-postgres.service

[Service]
Type=notify
NotifyAccess=main
WatchdogSec=12s
ExecStart=$repo_root/.venv/bin/python -m r3a_runtime.ring0 --config $config_file
WorkingDirectory=$repo_root
Restart=on-failure
RestartSec=2s
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$state_root

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now r3a-ap0-m1-ring0.service
echo "Isolated R3A AP0-M1 provisioning started."
echo "Config: $config_file"
echo "Data:   $state_root"
echo "Socket: $socket_dir (port $port; TCP disabled)"
echo "Units:  r3a-ap0-m1-postgres.service, r3a-ap0-m1-ring0.service"
