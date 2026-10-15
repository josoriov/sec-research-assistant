// Pure form logic for the Astro question UI (release v0.2, task T012).
//
// Kept framework- and DOM-free so both the browser script and `node --test`
// exercise the same code: validating the input, guarding duplicate submissions,
// and turning a response into the next UI state while preserving the user's
// original company/metric/prompt selections (needed for the clarification flow).

// Supported companies and metrics mirror the ingestion mapping and the API
// taxonomy (api/schemas.py). Kept in sync by hand — the API exposes no catalog.
export const COMPANIES = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'];

export const METRICS = [
  { value: 'revenue', label: 'Revenue' },
  { value: 'net_income', label: 'Net income' },
  { value: 'operating_cash_flow', label: 'Operating cash flow' },
];

export function initialForm() {
  return {
    company: '',
    metric: '',
    question: '',
    submitting: false,
    errors: {},
    clarifications: [],
    error: '',
    response: null,
  };
}

export function validateForm(state) {
  const errors = {};
  if (!state.company.trim()) errors.company = 'Select a company.';
  if (!state.question.trim()) errors.question = 'Enter a question.';
  return errors;
}

export function buildAskPayload(state) {
  const payload = { company: state.company.trim(), question: state.question.trim() };
  if (state.metric) payload.metric = state.metric;
  return payload;
}

const UNREADABLE = 'The answer service returned an unreadable response.';

// The browser trusts an HTTP success boundary: an error status must never be
// treated as an ordinary, silent success just because its JSON body lacks the
// application's `status` field (e.g. FastAPI's 422 `{"detail": ...}` or a 404).
export function applyHttpResult(state, response, body) {
  if (!response || response.ok !== true) {
    const status = response && Number.isInteger(response.status) ? response.status : null;
    return reducer(state, { type: 'failure', message: httpFailureMessage(status, body) });
  }
  if (!body || typeof body !== 'object') {
    return reducer(state, { type: 'failure', message: UNREADABLE });
  }
  return reducer(state, { type: 'response', response: body });
}

export function httpFailureMessage(status, body) {
  const detail = body && typeof body === 'object'
    ? (typeof body.detail === 'string' ? body.detail : body.error)
    : null;
  const where = status === null ? 'The request failed' : `The request failed (HTTP ${status})`;
  return typeof detail === 'string' && detail.trim() ? `${where}: ${detail.trim()}` : `${where}.`;
}

// A single reducer drives the UI; every branch spreads the previous state so the
// prompt and selections survive submit, failure, and clarification.
export function reducer(state, action) {
  switch (action.type) {
    case 'edit':
      return {
        ...state,
        [action.field]: action.value,
        errors: { ...state.errors, [action.field]: undefined },
        error: '',
      };
    case 'submit': {
      if (state.submitting) return state; // duplicate-submit guard
      const errors = validateForm(state);
      if (Object.keys(errors).length) return { ...state, errors, error: '' };
      return {
        ...state,
        submitting: true,
        errors: {},
        error: '',
        clarifications: [],
      };
    }
    case 'clear_response':
      return { ...state, response: null, clarifications: [], error: '' };
    case 'response':
      return applyResponse({ ...state, submitting: false }, action.response);
    case 'failure':
      return { ...state, submitting: false, error: action.message || 'The request failed. Please try again.' };
    default:
      return state;
  }
}

function applyResponse(state, response) {
  if (response.status === 'needs_clarification') {
    return {
      ...state,
      clarifications: Array.isArray(response.clarifications) ? response.clarifications : [],
      response,
    };
  }
  if (response.status === 'error') {
    return {
      ...state,
      error: response.error || 'The assistant could not interpret the question.',
      response: state.response ?? response,
    };
  }
  return { ...state, clarifications: [], response };
}
