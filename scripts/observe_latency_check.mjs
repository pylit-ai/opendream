#!/usr/bin/env node

const baseUrl = (process.env.OPENDREAM_OBSERVE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const routeBudgetMs = Number(process.env.OPENDREAM_ROUTE_BUDGET_MS || '5000');
const apiBudgetMs = Number(process.env.OPENDREAM_API_BUDGET_MS || '2000');
const routes = (process.env.OPENDREAM_OBSERVE_ROUTES || '/context,/memories/explorer,/memories/changes')
  .split(',')
  .map((route) => route.trim())
  .filter(Boolean);

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch (error) {
  console.error(
    JSON.stringify({
      ok: false,
      error: 'playwright_missing',
      detail: 'Install Playwright in the invoking environment, then rerun this script.',
      message: error instanceof Error ? error.message : String(error),
    }),
  );
  process.exit(2);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const apiRequests = [];

page.on('requestfinished', (request) => {
  const url = request.url();
  if (!url.startsWith(`${baseUrl}/api/`)) return;
  const timing = request.timing();
  const responseEnd = timing.responseEnd >= 0 ? timing.responseEnd : timing.responseStart;
  const durationMs = Math.max(0, Math.round(responseEnd - timing.startTime));
  apiRequests.push({
    method: request.method(),
    path: new URL(url).pathname,
    search: new URL(url).search,
    duration_ms: durationMs,
  });
});

const routeTimings = [];
for (const route of routes) {
  const started = performance.now();
  await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle', timeout: 120_000 });
  routeTimings.push({ route, duration_ms: Math.round(performance.now() - started) });
}

if (routes.includes('/memories/explorer')) {
  await page.goto(`${baseUrl}/memories/explorer`, { waitUntil: 'networkidle', timeout: 120_000 });
  const firstMemoryRow = page.locator('tbody tr[role="button"]').first();
  if (await firstMemoryRow.count()) {
    const started = performance.now();
    await firstMemoryRow.click();
    await page.waitForLoadState('networkidle', { timeout: 120_000 });
    routeTimings.push({ route: '/memories/explorer:first-memory-detail', duration_ms: Math.round(performance.now() - started) });
  }
}

await browser.close();

const slowRoutes = routeTimings.filter((row) => row.duration_ms > routeBudgetMs);
const slowApi = apiRequests.filter((row) => row.duration_ms > apiBudgetMs);
const payload = {
  ok: slowRoutes.length === 0 && slowApi.length === 0,
  base_url: baseUrl,
  budgets: {
    route_ms: routeBudgetMs,
    api_ms: apiBudgetMs,
  },
  route_timings: routeTimings,
  slow_routes: slowRoutes,
  api_request_count: apiRequests.length,
  slow_api_requests: slowApi,
  api_requests: apiRequests,
};

console.log(JSON.stringify(payload, null, 2));
if (!payload.ok) process.exit(1);
