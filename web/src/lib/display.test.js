// Task T013: the pure response-display logic, tested without a browser.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  UNAVAILABLE,
  answerDisplay,
  calculationRows,
  citationAnchor,
  citationRows,
  formatNumber,
  formatPercent,
  formatPeriod,
  formatValue,
  metadataRows,
  noAnswerMessage,
  passageRows,
  requestRows,
  safeUrl,
  splitAnswer,
  statusLabel,
} from './display.js';

function row(rows, label) {
  return rows.find((entry) => entry.label === label);
}

test('formatValue labels omitted fields but keeps a real zero', () => {
  assert.equal(formatValue(null), UNAVAILABLE);
  assert.equal(formatValue(undefined), UNAVAILABLE);
  assert.equal(formatValue(''), UNAVAILABLE);
  assert.equal(formatValue(0), '0');
  assert.equal(formatValue('10-K'), '10-K');
});

test('formatNumber and formatPercent keep zero and label omissions', () => {
  assert.equal(formatNumber(0), '0');
  assert.equal(formatNumber(null), UNAVAILABLE);
  assert.equal(formatPercent(0), '0%');
  assert.equal(formatPercent(undefined), UNAVAILABLE);
});

// F055: `change_percent` is a ratio ((b - a) / a), so it must be scaled to a
// percentage; the previous formatter appended '%' to the raw ratio.
test('formatPercent scales the API ratio to a percentage', () => {
  assert.equal(formatPercent(0.5), '50%');
  assert.equal(formatPercent(-0.25), '-25%');
  assert.equal(formatPercent(1.02), '102%');
  assert.equal(formatPercent(0), '0%');
  assert.equal(formatPercent(0.1778868679984666), '17.78868679984666%');
  assert.equal(formatPercent(null), UNAVAILABLE);
});

test('formatPeriod joins the two dates and labels a fully missing period', () => {
  assert.equal(formatPeriod('2023-01-01', '2023-12-31'), '2023-01-01 → 2023-12-31');
  assert.equal(formatPeriod(null, '2023-12-31'), '2023-12-31');
  assert.equal(formatPeriod(null, null), UNAVAILABLE);
});

// Untrusted URLs must never become a javascript:/data: href.
test('safeUrl accepts only http(s) and rejects hostile or malformed values', () => {
  assert.equal(safeUrl('https://www.sec.gov/Archives/x'), 'https://www.sec.gov/Archives/x');
  assert.equal(safeUrl('http://localhost:8000/x'), 'http://localhost:8000/x');
  assert.equal(safeUrl('javascript:alert(1)'), null);
  assert.equal(safeUrl('data:text/html,<script>'), null);
  assert.equal(safeUrl('not a url'), null);
  assert.equal(safeUrl(''), null);
  assert.equal(safeUrl(null), null);
});

test('metadataRows labels missing metadata as unavailable, not zero', () => {
  const rows = metadataRows({ model: null, latency_ms: 0, cost_usd: 0, usage: {} });
  assert.equal(row(rows, 'Model').value, UNAVAILABLE);
  assert.equal(row(rows, 'Prompt tokens').value, UNAVAILABLE);
  assert.equal(row(rows, 'Latency').value, '0 ms');
  assert.equal(row(rows, 'Cost (USD)').value, '$0');
});

test('statusLabel maps each API status to a human label', () => {
  assert.equal(statusLabel('ok'), 'Answer ready');
  assert.equal(statusLabel('needs_clarification'), 'More information needed');
  assert.equal(statusLabel('error'), 'Request failed');
  assert.equal(statusLabel('nonsense'), 'Unknown status');
});

const CITATIONS = [{ id: 'passage:p1' }, { id: 'metric:m1' }];

test('splitAnswer links bare and bracketed citation references to their source', () => {
  assert.deepEqual(splitAnswer('Growth came from [metric:m1] and passage:p1.', CITATIONS), [
    { kind: 'text', value: 'Growth came from ' },
    { kind: 'citation', id: 'metric:m1', index: 1 },
    { kind: 'text', value: ' and ' },
    { kind: 'citation', id: 'passage:p1', index: 0 },
    { kind: 'text', value: '.' },
  ]);
  assert.equal(citationAnchor(1), 'citation-1');
});

