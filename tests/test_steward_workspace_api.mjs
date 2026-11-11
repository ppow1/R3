/*
R3 CONTROLLED SOURCE
File: tests/test_steward_workspace_api.mjs
Component: R3A-STEWARD-WORKSPACE-CLIENT-TESTS
File Revision: 1.0.6
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Verify the versioned workspace browser client transport and denial behavior.
Execution Model: Node test runner with development-only mocked fetch responses; no institutional records.
Observability: Asserts routes, session credentials mode, contract headers, errors, correlation, and idempotency.
Dependencies: web/steward-workspace-api.mjs; Node.js built-in test modules.
Authority: R3A Class I website development, Issue #51.
Changed: 2026-11-07 | R3A-007/R3A-010/R3A-019 | Add chat, notification, session, objective, and capability client tests.
Changed: 2026-11-08 | R3A-007/R3A-010 | Cover DST-aware UTC-preserving time display and unavailable API routing.
Changed: 2026-11-10 | #51 | Verify delayed conversation responses cannot overwrite a newer resident selection.
Changed: 2026-11-10 | #51 | Cover explicit empty authoritative roster state.
Changed: 2026-11-10 | #51 | Verify compact chat rendering, action availability, Enter/IME behavior, Eastern seconds, and startup feedback.
Changed: 2026-11-10 | #51 | Cover live roster refresh, availability send gating, and session-revocation race protection.
Supersedes: None.
Contracts: r3a.steward-workspace-web.v1; r3a.steward-session.v1; r3a.notification-inbox.v1; r3a.grace-objective-submission.v1.
Tests: node --test tests/test_steward_workspace_api.mjs.
History/Predecessor: New file; initial publication recorded in Git.
*/
// Mock fetch never supplies live institutional data.
import test from 'node:test';
import assert from 'node:assert/strict';
import {StewardWorkspaceApi, WorkspaceApiError, WORKSPACE_CONTRACT, formatPresentationTimestamp, formatConversationTimestamp, messageSenderLabel, messageStatusPresentation, conversationDisplayTitle, conversationPollDelay, residentRosterRefreshDelay, residentAvailabilityPresentation, copyMessageText, shouldSendOnEnter, notificationPresentation, residentProgressLabel, residentBlockedLabel, residentChatStatusLabel, residentRosterSummary, conversationHistoryLoadingLabel, conversationPollState, mountResidentChat} from '../web/steward-workspace-api.mjs';

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

