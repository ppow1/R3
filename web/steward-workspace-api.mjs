/*
R3 CONTROLLED SOURCE
File: web/steward-workspace-api.js
Component: R3A-STEWARD-WORKSPACE-CLIENT
File Revision: 1.0.16
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Same-origin client for versioned resident conversation and notification contracts
Execution Model: Browser ES module; fetches authoritative APIs and never stores institutional records
Observability: Preserves server correlation IDs and exposes explicit unavailable/error states
Dependencies: r3a.steward-workspace-web.v1 proposal; #49 opaque Steward session boundary
Authority: Contract proposal documented in docs/architecture/R3A_STEWARD_WORKSPACE_WEB_API_V1.md
Changed: 2026-11-07 | R3A-007/R3A-010 | Add same-origin persistent chat and notification inbox clients
Changed: 2026-11-08 | R3A-007/R3A-010 | Show exact unmounted API state and render source UTC with configured IANA presentation zone. Preserve browser fetch receiver.
Changed: 2026-11-08 | #48/#51 | Render canonical notification details, recipient lifecycle, service deep links, and cursor-paged history.
Changed: 2026-11-08 | #49/#51 | Refresh directory on shared session establishment and clear resident conversation view on revocation/401.
Changed: 2026-11-08 | #51 | Gate creation on current resident selection and expose request progress accessibly.
Changed: 2026-11-09 | R3A-WEBSITE-WIDE-AUTH | R3A Coordinator | Inherit global Website authentication, redirect expired sessions, and remove chat sign-in/session activation controls.
Changed: 2026-11-09 | R3A-LOGIN-REDIRECT-LOOP | R3A Coordinator | Recheck only the canonical session after operation 401; preserve authenticated Website navigation on scoped denials.
Changed: 2026-11-09 | R3A-STEWARD-CHAT-ROSTER | R3A Coordinator | Render all dynamic roster rows and disable chat when the current response does not establish availability.
Changed: 2026-11-09 | R3A-STEWARD-CHAT-READINESS | R3A Coordinator | Show the evidence-backed route or authorization reason for disabled roster entries.
Changed: 2026-11-11 | #51 | Keep selected durable transcripts refreshing throughout long-running resident turns.
Changed: 2026-11-10 | #51 | Ignore stale resident/conversation responses after selection changes.
Changed: 2026-11-10 | #51 | Report and disable an empty authoritative resident roster accurately.
Changed: 2026-11-10 | #51 | Render compact resident chat, accessible message actions, and Eastern timestamps.
Changed: 2026-11-10 | #51 | Add truthful live readiness, cold-start-safe polling, message tools, and clear backend action limits.
Changed: 2026-11-10 | #51 | Refresh authoritative resident availability and prevent stale directory data after session revocation.
Changed: 2026-11-10 | #51 | Fail closed on stale/unavailable resident-directory evidence while retaining transcript history.
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

export function notificationPresentation(notification, timezone = '') {
  const message = notification?.message && typeof notification.message === 'object' ? notification.message : {};
  const actionability = notification?.requires_action === true ? 'Actionable' : notification?.requires_action === false ? 'Informational' : 'Actionability unknown';
  const detailUrl = typeof message.detail_url === 'string' && /^https?:\/\//i.test(message.detail_url) ? message.detail_url : null;
  return {
    title: message.title || notification?.title || notification?.delivery_id || 'Notification',
    summary: message.summary || notification?.summary || '',
    details: message.details || '',
    reason: message.reason || '',
    sourceId: message.source?.source_id || notification?.source_id || 'source unknown',
    eventType: message.source?.event_type || notification?.event_type || 'event type unknown',
    sourceEventId: message.source?.source_event_id || notification?.source_event_id || 'source event unknown',
    correlationId: message.correlation_id || notification?.correlation_id || 'correlation unavailable',
    occurredAt: message.occurred_at_local || formatPresentationTimestamp(message.occurred_at || notification?.created_at, timezone),
    status: notification?.status || notification?.lifecycle_status || 'state unknown',
    actionability,
    evidenceRefs: message.evidence_refs || notification?.evidence_refs || [],
    detailUrl,
  };
}

export function residentProgressLabel(displayName) {
  const name = typeof displayName === 'string' && displayName.trim()
    ? displayName.trim()
    : 'Selected resident';
  return `${name} is working on this turn through managed CME…`;
}

export function residentBlockedLabel(displayName) {
  const name = typeof displayName === 'string' && displayName.trim()
    ? displayName.trim()
    : 'Resident';
  return `${name} could not complete this turn. The service returned an explicit blocked result.`;
}

export function conversationHistoryLoadingLabel(isInitialLoad) {
  return isInitialLoad ? 'Loading durable conversation history…' : null;
}

export function conversationPollState(polls) {
  // Durable turns can outlive a browser tab's ordinary request window while a
  // host/model starts. Keep the selected conversation live indefinitely; the
  // delay is separately capped, and selection/session changes cancel polling.
  const continuePolling = Number.isInteger(polls) && polls >= 0;
  return {
    continuePolling,
    message: continuePolling
      ? 'Resident is working on this turn through managed CME…'
      : 'Conversation status is unavailable; refresh the conversation to check again.',
  };
}

export function residentChatStatusLabel(resident) {
  if (resident?.chat_available === true) return 'chat available';
  if (resident?.chat_status === 'required_execution_grant_missing') return 'chat unavailable · execution authorization missing';
  if (resident?.chat_status === 'office_role_route_unavailable') return 'chat unavailable · no configured office route';
  return 'chat unavailable · eligibility not confirmed';
}

export function residentRosterSummary(residents, freshness = 'unknown') {
  const records = Array.isArray(residents) ? residents.filter(resident => resident && resident.resident_id) : [];
  return {
    residents: records,
    status: records.length
      ? (freshness === 'current'
        ? `Institutional resident roster loaded · ${records.filter(resident => resident.chat_available !== true).length} resident(s) currently unavailable for chat.`
        : `Directory source ${freshness || 'unknown'}`)
      : 'The institutional directory returned no resident records.',
  };
}

export function messageSenderLabel(message, residentName = '') {
  if (message?.sender?.kind === 'steward') return 'Steward';
  const supplied = typeof message?.sender?.display_name === 'string' ? message.sender.display_name : '';
  const raw = residentName || supplied || 'Resident';
  const readable = raw.replace(/^resident[:/]/i, '').replace(/^steward[:/]/i, '').replace(/[._-]+/g, ' ').trim();
  return readable ? readable.replace(/\b\p{L}/gu, letter => letter.toLocaleUpperCase()) : 'Resident';
}

export function formatConversationTimestamp(value, timezone = 'America/New_York') {
  if (typeof value !== 'string' || !value.trim()) return 'Time unavailable';
  const instant = new Date(value);
  if (!Number.isFinite(instant.getTime())) return 'Time unavailable';
  const options = {timeZone: timezone || 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true, timeZoneName: 'short'};
  try { return new Intl.DateTimeFormat('en-US', options).format(instant); }
  catch { return new Intl.DateTimeFormat('en-US', {...options, timeZone: 'America/New_York'}).format(instant); }
}

export function conversationDisplayTitle(conversation, residentName = '', timezone = 'America/New_York') {
  const title = typeof conversation?.title === 'string' ? conversation.title.trim() : '';
  if (title && title.toLocaleLowerCase() !== 'conversation') return title;
  const raw = conversation?.updated_at || conversation?.created_at;
  const instant = typeof raw === 'string' ? new Date(raw) : new Date(NaN);
  let updated = formatConversationTimestamp(raw, timezone);
  if (Number.isFinite(instant.getTime())) {
    try { updated = new Intl.DateTimeFormat('en-US', {timeZone: timezone, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short'}).format(instant); }
    catch { /* use the safe Eastern time-only label */ }
  }
  const accurateResidentName = residentName || conversation?.resident_display_name || 'Resident';
  return `${messageSenderLabel({sender: {kind: 'resident', display_name: accurateResidentName}})} · ${updated}`;
}

