// DOM rendering for the /ask response (release v0.2, task T013).
//
// The builders take an explicit `document`, so the page wires them to the real
// DOM while `node --test` exercises the exact rendered output with a minimal
// stub. Every piece of untrusted text is written with `textContent` and only
// `http(s)` URLs become links, so answer/passage content cannot execute HTML.
import {
  answerDisplay,
  calculationRows,
  citationAnchor,
  citationRows,
  formatValue,
  metadataRows,
  passageRows,
  requestRows,
  safeUrl,
  splitAnswer,
  statusLabel,
} from './display.js';

const ABSTENTION_NOTICE = 'The assistant abstained.';

export function createRenderers(document) {
  function node(tag, text, attrs) {
    const element = document.createElement(tag);
    if (text !== undefined && text !== null) element.textContent = text;
    for (const [name, value] of Object.entries(attrs ?? {})) {
      if (value === null || value === undefined || value === false) continue;
      element.setAttribute(name, value === true ? '' : String(value));
    }
    return element;
  }

  function definitionList(rows) {
    const dl = document.createElement('dl');
    for (const { label, value } of rows) dl.append(node('dt', label), node('dd', value));
    return dl;
  }

  function externalLink(label, url) {
    const safe = safeUrl(url);
    if (!safe) return null;
    return node('a', label, { href: safe, target: '_blank', rel: 'noopener noreferrer' });
  }

  function details(summary) {
    const box = node('details');
    box.append(node('summary', summary));
    return box;
  }

  function titledSection(className, title, ...children) {
    const section = node('section', undefined, {
      class: className,
      'aria-labelledby': `${className}-heading`,
    });
    section.append(node('h3', title, { id: `${className}-heading` }), ...children);
    return section;
  }

  function renderAnswer(display) {
    const section = node('section', undefined, {
      class: 'answer',
      'aria-labelledby': 'answer-heading',
    });
    section.append(node('h3', 'Answer', { id: 'answer-heading' }));

    const textEl = node('p', undefined, { class: 'answer-text' });
    for (const segment of splitAnswer(display.text, display.citations)) {
      if (segment.kind === 'citation') {
        const citation = display.citations[segment.index];
        const label = `Source ${segment.index + 1}: ${citation.label || citation.id}`;
        textEl.append(node('a', `[${segment.index + 1}]`, {
          href: `#${citationAnchor(segment.index)}`,
          class: 'citation-ref',
          'aria-label': label,
          title: label,
        }));
      } else {
        textEl.append(document.createTextNode(segment.value));
      }
    }
    section.append(textEl);

    if (display.limitations) {
      section.append(node('h4', 'Limitations'));
      section.append(node('p', display.limitations, { class: 'caveat' }));
    }
    return section;
  }

  function renderCitations(citations) {
    const list = node('ol', undefined, { class: 'citation-list' });
    citations.forEach((citation, index) => {
      const item = node('li', undefined, { id: citationAnchor(index), class: 'citation', tabindex: '-1' });
      item.append(node('p', citation.label || citation.id, { class: 'citation-title' }));
      item.append(definitionList(citationRows(citation)));
      // The URL is both shown and clickable; `externalLink` drops unsafe schemes.
      const link = externalLink(citation.url, citation.url);
      if (link) item.append(link);
      list.append(item);
    });
    return titledSection('citations', `Citations (${citations.length})`, list);
  }

  function renderCalculations(calculations) {
    if (calculations.length === 0) {
      return titledSection(
        'calculations', 'Calculations (0)', node('p', 'No calculations were returned.'),
      );
    }
    const blocks = calculations.map((calc) => {
      const article = node('article');
      article.append(node('h4', `${formatValue(calc.metric)} — ${formatValue(calc.tool)}`));
      article.append(definitionList(calculationRows(calc)));
      return article;
    });
    return titledSection('calculations', `Calculations (${calculations.length})`, ...blocks);
  }

  function renderPassages(passages) {
    if (passages.length === 0) {
      return titledSection(
        'passages', 'Supporting passages (0)', node('p', 'No passages were returned.'),
      );
    }
    const blocks = passages.map((passage, index) => {
      const box = details(passage.heading || `Passage ${index + 1}`);
      box.append(definitionList(passageRows(passage)));
      box.append(node('blockquote', passage.text || '(no passage text was returned)', {
        class: 'passage-text',
      }));
      const link = externalLink('Open filing', passage.url);
      if (link) box.append(link);
      return box;
    });
    return titledSection('passages', `Supporting passages (${passages.length})`, ...blocks);
  }

  function renderDetails(response) {
    const section = node('section', undefined, {
      class: 'response-details',
      'aria-labelledby': 'response-details-heading',
    });
    section.append(node('h3', 'Response details', { id: 'response-details-heading' }));

    const interpretation = details('How the question was interpreted');
    interpretation.append(definitionList(requestRows(response.request)));
    if (response.request) {
      interpretation.append(node('h4', 'Validated request'));
      interpretation.append(node('pre', JSON.stringify(response.request, null, 2)));
    } else {
      interpretation.append(node('p', 'The prompt was not resolved to a request.'));
    }
    section.append(interpretation);

    if (response.answer) {
      const metadata = details('Model and usage metadata');
      metadata.append(definitionList(metadataRows(response.answer)));
      section.append(metadata);
    }

    const raw = details('Complete response (JSON)');
    raw.append(node('pre', JSON.stringify(response, null, 2)));
    section.append(raw);
    return section;
  }

  function renderStatus(element, response) {
    element.textContent = `Status: ${statusLabel(response.status)}`;
    element.dataset.status = response.status ?? '';
  }

  function renderResponse(container, response) {
    if (!response) {
      container.replaceChildren();
      return;
    }
    const display = answerDisplay(response);
    const body = [];
    if (display.hasText) {
      body.push(renderAnswer(display));
    } else {
      // No generated answer text: explain the state neutrally; the reason the
      // API gives (if any) follows with the evidence still inspectable.
      body.push(node('p', display.message, { class: 'no-answer' }));
    }
    // The abstention flag is shown once, in either branch, and never behind a
    // disclosure (F059). It is a flag only: the API also sets it for composition
    // failures, so no reason is asserted here (F057).
    if (display.abstained) {
      body.push(node('p', ABSTENTION_NOTICE, { class: 'caveat' }));
    }
    if (!display.hasText && display.limitations) {
      body.push(node('p', display.limitations, { class: 'caveat' }));
    }
    body.push(renderCitations(display.citations));
    body.push(renderCalculations(response.calculations ?? []));
    body.push(renderPassages(response.passages ?? []));
    body.push(renderDetails(response));
    container.replaceChildren(...body);
  }

  return { renderResponse, renderStatus };
}
