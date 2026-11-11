/*
R3 CONTROLLED SOURCE
File: web/r3a-operations.mjs
Component: R3A-WEBSITE-OPERATIONS
File Revision: 1.0.0
Created: 2026-11-11 UTC
Created By: Codex GPT-6
Purpose: Project authenticated CME diagnostics into the Website Infrastructure and Engineering views.
Execution Model: Read-only same-origin Website APIs; no local registry or fabricated telemetry.
Observability: Preserves server timestamps, freshness, lifecycle state, and explicit unavailable results.
Dependencies: r3a.website-about.v1; CME diagnostics.status and diagnostics.events.
Authority: R3A Website Integration Audit and Repair, Issue #51.
Tests: tests/test_r3a_operations.mjs.
*/

const EASTERN = 'America/New_York';

export function localTimestamp(value) {
  if (!value) return 'Time unavailable';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Time unavailable';
  return new Intl.DateTimeFormat('en-US', {
    timeZone: EASTERN, dateStyle: 'medium', timeStyle: 'medium',
  }).format(date);
}

export function projectRuntimeDiagnostics(status, history = {}) {
  if (!status || status.source !== 'postgresql' || !Array.isArray(status.processes)) {
    throw new TypeError('Authoritative CME diagnostics are unavailable or invalid');
  }
  return {
    observedAt: status.observed_at || null,
    freshness: status.source_freshness || 'unknown',
    source: status.source,
    implementationRevision: status.implementation_revision || 'unknown',
    configRevision: status.configuration?.revision_id || 'unknown',
    processes: status.processes.map(process => ({
      id: String(process.component_id || 'unknown'),
      state: String(process.state || 'unknown'),
      health: String(process.health || 'unknown'),
      freshness: String(process.freshness || 'unknown'),
      heartbeatAgeSeconds: Number.isFinite(process.heartbeat_age_seconds)
        ? process.heartbeat_age_seconds : null,
      heartbeatAt: process.heartbeat_at || null,
      schedulerTickAgeSeconds: Number.isFinite(process.details?.scheduler_tick_age_seconds)
        ? process.details.scheduler_tick_age_seconds : null,
    })),
    modules: (status.modules || []).map(module => ({
      id: String(module.module_id || 'unknown'),
      version: String(module.module_version || 'unknown'),
      state: String(module.lifecycle_state || 'unknown'),
      health: String(module.health || 'unknown'),
      freshness: String(module.freshness || 'unknown'),
      observedAt: module.observed_at || null,
    })),
    resources: (status.resources || []).map(resource => ({
      id: String(resource.resource_id || 'unknown'),
      health: String(resource.health || 'unknown'),
      observedAt: resource.observed_at || null,
    })),
    activityCounts: Object.fromEntries(Object.entries(status.activity_state_counts || {})
      .map(([state, count]) => [state, Number.isFinite(count) ? count : null])),
    activities: (status.activities || []).map(activity => ({
      id: String(activity.activity_id || 'unknown'),
      type: String(activity.activity_type || 'unknown'),
      state: String(activity.state || 'unknown'),
      updatedAt: activity.updated_at || null,
      attemptCount: Number.isFinite(activity.attempt_count) ? activity.attempt_count : null,
    })),
    events: (history.events || []).map(event => ({
      type: String(event.event_type || 'unknown'),
      subjectType: String(event.subject_type || 'unknown'),
      subjectId: String(event.subject_id || 'unknown'),
      persistedAt: event.persisted_at || null,
      correlationId: event.correlation_id || null,
    })),
  };
}

