/*
R3 CONTROLLED SOURCE
File: web/steward-workspace-api.js
Component: R3A-STEWARD-WORKSPACE-CLIENT
File Revision: 1.0.2
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Same-origin client for versioned resident conversation and notification contracts
Execution Model: Browser ES module; fetches authoritative APIs and never stores institutional records
Observability: Preserves server correlation IDs and exposes explicit unavailable/error states
Dependencies: r3a.steward-workspace-web.v1 proposal; #49 opaque Steward session boundary
Authority: Contract proposal documented in docs/architecture/R3A_STEWARD_WORKSPACE_WEB_API_V1.md
Changed: 2026-11-07 | R3A-007/R3A-010 | Add same-origin persistent chat and notification inbox clients
Changed: 2026-11-08 | R3A-007/R3A-010 | Show exact unmounted API state and render source UTC with configured IANA presentation zone. Preserve browser fetch receiver.
Tests: tests/test_steward_workspace_api.mjs uses mocked fetch only as a labeled development test
*/

export const WORKSPACE_CONTRACT = 'r3a.steward-workspace-web.v1';
const API_ROOT = '/api/v1/steward';

export class WorkspaceApiError extends Error {
  constructor(message, {status = 0, code = 'network_unavailable', correlationId = null} = {}) {
    super(message);
    this.name = 'WorkspaceApiError';
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
  }
}

// Convert a server timestamp only when the institution supplied an explicit
// IANA presentation zone. Keep the source instant visible so a conversion
// never hides the authoritative UTC value.
export function formatPresentationTimestamp(value, timezone = '') {
  if (typeof value !== 'string' || !value.trim()) return 'time unavailable · UTC source unavailable';
  const source = value.trim();
  if (!/(?:Z|[+-]\d{2}:?\d{2})$/i.test(source)) return `${source} · UTC offset missing; not converted`;
  const instant = new Date(source);
  if (!Number.isFinite(instant.getTime())) return `${source} · invalid timestamp; not converted`;
  const utc = `${instant.toISOString().replace('.000Z', 'Z')} UTC`;
  if (typeof timezone !== 'string' || !timezone.trim()) return `${utc} · presentation timezone not configured`;
  try {
    const local = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone, year: 'numeric', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
    }).format(instant);
    return `${utc} · ${local} (${timezone})`;
  } catch {
    return `${utc} · invalid presentation timezone (${timezone}); not converted`;
  }
}

export class StewardWorkspaceApi {
  constructor(fetchImpl = globalThis.fetch) {
    if (typeof fetchImpl !== 'function') throw new TypeError('A fetch implementation is required');
    // Native Window.fetch requires its global receiver. Preserve that receiver
    // when this transport invokes fetch as a stored client method.
    this.fetch = fetchImpl.bind(globalThis);
  }

  async request(path, {method = 'GET', body, signal, contract = WORKSPACE_CONTRACT} = {}) {
    const headers = contract ? {Accept: `application/vnd.${contract}+json`, 'X-R3A-Contract': contract} : {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    let response;
    try {
      response = await this.fetch(path.startsWith('/api/') ? path : `${API_ROOT}${path}`, {
        method, headers, credentials: 'same-origin', cache: 'no-store', signal,
        ...(body === undefined ? {} : {body: JSON.stringify(body)}),
      });
    } catch (cause) {
      throw new WorkspaceApiError('Steward workspace service is unavailable', {code: 'network_unavailable'});
    }
    const correlationId = response.headers?.get?.('X-Correlation-ID') || response.headers?.get?.('X-Request-ID') || null;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const code = payload.error?.code || payload.code || (response.status === 401 ? 'session_required' : 'request_failed');
      const message = payload.error?.message || payload.detail || `Workspace request failed (${response.status})`;
      throw new WorkspaceApiError(message, {status: response.status, code, correlationId});
    }
    if (contract && payload.contract !== contract) {
      throw new WorkspaceApiError('Workspace API contract version mismatch', {status: response.status, code: 'contract_mismatch', correlationId});
    }
    return {...payload, correlation_id: payload.correlation_id || correlationId};
  }

