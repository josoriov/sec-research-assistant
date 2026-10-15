// Pure display helpers for the /ask response (release v0.2, task T013).
//
// Kept framework- and DOM-free so `node --test` exercises the non-trivial logic.
// The page renders the returned data with `textContent` and URL scheme checks
// only — never `innerHTML` — so untrusted answer/passage text cannot execute
// HTML or JavaScript.

// The API omits fields it has no value for; label them so "unset" is never
// mistaken for a real zero.
export const UNAVAILABLE = 'Unavailable';

export function formatValue(value) {
  return value === null || value === undefined || value === '' ? UNAVAILABLE : String(value);
}

export function formatNumber(value) {
  return value === null || value === undefined || Number.isNaN(value)
    ? UNAVAILABLE
    : String(value);
}

// The API returns `change_percent` as a ratio ((b - a) / a), not a percentage
// (sql/compare_periods.sql), so scale it here. A real zero stays 0 and a
// missing value stays `Unavailable`.
export function formatPercent(ratio) {
  return ratio === null || ratio === undefined || Number.isNaN(ratio)
    ? UNAVAILABLE
    : `${ratio * 100}%`;
}

export function formatPeriod(start, end) {
  const parts = [start, end].filter((part) => part !== null && part !== undefined && part !== '');
  return parts.length ? parts.join(' → ') : UNAVAILABLE;
}

// Only http(s) links are rendered, so a hostile or malformed URL cannot become
// a `javascript:` or `data:` href.
export function safeUrl(value) {
  if (typeof value !== 'string' || value === '') return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:' ? value : null;
  } catch {
    return null;
  }
}

