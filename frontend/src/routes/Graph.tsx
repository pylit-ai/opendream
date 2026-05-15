import {
  createResource,
  createSignal,
  onCleanup,
  onMount,
  Show,
  For,
  type JSX,
} from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { GitBranch } from 'lucide-solid';
import GraphologyGraph from 'graphology';
import Sigma from 'sigma';
import { getGraph, getRuns, getOverview } from '~/api/client';
import type { GraphPayload, GraphParams, OverviewPayload, RunListResponse } from '~/api/types';
import { Chip } from '~/components/Chip';
import { EmptyState } from '~/components/EmptyState';
import { LoadingPage } from '~/components/Loading';
import { ErrorState } from '~/components/ErrorState';
import { SlideOver } from '~/components/SlideOver';
import { MemoryInspector } from '~/components/MemoryInspector';
import { IdLink } from '~/components/IdLink';
import { cachedFetch } from '~/lib/cache';

type LayoutMode = 'hierarchical' | 'force';
type NodeType = 'memory' | 'review' | 'run' | 'retrieval';

const NODE_TYPE_COLORS: Record<NodeType | string, string> = {
  memory: '#6366f1',
  review: '#f59e0b',
  run: '#10b981',
  retrieval: '#3b82f6',
};

const EDGE_KINDS = [
  'supersedes',
  'conflicts_with',
  'supports',
  'derived_from',
  'verified_by',
  'invalidated_by',
] as const;

const NODE_TYPES: NodeType[] = ['memory', 'review', 'run', 'retrieval'];
const DEPTH_OPTIONS = [0, 1, 2, 3];
const LIMIT_OPTIONS = [24, 100, 500, 1000];

function bfsHierarchicalLayout(
  nodes: NonNullable<GraphPayload['nodes']>,
  edges: NonNullable<GraphPayload['edges']>,
  focusId?: string | null,
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  if (nodes.length === 0) return positions;

  const adj = new Map<string, string[]>();
  for (const n of nodes) adj.set(n.id, []);
  for (const e of edges) {
    adj.get(e.source)?.push(e.target);
    adj.get(e.target)?.push(e.source);
  }

  const root = focusId ?? nodes[0]!.id;
  const visited = new Set<string>([root]);
  const levels: string[][] = [[root]];
  let queue = [root];

  while (queue.length > 0) {
    const next: string[] = [];
    for (const id of queue) {
      for (const nb of adj.get(id) ?? []) {
        if (!visited.has(nb)) {
          visited.add(nb);
          next.push(nb);
        }
      }
    }
    if (next.length > 0) levels.push(next);
    queue = next;
  }

  // Place unvisited nodes at last level
  const unvisited = nodes.filter((n) => !visited.has(n.id));
  if (unvisited.length > 0) levels.push(unvisited.map((n) => n.id));

  for (let depth = 0; depth < levels.length; depth++) {
    const level = levels[depth] ?? [];
    const count = level.length;
    for (let i = 0; i < count; i++) {
      const nodeId = level[i];
      if (nodeId !== undefined) {
        positions.set(nodeId, {
          x: depth * 200,
          y: i * 80 - ((count - 1) * 80) / 2,
        });
      }
    }
  }

  return positions;
}

