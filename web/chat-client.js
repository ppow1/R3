/* R3 CONTROLLED SOURCE
 * File: web/chat-client.js
 * Component: WEBSITE-CHAT-CLIENT
 * File Revision: 1.1.0
 * Created: Unknown (legacy)
 * Created By: Unknown (legacy)
 * Purpose: Dynamic multi-resident authenticated website Chat client.
 * Execution Model: Browser JavaScript; same-origin website API.
 * Observability: Accessible resident/runtime status; no credential logging.
 * Dependencies: Website Chat API; native R3 session and CSRF cookies.
 * Authority: Server-side Steward and HR directory authorization.
 * Changed: 2026-11-05 UTC | WEBSITE-MULTIRESIDENT-CHAT | ChatGPT GPT-6 | Use canonical HR IDs and server-validated runtime readiness.
 * Supersedes: Prior Grace-default Chat client; predecessor blob caac6e5a09d5fde275fbaf4d7abb4cf30a5a6242
 * Contracts: r3_chat_api.py; runtime/conversations.py; hints/file-provenance.md
 * Tests: tests/test_website_hr_directory.py; browser integration pending deployment.
 * History/Predecessor: Git blob caac6e5a09d5fde275fbaf4d7abb4cf30a5a6242
 */
(() => {
  'use strict';
  const base = window.R3_BASE || '';
  const api = path => `${base}/api/v1/chat${path}`;
  const json = async (path, options = {}) => {
    const response = await fetch(api(path), { credentials: 'same-origin', cache: 'no-store', ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const err = new Error(data.detail || data.error || `HTTP ${response.status}`);
      err.status = response.status;
      throw err;
    }
    return data;
  };

  window.r3ChatAdapter = {
    residents: () => json('/residents'),
    listConversations: (resident) => json(`/residents/${encodeURIComponent(resident)}/conversations`),
    capabilityManifest: (resident) => json(`/residents/${encodeURIComponent(resident)}/capabilities`),
    messages: (resident, id) => json(`/residents/${encodeURIComponent(resident)}/conversations/${encodeURIComponent(id)}/messages?after=0&limit=200`),
    createConversation: (title, resident) => json(`/residents/${encodeURIComponent(resident)}/conversations`, { method: 'POST', headers: mutationHeaders(), body: JSON.stringify({title}) }),
    sendMessage: (resident, id, content, client_message_id) => json(`/residents/${encodeURIComponent(resident)}/conversations/${encodeURIComponent(id)}/messages`, { method: 'POST', headers: mutationHeaders(), body: JSON.stringify({content, client_message_id}) })
  };

  function mutationHeaders() {
    const csrf = document.cookie.split(';').map(value => value.trim())
      .find(value => value.startsWith('r3_steward_csrf='));
    return {'Content-Type':'application/json', 'X-Riverview-CSRF': csrf ? decodeURIComponent(csrf.slice(csrf.indexOf('=') + 1)) : ''};
  }

  const el = (tag, attrs = {}, text = '') => {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (key === 'class') node.className = value;
      else if (key === 'dataset') Object.assign(node.dataset, value);
      else node.setAttribute(key, value);
    });
    if (text) node.textContent = text;
    return node;
  };
  const idFor = row => row.conversation_id || row.id;

  function init() {
    const panel = document.getElementById('chat-panel');
    const sidebar = panel?.querySelector('.chat-sidebar');
    const main = panel?.querySelector('.chat-main');
    if (!panel || !sidebar || !main) return;
    const sideHead = sidebar.querySelector('.chat-head');
    const mainHead = main.querySelector('.chat-head');
    sidebar.replaceChildren(sideHead);
    main.replaceChildren(mainHead);

    const search = el('input', {class:'chat-search', type:'search', placeholder:'Search conversations', 'aria-label':'Search conversations'});
    const list = el('div', {class:'r3-chat-list', role:'list'});
    const sideStatus = el('div', {class:'chat-status', id:'r3-chat-service-status', role:'status'});
    const noConversations = el('div', {class:'chat-empty'}, 'No conversations yet. Start one with +.');
    const residentSelect = el('select', {class:'r3-resident-select', 'aria-label':'Choose resident'});

    sidebar.append(residentSelect, search, sideStatus, list, noConversations);

    const status = el('div', {class:'r3-chat-status', role:'status', 'aria-live':'polite'});
    const messages = el('div', {class:'r3-chat-messages', 'aria-live':'polite'});
    const empty = el('div', {class:'r3-chat-empty'}, 'Choose a conversation or create one.');
    const form = el('form', {class:'r3-chat-compose'});
    form.innerHTML = '<textarea name="content" rows="2" maxlength="100000" placeholder="Write a message" aria-label="Write a message" disabled required></textarea><button class="icon-button" type="submit" aria-label="Send message" disabled>↑</button>';
    main.append(status, empty, messages, form);

    const newButton = document.getElementById('chat-new');
    if (newButton) { newButton.disabled = true; newButton.title = 'Select an available resident runtime first'; }
    const conference = document.getElementById('chat-conference');
    if (conference) { conference.disabled = true; conference.title = 'Conference rooms are not available yet'; }
    const composer = form.elements.content;
    const sendButton = form.querySelector('button[type=submit]');
    let residentId = '';
    let activeId = '';
    let conversations = [];
    let residentReady = false;
    let pollTimer;
    let pending = null;

    function announce(text, error = false) {
      status.textContent = text;
      status.classList.toggle('is-error', error);
      sideStatus.textContent = text;
    }
    function displayLogin(show) {
      form.hidden = show;
      if (show) {
        composer.disabled = true;
        sendButton.disabled = true;
      }
    }
    function listRows(rows) {
      conversations = Array.isArray(rows) ? rows : [];
      list.replaceChildren();
      noConversations.hidden = conversations.length > 0;
      conversations.filter(row => String(row.title || '').toLowerCase().includes(search.value.toLowerCase()))
        .forEach(row => {
          const id = idFor(row);
          if (!id) return;
          const button = el('button', {class:'r3-chat-conversation', type:'button', role:'listitem'}, row.title || 'Conversation');
          button.classList.toggle('is-active', id === activeId);
          button.addEventListener('click', () => openConversation(id));
          list.append(button);
        });
    }
    function renderMessages(rows) {
      messages.replaceChildren();
      empty.hidden = rows.length > 0;
      rows.forEach(item => {
        const article = el('article', {class:`r3-chat-message ${item.sender_type === 'RESIDENT' || item.sender_type === 'ASSISTANT' ? 'from-resident' : 'from-steward'}`});
        const header = el('div', {class:'r3-chat-message-meta'});
        header.append(el('strong', {}, item.sender || item.sender_id || (item.sender_type === 'STEWARD' ? 'Steward' : residentId)));
        if (item.created_at || item.timestamp) header.append(el('time', {}, item.created_at || item.timestamp));
        if (item.status || item.delivery_status) header.append(el('span', {class:'r3-chat-delivery'}, item.status || item.delivery_status));
        article.append(header, el('p', {}, item.content || ''));
        messages.append(article);
      });
      messages.scrollTop = messages.scrollHeight;
    }
    async function loadMessages() {
      if (!activeId) return;
      const data = await window.r3ChatAdapter.messages(residentId, activeId);
      renderMessages(data.messages || []);
    }
    async function refreshList() {
      const data = await window.r3ChatAdapter.listConversations(residentId);
      listRows(data.conversations || data.items || []);
      return conversations;
    }
    async function prepareResident() {
      residentReady = false;
      composer.disabled = true;
      sendButton.disabled = true;
      if (newButton) newButton.disabled = true;
      // The server resolves the selected HR ID through its confidential
      // association and returns 404 unless the configured runtime responds.
      await window.r3ChatAdapter.capabilityManifest(residentId);
      residentReady = true;
      if (newButton) { newButton.disabled = false; newButton.title = 'New conversation'; }
    }
    async function openConversation(id) {
      activeId = id;
      sessionStorage.setItem(`r3.chat.active.${residentId}`, id);
      listRows(conversations);
      composer.disabled = false;
      sendButton.disabled = false;
      empty.hidden = true;
      messages.replaceChildren();
      try { await loadMessages(); announce('Conversation ready.'); }
      catch (error) { announce(`Could not load messages: ${error.message}`, true); }
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(() => loadMessages().catch(e => announce(`Refresh failed: ${e.message}`, true)), 2500);
    }
    async function authenticate() {
      const session = await json('/session');
      const identity = session.identity || {};
      if (!session.authenticated && !identity.email) throw Object.assign(new Error('Sign in to use Chat.'), {status:401});
      displayLogin(false);
      announce(`Signed in as ${identity.email || 'Steward'}. Loading conversations…`);
      const directory = await window.r3ChatAdapter.residents();
      const residents = directory.residents || [];
      residentSelect.replaceChildren();
      residents.forEach(r => {
        const suffix = r.availability === 'unavailable' ? ' · Runtime unavailable' : '';
        const option = el('option', {value:r.id}, r.name + ' · ' + r.position + suffix);
        residentSelect.append(option);
      });
      if (!residents.length) throw new Error('No authorized residents are available');
      if (!residents.some(r => r.id === residentId)) {
        residentId = residents[0].id;
        activeId = sessionStorage.getItem(`r3.chat.active.${residentId}`) || '';
      }
      residentSelect.value = residentId;
      composer.placeholder = 'Message ' + residentSelect.selectedOptions[0]?.textContent.split(' · ')[0];
      composer.setAttribute('aria-label', composer.placeholder);
      try {
        await prepareResident();
        await refreshList();
        const selected = conversations.find(row => idFor(row) === activeId) || conversations[0];
        if (selected) await openConversation(idFor(selected));
        else announce('Connected. Create a conversation with +.');
      } catch (error) {
        announce(`Selected resident runtime is unavailable: ${error.message}`, true);
      }
    }

    search.addEventListener('input', () => listRows(conversations));
    residentSelect.addEventListener('change', async () => {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      residentId = residentSelect.value;
      residentReady = false;
      activeId = sessionStorage.getItem(`r3.chat.active.${residentId}`) || '';
      composer.placeholder = 'Message ' + residentSelect.selectedOptions[0]?.textContent.split(' · ')[0];
      composer.disabled = true; sendButton.disabled = true;
      messages.replaceChildren(); conversations = []; listRows([]);
      try {
        await prepareResident();
        await refreshList();
        const selected = conversations.find(row => idFor(row) === activeId) || conversations[0];
        if (selected) await openConversation(idFor(selected));
        else { activeId = ''; announce('No conversations yet. Select + to start one.'); }
      } catch (error) { announce('Resident Chat unavailable: ' + error.message, true); }
    });
    newButton?.addEventListener('click', async () => {
      try {
        if (!residentReady) await prepareResident();
        const data = await window.r3ChatAdapter.createConversation('Steward conversation', residentId);
        const row = data.conversation || data;
        const id = idFor(row);
        await refreshList();
        if (id) await openConversation(id);
        else announce('Conversation was created, but the service returned no conversation id.', true);
      } catch (error) { announce(`Could not create conversation: ${error.message}`, true); }
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const content = composer.value.trim();
      if (!residentReady || !activeId || !content) return;
      if (!pending || pending.content !== content || pending.conversation !== activeId) {
        const storageKey = `r3.chat.pending.${activeId}`;
        try { pending = JSON.parse(sessionStorage.getItem(storageKey) || 'null'); } catch (_) { pending = null; }
        if (!pending || pending.content !== content || pending.conversation !== activeId)
          pending = {content, conversation:activeId, id:(crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`)};
        sessionStorage.setItem(storageKey, JSON.stringify(pending));
      }
      sendButton.disabled = true;
      try {
        await window.r3ChatAdapter.sendMessage(residentId, activeId, content, pending.id);
        sessionStorage.removeItem(`r3.chat.pending.${activeId}`); pending = null; composer.value = ''; await loadMessages();
        announce('Message submitted. Waiting for resident…');
      } catch (error) { announce(`Send failed. Retry safely: ${error.message}`, true); }
      finally { sendButton.disabled = false; }
    });

    displayLogin(false);
    authenticate().catch(error => {
      displayLogin(false);
      if (error.status === 401 || error.status === 403) {
        announce('Website session is not authorized for Chat. Sign in through the main R3 login page.', true);
      } else {
        announce(`Chat service unavailable: ${error.message}`, true);
      }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
