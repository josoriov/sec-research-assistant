import { applyHttpResult, initialForm } from './form.js';

const SESSION_KEY = 'sec-research-response-v1';

export function restoreSession(storage) {
  try {
    const saved = JSON.parse(storage.getItem(SESSION_KEY));
    if (!saved || !['company', 'metric', 'question'].every((field) => typeof saved[field] === 'string')
      || !['ok', 'needs_clarification', 'error'].includes(saved.response?.status)) {
      return initialForm();
    }
    return applyHttpResult({
      ...initialForm(), company: saved.company, metric: saved.metric, question: saved.question,
    }, { ok: true }, saved.response);
  } catch {
    return initialForm();
  }
}

export function saveSession(storage, state) {
  try {
    if (!state.response) {
      storage.removeItem(SESSION_KEY);
      return;
    }
    const { company, metric, question, response } = state;
    storage.setItem(SESSION_KEY, JSON.stringify({ company, metric, question, response }));
  } catch {
    // A blocked/full store must not break the page or restore an older answer.
    try { storage.removeItem(SESSION_KEY); } catch {}
  }
}