export function residentRosterRefreshDelay(available) { return available ? 15000 : 5000; }

export function residentAvailabilityPresentation(resident, verified, checkedAt = null) {
  const checked = checkedAt ? ` · ${verified ? 'checked' : 'last confirmed'} ${formatConversationTimestamp(checkedAt)}` : '';
  if (!resident) return {available: false, className: 'unknown', label: `Resident availability unknown${checked}`};
  if (!verified) return {available: false, className: 'unknown', label: `Chat availability not confirmed${checked}`};
  if (resident?.chat_available === true) return {available: true, className: 'available', label: `Chat available${checked}`};
  return {available: false, className: 'unavailable', label: `${residentChatStatusLabel(resident)}${checked}`};
}

export function messageStatusPresentation(state) {
  const values = {
    pending: ['◷', 'Queued; waiting for the resident service'],
    accepted: ['◷', 'Accepted; waiting for the resident service'],
    processing: ['◌', 'Resident is working on this turn'],
    completed: ['✓', 'Completed'],
    blocked: ['!', 'Blocked; review details for the service result'],
    failed: ['×', 'Failed; review details and retry guidance'],
    rejected: ['×', 'Rejected; review details and authorization'],
  };
  const [icon, label] = values[state] || ['·', state || 'Status unavailable'];
  return {icon, label};
}

export function conversationPollDelay(attempt) {
  return Math.min(1500 * (1.6 ** Math.max(0, attempt - 1)), 8000);
}

export async function copyMessageText(text, clipboard = globalThis.navigator?.clipboard) {
  if (!clipboard || typeof clipboard.writeText !== 'function') throw new Error('Clipboard permission is unavailable');
  await clipboard.writeText(String(text ?? ''));
}

