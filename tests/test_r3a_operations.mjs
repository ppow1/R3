/*
R3 CONTROLLED SOURCE
File: tests/test_r3a_operations.mjs
Component: R3A-WEBSITE-OPERATIONS-TESTS
File Revision: 1.0.0
Created: 2026-11-11 (candidate publication date; original file creation time not recorded)
Created By: Unknown (upstream Website workstream author not recorded)
Purpose: Verify Website projections of authoritative CME diagnostics and Engineering registry state.
Execution Model: Node built-in test runner with controlled API fixtures.
Observability: Projection and HTTP contract assertions; fixtures are not live acceptance.
Dependencies: web/r3a-operations.mjs; Node.js built-in test modules.
Authority: R3A Website integration work under Issue #51.
Changed: 2026-11-11T18:04:20Z | R3A-WEBSITE-INTEGRATION-STEP46 | Codex GPT-6 | Add required source provenance during Coordinator integration.
Supersedes: None
Contracts: r3a.website-about.v1; CME diagnostics.status/events; hints/file-provenance.md.
Tests: node --test tests/test_r3a_operations.mjs.
History/Predecessor: New file from Website candidate 3bbe100ed112eb8f24416243a1c798962ac5f083.
*/
import test from 'node:test';
import assert from 'node:assert/strict';
import {localTimestamp, loadEngineeringRegistry, projectEngineeringRegistry, projectRuntimeDiagnostics} from '../web/r3a-operations.mjs';

test('runtime diagnostics preserve real process, queue, module, resource, and event evidence', () => {
  const projected = projectRuntimeDiagnostics({
    source: 'postgresql', source_freshness: 'fresh', observed_at: '2026-11-11T01:00:00Z',
    implementation_revision: 'core-sha', configuration: {revision_id: 'config-sha'},
    processes: [{component_id: 'cme', state: 'RUNNING', health: 'healthy', freshness: 'fresh',
      heartbeat_age_seconds: 1.25, heartbeat_at: '2026-11-11T00:59:59Z',
      details: {scheduler_tick_age_seconds: 0.5}}],
    modules: [{module_id: 'resident.grace', module_version: '1.2.13', lifecycle_state: 'ACTIVE',
      health: 'healthy', freshness: 'fresh', observed_at: '2026-11-11T00:59:58Z'}],
    resources: [{resource_id: 'model-role:resident.primary', health: 'ready', observed_at: '2026-11-11T00:59:57Z'}],
    activity_state_counts: {BLOCKED: 2, QUEUED: 1},
    activities: [{activity_id: 'activity-1', activity_type: 'grace.objective', state: 'BLOCKED',
      updated_at: '2026-11-11T00:59:56Z', attempt_count: 1, input: {private: 'not projected'}}],
  }, {events: [{event_type: 'activity.blocked', subject_type: 'activity', subject_id: 'activity-1',
    persisted_at: '2026-11-11T00:59:55Z', correlation_id: 'corr-1', evidence: {private: 'not projected'}}]});

  assert.equal(projected.source, 'postgresql');
  assert.equal(projected.implementationRevision, 'core-sha');
  assert.equal(projected.processes[0].schedulerTickAgeSeconds, 0.5);
  assert.deepEqual(projected.activityCounts, {BLOCKED: 2, QUEUED: 1});
  assert.equal(projected.modules[0].id, 'resident.grace');
  assert.equal(projected.resources[0].health, 'ready');
  assert.equal(projected.activities[0].state, 'BLOCKED');
  assert.equal(projected.events[0].correlationId, 'corr-1');
  assert.equal(JSON.stringify(projected).includes('private'), false);
});

test('infrastructure diagnostics fail closed on non-authoritative or malformed status', () => {
  assert.throws(() => projectRuntimeDiagnostics({source: 'cache', processes: []}), /unavailable or invalid/);
  assert.throws(() => projectRuntimeDiagnostics({source: 'postgresql', processes: {}}), /unavailable or invalid/);
});

test('Engineering view projects only registered R3A modules and operations', () => {
  const result = projectEngineeringRegistry({contract: 'r3a.website-about.v1', observed_at: '2026-11-11T01:00:00Z',
    freshness: 'fresh', deployed_runtime_revision: 'runtime-sha', modules: [
      {module_id: 'r3a.engineering.workflow', module_version: '1.0.0', lifecycle_state: 'ACTIVE', health: 'healthy', freshness: 'fresh'},
      {module_id: 'resident.grace', module_version: '1.2.13', lifecycle_state: 'ACTIVE', health: 'healthy'},
    ]}, {operations: [
      {descriptor: {operation_id: 'engineering.workspace.inspect', contract_version: '1.0.0', provider: {provider_id: 'r3a.engineering'}}},
      {descriptor: {operation_id: 'resident.objective.execute', contract_version: '1.0.0', provider: {provider_id: 'cme'}}},
    ]});
  assert.deepEqual(result.modules.map(item => item.id), ['r3a.engineering.workflow']);
  assert.deepEqual(result.operations.map(item => item.id), ['engineering.workspace.inspect']);
  assert.match(result.repository, /not provided/);
});

test('Engineering registry reads the authenticated Website contracts without legacy endpoints', async () => {
  const paths = [];
  const fetchImpl = async (path, options) => {
    paths.push([path, options.credentials, options.cache]);
    return {ok: true, json: async () => path.endsWith('/about')
      ? {contract: 'r3a.website-about.v1', modules: []} : {operations: []}};
  };
  await loadEngineeringRegistry({fetchImpl});
  assert.deepEqual(paths.map(item => item[0]), ['/api/v1/steward/about', '/api/v1/steward/capabilities']);
  assert.ok(paths.every(([, credentials, cache]) => credentials === 'same-origin' && cache === 'no-store'));
});

test('display timestamps use local Eastern time with seconds', () => {
  const formatted = localTimestamp('2026-11-11T01:00:00Z');
  assert.match(formatted, /8:00:00/);
  assert.match(formatted, /PM/);
  assert.equal(localTimestamp('invalid'), 'Time unavailable');
});
