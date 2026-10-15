import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initialForm } from './form.js';
import { restoreSession, saveSession } from './session.js';

function memoryStorage() {
  const entries = new Map();
  return {
    getItem: (key) => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, value),
    removeItem: (key) => entries.delete(key),
  };
}

const completed = {
  ...initialForm(), company: 'AAPL', metric: 'revenue', question: 'How did revenue change?',
  response: { status: 'ok', answer: { text: '<script>untrusted</script>', citations: [] } },
};

test('a new tab starts empty while the same tab restores the entire response and its question', () => {
  const storage = memoryStorage();
  saveSession(storage, completed);
  assert.deepEqual(restoreSession(storage), completed);
  assert.deepEqual(restoreSession(memoryStorage()), initialForm());
});

test('clearing a response removes the saved result', () => {
  const storage = memoryStorage();
  saveSession(storage, completed);
  saveSession(storage, { ...completed, response: null });
  assert.deepEqual(restoreSession(storage), initialForm());
});

test('only completed response data is restored, without loading or transient errors', () => {
  const storage = memoryStorage();
  saveSession(storage, { ...completed, submitting: true, error: 'temporary', errors: { question: 'temporary' } });
  assert.deepEqual(restoreSession(storage), completed);
});

test('clarification and provider messages are restored through the existing response handler', () => {
  const storage = memoryStorage();
  const clarifications = [{ field: 'fiscal_years', reason: 'Which years?' }];
  saveSession(storage, { ...completed, response: { status: 'needs_clarification', clarifications } });
  assert.deepEqual(restoreSession(storage).clarifications, clarifications);
  saveSession(storage, { ...completed, response: { status: 'error', error: 'Provider unavailable' } });
  assert.equal(restoreSession(storage).error, 'Provider unavailable');
});

test('unreadable, invalid, or blocked storage starts empty and never breaks the page', () => {
  for (const value of ['broken JSON', 'null', '{}', JSON.stringify({ ...completed, company: {} })]) {
    assert.deepEqual(restoreSession({ getItem: () => value }), initialForm());
  }
  const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  assert.deepEqual(restoreSession(blocked), initialForm());
  assert.doesNotThrow(() => saveSession(blocked, completed));
  assert.doesNotThrow(() => saveSession(undefined, { ...completed, response: null }));
});

test('a full store discards the older answer instead of restoring it as the new result', () => {
  const storage = memoryStorage();
  saveSession(storage, completed);
  storage.setItem = () => { throw new Error('quota exceeded'); };
  saveSession(storage, { ...completed, question: 'A different question' });
  assert.deepEqual(restoreSession(storage), initialForm());
});
