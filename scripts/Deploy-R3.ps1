# R3 CONTROLLED SOURCE
# File: scripts/Deploy-R3.ps1
# Component: R3-DEPLOYMENT
# File Revision: 1.0.3
# Created: 2026-10-31 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Parameterized deployment of R3 website to Camrui
# Execution Model: PowerShell 7 -> SSH camrui -> Bash
# Observability: Console and clipboard, HTTP checks, Git revision, process checks
# Dependencies: PowerShell 7, SSH alias camrui, Git, flock, curl, Python venv, ss
# Authority: Steward instruction to automate second deployment
# Changed: 2026-10-31 UTC | R3-DEPLOY-008 | ChatGPT GPT-6 | Verify Uvicorn process via user, cwd, executable and argv
# Supersedes: None
# Superseded By: None
# Contracts: docs/runbooks/R3_FIRST_WEBSITE_DEPLOYMENT.md; hints/file-provenance.md
# Tests: Not executed; live validation pending
# History/Predecessor: Git blob df394fc6f5f2a32b384753083ec1b2e70bc96a3f

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidatePattern('^[0-9a-fA-F]{7,40}$')]
    [string]$Commit
)
Clear-Host
$ErrorActionPreference = 'Stop'
$remote = @'
set -Eeuo pipefail
cd /home/admin1/R3
target="$1"
port=8303
log=/tmp/r3-website.log
old=""
changed=0
say() { printf '\n=== %s ===\n' "$1"; }
fail() { echo "ERROR: $*" >&2; exit 1; }
listener() { ss -ltnp '( sport = :8303 )' | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -1; }
owned() {
  local args user cwd exe
  args=$(ps -p "$1" -o args=) || return 1
  user=$(ps -p "$1" -o user= | tr -d ' ') || return 1
  cwd=$(readlink -f "/proc/$1/cwd") || return 1
  exe=$(readlink -f "/proc/$1/exe") || return 1
  [ "$user" = admin1 ] || return 1
  [ "$cwd" = /home/admin1/R3 ] || return 1
  [[ "$exe" == /home/admin1/R3/.venv/bin/python* || "$exe" == /usr/bin/python3* ]] || return 1
  [[ "$args" == *"uvicorn r3_app:app"* ]] || return 1
  [[ "$args" == *"--port 8303"* ]] || return 1
}
check_http() {
  local status
  status=$(curl --max-time 8 -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8303/api/v1/health) || return 1
  [ "$status" = 200 ] || return 1
  status=$(curl --max-time 8 -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8303/) || return 1
  [ "$status" = 200 ] || return 1
  status=$(curl --max-time 20 -s -o /dev/null -w '%{http_code} %{content_type} %{size_download}' http://127.0.0.1:8303/api/v1/visual/background) || return 1
  echo "BACKGROUND $status"
  [[ "$status" == "200 image/png "* ]] || return 1
  [ "$(echo "$status" | awk '{print $3}')" -gt 1000 ]
}
stop_r3() {
  local pid="$1" i
  owned "$pid" || fail "Refusing to stop unrecognized PID $pid"
  kill "$pid"
  for i in $(seq 1 20); do
    [ -z "$(listener)" ] && return 0
    sleep 1
  done
  fail "R3 did not release port"
}
start_r3() {
  local i pid
  [ -z "$(listener)" ] || fail "Port occupied before startup"
  nohup /home/admin1/R3/.venv/bin/uvicorn r3_app:app --host 0.0.0.0 --port 8303 >"$log" 2>&1 </dev/null &
  for i in $(seq 1 15); do
    sleep 1
    pid=$(listener)
    if [ -n "$pid" ]; then
      owned "$pid" || fail "Foreign process claimed port"
      if check_http; then echo "HEALTHY_PID=$pid"; return 0; fi
    fi
  done
  tail -n 20 "$log" || true
  return 1
}
on_exit() {
  local status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$changed" -eq 1 ]; then
    echo "DEPLOY_FAILED; attempting rollback to $old" >&2
    local pid
    pid=$(listener)
    if [ -n "$pid" ]; then
      if owned "$pid"; then stop_r3 "$pid" || true
      else echo "FOREIGN_PORT_OWNER; rollback blocked" >&2; exit "$status"; fi
    fi
    if git checkout --detach --force "$old" && start_r3; then
      echo "ROLLBACK_HEALTHY=$old"
    else
      echo "ROLLBACK_FAILED; manual recovery required" >&2
    fi
  fi
  exit "$status"
}
trap on_exit EXIT
say LOCK
exec 9>/tmp/r3-deploy.lock
flock -n 9 || fail "Another R3 deployment is in progress"
say PREFLIGHT
[ "$(id -un)" = admin1 ] || fail "Unexpected user"
[ "$(git remote get-url origin)" = https://github.com/ppow1/R3.git ] || fail "Wrong repository"
[ -z "$(git diff --name-only)" ] || fail "Tracked working tree modified"
[ -z "$(git diff --cached --name-only)" ] || fail "Staged changes present"
unexpected=$(git ls-files --others --exclude-standard | grep -Ev '^([.]venv/|__pycache__/)' || true)
[ -z "$unexpected" ] || fail "Unexpected untracked files: $unexpected"
echo "RUNTIME_DIRECTORIES_PRESERVED=.venv/,__pycache__/"
[ -x .venv/bin/uvicorn ] || fail "Missing Python environment"
[ -f web/index.html ] || fail "Missing frontend"
[ -f assets/visual-concepts/Riverview3_Visual_Concept_Library.zip ] || fail "Missing ZIP"
old=$(git rev-parse HEAD)
echo "PREVIOUS_COMMIT=$old"
git fetch --quiet origin main
resolved=$(git rev-parse --verify "$target^{commit}") || fail "Unknown commit"
git merge-base --is-ancestor "$resolved" origin/main || fail "Target not on main"
echo "TARGET_COMMIT=$resolved"
target_app=$(git show "${resolved}:r3_app.py") || fail "Target app missing"
[[ "$target_app" == *'R3_modern_estate_clean_concept.png'* ]] || fail "Target does not select clean estate image"
.venv/bin/python - <<'PY'
import zipfile
p="assets/visual-concepts/Riverview3_Visual_Concept_Library.zip"
member="Riverview3_Visual_Concept_Library/backgrounds/R3_modern_estate_clean_concept.png"
with zipfile.ZipFile(p) as z:
    if member not in z.namelist() or z.getinfo(member).file_size < 1000:
        raise SystemExit("Missing/invalid clean estate background")
    print("ZIP_BACKGROUND_OK",z.getinfo(member).file_size)
PY
pid=$(listener)
if [ -n "$pid" ]; then owned "$pid" || fail "Foreign owner of port 8303"; fi
echo "RUNNING_VERSION_UNVERIFIED: controlled restart required"
say ACTIVATE
if [ -n "$pid" ]; then stop_r3 "$pid"; fi
changed=1
git checkout --detach --force "$resolved"
start_r3 || fail "Health checks failed"
say VERIFIED
echo "DEPLOYED_COMMIT=$(git rev-parse HEAD)"
echo "VISUAL_ACCEPTANCE=PENDING"
echo "URL=http://192.168.1.155:8303/"
'@
$result = ''
$exitCode = 1
try {
    $outputLines = @($remote | & ssh -o BatchMode=yes -o ConnectTimeout=8 camrui bash -s -- $Commit 2>&1)
    $exitCode = $LASTEXITCODE
    $result = $outputLines | Out-String
} catch {
    $result = "Execution error: $($_.Exception.Message)"
}
$clipboard = "$result" + [Environment]::NewLine + "SSH exit code: $exitCode"
Clear-Host
$result
"SSH exit code: $exitCode"
Set-Clipboard -Value $clipboard
if ($exitCode -ne 0) { throw "R3 deployment failed; review copied diagnostics before retrying." }
