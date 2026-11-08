/*
R3 CONTROLLED SOURCE
File: web/roadmap-status.mjs
Component: R3A-WEBSITE-ROADMAP-STATUS
File Revision: 1.0.1
Created: 2026-11-08 UTC
Created By: Codex GPT-6
Purpose: Read and render live GitHub roadmap/workstream issue records with explicit provenance.
Execution Model: Browser module; public read-only GitHub REST API plus authenticated same-origin AP3 diagnostics.
Observability: Reports repository, issue source, timestamps, and explicit unavailable states.
Dependencies: r3a.website-identification.v1; GitHub REST API; shared AP3 session status API.
Authority: Issue #51, comment 6725058145.
Tests: tests/test_roadmap_status.mjs uses development-only mocked fetch responses.
Changed: 2026-11-08 | #51 | Add on-demand latest issue update drilldown for owner evidence and reported blockers/actions.
*/

const REPOSITORY_PATTERN = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

export async function fetchRoadmapIssues({repository, apiBase, fetchImpl = globalThis.fetch, signal} = {}) {
  if (!REPOSITORY_PATTERN.test(repository || '') || !/^https:\/\/[^/?#]+(?:\/[^?#]*)?$/.test(apiBase || '')) {
    throw new Error('Roadmap repository or API origin is not configured');
  }
  const issues = [];
  let next = `${apiBase.replace(/\/$/, '')}/repos/${repository}/issues?state=all&per_page=100`;
  const visited = new Set();
  while (next && !visited.has(next)) {
    visited.add(next);
    const response = await fetchImpl.call(globalThis, next, {headers: {Accept: 'application/vnd.github+json'}, signal, cache: 'no-store'});
    if (!response.ok) throw new Error(`GitHub issue source unavailable (${response.status})`);
    const page = await response.json();
    if (!Array.isArray(page)) throw new Error('GitHub issue source returned an invalid response');
    issues.push(...page.filter(item => !item.pull_request));
    const links = response.headers?.get?.('Link') || '';
    next = links.split(',').map(part => part.trim()).find(part => /rel="next"/.test(part))?.match(/<([^>]+)>/)?.[1] || '';
  }
  return issues.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));
}

export async function fetchLatestIssueUpdates({repository, issueNumber, apiBase, fetchImpl = globalThis.fetch, signal} = {}) {
  if (!REPOSITORY_PATTERN.test(repository || '') || !Number.isInteger(issueNumber) || issueNumber < 1 || !/^https:\/\/[^/?#]+(?:\/[^?#]*)?$/.test(apiBase || '')) {
    throw new Error('Roadmap issue update request is not configured');
  }
  const url = `${apiBase.replace(/\/$/, '')}/repos/${repository}/issues/${issueNumber}/comments?per_page=100&sort=updated&direction=desc`;
  const response = await fetchImpl.call(globalThis, url, {headers: {Accept: 'application/vnd.github+json'}, signal, cache: 'no-store'});
  if (!response.ok) throw new Error(`Issue update source unavailable (${response.status})`);
  const comments = await response.json();
  if (!Array.isArray(comments)) throw new Error('Issue update source returned an invalid response');
  return comments.sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || '')).slice(0, 5);
}

