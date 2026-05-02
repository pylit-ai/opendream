import {
  Activity,
  Boxes,
  Database,
  FileSearch,
  FileText,
  GitGraph,
  Home,
  Layers,
  ListChecks,
  Moon,
  PlayCircle,
  Settings,
  ShieldCheck,
  Sparkles,
  type LucideProps,
} from 'lucide-solid';
import type { Component } from 'solid-js';

export type RouteGroup = 'catalog' | 'workspace' | 'trace' | 'audit';

export const GROUP_LABELS: Record<RouteGroup, string> = {
  catalog: 'Catalog',
  workspace: 'Workspace',
  trace: 'Trace',
  audit: 'Audit',
};

export interface RouteDef {
  path: string;
  name: string;
  icon: Component<LucideProps>;
  group: RouteGroup;
}

export const ROUTES: RouteDef[] = [
  { path: '/workspaces', name: 'Workspaces', icon: Boxes, group: 'catalog' },
  { path: '/overview', name: 'Overview', icon: Home, group: 'workspace' },
  { path: '/showcase', name: 'Showcase', icon: Sparkles, group: 'workspace' },
  { path: '/memories', name: 'Memories', icon: Database, group: 'workspace' },
  { path: '/dreams', name: 'Dreams', icon: Moon, group: 'workspace' },
  { path: '/runs', name: 'Runs', icon: PlayCircle, group: 'trace' },
  { path: '/retrievals', name: 'Retrievals', icon: FileSearch, group: 'trace' },
  { path: '/sessions', name: 'Sessions', icon: Layers, group: 'trace' },
  { path: '/context', name: 'Context', icon: FileText, group: 'trace' },
  { path: '/reviews', name: 'Reviews', icon: ShieldCheck, group: 'audit' },
  { path: '/graph', name: 'Graph', icon: GitGraph, group: 'audit' },
  { path: '/evals', name: 'Evals', icon: Activity, group: 'audit' },
  { path: '/exports', name: 'Exports', icon: ListChecks, group: 'audit' },
  { path: '/settings', name: 'Settings', icon: Settings, group: 'audit' },
];

export const GROUP_ORDER: RouteGroup[] = ['catalog', 'workspace', 'trace', 'audit'];