function GraphCanvas(props: {
  payload: GraphPayload;
  layout: LayoutMode;
  nodeTypes: Set<NodeType>;
  edgeKinds: Set<string>;
  onNodeClick?: (nodeId: string, nodeType: string) => void;
  onCounts?: (counts: { nodes: number; edges: number; total: number }) => void;
}): JSX.Element {
  let container!: HTMLDivElement;
  let sigmaInstance: Sigma | null = null;

  onMount(async () => {
    const raw = props.payload;
    const allNodes = raw.nodes ?? [];
    const allEdges = raw.edges ?? [];

    const activeTypes = props.nodeTypes;
    const nodes = activeTypes.size === 0
      ? allNodes
      : allNodes.filter((n) => {
          const t = String(n.type ?? n.node_type ?? '');
          return activeTypes.has(t as NodeType);
        });

    const nodeIds = new Set(nodes.map((n) => n.id));
    const activeEdgeKinds = props.edgeKinds;
    const edges = allEdges.filter((e) => {
      if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) return false;
      if (activeEdgeKinds.size === 0) return true;
      const k = String(e.label ?? (e as { kind?: string }).kind ?? '');
      return activeEdgeKinds.has(k);
    });
    props.onCounts?.({ nodes: nodes.length, edges: edges.length, total: allNodes.length });

    const graph = new GraphologyGraph({ multi: false, type: 'directed' });

    // Determine positions
    let positions: Map<string, { x: number; y: number }>;
    if (props.layout === 'force') {
      // Use existing positions if available, else random spread
      positions = new Map(
        nodes.map((n) => [
          n.id,
          {
            x: typeof n.x === 'number' ? n.x : Math.random() * 800 - 400,
            y: typeof n.y === 'number' ? n.y : Math.random() * 600 - 300,
          },
        ]),
      );
    } else {
      positions = bfsHierarchicalLayout(nodes, edges, raw.focus);
    }

    for (const n of nodes) {
      const pos = positions.get(n.id) ?? { x: 0, y: 0 };
      const nodeType = String(n.type ?? n.node_type ?? '');
      graph.addNode(n.id, {
        label: n.label ?? n.id,
        x: pos.x,
        y: pos.y,
        size: 8,
        color: NODE_TYPE_COLORS[nodeType] ?? '#94a3b8',
      });
    }

    for (const e of edges) {
      try {
        graph.addEdge(e.source, e.target, {
          label: e.label ?? '',
          size: 0.7,
          color: 'rgba(140,148,164,0.28)',
        });
      } catch {
        // skip duplicate edges
      }
    }

    const cs = getComputedStyle(document.documentElement);
    const bgColor = cs.getPropertyValue('--color-bg').trim() || '#0a0b0d';
    container.style.background = bgColor;

    sigmaInstance = new Sigma(graph, container, {
      labelSize: 11,
      labelColor: { color: '#7e8693' },
      labelDensity: 0.7,
      labelGridCellSize: 80,
      labelRenderedSizeThreshold: 6,
      defaultNodeColor: '#7682ee',
      defaultEdgeColor: 'rgba(140,148,164,0.32)',
      renderEdgeLabels: false,
      minCameraRatio: 0.2,
      maxCameraRatio: 6,
    });

    // Hover and selection animation
    let hovered: string | null = null;
    sigmaInstance.on('enterNode', ({ node }) => {
      hovered = node;
      try {
        graph.setNodeAttribute(node, 'size', 11);
        sigmaInstance?.refresh();
      } catch {
        // ignore
      }
    });
    sigmaInstance.on('clickNode', ({ node }) => {
      const n = nodes.find((x) => x.id === node);
      const t = String(n?.type ?? n?.node_type ?? '');
      props.onNodeClick?.(node, t);
    });
    sigmaInstance.on('leaveNode', ({ node }) => {
      if (hovered === node) hovered = null;
      try {
        graph.setNodeAttribute(node, 'size', 8);
        sigmaInstance?.refresh();
      } catch {
        // ignore
      }
    });

    if (props.layout === 'force' && graph.order > 0) {
      // Dynamic import to avoid breaking if not installed
      try {
        const { default: forceAtlas2 } = await import('graphology-layout-forceatlas2');
        forceAtlas2.assign(graph, { iterations: 50 });
        sigmaInstance.refresh();
      } catch {
        // forceAtlas2 not available, use existing positions
      }
    }
  });

  onCleanup(() => {
    sigmaInstance?.kill();
    sigmaInstance = null;
  });

  return <div ref={container} class="h-full w-full" />;
}

