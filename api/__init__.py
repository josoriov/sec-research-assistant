"""FastAPI question API over published gold datasets (task T005).

`POST /answer` validates a company/metric/period request, asks for
clarification when it cannot resolve them, and otherwise routes to a small,
fixed tool set: read one metric, compare two periods, and search eligible
passages. `POST /ask` adds a natural-language entry point that interprets and
validates the prompt, then submits it to the same handler. The API connects with
the read-only gold role and never reads silver or bronze.
"""
