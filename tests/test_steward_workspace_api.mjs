/*
R3 CONTROLLED SOURCE
File: tests/test_steward_workspace_api.mjs
Component: R3A-STEWARD-WORKSPACE-CLIENT-TESTS
File Revision: 1.0.2
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Verify the versioned workspace browser client transport and denial behavior.
Execution Model: Node test runner with development-only mocked fetch responses; no institutional records.
Observability: Asserts routes, session credentials mode, contract headers, errors, correlation, and idempotency.
Dependencies: web/steward-workspace-api.mjs; Node.js built-in test modules.
Authority: R3A Class I website development, Issue #51.
Changed: 2026-11-07 | R3A-007/R3A-010/R3A-019 | Add chat, notification, session, objective, and capability client tests.
Changed: 2026-11-08 | R3A-007/R3A-010 | Cover DST-aware UTC-preserving time display and unavailable API routing.
Supersedes: None.
Contracts: r3a.steward-workspace-web.v1; r3a.steward-session.v1; r3a.notification-inbox.v1; r3a.grace-objective-submission.v1.
Tests: node --test tests/test_steward_workspace_api.mjs.
History/Predecessor: New file; initial publication recorded in Git.
*/
// Mock fetch never supplies live institutional data.
import test from 'node:test';
import assert from 'node:assert/strict';
import {StewardWorkspaceApi, WorkspaceApiError, WORKSPACE_CONTRACT, formatPresentationTimestamp} from '../web/steward-workspace-api.mjs';

function response(status, payload, headers = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {get: name => headers[name] || null},
    json: async () => payload,
  };
}

test('conversation discovery uses same-origin session and versioned contract headers', async () => {
  let call;
  const api = new StewardWorkspaceApi(async (...args) => {
    call = args;
    return response(200, {contract: WORKSPACE_CONTRACT, freshness: 'current', residents: []});
  });
  const result = await api.residents();
  assert.equal(result.freshness, 'current');
  assert.equal(call[0], '/api/v1/steward/residents');
  assert.equal(call[1].credentials, 'same-origin');
  assert.equal(call[1].headers['X-R3A-Contract'], WORKSPACE_CONTRACT);
  assert.match(call[1].headers.Accept, /r3a\.steward-workspace-web\.v1/);
  assert.equal('Authorization' in call[1].headers, false);
});

test('desktop and mobile consume the shared opaque cookie session lifecycle', async () => {
  const requests = [];
  const api = new StewardWorkspaceApi(async (...args) => {
    requests.push(args);
    const state = args[1].method === 'POST' ? 'authenticated' : args[1].method === 'DELETE' ? 'revoked' : 'authenticated';
    return response(200, {contract: 'r3a.steward-session.v1', state, correlation_id: 'session-correlation'});
  });
  assert.equal((await api.startSession()).state, 'authenticated');
  assert.equal((await api.session()).state, 'authenticated');
  assert.equal((await api.endSession()).state, 'revoked');
  assert.deepEqual(requests.map(request => request[0]), Array(3).fill('/api/v1/steward/session'));
  assert.deepEqual(requests.map(request => request[1].method), ['POST', 'GET', 'DELETE']);
  assert.ok(requests.every(request => request[1].credentials === 'same-origin' && request[1].cache === 'no-store'));
  assert.ok(requests.every(request => !('Authorization' in request[1].headers)));
});

test('Grace objective requests carry their versioned CME submission contract', async () => {
  let call;
  const api = new StewardWorkspaceApi(async (...args) => {
    call = args;
    return response(202, {contract: 'r3a.grace-objective-submission.v1', contract_version: '1.0.0', activity_id: 'activity-1'});
  });
  await api.submitObjective({contract: 'r3a.grace-objective-submission.v1', contract_version: '1.0.0', objective: 'Inspect lifecycle', acceptance_criteria: [], idempotency_key: 'request-key'});
  assert.equal(call[0], '/api/v1/steward/r3a/objectives');
  assert.deepEqual(JSON.parse(call[1].body), {contract: 'r3a.grace-objective-submission.v1', contract_version: '1.0.0', objective: 'Inspect lifecycle', acceptance_criteria: [], idempotency_key: 'request-key'});
});

test('capability discovery is an explicit non-authorizing registry read', async () => {
  let call;
  const api = new StewardWorkspaceApi(async (...args) => {
    call = args;
    return response(200, {contract: 'r3a.steward-capability-discovery.v1', authorization_evaluated: false, operations: []});
  });
  const result = await api.capabilityDiscovery();
  assert.equal(call[0], '/api/v1/steward/capabilities');
  assert.equal(result.authorization_evaluated, false);
});

