/* Permanent regressions for browser storage denial; uses no real browser data. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const source = await readFile(new URL('../web/browser-preferences.js', import.meta.url), 'utf8');

function loadWithWindow(window) {
  vm.runInNewContext(source, {window});
  return window.r3aBrowserPreferences;
}

test('restricted localStorage getter falls back to tab memory without throwing', () => {
  const window = {};
  Object.defineProperty(window, 'localStorage', {get() { throw new Error('SecurityError'); }});
  const preferences = loadWithWindow(window);
  assert.equal(preferences.isPersistent(), false);
  assert.equal(preferences.setItem('layout', '1'), false);
  assert.equal(preferences.getItem('layout'), '1');
  assert.equal(preferences.removeItem('layout'), false);
  assert.equal(preferences.getItem('layout'), null);
});

test('quota or storage method errors downgrade to memory and preserve current edits', () => {
  const storage = {
    getItem() { return null; },
    setItem() { throw new Error('QuotaExceededError'); },
    removeItem() { throw new Error('SecurityError'); },
  };
  const preferences = loadWithWindow({localStorage: storage});
  assert.equal(preferences.isPersistent(), true);
  assert.equal(preferences.setItem('opacity', '80'), false);
  assert.equal(preferences.isPersistent(), false);
  assert.equal(preferences.getItem('opacity'), '80');
  assert.equal(preferences.removeItem('opacity'), false);
  assert.equal(preferences.getItem('opacity'), null);
});

test('available storage remains durable and mirrors non-sensitive preferences', () => {
  const data = new Map();
  const storage = {
    getItem: key => data.has(key) ? data.get(key) : null,
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: key => data.delete(key),
  };
  const preferences = loadWithWindow({localStorage: storage});
  assert.equal(preferences.setItem('panel-opacity', 75), true);
  assert.equal(preferences.getItem('panel-opacity'), '75');
  assert.equal(data.get('panel-opacity'), '75');
  assert.equal(preferences.removeItem('panel-opacity'), true);
  assert.equal(preferences.getItem('panel-opacity'), null);
});