  session({signal} = {}) { return this.request('/api/v1/steward/session', {signal, contract: 'r3a.steward-session.v1'}); }
  startSession({signal} = {}) { return this.request('/api/v1/steward/session', {method: 'POST', signal, contract: 'r3a.steward-session.v1'}); }
  endSession({signal} = {}) { return this.request('/api/v1/steward/session', {method: 'DELETE', signal, contract: 'r3a.steward-session.v1'}); }
  accessStatus({signal} = {}) { return this.request('/api/v1/steward/status', {signal, contract: 'r3a.steward-access-status.v1'}); }
  capabilityDiscovery({signal} = {}) { return this.request('/api/v1/steward/capabilities', {signal, contract: 'r3a.steward-capability-discovery.v1'}); }
  invokeOperation(request, {signal} = {}) { return this.request('/api/v1/steward/operations/invoke', {method: 'POST', signal, contract: 'r3a.steward-operation-result.v1', body: {request}}); }
  submitObjective(body, {signal} = {}) { return this.request('/api/v1/steward/r3a/objectives', {method: 'POST', signal, contract: 'r3a.grace-objective-submission.v1', body}); }

  residents({signal} = {}) { return this.request('/residents', {signal}); }
  conversations({residentId, cursor, signal} = {}) {
    const query = new URLSearchParams();
    if (residentId) query.set('resident_id', residentId);
    if (cursor) query.set('cursor', cursor);
    return this.request(`/conversations${query.size ? `?${query}` : ''}`, {signal});
  }
  createConversation({residentId, clientConversationId, signal}) {
    return this.request('/conversations', {method: 'POST', signal, body: {
      resident_id: residentId, client_conversation_id: clientConversationId,
    }});
  }
  messages(conversationId, {cursor, signal} = {}) {
    const query = new URLSearchParams();
    if (cursor) query.set('cursor', cursor);
    return this.request(`/conversations/${encodeURIComponent(conversationId)}/messages${query.size ? `?${query}` : ''}`, {signal});
  }
  sendMessage(conversationId, {clientMessageId, text, signal}) {
    return this.request(`/conversations/${encodeURIComponent(conversationId)}/messages`, {
      method: 'POST', signal, body: {client_message_id: clientMessageId, text},
    });
  }
  notifications({cursor, signal} = {}) {
    const query = new URLSearchParams();
    if (cursor) query.set('cursor', cursor);
    return this.request(`/api/v1/notifications${query.size ? `?${query}` : ''}`, {signal, contract: 'r3a.notification-inbox.v1'});
  }
  acknowledgeNotification(deliveryId, {idempotencyKey, note, signal}) {
    return this.request(`/api/v1/notifications/${encodeURIComponent(deliveryId)}/acknowledgment`, {
      method: 'POST', signal, contract: 'r3a.notification-inbox.v1', body: {idempotency_key: idempotencyKey, ...(note ? {note} : {})},
    });
  }
  resolveNotification(deliveryId, {idempotencyKey, disposition, evidenceReferences, signal}) {
    return this.request(`/api/v1/notifications/${encodeURIComponent(deliveryId)}/resolution`, {
      method: 'POST', signal, contract: 'r3a.notification-inbox.v1', body: {
        idempotency_key: idempotencyKey, disposition, evidence_refs: evidenceReferences,
      },
    });
  }
}

function setText(node, text) { node.textContent = String(text ?? ''); }
function row(tag, className, title, detail) {
  const item = document.createElement(tag);
  item.className = className;
  const heading = document.createElement('b');
  heading.textContent = title;
  item.append(heading, document.createTextNode(detail || ''));
  return item;
}