test('splitAnswer leaves unknown ids and citation-free text as plain text', () => {
  assert.deepEqual(splitAnswer('No ids here [metric:zzz].', CITATIONS), [
    { kind: 'text', value: 'No ids here [metric:zzz].' },
  ]);
  assert.deepEqual(splitAnswer('plain', []), [{ kind: 'text', value: 'plain' }]);
  assert.deepEqual(splitAnswer(null, CITATIONS), [{ kind: 'text', value: '' }]);
});

// F058: an accepted id must not match the prefix of a longer, unknown id.
test('splitAnswer does not link an accepted id that prefixes an unknown one', () => {
  const accepted = [{ id: 'passage:4734' }];
  assert.deepEqual(splitAnswer('Known [passage:4734]. Unknown [passage:47340].', accepted), [
    { kind: 'text', value: 'Known ' },
    { kind: 'citation', id: 'passage:4734', index: 0 },
    { kind: 'text', value: '. Unknown [passage:47340].' },
  ]);
  // Bare forms behave the same, and punctuation after a known id still links.
  assert.deepEqual(splitAnswer('see passage:47340 now', accepted), [
    { kind: 'text', value: 'see passage:47340 now' },
  ]);
  assert.deepEqual(splitAnswer('xpassage:4734', accepted), [{ kind: 'text', value: 'xpassage:4734' }]);
  assert.deepEqual(splitAnswer('passage:4734, done', accepted), [
    { kind: 'citation', id: 'passage:4734', index: 0 },
    { kind: 'text', value: ', done' },
  ]);
});

test('splitAnswer picks the longest accepted id when ids overlap', () => {
  const accepted = [{ id: 'passage:47' }, { id: 'passage:4734' }];
  assert.deepEqual(splitAnswer('[passage:4734]', accepted), [
    { kind: 'citation', id: 'passage:4734', index: 1 },
  ]);
});

const COMPARE = {
  tool: 'compare_periods',
  cik: 320193,
  metric: 'revenue',
  unit: 'USD',
  year_a: 2023,
  year_b: 2024,
  value_a: 100,
  value_b: 150,
  source_a: { period_start: '2023-01-01', period_end: '2023-12-31', accession: '0000320193-23-000106' },
  source_b: { period_start: '2024-01-01', period_end: '2024-12-31', accession: '0000320193-24-000123' },
  change_absolute: 50,
  change_percent: 0.5,
  notes: ['base value is zero; percent change is undefined'],
};

test('calculationRows renders a comparison, its sources, and its notes', () => {
  const rows = calculationRows(COMPARE);
  assert.equal(row(rows, 'Metric').value, 'revenue');
  assert.equal(row(rows, 'Unit').value, 'USD');
  assert.equal(row(rows, 'FY2023 → FY2024').value, '100 → 150 USD');
  assert.equal(row(rows, 'Change').value, '50 (50%)');
  assert.equal(row(rows, 'Source filing').value, '0000320193-23-000106');
  assert.equal(row(rows, 'Note').value, 'base value is zero; percent change is undefined');
});

test('calculationRows keeps a zero change and labels a missing percent', () => {
  const zero = calculationRows({ ...COMPARE, change_absolute: 0, change_percent: 0 });
  assert.equal(row(zero, 'Change').value, '0 (0%)');
  const negative = calculationRows({ ...COMPARE, change_absolute: -25, change_percent: -0.25 });
  assert.equal(row(negative, 'Change').value, '-25 (-25%)');
  const missing = calculationRows({ ...COMPARE, change_absolute: null, change_percent: null });
  assert.equal(row(missing, 'Change').value, `${UNAVAILABLE} (${UNAVAILABLE})`);
});

