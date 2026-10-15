// F056 regression: the response is built with document.createElement after
// hydration, so its styles must live in a global style block. Astro scopes a
// plain <style> to template elements (adding a data-astro-cid attribute), so a
// scoped selector can never match a client-created response node.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { applyHttpResult, buildAskPayload, reducer } from '../lib/form.js';
import { restoreSession, saveSession } from '../lib/session.js';

const page = readFileSync(new URL('./index.astro', import.meta.url), 'utf8');

function collect(pattern) {
  return [...page.matchAll(pattern)].map((match) => match[1]).join('\n');
}

const globalStyles = collect(/<style\s+is:global>([\s\S]*?)<\/style>/g);
const scopedStyles = collect(/<style>([\s\S]*?)<\/style>/g);

test('response styles are global so client-created nodes are styled', () => {
  assert.notEqual(globalStyles.trim(), '', 'expected a <style is:global> block');
  for (const selector of ['.answer-text', '.passage-text', 'pre', 'dl', '.caveat', '.citation']) {
    assert.ok(
      globalStyles.includes(`#results ${selector}`),
      `global styles must contain "#results ${selector}"`,
    );
  }
  assert.match(globalStyles, /#results\s+\.answer-text[^{]*\{[^}]*white-space:\s*pre-wrap/);
  assert.match(globalStyles, /#results\s+pre\s*\{[^}]*overflow-x:\s*auto/);
});

test('response selectors are not left in the scoped style block', () => {
  for (const selector of ['.answer-text', '.passage-text', '.citation', '.caveat', '.no-answer']) {
    assert.ok(
      !scopedStyles.includes(selector),
      `"${selector}" must not be scoped; Astro would add a cid generated nodes lack`,
    );
  }
});

test('editing during a request saves the answer with the submitted form for reload', async () => {
  const elements = new Map();
  const entries = new Map();
  const storage = {
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
  };
  const document = {
    documentElement: { dataset: { theme: 'light' } },
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {
        value: '', listeners: {}, replaceChildren() {},
        addEventListener(event, listener) { this.listeners[event] = listener; },
      });
      return elements.get(id);
    },
  };
  let respond;
  let submittedPayload;
  const script = page.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^\s*import .*;$/gm, '');
  runInNewContext(script, {
    document, window: { sessionStorage: storage },
    applyHttpResult, buildAskPayload, reducer, restoreSession, saveSession,
    createRenderers: () => ({ renderResponse() {}, renderStatus() {} }),
    fetch(_url, options) {
      submittedPayload = JSON.parse(options.body);
      return new Promise((resolve) => { respond = resolve; });
    },
  });

  function edit(id, value) {
    const element = elements.get(id);
    element.value = value;
    element.listeners.input();
  }
  edit('company', 'AAPL');
  edit('question', 'What was Apple revenue in 2024?');
  const pending = elements.get('ask-form').listeners.submit({ preventDefault() {} });
  edit('company', 'MSFT');
  edit('metric', 'net_income');
  edit('question', 'What was Microsoft net income in 2025?');
  const response = { status: 'ok', answer: { text: 'Apple revenue was ...', citations: [] } };
  respond({ ok: true, json: async () => response });
  await pending;

  const restored = restoreSession(storage);
  assert.deepEqual(submittedPayload, { company: 'AAPL', question: 'What was Apple revenue in 2024?' });
  assert.equal(restored.company, 'AAPL');
  assert.equal(restored.metric, '');
  assert.equal(restored.question, submittedPayload.question);
  assert.deepEqual(restored.response, response);
  assert.equal(elements.get('question').value, 'What was Microsoft net income in 2025?');
});
