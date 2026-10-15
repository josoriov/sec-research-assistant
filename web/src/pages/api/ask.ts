// Server-side proxy from the browser to the Python POST /ask endpoint (T012).
//
// The browser only ever talks to this Astro server (same origin), so the API
// host stays private, no CORS is needed, and no credential crosses to the
// browser. The upstream error body is passed through unchanged so the UI can
// distinguish needs_clarification from error.
import type { APIRoute } from 'astro';

const API_BASE_URL = (process.env.API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, '');

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}

export const POST: APIRoute = async ({ request }) => {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return json({ status: 'error', error: 'The request body was not valid JSON.' }, 400);
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/ask`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    return json({ status: 'error', error: 'The answer service is unreachable.' }, 502);
  }

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
};
