// F056 regression: the response is built with document.createElement after
// hydration, so its styles must live in a global style block. Astro scopes a
// plain <style> to template elements (adding a data-astro-cid attribute), so a
// scoped selector can never match a client-created response node.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

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