export function mountResidentChat({api = new StewardWorkspaceApi(), root = document} = {}) {
  const panel = root.getElementById('chat-panel');
  if (!panel) return;
  const residentSelect = root.getElementById('chat-resident-select');
  const conversationList = root.getElementById('chat-conversation-list');
  const messageList = root.getElementById('chat-message-list');
  const status = root.getElementById('chat-service-status');
  const composer = root.getElementById('chat-composer-input');
  const sendButton = root.getElementById('chat-send');
  let selectedResident = '';
  let selectedConversation = '';
  let loaded = false;
  let directoryAvailable = false;
  let creatingConversation = false;
  const authorizedResidentIds = new Set();
  let pendingConversationId = null;
  let pendingMessage = null;
  const newConversationButton = root.getElementById('chat-new');
  function syncNewConversationButton() {
    newConversationButton.disabled = !directoryAvailable || !selectedResident || !authorizedResidentIds.has(selectedResident) || creatingConversation;
    newConversationButton.title = newConversationButton.disabled ? 'Select an authorized resident from the current directory' : 'Start a persistent conversation with the selected resident';
  }

  const unavailable = error => {
    const message = error instanceof WorkspaceApiError ? error.message : 'Resident conversation service unavailable';
    const missing = error?.status === 404 ? 'Authoritative resident directory and conversation APIs are not mounted on this website service. ' : '';
    setText(status, `${error?.status === 401 ? 'Sign in through the Steward session service. ' : missing}${message}${error?.correlationId ? ` · correlation ${error.correlationId}` : ''}`);
    status.dataset.state = error?.status === 401 ? 'unauthenticated' : 'unavailable';
    if (error?.status === 401) {
      const signIn = root.createElement('button');
      signIn.type = 'button';
      signIn.className = 'chat-sign-in';
      signIn.textContent = 'Open Steward sign-in';
      signIn.setAttribute('aria-label', 'Open the shared Steward session panel to sign in');
      signIn.addEventListener('click', () => root.getElementById('nav-steward')?.click());
      status.appendChild(signIn);
    }
  };

  async function loadMessages(conversationId) {
    selectedConversation = conversationId;
    setText(messageList, 'Loading durable conversation history…');
    try {
      const result = await api.messages(conversationId);
      messageList.replaceChildren();
      for (const message of result.messages || []) {
        const item = row('article', `workspace-message ${message.sender?.kind || 'unknown'}`, message.sender?.display_name || message.sender?.id || 'Unknown sender', `${formatPresentationTimestamp(message.created_at, root.documentElement?.dataset.presentationTimezone)} · ${message.delivery_state || 'state unavailable'}`);
        const body = document.createElement('p');
        body.textContent = message.text || '';
        item.appendChild(body);
        messageList.appendChild(item);
      }
      if (!messageList.childNodes.length) setText(messageList, 'This conversation has no messages yet.');
      setText(status, `History loaded from service · ${result.freshness || 'freshness unknown'}`);
      status.dataset.state = result.freshness || 'unknown';
      composer.disabled = false;
      sendButton.disabled = false;
    } catch (error) { unavailable(error); setText(messageList, 'History unavailable; no local transcript is shown.'); }
  }

  async function loadConversations() {
    if (!selectedResident) return;
    try {
      const result = await api.conversations({residentId: selectedResident});
      conversationList.replaceChildren();
      for (const conversation of result.conversations || []) {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'workspace-conversation';
        button.textContent = conversation.title || conversation.conversation_id;
        button.addEventListener('click', () => loadMessages(conversation.conversation_id));
        conversationList.appendChild(button);
      }
      if (!conversationList.childNodes.length) setText(conversationList, 'No conversations returned for this resident.');
      if (selectedConversation) await loadMessages(selectedConversation);
      else setText(status, result.freshness === 'current' ? 'Resident directory and conversations loaded.' : `Conversation source ${result.freshness || 'unknown'}`);
    } catch (error) { unavailable(error); setText(conversationList, 'Conversation list unavailable.'); }
  }

  async function loadResidents() {
    if (loaded) return;
    loaded = true;
    directoryAvailable = false;
    authorizedResidentIds.clear();
    selectedResident = '';
    syncNewConversationButton();
    residentSelect.disabled = true;
    residentSelect.replaceChildren(new Option('Loading authorized residents…', ''));
    try {
      const result = await api.residents();
      directoryAvailable = true;
      residentSelect.replaceChildren(new Option('Select a resident…', ''));
      for (const resident of result.residents || []) {
        if (!resident.resident_id || resident.authorized === false) continue;
        authorizedResidentIds.add(resident.resident_id);
        residentSelect.add(new Option(resident.display_name || resident.resident_id, resident.resident_id));
      }
      residentSelect.disabled = false;
      syncNewConversationButton();
      setText(status, result.freshness === 'current' ? 'Resident directory loaded from the institutional directory.' : `Directory source ${result.freshness || 'unknown'}`);
      status.dataset.state = result.freshness || 'unknown';
      if (!residentSelect.options.length) setText(status, 'No authorized residents were returned by the institutional directory.');
    } catch (error) {
      loaded = false;
      directoryAvailable = false;
      residentSelect.replaceChildren(new Option(error?.status === 401 ? 'Sign in to load residents' : 'Resident directory unavailable', ''));
      residentSelect.disabled = true;
      syncNewConversationButton();
      unavailable(error);
    }
  }

  residentSelect.addEventListener('change', () => {
    selectedResident = residentSelect.value;
    syncNewConversationButton();
    selectedConversation = '';
    conversationList.replaceChildren(); messageList.replaceChildren();
    composer.disabled = true; sendButton.disabled = true;
    if (selectedResident) loadConversations();
  });
  newConversationButton.addEventListener('click', async () => {
    if (newConversationButton.disabled) return;
    creatingConversation = true;
    syncNewConversationButton();
    try {
      pendingConversationId ||= crypto.randomUUID();
      const result = await api.createConversation({residentId: selectedResident, clientConversationId: pendingConversationId});
      if (!result.conversation?.conversation_id) throw new WorkspaceApiError('Service did not confirm conversation creation', {code: 'creation_unconfirmed'});
      selectedConversation = result.conversation.conversation_id;
      pendingConversationId = null;
      await loadConversations();
    } catch (error) { unavailable(error); }
    finally { creatingConversation = false; syncNewConversationButton(); }
  });
  sendButton.addEventListener('click', async () => {
    const text = composer.value.trim();
    if (!text || !selectedConversation || sendButton.disabled) return;
    sendButton.disabled = true;
    if (!pendingMessage || pendingMessage.text !== text) pendingMessage = {text, id: crypto.randomUUID()};
    try {
      const result = await api.sendMessage(selectedConversation, {clientMessageId: pendingMessage.id, text});
      if (!result.message?.message_id) throw new WorkspaceApiError('Service did not confirm durable message acceptance', {code: 'acceptance_unconfirmed'});
      composer.value = '';
      pendingMessage = null;
      setText(status, `Message accepted by service · ${result.message.delivery_state || 'state unknown'}${result.correlation_id ? ` · correlation ${result.correlation_id}` : ''}`);
      await loadMessages(selectedConversation);
    } catch (error) { unavailable(error); }
    finally { sendButton.disabled = false; }
  });
  root.getElementById('nav-chat')?.addEventListener('click', () => loadResidents());
  root.getElementById('chat-refresh')?.addEventListener('click', () => {
    if (selectedResident && directoryAvailable) loadConversations();
    else { loaded = false; loadResidents(); }
  });
}

