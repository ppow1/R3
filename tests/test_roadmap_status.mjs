/* Development test mocks only; no GitHub or institutional records are asserted as live. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {fetchRoadmapIssues} from '../web/roadmap-status.mjs';

test('roadmap reads configured repository issue pages and excludes pull requests', async () => {
  const calls = [];
  const fetchMock = async url => {
    calls.push(url);
    if (calls.length === 1) return {ok: true, headers: {get: () => '<https://api.example.test/page2>; rel="next"'}, json: async () => [
      {number: 2, updated_at: '2026-11-08T12:00:00Z'},
      {number: 3, pull_request: {url: 'https://example.test/pr/3'}},
    ]};
    return {ok: true, headers: {get: () => null}, json: async () => [{number: 1, updated_at: '2026-11-08T13:00:00Z'}]};
  };
  const issues = await fetchRoadmapIssues({repository: 'team/R3', apiBase: 'https://api.example.test', fetchImpl: fetchMock});
  assert.deepEqual(calls, ['https://api.example.test/repos/team/R3/issues?state=all&per_page=100', 'https://api.example.test/page2']);
  assert.deepEqual(issues.map(issue => issue.number), [1, 2]);
});

test('roadmap requires externally configured repository and HTTPS API origin', async () => {
  await assert.rejects(fetchRoadmapIssues({repository: '', apiBase: 'https://api.example.test', fetchImpl: async () => {throw new Error('must not fetch');}}), /not configured/);
  await assert.rejects(fetchRoadmapIssues({repository: 'owner/repo', apiBase: 'http://api.example.test', fetchImpl: async () => {throw new Error('must not fetch');}}), /not configured/);
});
