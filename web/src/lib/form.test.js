// Task T012: the pure UI logic, tested without a browser or framework.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  applyHttpResult,
  buildAskPayload,
  httpFailureMessage,
  initialForm,
  reducer,
  validateForm,
} from './form.js';

function filled(overrides = {}) {
  return { ...initialForm(), company: 'AAPL', question: 'why did revenue change?', ...overrides };
}

test('buildAskPayload trims input and omits an unset metric', () => {
  assert.deepEqual(buildAskPayload(filled({ question: '  why?  ' })), {
    company: 'AAPL',
    question: 'why?',
  });
});

test('buildAskPayload includes an explicitly selected metric', () => {
  assert.deepEqual(buildAskPayload(filled({ metric: 'net_income' })), {
    company: 'AAPL',
    metric: 'net_income',
    question: 'why did revenue change?',
  });
});

test('validateForm requires a company and a question', () => {
  assert.deepEqual(Object.keys(validateForm(initialForm())).sort(), ['company', 'question']);
  assert.deepEqual(validateForm(filled()), {});
});

test('submit with missing fields records errors and does not start a request', () => {
  const next = reducer(initialForm(), { type: 'submit' });
  assert.equal(next.submitting, false);
  assert.deepEqual(Object.keys(next.errors).sort(), ['company', 'question']);
});

test('a valid submit enters the loading state and clears prior messages', () => {
  const prior = filled({ error: 'old', clarifications: [{ field: 'metric', reason: 'old' }] });
  const next = reducer(prior, { type: 'submit' });
  assert.equal(next.submitting, true);
  assert.deepEqual(next.clarifications, []);
  assert.equal(next.error, '');
  assert.deepEqual(next.errors, {});
});

test('a second submit while loading is ignored (duplicate-submit guard)', () => {
  const loading = reducer(filled(), { type: 'submit' });
  assert.equal(loading.submitting, true);
  assert.strictEqual(reducer(loading, { type: 'submit' }), loading);
});

test('needs_clarification shows messages and preserves prompt and selections', () => {
  const loading = reducer(filled({ metric: 'revenue' }), { type: 'submit' });
  const next = reducer(loading, {
    type: 'response',
    response: {
      status: 'needs_clarification',
      clarifications: [{ field: 'fiscal_years', reason: 'Please choose 2023 or 2024.' }],
    },
  });
  assert.equal(next.submitting, false);
  assert.deepEqual(next.clarifications, [
    { field: 'fiscal_years', reason: 'Please choose 2023 or 2024.' },
  ]);
  assert.equal(next.company, 'AAPL');
  assert.equal(next.metric, 'revenue');
  assert.equal(next.question, 'why did revenue change?');
});

test('an error response surfaces the message', () => {
  const loading = reducer(filled(), { type: 'submit' });
  const next = reducer(loading, {
    type: 'response',
    response: { status: 'error', error: 'could not interpret the question: endpoint down' },
  });
  assert.equal(next.submitting, false);
  assert.match(next.error, /endpoint down/);
});

test('an ok response clears clarifications and keeps the selections', () => {
  const loading = reducer(filled({ metric: 'revenue' }), { type: 'submit' });
  const next = reducer(loading, { type: 'response', response: { status: 'ok' } });
  assert.equal(next.submitting, false);
  assert.deepEqual(next.clarifications, []);
  assert.equal(next.company, 'AAPL');
  assert.equal(next.metric, 'revenue');
});

test('a transport failure leaves the form editable and reports an error', () => {
  const loading = reducer(filled(), { type: 'submit' });
  const next = reducer(loading, { type: 'failure' });
  assert.equal(next.submitting, false);
  assert.notEqual(next.error, '');
});

test('edit updates one field and clears its error', () => {
  const errored = reducer(initialForm(), { type: 'submit' });
  const next = reducer(errored, { type: 'edit', field: 'company', value: 'MSFT' });
  assert.equal(next.company, 'MSFT');
  assert.equal(next.errors.company, undefined);
});

test('the last response remains visible during a new request and a transport failure', () => {
  const response = { status: 'ok', answer: { text: 'Previous answer' } };
  const loading = reducer(filled({ response }), { type: 'submit' });
  assert.strictEqual(loading.response, response);
  assert.strictEqual(reducer(loading, { type: 'failure' }).response, response);
});

test('a provider failure keeps the prior response and displays the new error', () => {
  const response = { status: 'ok', answer: { text: 'Previous answer' } };
  const loading = reducer(filled({ response }), { type: 'submit' });
  const next = reducer(loading, {
    type: 'response', response: { status: 'error', error: 'Provider unavailable' },
  });
  assert.strictEqual(next.response, response);
  assert.equal(next.error, 'Provider unavailable');
  assert.equal(next.submitting, false);
});

test('Clear response removes the result and messages while keeping the form editable', () => {
  const prior = filled({
    response: { status: 'ok' }, error: 'Old error',
    clarifications: [{ field: 'metric', reason: 'Which metric?' }],
  });
  const next = reducer(prior, { type: 'clear_response' });
  assert.equal(next.response, null);
  assert.deepEqual(next.clarifications, []);
  assert.equal(next.error, '');
  assert.equal(next.company, prior.company);
  assert.equal(next.question, prior.question);
});

// F054: a non-2xx JSON response (e.g. FastAPI's 422 ``{"detail": ...}``) must
// never be accepted as a silent success by the browser response boundary.
test('a non-2xx JSON response is shown as an error, not a success', () => {
  for (const [status, detail] of [[422, 'Invalid request'], [404, 'Not Found'], [503, 'Service temporarily unavailable']]) {
    const loading = reducer(filled({ metric: 'revenue' }), { type: 'submit' });
    const next = applyHttpResult(loading, { ok: false, status }, { detail });
    assert.equal(next.submitting, false, `status ${status} must stop loading`);
    assert.match(next.error, new RegExp(String(status)), `status ${status} must be reported`);
    assert.match(next.error, new RegExp(detail), `status ${status} detail must be shown`);
    assert.equal(next.company, 'AAPL');
    assert.equal(next.metric, 'revenue');
    assert.equal(next.question, 'why did revenue change?');
  }
});

test('a successful response still routes by the application status', () => {
  const loading = reducer(filled(), { type: 'submit' });
  const clarified = applyHttpResult(loading, { ok: true, status: 200 }, {
    status: 'needs_clarification',
    clarifications: [{ field: 'metric', reason: 'Which metric?' }],
  });
  assert.deepEqual(clarified.clarifications, [{ field: 'metric', reason: 'Which metric?' }]);

  const errored = applyHttpResult(loading, { ok: true, status: 200 }, {
    status: 'error',
    error: 'could not interpret the question',
  });
  assert.match(errored.error, /could not interpret/);
});

test('a 2xx response with an unreadable body is an error, not a silent success', () => {
  const loading = reducer(filled(), { type: 'submit' });
  const next = applyHttpResult(loading, { ok: true, status: 200 }, null);
  assert.equal(next.submitting, false);
  assert.match(next.error, /unreadable/);
});

test('httpFailureMessage includes the status and a safe detail', () => {
  assert.equal(httpFailureMessage(422, { detail: 'Invalid request' }),
    'The request failed (HTTP 422): Invalid request');
  assert.equal(httpFailureMessage(500, {}), 'The request failed (HTTP 500).');
  assert.equal(httpFailureMessage(null, null), 'The request failed.');
});