test('workspace client cannot manually activate a second session and can revoke the website session', async () => {
  const requests = [];
  const api = new StewardWorkspaceApi(async (...args) => {
    requests.push(args);
    const state = args[1].method === 'DELETE' ? 'revoked' : 'authenticated';
    return response(200, {contract: 'r3a.steward-session.v1', state, correlation_id: 'session-correlation'});
  });
  assert.equal(api.startSession, undefined);
  assert.equal((await api.session()).state, 'authenticated');
  assert.equal((await api.endSession()).state, 'revoked');
  assert.deepEqual(requests.map(request => request[0]), Array(2).fill('/api/v1/steward/session'));
  assert.deepEqual(requests.map(request => request[1].method), ['GET', 'DELETE']);
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

test('resident progress presentation uses the dynamically selected resident name', () => {
  assert.equal(residentProgressLabel('Grace'), 'Grace is working on this turn through managed CME…');
  assert.equal(residentProgressLabel('Vicky'), 'Vicky is working on this turn through managed CME…');
  assert.equal(residentProgressLabel('  '), 'Selected resident is working on this turn through managed CME…');
});

test('blocked turn status names the resident selected for that conversation', () => {
  assert.match(residentBlockedLabel('Vicky'), /^Vicky could not complete this turn/);
  assert.match(residentBlockedLabel('Grace'), /^Grace could not complete this turn/);
  assert.match(residentBlockedLabel(''), /^Resident could not complete this turn/);
});

test('history polling keeps loaded messages visible and stops with an explicit timeout state', () => {
  assert.equal(conversationHistoryLoadingLabel(true), 'Loading durable conversation history…');
  assert.equal(conversationHistoryLoadingLabel(false), null);
  assert.equal(conversationPollState(80).continuePolling, true);
  const timeout = conversationPollState(81);
  assert.equal(timeout.continuePolling, false);
  assert.match(timeout.message, /Automatic refresh is paused/);
});

test('conversation UI helpers present readable names, meaningful titles, Eastern seconds, and explicit states', async () => {
  assert.equal(messageSenderLabel({sender: {kind: 'steward'}}), 'Steward');
  assert.equal(messageSenderLabel({sender: {kind: 'resident', display_name: 'resident:grace_hopper'}}), 'Grace Hopper');
  assert.equal(messageSenderLabel({sender: {kind: 'resident', display_name: 'resident.37'}}, 'Grace'), 'Grace');
  assert.match(formatConversationTimestamp('2026-11-10T17:08:09Z'), /12:08:09 PM EST/);
  assert.match(formatConversationTimestamp('2026-07-10T17:08:09Z'), /01:08:09 PM EDT/);
  assert.equal(conversationDisplayTitle({title: 'Conversation', created_at: '2026-11-10T17:08:09Z'}, 'Grace'), 'Grace · Nov 10, 12:08 PM EST');
  assert.equal(conversationDisplayTitle({title: 'Conversation', resident_display_name: 'Vicky', created_at: '2026-11-10T17:08:09Z'}), 'Vicky · Nov 10, 12:08 PM EST');
  assert.equal(conversationDisplayTitle({title: 'Medication follow-up'}, 'Grace'), 'Medication follow-up');
  assert.equal(messageStatusPresentation('processing').label, 'Resident is working on this turn');
  assert.ok(conversationPollDelay(1) < conversationPollDelay(2));
  assert.equal(conversationPollDelay(20), 8000);
  assert.equal(residentRosterRefreshDelay(true), 15000);
  assert.equal(residentRosterRefreshDelay(false), 5000);
  assert.equal(residentAvailabilityPresentation({chat_available: true}, true, '2026-11-10T17:08:09Z').available, true);
  assert.equal(residentAvailabilityPresentation({chat_available: true}, false).className, 'unknown');
  assert.match(residentAvailabilityPresentation({chat_available: true}, false, '2026-11-10T17:08:09Z').label, /last confirmed/);
  assert.equal(residentAvailabilityPresentation({chat_available: false}, true).className, 'unavailable');
  assert.equal(residentAvailabilityPresentation(null, true).className, 'unknown');
  let copied;
  await copyMessageText('persisted reply', {writeText: async text => { copied = text; }});
  assert.equal(copied, 'persisted reply');
  await assert.rejects(copyMessageText('x', null), /Clipboard permission/);
  assert.equal(shouldSendOnEnter({key: 'Enter'}), true);
  assert.equal(shouldSendOnEnter({key: 'Enter', shiftKey: true}), false);
  assert.equal(shouldSendOnEnter({key: 'Enter', isComposing: true}), false);
  assert.equal(shouldSendOnEnter({key: 'Enter', keyCode: 229}), false);
});

test('resident roster labels chat eligibility from CME readiness evidence', () => {
  assert.equal(residentChatStatusLabel({chat_available: true}), 'chat available');
  assert.equal(residentChatStatusLabel({chat_available: false, chat_status: 'required_execution_grant_missing'}), 'chat unavailable · execution authorization missing');
  assert.equal(residentChatStatusLabel({chat_available: false, chat_status: 'office_role_route_unavailable'}), 'chat unavailable · no configured office route');
  assert.equal(residentChatStatusLabel({chat_available: false}), 'chat unavailable · eligibility not confirmed');
});

test('empty authoritative resident directory reports no residents instead of counting its placeholder', () => {
  assert.deepEqual(residentRosterSummary([], 'current'), {
    residents: [], status: 'The institutional directory returned no resident records.',
  });
  const summary = residentRosterSummary([{resident_id: 'resident:a', chat_available: false}], 'current');
  assert.equal(summary.residents.length, 1);
  assert.match(summary.status, /1 resident\(s\) currently unavailable for chat/);
});

test('resident changes and directory refreshes preserve selection and fail closed across stale responses', async () => {
  class FakeElement {
    constructor(tagName = '') { this.tagName = tagName; this.childNodes = []; this.listeners = {}; this.dataset = {}; this.attributes = {}; this.value = ''; this.disabled = false; this._text = null; }
    get options() { return this.childNodes.filter(node => node instanceof FakeOption); }
    set textContent(value) { this._text = String(value); this.childNodes = []; }
    get textContent() { return this._text ?? this.childNodes.map(node => node.textContent).join(''); }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    dispatch(name) { return this.listeners[name]?.({currentTarget: this}); }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    replaceChildren(...nodes) { this._text = null; this.childNodes = nodes; }
    appendChild(node) { this._text = null; this.childNodes.push(node); return node; }
    append(...nodes) { nodes.forEach(node => this.appendChild(node)); }
    add(node) { this.appendChild(node); }
  }
  class FakeOption extends FakeElement {
    constructor(text, value) { super('option'); this.textContent = text; this.value = value; }
  }
  const ids = ['chat-panel', 'chat-resident-select', 'chat-conversation-list', 'chat-message-list', 'chat-service-status', 'chat-runtime-status', 'chat-resident-indicator', 'chat-current-title', 'chat-conversation-toolbar', 'chat-conversation-actions', 'chat-composer-input', 'chat-send', 'chat-new', 'nav-chat', 'chat-refresh'];
  const elements = Object.fromEntries(ids.map(id => [id, new FakeElement(id === 'chat-resident-select' ? 'select' : 'div')]));
  const rootListeners = new Map();
  const root = {
    getElementById: id => elements[id] ?? null,
    createElement: tag => new FakeElement(tag),
    createTextNode: text => { const node = new FakeElement('#text'); node.textContent = text; return node; },
    addEventListener(name, callback) { const callbacks = rootListeners.get(name) || []; callbacks.push(callback); rootListeners.set(name, callbacks); },
    dispatch(name) { for (const callback of rootListeners.get(name) || []) callback(); },
    documentElement: {dataset: {r3aAuthVerified: 'true', presentationTimezone: 'America/New_York'}},
  };
  const previousDocument = globalThis.document;
  const previousOption = globalThis.Option;
  globalThis.document = root;
  globalThis.Option = FakeOption;
  let resolveResidentA;
  let resolveMessages;
  let resolveVickyMessages;
  let vickyMessageCalls = 0;
  let residentACalls = 0;
  let residentChatAvailable = true;
  let residentFreshness = 'current';
  let messageCalls = 0;
  let deferNextRoster = false;
  let resolveDeferredRoster;
  let failNextRoster = false;
  const api = {
    residents: async () => {
      if (failNextRoster) { failNextRoster = false; throw new Error('unavailable'); }
      if (deferNextRoster) { deferNextRoster = false; return new Promise(resolve => { resolveDeferredRoster = resolve; }); }
      return {freshness: residentFreshness, residents: [
        {resident_id: 'resident:a', display_name: 'A', chat_available: residentChatAvailable},
        {resident_id: 'resident:b', display_name: 'Vicky', chat_available: true},
      ]};
    },
    conversations: ({residentId}) => residentId === 'resident:a'
      ? (++residentACalls === 1
        ? new Promise(resolve => { resolveResidentA = resolve; })
        : Promise.resolve({freshness: 'A current', conversations: [{conversation_id: 'a-conversation', title: 'A conversation'}]}))
      : Promise.resolve({freshness: 'B current', conversations: [{conversation_id: 'b-conversation', title: 'B conversation'}]}),
    messages: conversationId => conversationId === 'b-conversation'
      ? (++vickyMessageCalls === 1
        ? new Promise(resolve => { resolveVickyMessages = resolve; })
        : Promise.resolve({freshness: 'current', messages: [{message_id: 'vicky-message', sender: {kind: 'resident'}, delivery_state: 'completed', created_at: '2026-11-10T17:08:09Z', text: 'Vicky response.'}]}))
      : ++messageCalls <= 2
      ? new Promise(resolve => { resolveMessages = resolve; })
      : Promise.resolve({freshness: 'current', messages: [{message_id: 'current-message', sender: {kind: 'steward'}, delivery_state: 'completed', created_at: '2026-11-10T17:08:09Z', text: 'The durable response.'}]}),
    about: async () => ({freshness: 'current', observed_at: '2026-11-10T12:00:00Z', ring0: {health: 'healthy'}, cme: {health: 'healthy'}, grace: {health: 'healthy'}}),
  };
  try {
    mountResidentChat({api, root});
    await new Promise(resolve => setImmediate(resolve));
    const select = elements['chat-resident-select'];
    assert.deepEqual(select.options.map(option => option.textContent), ['Select a resident…', 'A', 'Vicky']);
    assert.match(elements['chat-runtime-status'].textContent, /model\/provider readiness is not reported/);
    select.value = 'resident:a'; select.dispatch('change');
    select.value = 'resident:b'; select.dispatch('change');
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(elements['chat-conversation-list'].childNodes[0].childNodes[0].textContent, 'B conversation');
    const conversationToolbar = elements['chat-conversation-list'].childNodes[0].childNodes[2];
    assert.equal(conversationToolbar.childNodes[0].disabled, true);
    assert.match(conversationToolbar.childNodes[0].title, /not implemented/);
    elements['chat-conversation-list'].childNodes[0].childNodes[0].dispatch('click');
    await new Promise(resolve => setImmediate(resolve));
    select.value = 'resident:a'; select.dispatch('change');
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(elements['chat-conversation-list'].childNodes[0].childNodes[0].textContent, 'A conversation');
    resolveVickyMessages({freshness: 'current', messages: [{message_id: 'late-message', sender: {kind: 'resident', display_name: 'Vicky'}, created_at: '2026-11-10T12:00:00Z', text: 'Stale response'}]});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(elements['chat-message-list'].childNodes.length, 0);
    resolveResidentA({freshness: 'A current', conversations: [{conversation_id: 'a-conversation', title: 'A conversation'}]});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(elements['chat-conversation-list'].childNodes[0].childNodes[0].textContent, 'A conversation');
    assert.match(elements['chat-service-status'].textContent, /A current/);
    elements['chat-conversation-list'].childNodes[0].childNodes[0].dispatch('click');
    await new Promise(resolve => setImmediate(resolve));
    resolveMessages({freshness: 'current', messages: [{message_id: 'current-message', sender: {kind: 'steward'}, delivery_state: 'completed', created_at: '2026-11-10T17:08:09Z', text: 'The durable response.'}]});
    await new Promise(resolve => setImmediate(resolve));
    const card = elements['chat-message-list'].childNodes[0];
    assert.equal(card.className, 'workspace-message steward');
    assert.equal(card.childNodes[0].childNodes[0].textContent, 'Steward');
    assert.match(card.childNodes[0].childNodes[1].textContent, /12:08:09 PM EST/);
    assert.equal(card.childNodes[0].childNodes[2].attributes['aria-label'], 'Completed');
    const messageTools = card.childNodes[0].childNodes[3].childNodes[1];
    assert.equal(messageTools.hidden, true);
    const menu = card.childNodes[0].childNodes[3].childNodes[0];
    menu.dispatch('click');
    assert.equal(messageTools.hidden, false);
    assert.equal(messageTools.childNodes[0].disabled, false);
    assert.equal(messageTools.childNodes[1].disabled, false);
    assert.equal(messageTools.childNodes[2].disabled, true);
    assert.match(messageTools.childNodes[2].title, /not implemented/);
    messageTools.childNodes[1].dispatch('click');
    assert.equal(card.childNodes[2].hidden, false);
    assert.equal(elements['chat-composer-input'].disabled, false);
    residentChatAvailable = false;
    elements['chat-refresh'].dispatch('click');
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(elements['chat-resident-indicator'].className, 'resident-indicator unavailable');
    assert.equal(elements['chat-composer-input'].disabled, true, elements['chat-service-status'].textContent);
    assert.match(elements['chat-service-status'].textContent, /chat is currently unavailable/);
    residentChatAvailable = true;
    elements['chat-refresh'].dispatch('click');
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(elements['chat-resident-indicator'].className, 'resident-indicator available');
    assert.equal(elements['chat-composer-input'].disabled, false);
    select.value = 'resident:b'; select.dispatch('change');
    await new Promise(resolve => setImmediate(resolve));
    elements['chat-conversation-list'].childNodes[0].childNodes[0].dispatch('click');
    await new Promise(resolve => setImmediate(resolve));
    const vickyMessage = elements['chat-message-list'].childNodes[0];
    assert.equal(vickyMessage.className, 'workspace-message resident');
    assert.equal(vickyMessage.childNodes[0].childNodes[0].textContent, 'Vicky');
    assert.doesNotMatch(vickyMessage.textContent, /Assign work to Grace/);
    assert.doesNotMatch(elements['chat-message-list'].textContent, /Assign work to Grace/);
    failNextRoster = true;
    elements['chat-refresh'].dispatch('click');
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(elements['chat-resident-select'].options.map(option => option.textContent), ['Select a resident…', 'A', 'Vicky']);
    assert.equal(elements['chat-resident-indicator'].className, 'resident-indicator unknown');
    residentFreshness = 'stale';
    elements['chat-refresh'].dispatch('click');
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(elements['chat-resident-indicator'].className, 'resident-indicator unknown');
    assert.equal(elements['chat-composer-input'].disabled, true);
    assert.equal(elements['chat-new'].disabled, true);
    residentFreshness = 'current';
    elements['chat-refresh'].dispatch('click');
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(elements['chat-resident-indicator'].className, 'resident-indicator available');
    assert.equal(elements['chat-composer-input'].disabled, false);
    deferNextRoster = true;
    elements['chat-refresh'].dispatch('click');
    root.dispatch('r3:steward-session-revoked');
    resolveDeferredRoster({freshness: 'current', residents: [{resident_id: 'resident:a', display_name: 'A', chat_available: true}]});
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(elements['chat-resident-select'].options.map(option => option.textContent), ['Website session required']);
    assert.equal(elements['chat-resident-indicator'].className, 'resident-indicator unknown');
    assert.equal(elements['chat-composer-input'].disabled, true);
  } finally {
    globalThis.document = previousDocument;
    if (previousOption === undefined) delete globalThis.Option;
    else globalThis.Option = previousOption;
  }
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

test('notification history forwards the canonical pagination cursor', async () => {
  let call;
  const api = new StewardWorkspaceApi(async (...args) => { call = args; return response(200, {contract: 'r3a.notification-inbox.v1', contract_version: '1.0.0', freshness: 'current', presentation_timezone: 'America/New_York', deliveries: [], next_cursor: null}); });
  const result = await api.notifications({cursor: 'opaque cursor'});
  assert.equal(call[0], '/api/v1/notifications?cursor=opaque+cursor');
  assert.equal(result.presentation_timezone, 'America/New_York');
});

test('notification presentation consumes canonical message, status, detail, and safe deep-link fields', () => {
  const result = notificationPresentation({
    delivery_id: 'delivery-1', status: 'queued', requires_action: true,
    source_id: 'cme', source_event_id: 'event-1', correlation_id: 'correlation-1', created_at: '2026-11-08T12:00:00Z',
    message: {title: 'Activity paused', summary: 'Grace requires review', details: 'Full source details', reason: 'Policy boundary', source: {source_id: 'cme', source_event_id: 'event-1', event_type: 'activity.paused'}, correlation_id: 'correlation-1', occurred_at: '2026-11-08T12:00:00Z', occurred_at_local: 'Nov 8 07:00 EST', evidence_refs: ['event:event-1'], detail_url: 'https://r3.example/events/event-1'},
  });
  assert.equal(result.title, 'Activity paused'); assert.equal(result.details, 'Full source details');
  assert.equal(result.actionability, 'Actionable'); assert.equal(result.detailUrl, 'https://r3.example/events/event-1');
  assert.equal(notificationPresentation({message: {detail_url: 'javascript:alert(1)'}}).detailUrl, null);
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