export function mountRoadmapStatus({root = document, fetchImpl = globalThis.fetch} = {}) {
  const panel = root.getElementById('roadmap-panel');
  const open = root.getElementById('nav-roadmap');
  if (!panel || !open) return;
  const list = root.getElementById('roadmap-list');
  const status = root.getElementById('roadmap-status');
  const runtimeStatus = root.getElementById('roadmap-runtime-status');
  const setOpen = value => open.setAttribute('aria-expanded', String(value));
  let identity;
  const displayDate = value => {
    if (!value) return 'update time unavailable';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? `${value} · invalid timestamp` : `${date.toISOString()} UTC`;
  };
  async function refresh() {
    status.textContent = 'Loading live roadmap issue records…';
    list.replaceChildren();
    runtimeStatus.textContent = 'Reading authenticated CME diagnostics…';
    try {
      const runtimeResponse = await fetchImpl.call(globalThis, '/api/v1/steward/r3a/status', {credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}});
      const runtimePayload = await runtimeResponse.json().catch(() => ({}));
      if (!runtimeResponse.ok) throw new Error(runtimePayload.detail || `AP3 diagnostics unavailable (${runtimeResponse.status})`);
      runtimeStatus.textContent = `CME source: ${runtimePayload.source || 'unknown'} · observed: ${runtimePayload.observed_at || 'time unavailable'} · activity records: ${Array.isArray(runtimePayload.activities) ? runtimePayload.activities.length : 'not returned'}`;
      runtimeStatus.dataset.state = 'current';
    } catch (error) {
      runtimeStatus.textContent = `CME diagnostics ${error.message}; no runtime execution or module readiness is inferred from GitHub issues.`;
      runtimeStatus.dataset.state = 'unavailable';
    }
    try {
      identity ||= await (await fetchImpl.call(globalThis, '/api/v1/website/identity', {credentials: 'same-origin', cache: 'no-store'})).json();
      const issues = await fetchRoadmapIssues({repository: identity.roadmap_repository, apiBase: identity.roadmap_api_base, fetchImpl});
      const fragment = root.createDocumentFragment();
      for (const issue of issues) {
        const article = root.createElement('article'); article.className = 'roadmap-issue';
        const header = root.createElement('header');
        const title = root.createElement('a'); title.href = issue.html_url; title.target = '_blank'; title.rel = 'noopener noreferrer'; title.textContent = `#${issue.number} · ${issue.title || 'Untitled issue'}`;
        const state = root.createElement('span'); state.className = `roadmap-state ${issue.state === 'closed' ? 'closed' : 'open'}`; state.textContent = issue.state || 'state unknown';
        header.append(title, state);
        const metadata = root.createElement('p');
        const labels = (issue.labels || []).map(label => typeof label === 'string' ? label : label.name).filter(Boolean);
        const owners = (issue.assignees || []).map(person => person.login).filter(Boolean);
        metadata.textContent = [issue.milestone?.title || 'No milestone reported', owners.length ? `Owner: ${owners.join(', ')}` : 'Owner: not assigned', labels.length ? `Labels: ${labels.join(', ')}` : 'No labels', `Updated: ${displayDate(issue.updated_at)}`, `Comments: ${Number.isInteger(issue.comments) ? issue.comments : 'unknown'}`].join(' · ');
        const body = root.createElement('details');
        const summary = root.createElement('summary'); summary.textContent = 'Issue description and status context';
        const description = root.createElement('pre'); description.textContent = issue.body || 'No issue description supplied.';
        body.append(summary, description);
        const updateBox = root.createElement('details');
        const updateSummary = root.createElement('summary'); updateSummary.textContent = 'Latest reported evidence, blockers, and next actions';
        const loadUpdates = root.createElement('button'); loadUpdates.type = 'button'; loadUpdates.textContent = 'Load latest issue updates';
        const updates = root.createElement('div'); updates.className = 'roadmap-updates';
        loadUpdates.addEventListener('click', async () => {
          loadUpdates.disabled = true; loadUpdates.textContent = 'Loading issue updates…';
          try {
            const comments = await fetchLatestIssueUpdates({repository: identity.roadmap_repository, issueNumber: issue.number, apiBase: identity.roadmap_api_base, fetchImpl});
            updates.replaceChildren();
            for (const comment of comments) {
              const entry = root.createElement('article');
              const attribution = root.createElement('p'); attribution.textContent = `${comment.user?.login || 'Author unavailable'} · ${displayDate(comment.updated_at || comment.created_at)}`;
              const content = root.createElement('pre'); content.textContent = comment.body || 'Empty issue update.';
              entry.append(attribution, content); updates.appendChild(entry);
            }
            if (!comments.length) updates.textContent = 'No issue updates have been reported.';
            loadUpdates.textContent = 'Refresh latest issue updates';
          } catch (error) { updates.textContent = `Issue updates unavailable: ${error.message}`; loadUpdates.textContent = 'Retry latest issue updates'; }
          finally { loadUpdates.disabled = false; }
        });
        updateBox.append(updateSummary, loadUpdates, updates);
        article.append(header, metadata, body, updateBox); fragment.appendChild(article);
      }
      list.appendChild(fragment);
      if (!issues.length) list.textContent = 'No issue records returned.';
      status.textContent = `GitHub issue source · ${identity.roadmap_repository} · ${issues.length} issue records · issue reports are not proof of CME execution.`;
      status.dataset.state = 'current';
    } catch (error) {
      status.textContent = `${error.message}. Runtime state is reported separately by the authenticated AP3 diagnostics panel.`;
      status.dataset.state = 'unavailable';
      list.textContent = 'Roadmap data unavailable; no local or cached status is substituted.';
    }
  }
  open.addEventListener('click', () => { panel.hidden = false; panel.classList.remove('minimized'); setOpen(true); refresh(); });
  root.getElementById('roadmap-refresh')?.addEventListener('click', refresh);
  root.getElementById('roadmap-close')?.addEventListener('click', () => { panel.hidden = true; setOpen(false); });
  root.getElementById('roadmap-minimize')?.addEventListener('click', event => {
    panel.classList.toggle('minimized');
    const minimized = panel.classList.contains('minimized');
    event.currentTarget.textContent = minimized ? '□' : '−';
    event.currentTarget.setAttribute('aria-label', minimized ? 'Restore roadmap status' : 'Minimize roadmap status');
  });
}

if (typeof document !== 'undefined') mountRoadmapStatus();
