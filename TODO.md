# Roadmap

The backend is implemented and evaluated. The following work is planned; it is
not part of the current API. This is the public summary of the local work plan.

1. **Validate interpreted requests.** Reuse `QuestionRequest`, the three existing
   metrics, and the approved tools. Ask for clarification when a company, metric,
   or year is missing, unsupported, or ambiguous.
2. **Interpret natural-language questions on the server.** Reuse the LLM client
   to extract metrics and years. Explicit user selections take precedence;
   validate every result before querying. The model never generates SQL.
3. **Connect interpretation to the API.** Add `POST /ask` for natural-language
   questions; interpret and validate on the server, then submit to the structured
   `POST /answer` endpoint. Preserve the complete evidence package and handle
   clarification and provider errors.
4. **Build the Astro question form.** Add company and optional metric selectors,
   a prompt field, loading/error states, and a correction flow.
5. **Display answers and evidence.** Show citations, calculations, passages,
   abstentions, and limitations. Include interpreted inputs, usage, latency,
   estimated cost, and an expandable response view.
6. **Verify the complete journey.** Test comparisons, qualitative questions,
   typos, conflicting selections, invalid model output, and provider failures.
   Keep credentials server-side; verify safe text rendering and keyboard access.

The evaluation also leaves room to improve passage ranking and answer latency.
The current measured limitations remain visible in the [evaluation report](docs/evaluation-report.md).