test('message sends preserve client idempotency identity and server correlation', async () => {
  let call;
  const api = new StewardWorkspaceApi(async (...args) => {
    call = args;
    return response(202, {contract: WORKSPACE_CONTRACT, freshness: 'current', message: {message_id: 'm-1'}, correlation_id: 'cme-1'});
  });
  const result = await api.sendMessage('conversation / 1', {clientMessageId: 'client-1', text: 'Hello Grace'});
  assert.match(call[0], /conversation%20%2F%201\/messages$/);
  assert.deepEqual(JSON.parse(call[1].body), {client_message_id: 'client-1', text: 'Hello Grace'});
  assert.equal(result.correlation_id, 'cme-1');
});

test('new conversation creation routes the selected authoritative resident with a retry key', async () => {
  let call;
  const api = new StewardWorkspaceApi(async (...args) => {
    call = args;
    return response(201, {contract: WORKSPACE_CONTRACT, freshness: 'current', conversation: {conversation_id: 'conversation-1', resident_id: 'resident:grace'}});
  });
  const result = await api.createConversation({residentId: 'resident:grace', clientConversationId: 'request-1'});
  assert.equal(call[0], '/api/v1/steward/conversations');
  assert.equal(call[1].method, 'POST');
  assert.equal(call[1].credentials, 'same-origin');
  assert.deepEqual(JSON.parse(call[1].body), {resident_id: 'resident:grace', client_conversation_id: 'request-1'});
  assert.equal(result.conversation.resident_id, 'resident:grace');
});

test('notification acknowledgment uses the #48 delivery route and idempotency key', async () => {
  let call;
  const api = new StewardWorkspaceApi(async (...args) => {
    call = args;
    return response(200, {contract: 'r3a.notification-inbox.v1', freshness: 'current', status: 'acknowledged'});
  });
  await api.acknowledgeNotification('delivery-1', {idempotencyKey: 'request-1'});
  assert.equal(call[0], '/api/v1/notifications/delivery-1/acknowledgment');
  assert.deepEqual(JSON.parse(call[1].body), {idempotency_key: 'request-1'});
  assert.equal(call[1].headers['X-R3A-Contract'], 'r3a.notification-inbox.v1');
});

test('notification resolution submits disposition and evidence references', async () => {
  let call;
  const api = new StewardWorkspaceApi(async (...args) => {
    call = args;
    return response(200, {contract: 'r3a.notification-inbox.v1', freshness: 'current', status: 'resolved'});
  });
  await api.resolveNotification('delivery/2', {idempotencyKey: 'request-2', disposition: 'Reviewed', evidenceReferences: ['event:1']});
  assert.equal(call[0], '/api/v1/notifications/delivery%2F2/resolution');
  assert.deepEqual(JSON.parse(call[1].body), {idempotency_key: 'request-2', disposition: 'Reviewed', evidence_refs: ['event:1']});
});

test('HTTP denials and contract mismatches remain explicit', async () => {
  const denied = new StewardWorkspaceApi(async () => response(401, {error: {code: 'session_required', message: 'Sign-in required'}}));
  await assert.rejects(denied.notifications(), error => error instanceof WorkspaceApiError && error.status === 401 && error.code === 'session_required');
  const mismatch = new StewardWorkspaceApi(async () => response(200, {contract: 'other.v1'}));
  await assert.rejects(mismatch.notifications(), error => error instanceof WorkspaceApiError && error.code === 'contract_mismatch');
});


test('presentation timestamps preserve UTC and use only an explicit IANA zone across DST', () => {
  const winter = formatPresentationTimestamp('2026-01-15T17:00:00Z', 'America/New_York');
  const summer = formatPresentationTimestamp('2026-07-15T16:00:00Z', 'America/New_York');
  const foldEarly = formatPresentationTimestamp('2026-11-01T05:30:00Z', 'America/New_York');
  const foldLate = formatPresentationTimestamp('2026-11-01T06:30:00Z', 'America/New_York');
  assert.match(winter, /2026-01-15T17:00:00Z UTC/); assert.match(winter, /EST/);
  assert.match(summer, /2026-07-15T16:00:00Z UTC/); assert.match(summer, /EDT/);
  assert.match(foldEarly, /EDT/); assert.match(foldLate, /EST/);
  assert.notEqual(foldEarly, foldLate);
  assert.match(formatPresentationTimestamp('2026-03-08T07:30:00Z', 'America/New_York'), /EDT/);
  assert.match(formatPresentationTimestamp('2026-01-15T17:00:00Z'), /presentation timezone not configured/);
  assert.match(formatPresentationTimestamp('2026-01-15T17:00:00Z', 'Not/AZone'), /invalid presentation timezone/);
  assert.match(formatPresentationTimestamp('2026-01-15 17:00:00', 'America/New_York'), /offset missing; not converted/);
});


test('native fetch is called with its global receiver', async () => {
  let receiver;
  function fetchMock() { receiver = this; return Promise.resolve(response(200, {contract: WORKSPACE_CONTRACT, freshness: 'current', residents: []})); }
  const api = new StewardWorkspaceApi(fetchMock);
  await api.residents();
  assert.equal(receiver, globalThis);
});