export default function GraphRoute(): JSX.Element {
  const navigate = useNavigate();
  const [layout, setLayout] = createSignal<LayoutMode>('hierarchical');
  const [depth, setDepth] = createSignal(1);
  const [limit, setLimit] = createSignal(100);
  const [focus, setFocus] = createSignal('');
  const [activeTypes, setActiveTypes] = createSignal<Set<NodeType>>(new Set());
  const [activeEdgeKinds, setActiveEdgeKinds] = createSignal<Set<string>>(new Set());
  const [counts, setCounts] = createSignal({ nodes: 0, edges: 0, total: 0 });

  const [selectedNode, setSelectedNode] = createSignal<{ id: string; type: string } | null>(null);

  const params = (): GraphParams => ({
    depth: depth(),
    layout: layout(),
    focus: focus() || undefined,
    limit: limit(),
  });

  const [graph, { refetch }] = createResource<GraphPayload, GraphParams>(params, (p) =>
    cachedFetch(`graph:${JSON.stringify(p)}`, () => getGraph(p), 30_000),
  );

  const [recentRuns] = createResource<RunListResponse>(() =>
    cachedFetch('graph:recent-runs', () => getRuns({ limit: 12 } as never), 60_000),
  );
  const [overviewSnapshot] = createResource<OverviewPayload>(() =>
    cachedFetch('overview', getOverview, 30_000),
  );

  type FocusOption = { id: string; label: string; group: string };
  const focusOptions = (): FocusOption[] => {
    const out: FocusOption[] = [];
    const runs = recentRuns()?.items ?? [];
    const stringify = (v: unknown): string => {
      if (typeof v === 'string') return v;
      if (v == null) return '';
      try { return JSON.stringify(v); } catch { return ''; }
    };
    const compact = (v: unknown, fallback: string): string => {
      const text = stringify(v).replace(/\s+/g, ' ').trim();
      const label = text || fallback;
      return label.length > 48 ? `${label.slice(0, 45)}...` : label;
    };
    const withShortId = (label: string, id: string): string => `${label} · ${id.slice(0, 12)}`;
    for (const r of runs.slice(0, 8)) {
      const label = compact(r.summary ?? r.status, r.run_id);
      out.push({
        id: r.run_id,
        label: withShortId(label, r.run_id),
        group: 'Recent runs',
      });
    }
    const ov = overviewSnapshot() as
      | (OverviewPayload & {
          memory_surface?: { recent_highlights?: Array<{ memory_id?: string; title?: string }> };
          recent_sessions?: Array<{ session_id?: string; display_name?: string; event_count?: number }>;
        })
      | undefined;
    const highlights = ov?.memory_surface?.recent_highlights ?? [];
    for (const h of highlights.slice(0, 6)) {
      if (h.memory_id) {
        out.push({
          id: h.memory_id,
          label: withShortId(compact(h.title, h.memory_id), h.memory_id),
          group: 'Recent memories',
        });
      }
    }
    const sessions = ov?.recent_sessions ?? [];
    for (const s of sessions.slice(0, 6)) {
      if (s.session_id) {
        out.push({
          id: s.session_id,
          label: withShortId(
            compact(
              s.display_name ?? (
                typeof s.event_count === 'number'
                  ? `${s.event_count} event${s.event_count === 1 ? '' : 's'}`
                  : undefined
              ),
              s.session_id,
            ),
            s.session_id,
          ),
          group: 'Recent sessions',
        });
      }
    }
    return out;
  };

  function toggleEdgeKind(k: string) {
    setActiveEdgeKinds((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }

  function toggleType(t: NodeType) {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  }

  const nodes = () => graph()?.nodes ?? [];

  function SectionLabel(p: { children: JSX.Element }): JSX.Element {
    return (
      <div class="text-[10px] uppercase tracking-[0.1em] text-text-subtle">
        {p.children}
      </div>
    );
  }

  function SegButton(p: { active: boolean; onClick: () => void; children: JSX.Element }): JSX.Element {
    return (
      <button
        type="button"
        onClick={p.onClick}
        class={
          'flex-1 rounded px-3 py-1 text-xs transition-colors duration-150 ' +
          (p.active
            ? 'bg-surface-elevated text-text hairline'
            : 'text-text-muted hover:text-text')
        }
      >
        {p.children}
      </button>
    );
  }

  return (
    <div class="page-enter -mx-8 -mt-10 flex h-[calc(100vh-3.5rem)] gap-0 overflow-hidden">
      {/* Left rail */}
      <aside class="hairline-r flex w-[260px] shrink-0 flex-col gap-6 overflow-y-auto bg-surface px-5 py-6 scrollbar-thin">
        <SectionLabel>Layout</SectionLabel>
        <div class="-mt-4 inline-flex items-center gap-px rounded-md bg-bg p-0.5 hairline">
          <SegButton active={layout() === 'hierarchical'} onClick={() => setLayout('hierarchical')}>
            Hierarchical
          </SegButton>
          <SegButton active={layout() === 'force'} onClick={() => setLayout('force')}>
            Force
          </SegButton>
        </div>

        <SectionLabel>Depth</SectionLabel>
        <div class="-mt-4 inline-flex items-center gap-px rounded-md bg-bg p-0.5 hairline">
          <For each={DEPTH_OPTIONS}>
            {(d) => (
              <SegButton active={depth() === d} onClick={() => setDepth(d)}>
                {d}
              </SegButton>
            )}
          </For>
        </div>

        <SectionLabel>Limit</SectionLabel>
        <div class="-mt-4 inline-flex items-center gap-px rounded-md bg-bg p-0.5 hairline">
          <For each={LIMIT_OPTIONS}>
            {(n) => (
              <SegButton active={limit() === n} onClick={() => setLimit(n)}>
                {n}
              </SegButton>
            )}
          </For>
        </div>

        <div class="flex flex-col gap-2">
          <SectionLabel>Focus</SectionLabel>
          <select
            value={focus()}
            onChange={(e) => setFocus(e.currentTarget.value)}
            class="h-9 w-full rounded-md bg-bg px-2 text-xs text-text hairline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
          >
            <option value="">— Auto (no focus) —</option>
            <For each={Array.from(new Set(focusOptions().map((o) => o.group)))}>
              {(group) => (
                <optgroup label={group}>
                  <For each={focusOptions().filter((o) => o.group === group)}>
                    {(o) => <option value={o.id}>{o.label}</option>}
                  </For>
                </optgroup>
              )}
            </For>
          </select>
          <input
            type="text"
            placeholder="Or enter node ID…"
            value={focus()}
            onInput={(e) => setFocus(e.currentTarget.value)}
            class="h-8 w-full rounded-md bg-bg px-3 text-[11px] text-text placeholder:text-text-subtle hairline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
          />
          <Show when={focus()}>
            <button
              type="button"
              onClick={() => setFocus('')}
              class="self-start text-[11px] text-text-subtle hover:text-text"
            >
              clear focus
            </button>
          </Show>
        </div>

        <div class="flex flex-col gap-2">
          <SectionLabel>Node types</SectionLabel>
          <div class="flex flex-wrap gap-1.5">
            <For each={NODE_TYPES}>
              {(t) => (
                <button
                  type="button"
                  onClick={() => toggleType(t)}
                  aria-label={`${activeTypes().has(t) ? 'Hide' : 'Show'} ${t} nodes`}
                  aria-pressed={activeTypes().has(t)}
                  class="transition-opacity duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 rounded"
                  style={{ opacity: activeTypes().has(t) || activeTypes().size === 0 ? 1 : 0.45 }}
                >
                  <Chip variant={activeTypes().has(t) ? 'accent' : 'neutral'}>{t}</Chip>
                </button>
              )}
            </For>
          </div>
        </div>

        <div class="flex flex-col gap-2">
          <SectionLabel>Edge kinds</SectionLabel>
          <p class="text-[10px] text-text-subtle">Empty = show all</p>
          <div class="flex flex-wrap gap-1.5">
            <For each={EDGE_KINDS}>
              {(k) => (
                <button
                  type="button"
                  onClick={() => toggleEdgeKind(k)}
                  aria-label={`${activeEdgeKinds().has(k) ? 'Hide' : 'Show'} ${k.replace(/_/g, ' ')} edges`}
                  aria-pressed={activeEdgeKinds().has(k)}
                  class="transition-opacity duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 rounded"
                  style={{ opacity: activeEdgeKinds().has(k) || activeEdgeKinds().size === 0 ? 1 : 0.45 }}
                >
                  <Chip variant={activeEdgeKinds().has(k) ? 'accent' : 'neutral'}>
                    {k.replace(/_/g, ' ')}
                  </Chip>
                </button>
              )}
            </For>
          </div>
        </div>
      </aside>

      {/* Graph canvas area */}
      <div class="relative flex-1 overflow-hidden bg-bg">
        <Show when={graph.loading}>
          <div class="absolute inset-0 flex items-center justify-center">
            <LoadingPage
              label="Loading graph"
              detail="Building memory, run, retrieval, and context links."
            />
          </div>
        </Show>
        <Show when={graph.error}>
          <div class="absolute inset-0 flex items-center justify-center p-8">
            <ErrorState
              message={graph.error instanceof Error ? graph.error.message : String(graph.error)}
              onRetry={refetch}
            />
          </div>
        </Show>
        <Show when={!graph.loading && !graph.error}>
          <Show
            when={nodes().length > 0}
            fallback={
              <div class="absolute inset-0 flex items-center justify-center">
                <EmptyState
                  icon={GitBranch}
                  title="No graph data"
                  description={`No nodes for current filters. Try raising Limit (now ${limit()}), increasing Depth, or picking a Focus from the dropdown.`}
                />
              </div>
            }
          >
            <GraphCanvas
              payload={graph()!}
              layout={layout()}
              nodeTypes={activeTypes()}
              edgeKinds={activeEdgeKinds()}
              onNodeClick={(id, type) => setSelectedNode({ id, type })}
              onCounts={setCounts}
            />
            <div class="pointer-events-none absolute right-4 top-4 flex flex-col items-end gap-1.5">
              <div class="rounded-md bg-surface-elevated/85 px-3 py-1.5 text-[11px] text-text-muted hairline backdrop-blur">
                <span class="font-mono text-text">{counts().nodes}</span> nodes ·{' '}
                <span class="font-mono text-text">{counts().edges}</span> edges
                <Show when={counts().total > counts().nodes}>
                  <span class="text-text-subtle"> · of {counts().total} fetched</span>
                </Show>
              </div>
              <Show when={counts().nodes > 0 && counts().edges === 0}>
                <div class="rounded-md bg-surface-elevated/85 px-3 py-1.5 text-[11px] text-text-subtle hairline backdrop-blur max-w-[220px] text-right">
                  No edges visible. Try increasing Depth or selecting a Focus node to see relationships.
                </div>
              </Show>
            </div>
            <SlideOver
              open={selectedNode() !== null}
              onOpenChange={(o) => !o && setSelectedNode(null)}
              title="Graph node"
              description={selectedNode()?.id}
            >
              <Show when={selectedNode()}>
                {(s) => {
                  const n = s();
                  if (n.type === 'memory' || n.id.startsWith('mem_')) {
                    return (
                      <MemoryInspector
                        memoryId={n.id}
                        onNavigate={(next) => setSelectedNode({ id: next, type: 'memory' })}
                      />
                    );
                  }
                  const t = (n.type || '').toLowerCase();
                  const route =
                    t === 'run'
                      ? `/runs?id=${encodeURIComponent(n.id)}`
                      : t === 'retrieval'
                      ? `/retrievals?id=${encodeURIComponent(n.id)}`
                      : t === 'review'
                      ? `/reviews?id=${encodeURIComponent(n.id)}`
                      : null;
                  return (
                    <div class="flex flex-col gap-3 p-5">
                      <div class="flex items-center gap-2">
                        <IdLink id={n.id} full />
                      </div>
                      <p class="text-[12.5px] text-text-muted">
                        Type: <span class="font-mono text-text">{n.type || 'unknown'}</span>
                      </p>
                      <Show
                        when={route}
                        fallback={
                          <p class="text-[12px] text-text-subtle">
                            Detail inspector for <code>{n.type}</code> nodes is not
                            implemented in this surface.
                          </p>
                        }
                      >
                        <button
                          type="button"
                          onClick={() => navigate(route!)}
                          class="self-start rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-fg hover:opacity-90"
                        >
                          Open in {t} inspector
                        </button>
                      </Show>
                    </div>
                  );
                }}
              </Show>
            </SlideOver>
          </Show>
        </Show>
      </div>
    </div>
  );
}