export function mountNotificationInbox({api = new StewardWorkspaceApi(), root = document} = {}) {
  const panel = root.getElementById('notifications-panel');
  if (!panel) return;
  const list = root.getElementById('notification-list');
  const status = root.getElementById('notification-service-status');
  const pendingActionKeys = new Map();

  function actionKey(deliveryId, actionName, payload) {
    const key = `${deliveryId}:${actionName}`;
    const fingerprint = JSON.stringify(payload);
    const previous = pendingActionKeys.get(key);
    if (!previous || previous.fingerprint !== fingerprint) pendingActionKeys.set(key, {fingerprint, id: crypto.randomUUID()});
    return pendingActionKeys.get(key).id;
  }

  async function refresh() {
    setText(status, 'Loading recipient-specific notifications…');
    try {
      const result = await api.notifications();
      list.replaceChildren();
      for (const notification of result.deliveries || result.notifications || []) {
        const item = document.createElement('article');
        item.className = 'notification-item';
        const lifecycle = notification.lifecycle_status || notification.status || 'unknown';
        const heading = row('div', 'notification-heading', notification.title || notification.delivery_id || notification.notification_id, `${notification.severity || notification.urgency || 'severity unknown'} · ${formatPresentationTimestamp(notification.created_at || notification.received_at, root.documentElement?.dataset.presentationTimezone)} · ${notification.source_id || notification.source || 'source unknown'} · correlation ${notification.correlation_id || notification.source_correlation_id || 'not supplied'}`);
        const body = document.createElement('p'); body.textContent = notification.summary || notification.message || '';
        const requiresAction = notification.actionable === true || notification.action_required === true || notification.requires_action === true;
        const state = document.createElement('p'); state.textContent = `Status: ${lifecycle} · ${requiresAction ? 'Actionable' : notification.actionable === false || notification.action_required === false || notification.requires_action === false ? 'Informational' : 'Actionability unknown'}`;
        const evidence = document.createElement('p'); evidence.textContent = `Evidence: ${(notification.evidence_refs || notification.evidence_references || []).join(', ') || 'none provided'}`;
        item.append(heading, body, state, evidence);
        if (requiresAction && lifecycle !== 'acknowledged' && lifecycle !== 'resolved') {
          const acknowledge = document.createElement('button');
          acknowledge.type = 'button'; acknowledge.textContent = 'Acknowledge';
          acknowledge.addEventListener('click', async () => {
            acknowledge.disabled = true;
            try {
              const deliveryId = notification.delivery_id || notification.notification_id;
              const idempotencyKey = actionKey(deliveryId, 'acknowledgment', {});
              const result = await api.acknowledgeNotification(deliveryId, {idempotencyKey});
              pendingActionKeys.delete(`${deliveryId}:acknowledgment`);
              setText(status, `Acknowledgment submitted · ${result.status || 'state unknown'}${result.correlation_id ? ` · correlation ${result.correlation_id}` : ''}`);
              await refresh();
            } catch (error) { setText(status, `${error.message}${error.correlationId ? ` · correlation ${error.correlationId}` : ''}`); }
            finally { acknowledge.disabled = false; }
          });
          item.appendChild(acknowledge);
        }
        if (requiresAction && lifecycle !== 'resolved') {
          const disposition = document.createElement('input'); disposition.type = 'text'; disposition.maxLength = 2000; disposition.placeholder = 'Resolution disposition'; disposition.setAttribute('aria-label', 'Resolution disposition');
          const evidence = document.createElement('input'); evidence.type = 'text'; evidence.maxLength = 2000; evidence.placeholder = 'Evidence references, comma separated'; evidence.setAttribute('aria-label', 'Resolution evidence references');
          const resolve = document.createElement('button'); resolve.type = 'button'; resolve.textContent = 'Resolve';
          resolve.addEventListener('click', async () => {
            const evidenceReferences = evidence.value.split(',').map(value => value.trim()).filter(Boolean);
            if (!disposition.value.trim() || !evidenceReferences.length) { setText(status, 'Resolution requires a disposition and at least one evidence reference.'); return; }
            resolve.disabled = true;
            try {
              const deliveryId = notification.delivery_id || notification.notification_id;
              const actionPayload = {disposition: disposition.value.trim(), evidenceReferences};
              const result = await api.resolveNotification(deliveryId, {idempotencyKey: actionKey(deliveryId, 'resolution', actionPayload), ...actionPayload});
              pendingActionKeys.delete(`${deliveryId}:resolution`);
              setText(status, `Resolution submitted · ${result.status || 'state unknown'}${result.correlation_id ? ` · correlation ${result.correlation_id}` : ''}`);
              await refresh();
            } catch (error) { setText(status, `${error.message}${error.correlationId ? ` · correlation ${error.correlationId}` : ''}`); }
            finally { resolve.disabled = false; }
          });
          item.append(disposition, evidence, resolve);
        }
        list.appendChild(item);
      }
      if (!list.childNodes.length) setText(list, 'No notifications were returned for this Steward session.');
      setText(status, `Notifications loaded from service · ${result.freshness || 'freshness unknown'}`);
      status.dataset.state = result.freshness || 'unknown';
    } catch (error) {
      list.replaceChildren();
      const unavailable = error.status === 404 ? 'Recipient notification inbox API is not mounted on this website service. ' : '';
      setText(status, `${error.status === 401 ? 'Sign in through the Steward session service. ' : unavailable}${error.message}${error.correlationId ? ` · correlation ${error.correlationId}` : ''}`);
      status.dataset.state = error.status === 401 ? 'unauthenticated' : 'unavailable';
    }
  }
  root.getElementById('nav-notifications')?.addEventListener('click', refresh);
  root.getElementById('notifications-refresh')?.addEventListener('click', refresh);
  root.addEventListener?.('r3:presentation-timezone', refresh);
}

if (typeof document !== 'undefined') {
  mountResidentChat();
  mountNotificationInbox();
}
