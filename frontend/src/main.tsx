/* @refresh reload */
import { Navigate, Route, Router } from '@solidjs/router';
import { render } from 'solid-js/web';
import { AppShell } from './app/AppShell';
import { ROUTES } from './app/routes';
import { ThemeProvider } from './app/ThemeProvider';
import './index.css';
import { PerfBanner } from './components/PerfBanner';
import { StubRoute } from './routes/Stub';

// Dev-only: log fetch timing to surface slow API calls during nav.
if (import.meta.env.DEV) {
  const orig = window.fetch.bind(window);
  window.fetch = async (...a: Parameters<typeof fetch>) => {
    const t = performance.now();
    const r = await orig(...a);
    const dt = performance.now() - t;
    const url = typeof a[0] === 'string' ? a[0] : (a[0] as Request | URL).toString();
    // eslint-disable-next-line no-console
    console.log(`[fetch ${dt.toFixed(0)}ms]`, url);
    return r;
  };
}
import OverviewRoute from './routes/Overview';
import DreamsRoute from './routes/Dreams';
import RunsRoute from './routes/Runs';
import {
  MemoriesSurface,
  MemoriesExplorer,
  MemoriesChanges,
} from './routes/Memories';
import GraphRoute from './routes/Graph';
import EvalsRoute from './routes/Evals';
import ExportsRoute from './routes/Exports';
import SettingsRoute from './routes/Settings';
import WorkspacesRoute from './routes/Workspaces';
import RetrievalsRoute from './routes/Retrievals';
import SessionsRoute from './routes/Sessions';
import ContextRoute from './routes/Context';
import ReviewsRoute from './routes/Reviews';

const IMPLEMENTED = new Set<string>([
  '/overview', '/runs', '/memories', '/dreams',
  '/graph', '/evals', '/exports', '/settings', '/workspaces',
  '/retrievals', '/sessions', '/context', '/reviews',
]);

const root = document.getElementById('root');
if (!root) throw new Error('Missing #root element');

render(
  () => (
    <ThemeProvider>
      <Router root={(p) => <AppShell><PerfBanner />{p.children}</AppShell>}>
        <Route path="/" component={() => <Navigate href="/overview" />} />
        <Route path="/overview" component={OverviewRoute} />
        <Route path="/runs" component={RunsRoute} />
        <Route path="/memories" component={MemoriesSurface} />
        <Route path="/memories/explorer" component={MemoriesExplorer} />
        <Route path="/memories/changes" component={MemoriesChanges} />
        <Route path="/dreams" component={DreamsRoute} />
        <Route path="/graph" component={GraphRoute} />
        <Route path="/evals" component={EvalsRoute} />
        <Route path="/exports" component={ExportsRoute} />
        <Route path="/settings" component={SettingsRoute} />
        <Route path="/workspaces" component={WorkspacesRoute} />
        <Route path="/retrievals" component={RetrievalsRoute} />
        <Route path="/sessions" component={SessionsRoute} />
        <Route path="/context" component={ContextRoute} />
        <Route path="/reviews" component={ReviewsRoute} />
        {ROUTES.filter((r) => !IMPLEMENTED.has(r.path)).map((route) => (
          <Route path={route.path} component={() => <StubRoute name={route.name} />} />
        ))}
        <Route path="*" component={() => <StubRoute name="Not Found" />} />
      </Router>
    </ThemeProvider>
  ),
  root,
);