export function shouldSendOnEnter(event) {
  return event?.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229;
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
      if (response.status === 401) globalThis.window?.r3aCheckWebsiteSession?.();
      throw new WorkspaceApiError(message, {status: response.status, code, correlationId});
    }
    if (contract && payload.contract !== contract) {
      throw new WorkspaceApiError('Workspace API contract version mismatch', {status: response.status, code: 'contract_mismatch', correlationId});
    }
    return {...payload, correlation_id: payload.correlation_id || correlationId};
  }

  session({signal} = {}) { return this.request('/api/v1/steward/session', {signal, contract: 'r3a.steward-session.v1'}); }
  endSession({signal} = {}) { return this.request('/api/v1/steward/session', {method: 'DELETE', signal, contract: 'r3a.steward-session.v1'}); }
  accessStatus({signal} = {}) { return this.request('/api/v1/steward/status', {signal, contract: 'r3a.steward-access-status.v1'}); }
  about({signal} = {}) { return this.request('/api/v1/steward/about', {signal, contract: 'r3a.website-about.v1'}); }
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
  const runtimeStatus = root.getElementById('chat-runtime-status');
  const residentIndicator = root.getElementById('chat-resident-indicator');
  const currentTitle = root.getElementById('chat-current-title');
  const composer = root.getElementById('chat-composer-input');
  const sendButton = root.getElementById('chat-send');
  let selectedResident = '';
  let selectedConversation = '';
  let loaded = false;
  let directoryAvailable = false;
  let creatingConversation = false;
  const chatAvailableResidentIds = new Set();
  const residentNames = new Map();
  let pendingConversationId = null;
  let pendingMessage = null;
  const newConversationButton = root.getElementById('chat-new');
  const processingPolls = new Map();
  let conversationLoadRevision = 0;
  let messageLoadRevision = 0;
  let runtimePollTimer = null;
  let residentRosterTimer = null;
  let directoryRefreshing = false;
  let residentDirectoryRevision = 0;
  let residentRosterVerified = false;
  let residentRosterCheckedAt = null;
  const pollTimers = new Map();
  const loadedConversationIds = new Set();
  const conversationTitles = new Map();
  const conversationMenu = root.getElementById('chat-conversation-toolbar');
  const conversationMenuButton = root.getElementById('chat-conversation-actions');
  const lastResidentRecords = new Map();
  function syncNewConversationButton() {
    newConversationButton.disabled = !directoryAvailable || !residentRosterVerified || !selectedResident || !chatAvailableResidentIds.has(selectedResident) || creatingConversation;
    newConversationButton.setAttribute('aria-busy', String(creatingConversation));
    newConversationButton.title = creatingConversation
      ? 'Conversation creation in progress'
      : newConversationButton.disabled
        ? `New conversation unavailable · ${lastResidentRecords.has(selectedResident) ? residentAvailabilityPresentation(lastResidentRecords.get(selectedResident), residentRosterVerified, residentRosterCheckedAt).label : 'select an available resident'}`
        : 'Start a persistent conversation with the selected resident';
  }

  const unavailable = error => {
    const message = error instanceof WorkspaceApiError ? error.message : 'Resident conversation service unavailable';
    const missing = error?.status === 404 ? 'Authoritative resident directory and conversation APIs are not mounted on this website service. ' : '';
    setText(status, `${error?.status === 401 ? 'This request was unauthorized (401); checking Website session separately. ' : missing}${message}${error?.correlationId ? ` · correlation ${error.correlationId}` : ''}`);
    status.dataset.state = error?.status === 401 ? 'unauthorized' : 'unavailable';
    if (error?.status === 401) {
      globalThis.window?.r3aCheckWebsiteSession?.();
    }
  };

  function cancelConversationPolls() {
    for (const timer of pollTimers.values()) clearTimeout(timer);
    pollTimers.clear();
  }

  function scheduleMessages(conversationId, attempt, delay = conversationPollDelay(attempt)) {
    const oldTimer = pollTimers.get(conversationId);
    if (oldTimer) clearTimeout(oldTimer);
    const timer = setTimeout(() => {
      pollTimers.delete(conversationId);
      if (selectedConversation === conversationId) loadMessages(conversationId, {attempt});
    }, delay);
    pollTimers.set(conversationId, timer);
    timer?.unref?.();
  }

  function setResidentAvailability(residentId) {
    const record = lastResidentRecords.get(residentId);
    const presentation = residentAvailabilityPresentation(record, residentRosterVerified, residentRosterCheckedAt);
    residentIndicator.className = `resident-indicator ${presentation.className}`;
    residentIndicator.title = presentation.label;
    residentIndicator.setAttribute('aria-label', residentIndicator.title);
  }

  function toolbarButton(container, {icon, label, available = true, onClick}) {
    const button = root.createElement('button');
    button.type = 'button';
    button.className = 'icon-button';
    button.textContent = icon;
    button.title = available ? `${label} · available` : `${label} · not implemented by the current service`;
    button.setAttribute('aria-label', button.title);
    button.disabled = !available;
    if (onClick) button.addEventListener('click', onClick);
    container.appendChild(button);
    return button;
  }

  function renderMessage(message, residentName) {
    const sender = messageSenderLabel(message, residentName);
    const state = message.delivery_state || 'unknown';
    const presentation = messageStatusPresentation(state);
    const article = root.createElement('article');
    article.className = `workspace-message ${message.sender?.kind === 'resident' ? 'resident' : 'steward'}`;
    article.dataset.state = state;

    const header = root.createElement('header');
    header.className = 'workspace-message-head';
    const senderNode = root.createElement('span');
    senderNode.className = 'workspace-message-sender'; senderNode.textContent = sender;
    const time = root.createElement('time');
    time.className = 'workspace-message-time'; time.dateTime = message.created_at || '';
    time.textContent = formatConversationTimestamp(message.created_at);
    const statusIcon = root.createElement('span');
    statusIcon.className = 'workspace-message-status'; statusIcon.textContent = presentation.icon;
    statusIcon.setAttribute('role', 'img'); statusIcon.setAttribute('aria-label', presentation.label); statusIcon.title = presentation.label;

    const toolsAnchor = root.createElement('div'); toolsAnchor.className = 'workspace-message-tools-anchor';
    const menuButton = root.createElement('button');
    menuButton.type = 'button'; menuButton.className = 'icon-button workspace-message-menu';
    menuButton.textContent = '⋯'; menuButton.title = `Message actions for ${sender}`;
    menuButton.setAttribute('aria-label', menuButton.title); menuButton.setAttribute('aria-expanded', 'false');
    const toolbar = root.createElement('div'); toolbar.className = 'message-toolbar'; toolbar.setAttribute('role', 'toolbar'); toolbar.setAttribute('aria-label', `${sender} message actions`); toolbar.hidden = true;
    menuButton.addEventListener('click', () => {
      toolbar.hidden = !toolbar.hidden;
      menuButton.setAttribute('aria-expanded', String(!toolbar.hidden));
    });

    const body = root.createElement('p'); body.className = 'workspace-message-body'; body.textContent = message.text || '';
    const details = root.createElement('section'); details.className = 'workspace-message-details'; details.hidden = true;
    const detailHeading = root.createElement('b'); detailHeading.textContent = 'Message details'; details.appendChild(detailHeading);
    const list = root.createElement('dl');
    const metadata = [
      ['Status', presentation.label], ['Local time', formatConversationTimestamp(message.created_at)],
      ['Source time', message.created_at || 'Unavailable'], ['Resident', residentName || sender],
      ['Activity reference', message.activity_id || 'Not assigned'], ['Message reference', message.message_id || 'Unavailable'],
    ];
    for (const [label, value] of metadata) {
      const term = root.createElement('dt'); term.textContent = label;
      const description = root.createElement('dd'); description.textContent = String(value);
      list.append(term, description);
    }
    details.appendChild(list);

    toolbarButton(toolbar, {icon: '⧉', label: 'Copy message text', onClick: async () => {
      try { await copyMessageText(message.text || ''); setText(status, `Copied ${sender} message.`); }
      catch { setText(status, 'Clipboard unavailable. Check browser clipboard permission or select the message text to copy.'); }
      toolbar.hidden = true; menuButton.setAttribute('aria-expanded', 'false');
    }});
    toolbarButton(toolbar, {icon: 'ⓘ', label: 'Details', onClick: () => {
      details.hidden = !details.hidden;
      const button = toolbar.querySelector?.('[aria-label^="Details"]');
      if (button) button.setAttribute('aria-expanded', String(!details.hidden));
      toolbar.hidden = true; menuButton.setAttribute('aria-expanded', 'false');
    }});
    toolbarButton(toolbar, {icon: '✎', label: 'Edit message', available: false});
    toolbarButton(toolbar, {icon: '⌫', label: 'Delete message', available: false});
    toolbarButton(toolbar, {icon: '▧', label: 'Generate image', available: false});
    header.append(senderNode, time, statusIcon);
    toolsAnchor.append(menuButton, toolbar);
    header.appendChild(toolsAnchor);
    article.append(header, body, details);
    return article;
  }

  async function loadMessages(conversationId, {attempt = 1} = {}) {
    const changingConversation = selectedConversation !== conversationId;
    const requestedResident = selectedResident;
    const revision = ++messageLoadRevision;
    selectedConversation = conversationId;
    currentTitle.textContent = conversationTitles.get(conversationId) || residentNames.get(requestedResident) || 'Resident conversation';
    const loadingLabel = conversationHistoryLoadingLabel(changingConversation || !messageList.childNodes.length);
    if (loadingLabel) setText(messageList, loadingLabel);
    try {
      const result = await api.messages(conversationId);
      if (selectedResident !== requestedResident || selectedConversation !== conversationId || revision !== messageLoadRevision) return [];
      messageList.replaceChildren();
      for (const message of result.messages || []) messageList.appendChild(renderMessage(message, residentNames.get(requestedResident)));
      if (!messageList.childNodes.length) setText(messageList, 'This conversation has no messages yet.');
      loadedConversationIds.add(conversationId);
      const messages = result.messages || [];
      const processing = messages.some(message => message.sender?.kind === 'steward' && ['pending', 'accepted', 'processing'].includes(message.delivery_state));
      const lastMessage = messages.at(-1);
      const failedMessage = lastMessage && ['blocked', 'failed', 'rejected'].includes(lastMessage.delivery_state) ? lastMessage : null;
      const residentCanChat = residentRosterVerified && chatAvailableResidentIds.has(requestedResident);
      composer.disabled = processing || !residentCanChat;
      sendButton.disabled = processing || !residentCanChat;
      if (processing) {
        const pollAttempt = processingPolls.get(conversationId) || 0;
        const nextAttempt = pollAttempt + 1;
        processingPolls.set(conversationId, nextAttempt);
        const pollState = conversationPollState(nextAttempt);
        if (pollState.continuePolling) {
          const runtime = runtimeStatus.dataset.modelReadiness === 'starting' ? ' The model service is still starting; the conversation will update here.' : '';
          setText(status, `${residentProgressLabel(residentNames.get(requestedResident))}${runtime} · checked ${formatConversationTimestamp(new Date().toISOString())}`);
          scheduleMessages(conversationId, nextAttempt);
        } else {
          setText(status, 'This turn is still processing. Automatic checks paused; refresh to check its durable status.');
          status.dataset.state = 'processing-timeout';
        }
      } else if (failedMessage) {
        processingPolls.delete(conversationId);
        const name = residentNames.get(requestedResident);
        setText(status, failedMessage.delivery_state === 'blocked'
          ? residentBlockedLabel(name)
          : `${name || 'Resident'}'s turn failed. Review message details, check service readiness, and retry when available.`);
        status.dataset.state = failedMessage.delivery_state;
      } else if (!residentCanChat) {
        processingPolls.delete(conversationId);
        setText(status, `Conversation history is current; ${residentAvailabilityPresentation(lastResidentRecords.get(requestedResident), residentRosterVerified, residentRosterCheckedAt).label}. Sending is unavailable.`);
        status.dataset.state = 'resident-unavailable';
      } else {
        processingPolls.delete(conversationId);
        setText(status, `Conversation current · ${result.freshness || 'freshness unknown'}`);
        status.dataset.state = result.freshness || 'unknown';
      }
      return result.messages || [];
    } catch (error) {
      if (selectedResident === requestedResident && selectedConversation === conversationId && revision === messageLoadRevision) {
        unavailable(error);
        if (!loadedConversationIds.has(conversationId)) setText(messageList, 'Conversation history is not available yet. The service will retry automatically when the session and runtime are reachable.');
        if (!error.status || error.status === 429 || error.status >= 500) {
          setText(status, 'Connection to the conversation service was lost; previous messages are retained while it reconnects.');
          status.dataset.state = 'reconnecting';
          scheduleMessages(conversationId, attempt + 1);
        }
      }
    }
  }

  async function loadConversations() {
    if (!selectedResident) return;
    const requestedResident = selectedResident;
    const revision = ++conversationLoadRevision;
    try {
      const result = await api.conversations({residentId: requestedResident});
      if (selectedResident !== requestedResident || revision !== conversationLoadRevision) return;
      conversationList.replaceChildren();
      for (const conversation of result.conversations || []) {
        const title = conversationDisplayTitle(conversation, residentNames.get(requestedResident));
        conversationTitles.set(conversation.conversation_id, title);
        const row = root.createElement('div'); row.className = 'workspace-conversation-row';
        const button = root.createElement('button');
        button.type = 'button'; button.className = 'workspace-conversation';
        button.textContent = title;
        button.setAttribute('aria-current', String(selectedConversation === conversation.conversation_id));
        button.title = title;
        button.addEventListener('click', () => {
          conversationList.querySelectorAll?.('.workspace-conversation').forEach(item => item.setAttribute('aria-current', 'false'));
          button.setAttribute('aria-current', 'true');
          loadMessages(conversation.conversation_id);
        });
        const actionsButton = root.createElement('button');
        actionsButton.type = 'button'; actionsButton.className = 'icon-button conversation-menu-trigger';
        actionsButton.textContent = '⋯'; actionsButton.title = `Conversation actions for ${title}`;
        actionsButton.setAttribute('aria-label', actionsButton.title); actionsButton.setAttribute('aria-expanded', 'false');
        const actions = root.createElement('div'); actions.className = 'conversation-toolbar';
        actions.setAttribute('role', 'toolbar'); actions.setAttribute('aria-label', `${title} actions`); actions.hidden = true;
        actionsButton.addEventListener('click', () => {
          actions.hidden = !actions.hidden;
          actionsButton.setAttribute('aria-expanded', String(!actions.hidden));
        });
        toolbarButton(actions, {icon: '✎', label: 'Rename conversation', available: false});
        toolbarButton(actions, {icon: '▱', label: 'Archive conversation', available: false});
        toolbarButton(actions, {icon: '⌫', label: 'Delete conversation', available: false});
        row.append(button, actionsButton, actions);
        conversationList.appendChild(row);
      }
      if (!conversationList.childNodes.length) setText(conversationList, 'No conversations returned for this resident.');
      if (selectedConversation) await loadMessages(selectedConversation);
      else setText(status, result.freshness === 'current' ? 'Resident directory and conversations loaded.' : `Conversation source ${result.freshness || 'unknown'}`);
    } catch (error) {
      if (selectedResident === requestedResident && revision === conversationLoadRevision) {
        unavailable(error); setText(conversationList, 'Conversation list unavailable.');
      }
    }
  }

  function scheduleResidentRosterRefresh(available = true) {
    clearTimeout(residentRosterTimer);
    residentRosterTimer = setTimeout(() => loadResidents({refresh: true}), residentRosterRefreshDelay(available));
    residentRosterTimer?.unref?.();
  }

  async function loadResidents({refresh = false} = {}) {
    if ((loaded && !refresh) || directoryRefreshing) return;
    directoryRefreshing = true;
    const revision = ++residentDirectoryRevision;
    const hadDirectory = directoryAvailable;
    if (!hadDirectory) {
      residentSelect.disabled = true;
      residentSelect.replaceChildren(new Option('Loading resident list…', ''));
    }
    try {
      const result = await api.residents();
      if (revision !== residentDirectoryRevision) return;
      directoryAvailable = true;
      loaded = true;
      const roster = residentRosterSummary(result.residents, result.freshness);
      const selectedWasAvailable = residentRosterVerified && chatAvailableResidentIds.has(selectedResident);
      residentRosterVerified = result.freshness === 'current';
      if (residentRosterVerified) residentRosterCheckedAt = new Date().toISOString();
      chatAvailableResidentIds.clear(); residentNames.clear(); lastResidentRecords.clear();
      residentSelect.replaceChildren(new Option('Select a resident…', ''));
      for (const resident of roster.residents) {
        const chatAvailable = resident.chat_available === true;
        if (chatAvailable && residentRosterVerified) chatAvailableResidentIds.add(resident.resident_id);
        residentNames.set(resident.resident_id, resident.display_name || 'Resident');
        lastResidentRecords.set(resident.resident_id, resident);
        const option = new Option(messageSenderLabel({sender: {kind: 'resident', display_name: resident.display_name || 'Resident'}}), resident.resident_id);
        residentSelect.add(option);
      }
      residentSelect.disabled = roster.residents.length === 0;
      const hasSelectedResident = roster.residents.some(resident => resident.resident_id === selectedResident);
      if (hasSelectedResident) {
        residentSelect.value = selectedResident;
        setResidentAvailability(selectedResident);
        const selectedIsAvailable = chatAvailableResidentIds.has(selectedResident);
        if (!selectedIsAvailable) {
          composer.disabled = true; sendButton.disabled = true;
          if (selectedWasAvailable) setText(status, `${residentNames.get(selectedResident)} chat is currently unavailable. Existing conversation history remains available.`);
          else if (!residentRosterVerified) setText(status, 'Chat availability is not confirmed by a current directory response. Sending is paused; history remains available.');
        } else if (!selectedWasAvailable && selectedConversation) {
          loadMessages(selectedConversation);
        }
      } else if (selectedResident) {
        selectedResident = ''; selectedConversation = '';
        conversationLoadRevision += 1; messageLoadRevision += 1;
        cancelConversationPolls(); processingPolls.clear();
        conversationList.replaceChildren(); messageList.replaceChildren();
        currentTitle.textContent = 'Resident conversation';
        composer.disabled = true; sendButton.disabled = true;
        residentSelect.value = '';
        setResidentAvailability('');
      }
      syncNewConversationButton();
      if (!hadDirectory || !residentRosterVerified) {
        setText(status, residentRosterVerified ? roster.status : 'Directory information is not current; resident chat availability cannot be confirmed.');
        status.dataset.state = result.freshness || 'unknown';
      }
      scheduleResidentRosterRefresh(residentRosterVerified);
    } catch (error) {
      if (revision !== residentDirectoryRevision) return;
      if (!hadDirectory) {
        loaded = false; directoryAvailable = false;
        residentRosterVerified = false;
        residentSelect.replaceChildren(new Option('Resident list unavailable', ''));
        residentSelect.disabled = true;
        unavailable(error);
      } else if (error?.status === 401) {
        residentRosterVerified = false;
        composer.disabled = true; sendButton.disabled = true;
        setResidentAvailability(selectedResident);
        unavailable(error);
      } else {
        residentRosterVerified = false;
        composer.disabled = true; sendButton.disabled = true;
        setResidentAvailability(selectedResident);
        setText(status, 'Resident availability could not be refreshed; showing the last confirmed names. Sending is paused until a current check succeeds.');
        status.dataset.state = 'reconnecting';
      }
      syncNewConversationButton();
      scheduleResidentRosterRefresh(false);
    } finally {
      if (revision === residentDirectoryRevision) directoryRefreshing = false;
    }
  }

  residentSelect.addEventListener('change', () => {
    conversationLoadRevision += 1;
    messageLoadRevision += 1;
    selectedResident = residentSelect.value;
    setResidentAvailability(selectedResident);
    pendingConversationId = null;
    pendingMessage = null;
    composer.value = '';
    syncNewConversationButton();
    selectedConversation = '';
    currentTitle.textContent = residentNames.get(selectedResident) || 'Resident conversation';
    cancelConversationPolls();
    processingPolls.clear();
    conversationList.replaceChildren(); messageList.replaceChildren();
    composer.disabled = true; sendButton.disabled = true;
    if (selectedResident) loadConversations();
  });
  newConversationButton.addEventListener('click', async () => {
    if (newConversationButton.disabled) return;
    const requestedResident = selectedResident;
    creatingConversation = true;
    syncNewConversationButton();
    setText(status, 'Creating a persistent conversation through the institutional service…');
    try {
      pendingConversationId ||= crypto.randomUUID();
      const result = await api.createConversation({residentId: requestedResident, clientConversationId: pendingConversationId});
      if (!result.conversation?.conversation_id) throw new WorkspaceApiError('Service did not confirm conversation creation', {code: 'creation_unconfirmed'});
      if (selectedResident !== requestedResident) return;
      selectedConversation = result.conversation.conversation_id;
      pendingConversationId = null;
      await loadConversations();
    } catch (error) { unavailable(error); }
    finally { creatingConversation = false; syncNewConversationButton(); }
  });
  sendButton.addEventListener('click', async () => {
    const text = composer.value.trim();
    if (!text || !selectedConversation || sendButton.disabled) return;
    const requestedConversation = selectedConversation;
    const requestedResident = selectedResident;
    sendButton.disabled = true;
    if (!pendingMessage || pendingMessage.text !== text) pendingMessage = {text, id: crypto.randomUUID()};
    try {
      const result = await api.sendMessage(requestedConversation, {clientMessageId: pendingMessage.id, text});
      if (selectedConversation !== requestedConversation || selectedResident !== requestedResident) return;
      if (!result.message?.message_id) throw new WorkspaceApiError('Service did not confirm durable message acceptance', {code: 'acceptance_unconfirmed'});
      composer.value = '';
      pendingMessage = null;
      setText(status, `Message accepted by service · ${result.message.delivery_state || 'state unknown'}${result.correlation_id ? ` · correlation ${result.correlation_id}` : ''}`);
      await loadMessages(requestedConversation);
    } catch (error) {
      if (selectedConversation === requestedConversation && selectedResident === requestedResident) unavailable(error);
    }
    finally { sendButton.disabled = !selectedConversation || composer.disabled; }
  });
  composer.addEventListener('keydown', event => {
    if (!shouldSendOnEnter(event)) return;
    event.preventDefault();
    if (!sendButton.disabled) sendButton.click();
  });

  function processHealth(process) {
    const health = String(process?.health || process?.state || '').toLowerCase();
    if (['healthy', 'ready', 'active', 'running'].includes(health)) return 'ready';
    if (['starting', 'initializing', 'warming', 'recovering'].includes(health)) return 'starting';
    if (['stale', 'degraded', 'unavailable', 'failed', 'stopped', 'blocked'].includes(health)) return health;
    return 'unknown';
  }

  async function refreshRuntimeStatus() {
    clearTimeout(runtimePollTimer);
    try {
      const about = await api.about();
      const ring0 = processHealth(about.ring0);
      const cme = processHealth(about.cme);
      const grace = processHealth(about.grace);
      runtimeStatus.dataset.modelReadiness = 'unknown';
      runtimeStatus.dataset.state = about.freshness || 'unknown';
      const checked = formatConversationTimestamp(about.observed_at);
      setText(runtimeStatus, `Website API connected · Ring0 ${ring0} · CME ${cme} · resident runtime ${grace} · model/provider readiness is not reported by this Website API · checked ${checked}`);
      runtimePollTimer = setTimeout(refreshRuntimeStatus, ring0 === 'ready' && cme === 'ready' ? 15000 : 5000);
      runtimePollTimer?.unref?.();
    } catch (error) {
      runtimeStatus.dataset.state = error?.status === 401 ? 'unauthenticated' : 'unavailable';
      runtimeStatus.dataset.modelReadiness = 'unknown';
      const detail = error?.status === 401
        ? 'Session verification required'
        : !error?.status ? 'Website API unreachable' : 'Website API reachable; Ring0/CME diagnostics unavailable';
      setText(runtimeStatus, `${detail}; checking again automatically · last check ${formatConversationTimestamp(new Date().toISOString())}`);
      runtimePollTimer = setTimeout(refreshRuntimeStatus, 5000);
      runtimePollTimer?.unref?.();
    }
  }

  root.addEventListener?.('r3:steward-session-established', refreshRuntimeStatus);
  root.addEventListener?.('r3:steward-session-revoked', () => {
    clearTimeout(runtimePollTimer); runtimePollTimer = null;
    clearTimeout(residentRosterTimer); residentRosterTimer = null;
    cancelConversationPolls();
    setText(runtimeStatus, 'Website session ended · runtime checks stopped.');
    runtimeStatus.dataset.state = 'unauthenticated';
  });
  if (root.documentElement?.dataset.r3aAuthVerified === 'true') refreshRuntimeStatus();
  root.getElementById('nav-chat')?.addEventListener('click', () => loadResidents());
  root.addEventListener?.('r3:steward-session-established', () => {
    clearTimeout(residentRosterTimer); residentRosterTimer = null;
    residentDirectoryRevision += 1; directoryRefreshing = false;
    cancelConversationPolls(); loadedConversationIds.clear(); conversationTitles.clear();
    residentNames.clear(); lastResidentRecords.clear();
    loaded = false; directoryAvailable = false; selectedResident = ''; selectedConversation = '';
    residentRosterVerified = false; residentRosterCheckedAt = null;
    pendingConversationId = null; pendingMessage = null; chatAvailableResidentIds.clear();
    residentSelect.disabled = true; residentSelect.replaceChildren(new Option('Loading institutional resident roster…', ''));
    conversationList.replaceChildren(); messageList.replaceChildren(); composer.value = '';
    composer.disabled = true; sendButton.disabled = true; syncNewConversationButton();
    loadResidents();
  });
  root.addEventListener?.('r3:steward-session-revoked', () => {
    clearTimeout(residentRosterTimer); residentRosterTimer = null;
    residentDirectoryRevision += 1; directoryRefreshing = false;
    cancelConversationPolls(); loadedConversationIds.clear(); conversationTitles.clear();
    residentNames.clear(); lastResidentRecords.clear();
    loaded = false; directoryAvailable = false; selectedResident = ''; selectedConversation = '';
    residentRosterVerified = false; residentRosterCheckedAt = null;
    pendingConversationId = null; pendingMessage = null; composer.value = '';
    chatAvailableResidentIds.clear(); residentSelect.disabled = true;
    residentSelect.replaceChildren(new Option('Website session required', ''));
    setResidentAvailability('');
    conversationList.replaceChildren(); messageList.replaceChildren();
    composer.disabled = true; sendButton.disabled = true; syncNewConversationButton();
    setText(status, 'Steward session revoked · conversation data cleared from this view.'); status.dataset.state = 'unauthenticated';
  });
  root.getElementById('chat-refresh')?.addEventListener('click', () => {
    if (selectedResident && directoryAvailable) { loadResidents({refresh: true}); loadConversations(); }
    else { loaded = false; loadResidents(); }
  });
  conversationMenuButton?.addEventListener('click', () => {
    conversationMenu.hidden = !conversationMenu.hidden;
    conversationMenuButton.setAttribute('aria-expanded', String(!conversationMenu.hidden));
  });
  if (conversationMenu) {
    toolbarButton(conversationMenu, {icon: '✎', label: 'Rename conversation', available: false});
    toolbarButton(conversationMenu, {icon: '▱', label: 'Archive conversation', available: false});
    toolbarButton(conversationMenu, {icon: '⌫', label: 'Delete conversation', available: false});
  }
  if (root.documentElement?.dataset.r3aAuthVerified === 'true') loadResidents();
}