export function citationAnchor(index) {
  return `citation-${index}`;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Split untrusted answer text into ordered segments, turning a citation the
// model referenced (bare id or [id]) into a link to its source entry. The
// longest ids are matched first, and a match must be a whole identity token:
// an accepted id never matches the prefix of a longer, unknown id in the text
// (e.g. accepted `passage:4734` must not match inside `passage:47340`).
export function splitAnswer(text, citations = []) {
  const body = typeof text === 'string' ? text : '';
  const ids = citations
    .map((citation) => citation && citation.id)
    .filter((id) => typeof id === 'string' && id.length > 0);
  if (!body || ids.length === 0) return [{ kind: 'text', value: body }];

  const ordered = [...ids].sort((a, b) => b.length - a.length);
  const pattern = new RegExp(
    `(?:\\[)?(?<![\\w:-])(${ordered.map(escapeRegExp).join('|')})(?:\\])?(?![\\w:-])`,
    'g',
  );
  const indexOf = new Map(ids.map((id, index) => [id, index]));

  const segments = [];
  let last = 0;
  for (const match of body.matchAll(pattern)) {
    if (match.index > last) segments.push({ kind: 'text', value: body.slice(last, match.index) });
    segments.push({ kind: 'citation', id: match[1], index: indexOf.get(match[1]) });
    last = match.index + match[0].length;
  }
  if (last < body.length) segments.push({ kind: 'text', value: body.slice(last) });
  return segments;
}

export function statusLabel(status) {
  switch (status) {
    case 'ok':
      return 'Answer ready';
    case 'needs_clarification':
      return 'More information needed';
    case 'error':
      return 'Request failed';
    default:
      return 'Unknown status';
  }
}

// The answer's own metadata; a missing field is "Unavailable", not 0.
export function metadataRows(answer = {}) {
  const usage = answer.usage || {};
  const rows = [
    ['Model', answer.model],
    ['Prompt tokens', usage.prompt_tokens],
    ['Completion tokens', usage.completion_tokens],
    ['Latency', answer.latency_ms == null ? null : `${answer.latency_ms} ms`],
    ['Cost (USD)', answer.cost_usd == null ? null : `$${answer.cost_usd}`],
  ];
  return rows.map(([label, value]) => ({ label, value: formatValue(value) }));
}

function sourceRows(source) {
  if (!source) return [];
  const rows = [
    { label: 'Source period', value: formatPeriod(source.period_start, source.period_end) },
  ];
  if (source.accession) rows.push({ label: 'Source filing', value: String(source.accession) });
  if (source.form) rows.push({ label: 'Source form', value: String(source.form) });
  if (source.filed_date) rows.push({ label: 'Source filed', value: String(source.filed_date) });
  if (source.is_ambiguous) {
    rows.push({ label: 'Ambiguity', value: 'Flagged: restated or conflicting disclosures' });
  }
  return rows;
}

// One calculation as labelled rows: values, periods, units, the comparison and
// its sources, ambiguity flags, and the tool's notes.
export function calculationRows(calc = {}) {
  const rows = [];
  const push = (label, value) => rows.push({ label, value: formatValue(value) });
  push('Tool', calc.tool);
  if ('metric' in calc) push('Metric', calc.metric);
  if ('unit' in calc) push('Unit', calc.unit);

  if (Array.isArray(calc.values)) {
    for (const value of calc.values) {
      const unit = value.unit ?? calc.unit ?? '';
      push(`FY${value.fiscal_year}`, `${formatNumber(value.value)} ${unit}`.trim());
      push('Period', formatPeriod(value.period_start, value.period_end));
      rows.push(...sourceRows(value));
      if (value.is_ambiguous) {
        push('Ambiguity', 'Flagged: restated or conflicting disclosures');
      }
    }
  }

  if (calc.tool === 'compare_periods') {
    const unit = calc.unit ?? '';
    push(
      `FY${calc.year_a} → FY${calc.year_b}`,
      `${formatNumber(calc.value_a)} → ${formatNumber(calc.value_b)} ${unit}`.trim(),
    );
    push('Change', `${formatNumber(calc.change_absolute)} (${formatPercent(calc.change_percent)})`);
    rows.push(...sourceRows(calc.source_a));
    rows.push(...sourceRows(calc.source_b));
  }

  for (const note of calc.notes ?? []) push('Note', note);
  return rows;
}

export function citationRows(citation = {}) {
  const rows = [{ label: 'Kind', value: formatValue(citation.kind) }];
  if (citation.label) rows.push({ label: 'Label', value: String(citation.label) });
  if (citation.section) rows.push({ label: 'Section', value: String(citation.section) });
  if (citation.accession) rows.push({ label: 'Accession', value: String(citation.accession) });
  return rows;
}

export function passageRows(passage = {}) {
  const rows = [];
  const push = (label, value) => rows.push({ label, value: formatValue(value) });
  push('Filing', passage.accession);
  push('Section', passage.section);
  if (passage.cik !== null && passage.cik !== undefined) push('CIK', passage.cik);
  if (passage.similarity !== null && passage.similarity !== undefined) {
    push('Similarity', passage.similarity);
  }
  if (passage.passage_id) push('Passage id', passage.passage_id);
  return rows;
}

// How the prompt was understood: the interpreted company/metric/years/tool.
export function requestRows(request) {
  if (!request) return [];
  const years = Array.isArray(request.fiscal_years) ? request.fiscal_years : [];
  const rows = [
    { label: 'Company', value: formatValue(request.company) },
    { label: 'Metric', value: formatValue(request.metric) },
    { label: 'Fiscal years', value: years.length ? years.join(', ') : UNAVAILABLE },
  ];
  if (request.tool) rows.push({ label: 'Tool', value: String(request.tool) });
  return rows;
}

// A neutral explanation for a missing generated answer. It never asserts why the
// model produced no text; the API's own `limitations` carry the actual reason.
export function noAnswerMessage(response = {}) {
  if (response.status === 'needs_clarification') {
    return 'No answer was generated because the request still needs clarification.';
  }
  if (response.status === 'error') {
    return 'No answer was generated because the question could not be interpreted.';
  }
  return 'No generated answer was returned. The evidence below is what the API provided.';
}

// What to render for the answer: the generated text when it exists, otherwise a
// neutral message plus the API's own limitation. `abstained` is a flag only —
// the display must not turn it into a claim about evidence sufficiency, because
// the API also sets it for composition failures.
export function answerDisplay(response = {}) {
  const answer = response.answer || null;
  const text = answer && typeof answer.text === 'string' ? answer.text : '';
  const citations = answer && Array.isArray(answer.citations) ? answer.citations : [];
  return {
    hasText: text.trim().length > 0,
    text,
    citations,
    abstained: Boolean(answer && answer.abstained),
    limitations: answer && answer.limitations ? String(answer.limitations) : null,
    message: noAnswerMessage(response),
  };
}
