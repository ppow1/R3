# R3 CONTROLLED SOURCE
# File: tests/Test-R3CandidateBridge.ps1
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.3
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Permanent PowerShell 7 offline bridge regression tests
# Execution Model: Local only; invokes bridge with invalid paths, no SSH permitted
# Observability: Assertions and nonzero exit on failure
# Dependencies: PowerShell 7, scripts/deployment/Prepare-R3Candidate.ps1
# Authority: Steward permanent regression policy
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-015 | ChatGPT GPT-6 | Initial bridge validation tests
# Changed: 2026-11-04 UTC | R3-MANIFEST-DEPLOY-017 | ChatGPT GPT-6 | Add missing, malformed and unapproved manifest regression cases
# Changed: 2026-11-04 UTC | R3-MANIFEST-DEPLOY-019 | ChatGPT GPT-6 | Enforce bounded SSH/fetch/build contract
# Changed: 2026-11-04 UTC | R3-MANIFEST-DEPLOY-020 | ChatGPT GPT-6 | Preserve literal variable in timeout substitution assertion
# Supersedes: None
# Superseded By: None
# Contracts: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not yet executed on Windows
# History/Predecessor: None
$ErrorActionPreference = 'Stop'
$bridge = Join-Path $PSScriptRoot '../scripts/deployment/Prepare-R3Candidate.ps1'
$validator = Join-Path $PSScriptRoot '../scripts/deployment/Deploy-R3.ps1'
$passed = 0
$failed = 0

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Test-Parser([string]$Path) {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path $Path).Path, [ref]$tokens, [ref]$errors) | Out-Null
    Assert-True ($errors.Count -eq 0) "Parser errors in $Path : $($errors | Out-String)"
}
function Test-Case([string]$Name, [scriptblock]$Action) {
    try {
        & $Action
        $script:passed++
        Write-Host "PASS $Name"
    } catch {
        $script:failed++
        Write-Host "FAIL $Name : $($_.Exception.Message)"
    }
}
Test-Case 'bridge parses' { Test-Parser $bridge }
Test-Case 'validator parses' { Test-Parser $validator }

