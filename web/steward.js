/*
R3 CONTROLLED SOURCE
File: web/steward.js
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.0.1
Created: 2026-11-07T21:46:03Z
Created By: Codex GPT-6
Purpose: Drive the same-origin Steward session, status, logout, and authorized operation controls.
Execution Model: Browser-side fetch with same-origin credentials and no persistent bearer-token storage.
Observability: Renders session freshness, service state, and correlated operation evidence as text.
Dependencies: /api/v1/steward/session; /api/v1/steward/status; /api/v1/steward/operations/invoke.
Authority: AP3-M1 Issue #49; CSP allows same-origin scripts only.
Changed: 2026-11-07T21:46:03Z | AP3-M1 | Codex GPT-6 | Move controls to a same-origin script for a restrictive CSP.
Changed: 2026-11-07T21:48:11Z | AP3-M1 | Codex GPT-6 | Show measured CME health in the session status line.
Supersedes: None.
Contracts: r3a.steward-session.v1; r3a.steward-operation-result.v1; r3a.steward-access-status.v1.
Tests: tests/test_r3a_steward_access.py; mobile transport verification awaits configured ingress.
History/Predecessor: New file; initial publication recorded in Git.
*/
const $ = id => document.getElementById(id);

async function call(path, options = {}) {
  const response = await fetch(path, {credentials: 'same-origin', cache: 'no-store', ...options});
  let body;
  try { body = await response.json(); } catch { body = {status: response.status, state: 'unavailable'}; }
  if (!response.ok) throw Object.assign(new Error(body.detail || `Request unavailable (${response.status})`), {body, status: response.status});
  return body;
}

function show(value) { $('result').textContent = JSON.stringify(value, null, 2); }

async function refresh() {
  try {
    const state = await call('/api/v1/steward/status');
    $('session-state').textContent = `${state.authentication} · CME ${state.cme.health} · session ${state.session_freshness} · transport ${state.remote_transport}`;
    show(state);
  } catch (error) {
    $('session-state').textContent = error.message;
    show({state: 'unavailable', status: error.status || null});
  }
}

$('begin').addEventListener('click', async () => {
  try {
    show(await call('/api/v1/steward/session', {method: 'POST'}));
    await refresh();
  } catch (error) {
    show({state: 'authentication_denied_or_unavailable', status: error.status || null});
  }
});
$('refresh').addEventListener('click', refresh);
$('end').addEventListener('click', async () => {
  try {
    show(await call('/api/v1/steward/session', {method: 'DELETE'}));
    $('session-state').textContent = 'Session ended.';
  } catch (error) {
    show({state: 'session_unavailable', status: error.status || null});
  }
});
$('invoke').addEventListener('click', async () => {
  try {
    const request = JSON.parse($('invocation').value);
    show(await call('/api/v1/steward/operations/invoke', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({request})
    }));
  } catch (error) {
    show({state: error instanceof SyntaxError ? 'invalid_invocation_json' : 'operation_denied_or_unavailable',
          status: error.status || null, detail: error instanceof SyntaxError ? error.message : undefined});
  }
});
refresh();