test('calculationRows renders metric values with period and ambiguity flag', () => {
  const rows = calculationRows({
    tool: 'get_metric',
    metric: 'net_income',
    unit: 'USD',
    values: [
      { fiscal_year: 2023, value: 96995000000, period_start: '2022-09-25', period_end: '2023-09-30', is_ambiguous: false, accession: 'a', form: '10-K', filed_date: '2023-11-03' },
      { fiscal_year: 2024, value: 0, period_start: '2023-10-01', period_end: '2024-09-28', is_ambiguous: true, accession: 'b', form: '10-K', filed_date: '2024-11-01' },
    ],
    notes: [],
  });
  assert.equal(row(rows, 'FY2024').value, '0 USD');
  assert.equal(row(rows, 'Ambiguity').value, 'Flagged: restated or conflicting disclosures');
  assert.equal(row(rows, 'Source form').value, '10-K');
});

test('citationRows and passageRows expose the returned metadata', () => {
  const citation = citationRows({ id: 'passage:p1', kind: 'passage', label: 'Revenues', section: 'MD&A', accession: 'acc', url: 'https://x' });
  assert.equal(row(citation, 'Kind').value, 'passage');
  assert.equal(row(citation, 'Section').value, 'MD&A');
  assert.equal(row(citation, 'Accession').value, 'acc');

  const passage = passageRows({ passage_id: 'p1', cik: 320193, accession: 'acc', section: 'MD&A', similarity: 0.8 });
  assert.equal(row(passage, 'Filing').value, 'acc');
  assert.equal(row(passage, 'Similarity').value, '0.8');
  assert.equal(row(passage, 'Passage id').value, 'p1');
});

test('requestRows shows the interpreted selections and labels missing ones', () => {
  const rows = requestRows({ company: 'AAPL', metric: 'revenue', fiscal_years: [2023, 2024] });
  assert.equal(row(rows, 'Company').value, 'AAPL');
  assert.equal(row(rows, 'Fiscal years').value, '2023, 2024');
  assert.equal(row(requestRows({ company: 'AAPL', metric: null, fiscal_years: [] }), 'Metric').value, UNAVAILABLE);
  assert.deepEqual(requestRows(null), []);
});

test('answerDisplay shows the text when present and preserves limitations', () => {
  const ok = answerDisplay({ answer: { text: 'Revenue rose.', citations: [{ id: 'x' }] } });
  assert.equal(ok.hasText, true);
  assert.equal(ok.text, 'Revenue rose.');
  assert.deepEqual(ok.citations, [{ id: 'x' }]);
  assert.equal(ok.abstained, false);
  assert.equal(ok.limitations, null);

  const abstained = answerDisplay({
    answer: { text: 'I cannot support this.', abstained: true, limitations: 'Conflicting figures.' },
  });
  assert.equal(abstained.hasText, true);
  assert.equal(abstained.abstained, true);
  assert.equal(abstained.limitations, 'Conflicting figures.');
});

// F057: `abstained=true` is also set for composition provider/malformed-reply
// failures, so the empty-answer display must stay neutral and carry the API's
// own limitation instead of asserting a reason about the evidence.
test('answerDisplay explains an empty answer neutrally and keeps the real limitation', () => {
  for (const limitation of [
    'Answer composition failed: model request timed out',
    'The model reply was not valid JSON.',
  ]) {
    const display = answerDisplay({
      status: 'ok',
      answer: { text: '', abstained: true, limitations: limitation },
      calculations: [{ tool: 'get_metric' }],
    });
    assert.equal(display.hasText, false);
    assert.equal(display.limitations, limitation);
    assert.equal(display.message, noAnswerMessage({ status: 'ok' }));
    assert.equal(display.message, 'No generated answer was returned. The evidence below is what the API provided.');
    assert.doesNotMatch(display.message, /could not support|because the evidence|not enough evidence/i);
  }
});

test('noAnswerMessage distinguishes clarification, error, and an evidence-only reply', () => {
  assert.match(noAnswerMessage({ status: 'needs_clarification' }), /clarification/);
  assert.match(noAnswerMessage({ status: 'error' }), /could not be interpreted/);
  assert.match(noAnswerMessage({ status: 'ok' }), /No generated answer was returned/);
  assert.match(noAnswerMessage({ status: 'ok', answer: null }), /No generated answer was returned/);
});
