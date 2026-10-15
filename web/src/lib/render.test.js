// F059 regression: the response is rendered at the page boundary with a minimal
// DOM stub, so the visible output (outside collapsed disclosures) is asserted
// directly. Astro has no browser-test framework (H018); this exercises the same
// render functions the page wires to the real document.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createRenderers } from './render.js';

class TextNode {
  constructor(text) { this.nodeValue = String(text); }
  get textContent() { return this.nodeValue; }
}

class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.dataset = {};
    this._text = '';
  }
  set textContent(value) {
    this._text = value === null || value === undefined ? '' : String(value);
    this.children = [];
  }
  get textContent() {
    return this.children.length ? this.children.map((c) => c.textContent).join('') : this._text;
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
}

const document = {
  createElement: (tag) => new Element(tag),
  createTextNode: (text) => new TextNode(text),
};
const { renderResponse, renderStatus } = createRenderers(document);

// Text a user can see without expanding a <details> disclosure.
function visibleText(element) {
  if (element.tagName === 'DETAILS') return '';
  if (element.children?.length) return element.children.map(visibleText).join('');
  return element.textContent;
}

function render(response) {
  const container = new Element('div');
  renderResponse(container, response);
  return container;
}

const ABSTENTION = 'The assistant abstained.';

function blankAnswer(overrides = {}) {
  return {
    status: 'ok',
    answer: { text: '', abstained: true, citations: [], limitations: null, ...overrides },
    calculations: [{ tool: 'get_metric' }],
    passages: [],
    request: { company: 'AAPL', metric: 'revenue', fiscal_years: [2024] },
  };
}

// F059: an empty-text abstention must still show the returned flag, not only in
// the collapsed JSON.
test('an empty abstained answer shows the abstention notice outside the JSON view', () => {
  const container = render(blankAnswer({ limitations: 'Evidence conflicts.' }));
  const visible = visibleText(container);
  assert.ok(visible.includes('No generated answer was returned.'));
  assert.ok(visible.includes(ABSTENTION), 'the abstention flag must be visible');
  assert.ok(visible.includes('Evidence conflicts.'));
  // The flag survives in the JSON view too, but that is not the only place.
  assert.ok(container.textContent.includes('"abstained": true'));
});

test('an empty abstained answer without a limitation still shows the notice', () => {
  const visible = visibleText(render(blankAnswer()));
  assert.ok(visible.includes(ABSTENTION));
});

test('an empty non-abstained answer shows no abstention notice', () => {
  const container = render(blankAnswer({ abstained: false, text: '' }));
  assert.ok(!visibleText(container).includes(ABSTENTION));
});

test('a non-empty abstained answer shows the notice exactly once', () => {
  const container = render(blankAnswer({ text: 'The evidence does not support a cause.' }));
  const visible = visibleText(container);
  assert.ok(visible.includes('The evidence does not support a cause.'));
  assert.equal(visible.split(ABSTENTION).length - 1, 1);
});

test('an answer-null response is explained without an abstention notice', () => {
  const container = render({ status: 'needs_clarification', answer: null, clarifications: [] });
  const visible = visibleText(container);
  assert.ok(visible.includes('No answer was generated because the request still needs clarification.'));
  assert.ok(!visible.includes(ABSTENTION));
});

test('renderStatus labels the API status', () => {
  const element = new Element('p');
  renderStatus(element, { status: 'error' });
  assert.equal(element.textContent, 'Status: Request failed');
  assert.equal(element.dataset.status, 'error');
});

test('inline citations use source numbers and preserve exact destinations and metadata', () => {
  const citations = [
    { id: 'metric:320193:revenue:2021-09-26:2022-09-24', kind: 'metric', label: 'Revenue FY2022' },
    { id: 'passage:346', kind: 'passage', section: 'Item 7' },
  ];
  const container = render(blankAnswer({
    text: `Revenue declined [${citations[0].id}] [passage:346]. See [passage:3460].`,
    abstained: false,
    citations,
  }));
  function elements(element) {
    return [element, ...(element.children ?? []).flatMap(elements)];
  }
  const nodes = elements(container);
  const answer = nodes.find((element) => element.getAttribute?.('class') === 'answer-text');
  const links = answer.children.filter((element) => element.tagName === 'A');
  assert.equal(answer.textContent, 'Revenue declined [1] [2]. See [passage:3460].');
  assert.deepEqual(links.map((link) => link.getAttribute('href')), ['#citation-0', '#citation-1']);
  assert.equal(links[0].getAttribute('aria-label'), 'Source 1: Revenue FY2022');
  assert.equal(links[1].getAttribute('title'), 'Source 2: passage:346');
  assert.ok(links.every((link) => link.getAttribute('class') === 'citation-ref'));
  for (const [index, citation] of citations.entries()) {
    const source = nodes.find((element) => element.getAttribute?.('id') === `citation-${index}`);
    assert.equal(source.getAttribute('tabindex'), '-1');
    assert.ok(source.textContent.includes(citation.label || citation.id));
  }
  assert.ok(container.textContent.includes(citations[0].id));
});