# This test runs each invalid request in its own PowerShell process. Even if
# the bridge calls exit 1, the test harness remains alive.
Test-Case 'unsafe paths fail before SSH' {
    $manifest = Join-Path ([IO.Path]::GetTempPath()) ("r3-bridge-" + [guid]::NewGuid().ToString('N') + '.json')
    try {
        $fixture = @{
            schemaVersion = 1
            source = @{ type='github'; repositoryUrl='https://github.com/ppow1/R3.git'; commit=('a'*40) }
            target = @{ service='website'; sshAlias='camrui'; port=18303; releaseRoot='/tmp/releases'; activeSymlink='/tmp/active'; venvPath='/tmp/venv'; entrypoint='r3_app:app'; healthPath='/health' }
            dependencies = @{ manager='pip'; installMode='locked'; requirementsFile='requirements-deploy.lock'; pythonVersion='3.12'; hashesRequired=$true }
            tests = @{ profile='website'; timeoutSeconds=30; onFailure='abort-before-activation' }
        }
        $fixture | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifest
        foreach ($unsafe in @('/home/admin1/R3/overwrite',
                              '/home/admin1/candidate$(touch /tmp/r3-pwned)',
                              '/home/admin1/candidate'';echo bad',
                              '/home/admin1/../tmp/candidate',
                              '/tmp/candidate')) {
            $output = & pwsh -NoProfile -NonInteractive -File $bridge -Manifest $manifest -CandidateRoot $unsafe -SkipClipboard 2>&1 | Out-String
            Assert-True ($LASTEXITCODE -ne 0) "Accepted unsafe path: $unsafe"
            Assert-True ($output -match 'ERROR=') "No failure diagnostics for: $unsafe"
            Assert-True ($output -notmatch 'R3_CANDIDATE_BUILD_ONLY=TRUE') "Attempted SSH for unsafe path: $unsafe"
        }
    } finally {
        Remove-Item -LiteralPath $manifest -ErrorAction SilentlyContinue
    }
}
# Invalid inputs must fail before any remote command can be constructed.
# Keep these as permanent tests, not one-off diagnostics.
Test-Case 'missing manifest fails before SSH' {
    $missing = Join-Path ([IO.Path]::GetTempPath()) ("r3-missing-" + [guid]::NewGuid().ToString('N') + '.json')
    $output = & pwsh -NoProfile -NonInteractive -File $bridge -Manifest $missing -CandidateRoot '/home/admin1/r3-candidate-test' -SkipClipboard 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -ne 0) 'Accepted nonexistent manifest'
    Assert-True ($output -match 'ERROR=') 'Missing manifest produced no diagnostics'
    Assert-True ($output -notmatch 'R3_CANDIDATE_BUILD_ONLY=TRUE') 'Attempted SSH with missing manifest'
}
Test-Case 'malformed JSON fails before SSH' {
    $manifest = Join-Path ([IO.Path]::GetTempPath()) ("r3-malformed-" + [guid]::NewGuid().ToString('N') + '.json')
    try {
        [IO.File]::WriteAllText($manifest, '{invalid json')
        $output = & pwsh -NoProfile -NonInteractive -File $bridge -Manifest $manifest -CandidateRoot '/home/admin1/r3-candidate-test' -SkipClipboard 2>&1 | Out-String
        Assert-True ($LASTEXITCODE -ne 0) 'Accepted malformed JSON'
        Assert-True ($output -match 'ERROR=') 'Malformed JSON produced no diagnostics'
        Assert-True ($output -notmatch 'R3_CANDIDATE_BUILD_ONLY=TRUE') 'Attempted SSH with malformed JSON'
    } finally {
        Remove-Item -LiteralPath $manifest -ErrorAction SilentlyContinue
    }
}
Test-Case 'unapproved repository fails before SSH' {
    $manifest = Join-Path ([IO.Path]::GetTempPath()) ("r3-repository-" + [guid]::NewGuid().ToString('N') + '.json')
    try {
        $fixture = @{
            schemaVersion = 1
            source = @{ type='github'; repositoryUrl='https://github.com/other/repo.git'; commit=('a'*40) }
            target = @{ service='website'; sshAlias='camrui'; port=18303; releaseRoot='/tmp/releases'; activeSymlink='/tmp/active'; venvPath='/tmp/venv'; entrypoint='r3_app:app'; healthPath='/health' }
            dependencies = @{ manager='pip'; installMode='locked'; requirementsFile='requirements-deploy.lock'; pythonVersion='3.12'; hashesRequired=$true }
            tests = @{ profile='website'; timeoutSeconds=30; onFailure='abort-before-activation' }
        }
        $fixture | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifest
        $output = & pwsh -NoProfile -NonInteractive -File $bridge -Manifest $manifest -CandidateRoot '/home/admin1/r3-candidate-test' -SkipClipboard 2>&1 | Out-String
        Assert-True ($LASTEXITCODE -ne 0) 'Accepted unapproved repository'
        Assert-True ($output -match 'ERROR=') 'Unapproved repository produced no diagnostics'
        Assert-True ($output -notmatch 'R3_CANDIDATE_BUILD_ONLY=TRUE') 'Attempted SSH with unapproved repository'
    } finally {
        Remove-Item -LiteralPath $manifest -ErrorAction SilentlyContinue
    }
}
# Enforce fail-fast SSH options and bounded remote work in the checked-in bridge.
Test-Case 'SSH and remote work are bounded' {
    $source = Get-Content -LiteralPath $bridge -Raw
    Assert-True ($source.Contains('-o BatchMode=yes -o ConnectTimeout=10 -o ConnectionAttempts=1')) 'SSH fail-fast options missing'
    Assert-True ($source.Contains('timeout 30s git fetch origin main --quiet')) 'Remote Git fetch is unbounded'
    Assert-True ($source.Contains('timeout __BUILD_TIMEOUT__s python3')) 'Remote candidate builder is unbounded'
    Assert-True ($source.Contains('Replace(''__BUILD_TIMEOUT__'', [string]$buildTimeout)')) 'Builder timeout substitution missing'
    Assert-True ($source.Contains('if ($sshExit -ne 0)')) 'Nonzero SSH exit not rejected'
    Assert-True ($source.Contains("Emit 'WEBSITE_ACTIVATION=NOT_RUN'")) 'No activation safety status'
}
Write-Host "BRIDGE_TESTS_PASS=$passed"
Write-Host "BRIDGE_TESTS_FAIL=$failed"
Write-Host 'WEBSITE_ACTIVATION=NOT_RUN'
if ($failed -gt 0) { exit 1 }