export function projectEngineeringRegistry(about, capabilities) {
  if (about?.contract !== 'r3a.website-about.v1' || !Array.isArray(about.modules)
      || !Array.isArray(capabilities?.operations)) {
    throw new TypeError('R3A Engineering registry contracts are unavailable or invalid');
  }
  const engineeringModules = about.modules.filter(module =>
    /engineering|workspace/i.test(String(module.module_id || '')));
  const engineeringOperations = capabilities.operations.map(entry => entry.descriptor || entry)
    .filter(operation => /engineering|workspace/i.test(String(operation.operation_id || '')))
    .map(operation => ({id: String(operation.operation_id), version: String(operation.contract_version
      || operation.operation_contract_version || 'unknown'), provider: String(operation.provider?.provider_id || 'unknown')}));
  return {
    observedAt: about.observed_at || null,
    freshness: String(about.freshness || 'unknown'),
    runtimeRevision: String(about.deployed_runtime_revision || 'unknown'),
    repository: 'Repository source is not provided by the R3A Engineering contracts currently exposed to this Website.',
    modules: engineeringModules.map(module => ({id: String(module.module_id || 'unknown'),
      version: String(module.module_version || 'unknown'), state: String(module.lifecycle_state || 'unknown'),
      health: String(module.health || 'unknown'), freshness: String(module.freshness || 'unknown')})),
    operations: engineeringOperations,
  };
}

export async function loadEngineeringRegistry({fetchImpl = globalThis.fetch} = {}) {
  const [aboutResponse, capabilitiesResponse] = await Promise.all([
    fetchImpl.call(globalThis, '/api/v1/steward/about', {credentials: 'same-origin', cache: 'no-store'}),
    fetchImpl.call(globalThis, '/api/v1/steward/capabilities', {credentials: 'same-origin', cache: 'no-store'}),
  ]);
  if (!aboutResponse.ok || !capabilitiesResponse.ok) {
    const status = !aboutResponse.ok ? aboutResponse.status : capabilitiesResponse.status;
    throw new Error(status === 401 ? 'Website session required' : `R3A registry unavailable (${status})`);
  }
  return projectEngineeringRegistry(await aboutResponse.json(), await capabilitiesResponse.json());
}

function renderRows(root, id, rows, format) {
  const list = root.getElementById(id);
  if (!list) return;
  list.replaceChildren();
  if (!rows.length) {
    const item = root.createElement('li');
    item.textContent = 'No records were returned.';
    list.appendChild(item);
    return;
  }
  for (const row of rows) {
    const item = root.createElement('li');
    item.textContent = format(row);
    list.appendChild(item);
  }
}

export function renderRuntimeDiagnostics(root, data) {
  const set = (id, value) => {
    const element = root.getElementById(id);
    if (element) element.textContent = String(value);
  };
  set('infra-source-status', `Source: ${data.source} · ${data.freshness} · observed ${localTimestamp(data.observedAt)}`);
  set('infra-revision-status', `CME ${data.implementationRevision} · configuration ${data.configRevision}`);
  renderRows(root, 'infra-processes', data.processes, process => {
    const ages = [`heartbeat ${process.heartbeatAgeSeconds === null ? 'unavailable' : `${process.heartbeatAgeSeconds.toFixed(1)}s`} ago`];
    if (process.schedulerTickAgeSeconds !== null) ages.push(`scheduler tick ${process.schedulerTickAgeSeconds.toFixed(1)}s ago`);
    return `${process.id} · ${process.state} · ${process.health}/${process.freshness} · ${ages.join(' · ')}`;
  });
  renderRows(root, 'infra-activity-counts', Object.entries(data.activityCounts), ([state, count]) => `${state}: ${count}`);
  renderRows(root, 'infra-modules', data.modules, module =>
    `${module.id}@${module.version} · ${module.state} · ${module.health}/${module.freshness} · ${localTimestamp(module.observedAt)}`);
  renderRows(root, 'infra-resources', data.resources, resource =>
    `${resource.id} · ${resource.health} · observed ${localTimestamp(resource.observedAt)}`);
  renderRows(root, 'infra-activities', data.activities, activity =>
    `${activity.type} · ${activity.state} · attempts ${activity.attemptCount ?? 'unknown'} · ${localTimestamp(activity.updatedAt)}`);
  renderRows(root, 'infra-event-history', data.events, event =>
    `${event.type} · ${event.subjectType}:${event.subjectId} · ${localTimestamp(event.persistedAt)}${event.correlationId ? ` · ${event.correlationId}` : ''}`);
}