export function mountNotificationInbox({api = new StewardWorkspaceApi(), root = document} = {}) {
  const panel = root.getElementById('notifications-panel');
  if (!panel) return;
  const list = root.getElementById('notification-list');
  const status = root.getElementById('notification-service-status');
  const pendingActionKeys = new Map();
  let nextCursor = null;

  function actionKey(deliveryId, actionName, payload) {
    const key = `${deliveryId}:${actionName}`;
    const fingerprint = JSON.stringify(payload);
    const previous = pendingActionKeys.get(key);
    if (!previous || previous.fingerprint !== fingerprint) pendingActionKeys.set(key, {fingerprint, id: crypto.randomUUID()});
    return pendingActionKeys.get(key).id;
  }

  async function refresh({cursor = null, append = false} = {}) {
    const olderControl = append ? list.querySelector?.('.notification-load-older') : null;
    if (olderControl) olderControl.disabled = true;
    setText(status, 'Loading recipient-specific notifications…');
    try {
      const result = await api.notifications({cursor});
      if (!append) list.replaceChildren();
      for (const notification of result.deliveries || result.notifications || []) {
        const item = document.createElement('article');
        item.className = 'notification-item';
        const presentation = notificationPresentation(notification, result.presentation_timezone || root.documentElement?.dataset.presentationTimezone || '');
        const heading = row('div', 'notification-heading', presentation.title, `${notification.severity || notification.urgency || 'severity unknown'} · ${presentation.occurredAt} · ${presentation.sourceId} · ${presentation.eventType} · correlation ${presentation.correlationId}`);
        const summary = document.createElement('p'); summary.textContent = presentation.summary;
        const state = document.createElement('p'); state.textContent = `Status: ${presentation.status} · ${presentation.actionability}`;
        const reason = document.createElement('p'); reason.textContent = `Reason: ${presentation.reason || 'not supplied'}`;
        const source = document.createElement('p'); source.textContent = `Source event: ${presentation.sourceEventId}`;
        const evidence = document.createElement('p'); evidence.textContent = `Evidence: ${presentation.evidenceRefs.join(', ') || 'none provided'}`;
        item.append(heading, summary, state, reason, source, evidence);
        if (presentation.details) {
          const details = document.createElement('details');
          const summaryLabel = document.createElement('summary'); summaryLabel.textContent = 'Full notification details';
          const fullDetails = document.createElement('p'); fullDetails.textContent = presentation.details;
          details.append(summaryLabel, fullDetails); item.appendChild(details);
        }
        if (notification.notification && typeof notification.notification === 'object') {
          const payloadDetails = document.createElement('details');
          const payloadSummary = document.createElement('summary'); payloadSummary.textContent = 'Original notification payload';
          const payload = document.createElement('pre'); payload.textContent = JSON.stringify(notification.notification, null, 2);
          payloadDetails.append(payloadSummary, payload); item.appendChild(payloadDetails);
        }
        if (presentation.detailUrl) {
          const deepLink = document.createElement('a'); deepLink.href = presentation.detailUrl; deepLink.target = '_blank'; deepLink.rel = 'noopener noreferrer'; deepLink.textContent = 'Open associated event';
          item.appendChild(deepLink);
        }
        const deliveryActions = notification.message?.actions || [];
        for (const action of deliveryActions) {
          if (action.action_id !== 'open' || typeof action.destination !== 'string' || !/^https?:\/\//i.test(action.destination)) continue;
          const link = document.createElement('a'); link.href = action.destination; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = action.label || 'Open notification'; item.appendChild(link);
        }
        const requiresAction = notification.requires_action === true;
        const lifecycle = notification.status || notification.lifecycle_status || 'unknown';
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
      list.querySelector?.('.notification-load-older')?.remove();
      nextCursor = result.next_cursor || null;
      if (nextCursor) {
        const older = document.createElement('button'); older.type = 'button'; older.className = 'notification-load-older'; older.textContent = 'Load older notifications';
        older.addEventListener('click', () => refresh({cursor: nextCursor, append: true})); list.appendChild(older);
      }
      if (!list.childNodes.length) setText(list, 'No notifications were returned for this Steward session.');
      setText(status, `Notifications loaded from recipient service · ${result.freshness || 'freshness unknown'} · ${result.presentation_timezone || 'presentation timezone unavailable'}`);
      status.dataset.state = result.freshness || 'unknown';
    } catch (error) {
      if (!append) list.replaceChildren();
      if (olderControl) olderControl.disabled = false;
      const unavailable = error.status === 404 ? 'Recipient notification inbox API is not mounted on this website service. ' : '';
      setText(status, `${error.status === 401 ? 'This notification request was unauthorized (401); Website session is checked separately. ' : unavailable}${append ? 'Older notification history unavailable; previously loaded records are retained. ' : ''}${error.message}${error.correlationId ? ` · correlation ${error.correlationId}` : ''}`);
      status.dataset.state = error.status === 401 ? 'unauthorized' : 'unavailable';
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
