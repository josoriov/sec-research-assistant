// Astro runs as a Node server (SSR) so the browser only talks to this app:
// the server route in src/pages/api/ask.ts proxies to the Python API, keeping
// the API host private and avoiding CORS. `HOST`/`PORT` are read from the
// environment by the standalone adapter (Compose sets them).
import { defineConfig } from 'astro/config';
import node from '@astrojs/node';

export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),
});