export async function loadRuntimeDiagnostics({fetchImpl = globalThis.fetch} = {}) {
  const [statusResponse, historyResponse] = await Promise.all([
    fetchImpl.call(globalThis, '/api/v1/steward/r3a/status', {
      credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'},
    }),
    fetchImpl.call(globalThis, '/api/v1/steward/r3a/events', {
      credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'},
    }),
  ]);
  if (!statusResponse.ok || !historyResponse.ok) {
    const status = !statusResponse.ok ? statusResponse.status : historyResponse.status;
    const error = new Error(status === 401 ? 'Website session required' : `R3A diagnostics unavailable (${status})`);
    error.status = status;
    throw error;
  }
  return projectRuntimeDiagnostics(await statusResponse.json(), await historyResponse.json());
}

export function mountInfrastructure({root = document, fetchImpl = globalThis.fetch} = {}) {
  const panel = root.getElementById('infrastructure-panel');
  const refresh = root.getElementById('infrastructure-refresh');
  const status = root.getElementById('infra-source-status');
  if (!panel || !refresh || !status) return;
  let busy = false;
  const update = async () => {
    if (busy) return;
    busy = true;
    refresh.disabled = true;
    status.textContent = 'Loading authenticated CME diagnostics…';
    try {
      const data = await loadRuntimeDiagnostics({fetchImpl});
      renderRuntimeDiagnostics(root, data);
    } catch (error) {
      status.textContent = `${error.message}. No cached or fabricated telemetry is displayed.`;
      for (const id of ['infra-processes', 'infra-activity-counts', 'infra-modules', 'infra-resources', 'infra-activities', 'infra-event-history']) {
        renderRows(root, id, [], () => '');
      }
    } finally {
      busy = false;
      refresh.disabled = false;
    }
  };
  refresh.addEventListener('click', update);
  root.getElementById('nav-infrastructure')?.addEventListener('click', update);
  update();
}

if (typeof document !== 'undefined') mountInfrastructure();

export function mountEngineering({root = document, fetchImpl = globalThis.fetch} = {}) {
  const refresh = root.getElementById('refresh-status');
  const status = root.getElementById('api-status');
  if (!refresh || !status) return;
  const repository = root.getElementById('repo-status');
  const modules = root.getElementById('branch-list');
  const operations = root.getElementById('worktree-list');
  let busy = false;
  const update = async () => {
    if (busy) return;
    busy = true;
    refresh.disabled = true;
    status.textContent = 'Loading authenticated R3A Engineering registry…';
    try {
      const data = await loadEngineeringRegistry({fetchImpl});
      status.textContent = `R3A runtime ${data.runtimeRevision} · ${data.freshness} · observed ${localTimestamp(data.observedAt)}`;
      repository.textContent = data.repository;
      renderRows(root, 'branch-list', data.modules, module =>
        `${module.id}@${module.version} · ${module.state} · ${module.health}/${module.freshness}`);
      renderRows(root, 'worktree-list', data.operations, operation =>
        `${operation.id} · ${operation.version} · provider ${operation.provider}`);
    } catch (error) {
      status.textContent = `R3A Engineering registry unavailable: ${error.message}. No legacy or cached status is shown.`;
      repository.textContent = 'R3A repository information unavailable from the registered Website contracts.';
      renderRows(root, 'branch-list', [], () => '');
      renderRows(root, 'worktree-list', [], () => '');
    } finally {
      busy = false;
      refresh.disabled = false;
    }
  };
  refresh.addEventListener('click', update);
  update();
}

if (typeof document !== 'undefined') mountEngineering();
