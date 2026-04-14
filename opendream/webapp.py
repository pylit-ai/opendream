from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from . import workspace_catalog
from .observability import (
    build_graph,
    create_annotation,
    create_export,
    create_review_decision,
    index_observability,
    load_or_build_index,
    query_memories,
    query_retrievals,
    query_runs,
)
from .storage import MemoryStore


_STATIC_ROOT = (Path(__file__).parent / "static").resolve()
_STATIC_MIME_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".md": "text/markdown",
    ".html": "text/html; charset=utf-8",
}

_MEMORY_LIST_LIMIT_CAP = 500
_RETRIEVAL_LIST_LIMIT_CAP = 500
_RUN_LIST_LIMIT_CAP = 500


def _parse_query_float(raw: str | None) -> float | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_query_int(raw: str | None, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(raw) if raw is not None and str(raw).strip() else default
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <script>
(function(){
  try {
    var k='opendream-ui-theme';
    var s=localStorage.getItem(k);
    if(s==='light'||s==='dark') document.documentElement.setAttribute('data-theme',s);
    else document.documentElement.setAttribute('data-theme', window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
  } catch(e) { document.documentElement.setAttribute('data-theme','dark'); }
  try {
    var sk='opendream-sidebar';
    var sv=localStorage.getItem(sk);
    if(sv==='wide'||sv==='narrow') document.documentElement.setAttribute('data-sidebar',sv);
    else document.documentElement.setAttribute('data-sidebar','wide');
  } catch(e2) { document.documentElement.setAttribute('data-sidebar','wide'); }
})();
  </script>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenDream Observability</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    html[data-theme="dark"] {
      color-scheme: dark;
      --bg: #1a1b1e;
      --bg-subtle: #141416;
      --panel: #212224;
      --panel-veil: rgba(33, 34, 36, 0.92);
      --border: #2d2f33;
      --text: #eaeaea;
      --muted: #a8adb8;
      --accent: #3b82f6;
      --accent-soft: rgba(59, 130, 246, 0.18);
      --interactive: #22242a;
      --interactive-hover: #2a2d36;
      --input-bg: #2a2a2a;
      --pre-bg: #0f1114;
      --rail-bg: #0f1114;
      --shadow: rgba(0,0,0,0.45);
      --good: #4ade80;
      --warn: #fbbf24;
      --bad: #f87171;
      --dot-border: #0f1114;
      --table-stripe: rgba(255,255,255,0.03);
      --table-head: #26282c;
      --focus-ring: rgba(59, 130, 246, 0.45);
      --on-accent: #ffffff;
      --rail-dot: #6b7280;
      --timeline-mark-bg: rgba(251, 191, 36, 0.22);
      --th-help-underline: rgba(168, 173, 184, 0.55);
      --badge-good-bg: rgba(74, 222, 128, 0.16);
      --badge-warn-bg: rgba(251, 191, 36, 0.16);
      --badge-bad-bg: rgba(248, 113, 113, 0.16);
      --bad-border: rgba(248, 113, 113, 0.45);
    }
    html[data-theme="light"] {
      color-scheme: light;
      --bg: #f4f4f5;
      --bg-subtle: #e4e4e7;
      --panel: #ffffff;
      --panel-veil: rgba(255, 255, 255, 0.95);
      --border: #e4e4e7;
      --text: #18181b;
      --muted: #5c5c66;
      --accent: #2563eb;
      --accent-soft: rgba(37, 99, 235, 0.12);
      --interactive: #f4f4f5;
      --interactive-hover: #e4e4e7;
      --input-bg: #ffffff;
      --pre-bg: #f4f4f5;
      --rail-bg: #fafafa;
      --shadow: rgba(0,0,0,0.08);
      --good: #16a34a;
      --warn: #d97706;
      --bad: #dc2626;
      --dot-border: #ffffff;
      --table-stripe: rgba(0,0,0,0.02);
      --table-head: #f4f4f5;
      --focus-ring: rgba(37, 99, 235, 0.35);
      --on-accent: #ffffff;
      --rail-dot: #94a3b8;
      --timeline-mark-bg: rgba(217, 119, 6, 0.18);
      --th-help-underline: rgba(92, 92, 102, 0.45);
      --badge-good-bg: rgba(22, 163, 74, 0.14);
      --badge-warn-bg: rgba(217, 119, 6, 0.14);
      --badge-bad-bg: rgba(220, 38, 38, 0.12);
      --bad-border: rgba(220, 38, 38, 0.45);
    }
    * { box-sizing: border-box; }
    body { margin:0; font-family: "Inter", system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; -webkit-font-smoothing: antialiased; }
    .app-shell { display: flex; min-height: 100vh; }
    .sidebar {
      width: 17.5rem;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      padding: 1rem 0.75rem;
      background: var(--bg);
      border-right: 1px solid var(--border);
      transition: width 0.2s ease, padding 0.2s ease;
    }
    html[data-sidebar="narrow"] .sidebar {
      width: 4.35rem;
      padding: 0.65rem 0.4rem;
    }
    .icon-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 2.25rem;
      min-height: 2.25rem;
      padding: 0.35rem;
      margin: 0;
      border: 1px solid var(--border);
      border-radius: 0.5rem;
      background: var(--input-bg);
      color: var(--muted);
      cursor: pointer;
      line-height: 0;
    }
    .icon-btn:hover { color: var(--text); background: var(--interactive-hover); }
    .icon-btn.theme-btn-active { background: var(--accent); color: var(--on-accent); border-color: transparent; }
    .icon-svg { width: 1.15rem; height: 1.15rem; flex-shrink: 0; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .icon-svg--fill { fill: currentColor; stroke: none; }
    .sidebar-toggle {
      width: 100%;
      margin-bottom: 0.5rem;
      background: var(--interactive);
    }
    html[data-sidebar="narrow"] .sidebar-toggle { margin-bottom: 0.35rem; }
    .sidebar-toggle .when-narrow { display: none; }
    html[data-sidebar="narrow"] .sidebar-toggle .when-wide { display: none; }
    html[data-sidebar="narrow"] .sidebar-toggle .when-narrow { display: inline-flex; }
    .sidebar-brand { display: flex; align-items: center; gap: 0.75rem; padding: 0.25rem 0.5rem 1rem 0.5rem; }
    html[data-sidebar="narrow"] .sidebar-brand { flex-direction: column; justify-content: center; padding: 0.15rem 0 0.65rem 0; gap: 0; }
    .sidebar-logo {
      width: 2rem; height: 2rem; border-radius: 0.5rem;
      background: var(--interactive);
      border: 1px solid var(--border);
      display: flex; align-items: center; justify-content: center;
      font-size: 0.65rem; font-weight: 700; letter-spacing: 0.06em; color: var(--accent);
    }
    .sidebar-brand-kicker { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.2em; color: var(--muted); }
    .sidebar-brand-title { font-size: 1.05rem; font-weight: 600; letter-spacing: 0.02em; margin-top: 2px; }
    .sidebar-brand-text { min-width: 0; }
    html[data-sidebar="narrow"] .sidebar-brand-text { display: none; }
    .sidebar-nav { flex: 1; min-height: 0; overflow-y: auto; overflow-x: hidden; }
    .sidebar-nav ul, .sidebar-nav .sidebar-nav-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
    .sidebar-nav a {
      display: flex; align-items: center; padding: 0.5rem 0.75rem; border-radius: 0.375rem;
      font-size: 0.875rem; font-weight: 400; letter-spacing: 0.04em;
      color: var(--muted); text-decoration: none; border-left: 3px solid transparent;
      transition: background 0.15s, color 0.15s;
      position: relative;
    }
    .sidebar-nav a:hover { background: var(--interactive); color: var(--text); }
    .sidebar-nav a.active {
      background: var(--interactive);
      color: var(--accent);
      font-weight: 500;
      border-left-color: var(--accent);
    }
    html[data-sidebar="narrow"] .sidebar-nav a {
      justify-content: center;
      padding: 0.5rem 0.2rem;
      border-left: none;
    }
    html[data-sidebar="narrow"] .sidebar-nav a.active {
      border-left: none;
      box-shadow: inset 0 0 0 2px var(--accent);
    }
    .nav-label { flex: 1; min-width: 0; }
    html[data-sidebar="narrow"] .nav-label {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
    }
    html[data-sidebar="narrow"] .sidebar-nav a::after {
      content: attr(data-short);
      font-size: 0.62rem;
      font-weight: 700;
      letter-spacing: 0.02em;
      line-height: 1.2;
      text-align: center;
      color: inherit;
    }
    .sidebar-footer { padding-top: 0.75rem; margin-top: auto; border-top: 1px solid var(--border); }
    html[data-sidebar="narrow"] .sidebar-footer { padding-top: 0.5rem; }
    .theme-toggle { display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; }
    html[data-sidebar="narrow"] .theme-toggle { flex-direction: column; align-items: stretch; }
    .main-wrap { flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; background: var(--bg); }
    .main-content {
      flex: 1;
      padding: 1.25rem 1.5rem;
      overflow-x: hidden;
      overflow-y: auto;
      display: grid;
      gap: 1rem;
      grid-template-columns: 1.2fr 1fr;
    }
    a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    .full { grid-column: 1 / -1; }
    .panel { background: var(--panel); border:1px solid var(--border); border-radius: 0.75rem; padding: 1rem; box-shadow: 0 8px 28px var(--shadow); }
    .panel-fs { padding: 0; overflow: hidden; display: flex; flex-direction: column; }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      background: var(--panel);
    }
    .panel-fs .panel-title { margin: 0; font-size: 1.05rem; font-weight: 600; letter-spacing: 0.02em; }
    .panel-fs .panel-body-od { padding: 1rem; flex: 1; min-height: 0; overflow: auto; }
    .panel-fs-open { flex-shrink: 0; }
    /* Native <dialog> has UA max-width/centering; override for true fullscreen. */
    dialog.od-fs-dialog:not([open]) {
      display: none !important;
    }
    dialog.od-fs-dialog[open] {
      position: fixed;
      inset: 0;
      z-index: 2147483000;
      width: 100vw !important;
      max-width: none !important;
      height: 100vh;
      height: 100dvh;
      max-height: 100dvh;
      margin: 0 !important;
      padding: 0;
      border: none;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      box-sizing: border-box;
      overflow: hidden;
      overscroll-behavior: contain;
    }
    .od-fs-dialog::backdrop { background: rgba(0,0,0,0.48); }
    .od-fs-chrome {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 0.65rem 1rem;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      flex: 0 0 auto;
    }
    .od-fs-title { margin: 0; font-size: 1.1rem; font-weight: 600; }
    .od-fs-scroll {
      flex: 1 1 auto;
      min-height: 0;
      overflow-x: hidden;
      overflow-y: auto;
      padding: 1rem;
      -webkit-overflow-scrolling: touch;
    }
    html.od-modal-open,
    html.od-modal-open body {
      overflow: hidden !important;
      overscroll-behavior: none;
    }
    .mem-view-toggle.icon-toolbar { gap: 4px; align-items: center; }
    .mem-view-toggle.icon-toolbar .icon-btn.mem-view-active { border-color: var(--accent); color: var(--accent); box-shadow: 0 0 0 1px var(--focus-ring); }
    .pager .icon-btn { min-width: 2.5rem; }
    .metric { display:inline-block; min-width: 140px; margin: 0 16px 12px 0; }
    .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
    .value { font-size: 28px; font-weight: 700; }
    input, select, button, textarea { background: var(--input-bg); border:1px solid var(--border); color: var(--text); border-radius: 0.5rem; padding: 10px 12px; }
    button { cursor:pointer; }
    table { width:100%; border-collapse: collapse; }
    th, td { text-align:left; padding:10px; border-bottom: 1px solid var(--border); vertical-align: top; }
    tr:hover { background: var(--table-stripe); }
    pre { white-space: pre-wrap; word-break: break-word; background: var(--pre-bg); padding:12px; border-radius:10px; max-height: 420px; overflow:auto; border: 1px solid var(--border); }
    .badge { display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; margin-right: 6px; }
    .active-badge { background: var(--badge-good-bg); color: var(--good); }
    .contested-badge, .warning-badge { background: var(--badge-warn-bg); color: var(--warn); }
    .superseded-badge, .error-badge { background: var(--badge-bad-bg); color: var(--bad); }
    .muted { color: var(--muted); }
    .row { display:flex; gap:12px; flex-wrap: wrap; align-items:center; }
    .split { display:grid; gap:16px; grid-template-columns: 1fr 1fr; }
    .memories-toolbar { display:flex; flex-direction: column; gap:12px; margin-bottom:12px; }
    .memories-toolbar details { border:1px solid var(--border); border-radius:10px; padding:8px 12px; background: var(--interactive); }
    .memories-toolbar summary { cursor:pointer; color: var(--muted); font-size: 13px; }
    .table-scroll { overflow: auto; max-height: min(70vh, 720px); border-radius: 10px; border: 1px solid var(--border); }
    .memories-table { width:100%; border-collapse: collapse; }
    .memories-table thead th { position: sticky; top: 0; z-index: 1; background: var(--table-head); color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; border-bottom: 1px solid var(--border); }
    .memories-table tbody tr:nth-child(even) { background: var(--table-stripe); }
    .memories-table td.num, .memories-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
    .pager { display:flex; flex-wrap: wrap; gap:10px; align-items:center; margin-top:12px; }
    .pager button:disabled { opacity: 0.45; cursor: not-allowed; }
    input[type="datetime-local"] { min-width: 11.5rem; }
    .mem-view-toggle { display:inline-flex; gap:6px; align-items:center; flex-wrap:wrap; }
    .mem-view-toggle:not(.icon-toolbar) button { padding:8px 14px; font-size:13px; border-radius:10px; }
    .mem-view-toggle:not(.icon-toolbar) button.mem-view-active { border-color: var(--accent); color: var(--accent); box-shadow: 0 0 0 1px var(--focus-ring); }
    .mem-timeline { padding: 4px 0 8px 0; }
    .mem-timeline-day { margin: 18px 0 10px 0; padding-left: 7.5rem; font-size: 12px; letter-spacing: 0.08em; color: var(--muted); text-transform: uppercase; }
    .mem-timeline-day:first-child { margin-top: 0; }
    .mem-timeline-item { display:flex; align-items: stretch; }
    .mem-timeline-time { width: 5.25rem; flex-shrink:0; text-align:right; padding: 2px 12px 0 0; font-size: 12px; color: var(--muted); line-height: 1.3; }
    .mem-timeline-rail { width: 1.75rem; flex-shrink:0; display:flex; flex-direction:column; align-items:center; }
    .mem-timeline-dot { width: 10px; height: 10px; border-radius: 999px; background: var(--rail-dot); border: 2px solid var(--dot-border); z-index: 1; flex-shrink: 0; margin-top: 3px; }
    .mem-timeline-bar { width: 6px; border-radius: 999px; flex: 1; min-height: 28px; transition: height 0.25s ease-out; }
    .mem-timeline-body { flex:1; min-width:0; padding: 0 0 16px 14px; }
    .mem-timeline-body .t-meta { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-bottom:4px; }
    .mem-timeline-body .t-title { font-size: 14px; font-weight: 600; }
    .mem-timeline-body .t-title a { color: var(--text); text-decoration: none; }
    .mem-timeline-body .t-title a:hover { color: var(--accent); text-decoration: underline; }
    .mem-timeline-body .t-sum { font-size: 12px; color: var(--muted); line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .mem-timeline-body .t-id { font-size: 11px; color: var(--muted); font-family: ui-monospace, monospace; margin-top: 6px; }
    .timeline-mark { background: var(--timeline-mark-bg); padding: 0 3px; border-radius: 4px; }
    .mem-detail-toggle { margin: 12px 0 0 0; }
    .mem-detail-body { margin-top: 10px; }
    .mem-detail-meta { display: grid; gap: 8px; margin-bottom: 4px; }
    .mem-detail-field { display: grid; grid-template-columns: minmax(0, 9.5rem) 1fr; gap: 6px 12px; font-size: 13px; align-items: start; }
    .mem-detail-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }
    .mem-detail-val { word-break: break-word; }
    .mem-detail-section { margin-top: 14px; }
    .mem-detail-h { font-size: 12px; color: var(--muted); margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: .06em; }
    .mem-detail-body-text { white-space: pre-wrap; font-size: 13px; line-height: 1.5; background: var(--interactive); padding: 12px; border-radius: 10px; border: 1px solid var(--border); }
    .mem-detail-list { margin: 0; padding-left: 1.2rem; }
    .mem-detail-list pre { margin: 4px 0; font-size: 11px; max-height: 220px; overflow: auto; background: var(--pre-bg); padding: 8px; border-radius: 8px; }
    .ret-ex-card { background: var(--interactive); border: 1px solid var(--border); border-radius: 12px; padding: 14px; margin-bottom: 12px; }
    .ret-ex-card h5 { font-size: 12px; color: var(--muted); margin: 12px 0 6px 0; text-transform: uppercase; letter-spacing: .06em; }
    .ret-ex-card h5:first-of-type { margin-top: 0; }
    .ret-dl { display: grid; grid-template-columns: minmax(0, 10rem) 1fr; gap: 4px 12px; font-size: 12px; align-items: baseline; }
    .ret-dl dt { color: var(--muted); }
    .ret-dl dd { margin: 0; word-break: break-word; }
    .ret-tag { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 6px; background: var(--accent-soft); color: var(--accent); margin: 2px 4px 2px 0; }
    .ret-why-card { border-left: 3px solid var(--accent); padding: 8px 0 8px 12px; margin-bottom: 10px; }
    .ret-why-card--error { border-left-color: var(--bad-border); }
    .glossary-hint { font-size: 12px; color: var(--muted); margin: 0 0 10px 0; line-height: 1.55; }
    .mem-detail-details { margin-bottom: 12px; border: 1px solid var(--border); border-radius: 12px; padding: 10px 12px; background: var(--interactive); }
    .mem-detail-details > summary { cursor: pointer; font-size: 12px; color: var(--muted); letter-spacing: .06em; text-transform: uppercase; list-style: none; }
    .mem-detail-details > summary::-webkit-details-marker { display: none; }
    .mem-detail-details[open] > summary { color: var(--accent); margin-bottom: 8px; }
    .mem-detail-details .mem-detail-section { margin-top: 10px; }
    th[title] { cursor: help; text-decoration: underline dotted var(--th-help-underline); text-underline-offset: 3px; }
    .mem-detail-inline-pre { font-size: 11px; margin: 8px 0; }
    .sidebar-nav-section {
      margin: 0.65rem 0 0.25rem;
      padding: 0 0.5rem;
      font-size: 0.62rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
    }
    .sidebar-nav-section:first-of-type { margin-top: 0; }
    html[data-sidebar="narrow"] .sidebar-nav-section {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .od-data-freshness {
      font-size: 12px;
      padding: 0 1.25rem 6px 1.25rem;
      text-align: right;
      flex-shrink: 0;
    }
    .od-empty-nextsteps pre {
      margin: 8px 0;
      font-size: 11px;
      padding: 10px 12px;
      border-radius: 8px;
      background: var(--pre-bg);
      border: 1px solid var(--border);
      white-space: pre-wrap;
      word-break: break-all;
    }
    .od-api-copy-btn { min-width: 44px; min-height: 44px; }
    @media (max-width: 900px) {
      .app-shell { flex-direction: row; position: relative; }
      .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        bottom: 0;
        z-index: 40;
        width: min(18rem, 88vw);
        max-width: 18rem;
        border-right: 1px solid var(--border);
        border-bottom: none;
        box-shadow: 4px 0 24px var(--shadow);
        transform: translateX(-102%);
        transition: transform 0.2s ease;
        overflow-y: auto;
      }
      html[data-mobile-nav="open"] .sidebar { transform: translateX(0); }
      .sidebar-backdrop {
        display: none;
        position: fixed;
        inset: 0;
        z-index: 30;
        background: rgba(0,0,0,0.35);
      }
      html[data-mobile-nav="open"] .sidebar-backdrop { display: block; }
      .sidebar-toggle--mobile {
        display: inline-flex !important;
        position: fixed;
        top: 10px;
        left: 10px;
        z-index: 50;
        min-width: 44px;
        min-height: 44px;
      }
      .main-wrap { margin-left: 0; padding-top: 3.25rem; }
      html[data-sidebar="narrow"] .sidebar { width: min(18rem, 88vw); }
      html[data-sidebar="narrow"] .sidebar-brand-text { display: block; }
      html[data-sidebar="narrow"] .nav-label { position: static; width: auto; height: auto; margin: 0; overflow: visible; clip: auto; }
      html[data-sidebar="narrow"] .sidebar-nav a::after { display: none; content: none; }
      .sidebar-nav-list { flex-direction: column; flex-wrap: nowrap; }
      .sidebar-nav a { border-left: 3px solid transparent; border-bottom: none; }
      .sidebar-nav a.active { border-left-color: var(--accent); border-bottom-color: transparent; }
      .main-content { grid-template-columns: 1fr; padding: 1rem; }
      .split { grid-template-columns: 1fr; }
      .theme-toggle .icon-btn { min-width: 44px; min-height: 44px; }
    }
    @media (min-width: 901px) {
      .sidebar-toggle--mobile { display: none !important; }
      .sidebar-backdrop { display: none !important; }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <button type="button" class="icon-btn sidebar-toggle sidebar-toggle--mobile" id="sidebar-mobile-open" aria-controls="sidebar-nav" aria-expanded="false" title="Open menu">
      <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
    </button>
    <div class="sidebar-backdrop" id="sidebar-backdrop" aria-hidden="true"></div>
    <aside class="sidebar" id="sidebar-aside" aria-label="App">
      <button type="button" class="icon-btn sidebar-toggle" id="sidebar-toggle" aria-controls="sidebar-nav" title="Narrow sidebar">
        <span class="when-wide" aria-hidden="true"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg></span>
        <span class="when-narrow" aria-hidden="true"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg></span>
      </button>
      <div class="sidebar-brand">
        <div class="sidebar-logo" aria-hidden="true">OD</div>
        <div class="sidebar-brand-text">
          <div class="sidebar-brand-kicker">Observe</div>
          <div class="sidebar-brand-title">OpenDream</div>
        </div>
      </div>
      <nav class="sidebar-nav" id="sidebar-nav" aria-label="Primary">
        <p class="sidebar-nav-section" id="sidebar-sec-workspace">Workspace</p>
        <ul class="sidebar-nav-list" aria-labelledby="sidebar-sec-workspace">
          <li><a href="/overview" data-short="Ov"><span class="nav-label">Overview</span></a></li>
          <li><a href="/workspaces" data-short="Ws"><span class="nav-label">Workspaces</span></a></li>
          <li><a href="/memories" data-short="Mem"><span class="nav-label">Memories</span></a></li>
        </ul>
        <p class="sidebar-nav-section" id="sidebar-sec-trace">Trace</p>
        <ul class="sidebar-nav-list" aria-labelledby="sidebar-sec-trace">
          <li><a href="/runs" data-short="Rn"><span class="nav-label">Runs</span></a></li>
          <li><a href="/retrievals" data-short="Ret"><span class="nav-label">Retrievals</span></a></li>
          <li><a href="/sessions" data-short="Ses"><span class="nav-label">Sessions</span></a></li>
          <li><a href="/context" data-short="Ctx"><span class="nav-label">Context</span></a></li>
        </ul>
        <p class="sidebar-nav-section" id="sidebar-sec-audit">Audit and tools</p>
        <ul class="sidebar-nav-list" aria-labelledby="sidebar-sec-audit">
          <li><a href="/reviews" data-short="Rev"><span class="nav-label">Reviews</span></a></li>
          <li><a href="/graph" data-short="Gr"><span class="nav-label">Graph</span></a></li>
          <li><a href="/evals" data-short="Ev"><span class="nav-label">Evals</span></a></li>
          <li><a href="/exports" data-short="Ex"><span class="nav-label">Exports</span></a></li>
          <li><a href="/settings" data-short="St"><span class="nav-label">Settings</span></a></li>
        </ul>
      </nav>
      <div class="sidebar-footer">
        <div class="theme-toggle" role="group" aria-label="Color theme">
          <button type="button" data-theme="light" id="theme-btn-light" class="icon-btn" aria-label="Light theme" title="Light theme">
            <svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
          </button>
          <button type="button" data-theme="dark" id="theme-btn-dark" class="icon-btn" aria-label="Dark theme" title="Dark theme">
            <svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          </button>
        </div>
      </div>
    </aside>
    <div class="main-wrap">
      <div id="od-data-freshness" class="od-data-freshness muted" aria-live="polite"></div>
      <main id="app" class="main-content" aria-live="polite"></main>
    </div>
  </div>
  <dialog id="od-fs-dialog" class="od-fs-dialog" aria-labelledby="od-fs-title" aria-modal="true">
    <div class="od-fs-chrome">
      <h2 id="od-fs-title" class="od-fs-title"></h2>
      <button type="button" class="icon-btn" id="od-fs-close" aria-label="Close fullscreen" title="Close">
        <svg class="icon-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    </div>
    <div class="od-fs-scroll" id="od-fs-host"></div>
  </dialog>
  <script>
    const app = document.getElementById('app');
    const route = location.pathname;
    function pathMatchesNav(href, path) {
      if (!href) return false;
      if (href === '/overview' && (path === '/' || path === '/overview')) return true;
      if (path === href) return true;
      if (href !== '/' && path.startsWith(href + '/')) return true;
      return false;
    }
    document.querySelectorAll('.sidebar-nav a').forEach((a) => {
      if (pathMatchesNav(a.getAttribute('href'), route)) a.classList.add('active');
    });
    (function themeUi(){
      var KEY='opendream-ui-theme';
      function sync(){
        var t=document.documentElement.getAttribute('data-theme')||'dark';
        document.querySelectorAll('.theme-toggle button[data-theme]').forEach(function(b){
          b.classList.toggle('theme-btn-active', b.getAttribute('data-theme')===t);
          b.setAttribute('aria-pressed', b.getAttribute('data-theme')===t ? 'true' : 'false');
        });
      }
      function set(t){
        document.documentElement.setAttribute('data-theme', t);
        try { localStorage.setItem(KEY, t); } catch(e) {}
        sync();
      }
      document.querySelectorAll('.theme-toggle button[data-theme]').forEach(function(btn){
        btn.addEventListener('click', function(){ set(btn.getAttribute('data-theme')); });
      });
      sync();
    })();
    (function sidebarUi(){
      var KEY='opendream-sidebar';
      function sync(){
        var m=document.documentElement.getAttribute('data-sidebar')||'wide';
        var btn=document.getElementById('sidebar-toggle');
        if(btn){
          btn.setAttribute('aria-pressed', m==='narrow' ? 'true' : 'false');
          btn.title=m==='wide' ? 'Narrow sidebar' : 'Widen sidebar';
          btn.setAttribute('aria-label', m==='wide' ? 'Narrow sidebar' : 'Widen sidebar');
        }
      }
      function set(mode){
        document.documentElement.setAttribute('data-sidebar', mode);
        try { localStorage.setItem(KEY, mode); } catch(e) {}
        sync();
      }
      var tbtn=document.getElementById('sidebar-toggle');
      if(tbtn) tbtn.addEventListener('click', function(){
        var cur=document.documentElement.getAttribute('data-sidebar')||'wide';
        set(cur==='wide' ? 'narrow' : 'wide');
      });
      sync();
    })();
    (function mobileNav(){
      function set(open){
        document.documentElement.setAttribute('data-mobile-nav', open ? 'open' : '');
        var b = document.getElementById('sidebar-mobile-open');
        if (b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
        var bd = document.getElementById('sidebar-backdrop');
        if (bd) bd.setAttribute('aria-hidden', open ? 'false' : 'true');
      }
      var openBtn = document.getElementById('sidebar-mobile-open');
      var backdrop = document.getElementById('sidebar-backdrop');
      if (openBtn) openBtn.addEventListener('click', function(){
        set(document.documentElement.getAttribute('data-mobile-nav') !== 'open');
      });
      if (backdrop) backdrop.addEventListener('click', function(){ set(false); });
      document.querySelectorAll('.sidebar-nav a').forEach(function(a){
        a.addEventListener('click', function(){
          try {
            if (window.matchMedia('(max-width: 900px)').matches) set(false);
          } catch (e) {}
        });
      });
    })();
    const qs = (obj) => new URLSearchParams(obj).toString();
    const escapeHtml = (s) => String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    var odFsRestore = null;
    function closeOdPanelFullscreen() {
      var dlg = document.getElementById('od-fs-dialog');
      if (dlg && dlg.open) dlg.close();
    }
    window.closeOdPanelFullscreen = closeOdPanelFullscreen;
    (function odFullscreenDialog() {
      var dlg = document.getElementById('od-fs-dialog');
      var host = document.getElementById('od-fs-host');
      if (!dlg || !host) return;
      dlg.addEventListener('close', function() {
        document.documentElement.classList.remove('od-modal-open');
        if (!odFsRestore || !odFsRestore.el || !odFsRestore.section) return;
        var head = odFsRestore.section.querySelector('.panel-head');
        if (head) head.insertAdjacentElement('afterend', odFsRestore.el);
        else odFsRestore.section.appendChild(odFsRestore.el);
        odFsRestore = null;
      });
      dlg.addEventListener('click', function(e) {
        if (e.target === dlg) closeOdPanelFullscreen();
      });
      var xb = document.getElementById('od-fs-close');
      if (xb) xb.addEventListener('click', closeOdPanelFullscreen);
      document.addEventListener('click', function(e) {
        var b = e.target.closest('[data-fs-panel]');
        if (!b || !app.contains(b)) return;
        e.preventDefault();
        var key = b.getAttribute('data-fs-panel');
        var body = document.querySelector('[data-panel-body="' + key + '"]');
        if (!body) return;
        var section = body.closest('section.panel');
        if (!section) return;
        odFsRestore = { section: section, el: body };
        var t = document.getElementById('od-fs-title');
        if (t) t.textContent = body.getAttribute('data-panel-title') || '';
        host.appendChild(body);
        document.documentElement.classList.add('od-modal-open');
        dlg.showModal();
      });
    })();
    const memoryExplorerParams = (updates = {}) => {
      const p = new URLSearchParams(location.search);
      for (const [k, v] of Object.entries(updates)) {
        if (v === '' || v === null || v === undefined) p.delete(k);
        else p.set(k, String(v));
      }
      return p;
    };
    function applyMemoryTimePreset(hours) {
      const now = new Date();
      const from = new Date(now.getTime() - hours * 3600 * 1000);
      const p = memoryExplorerParams({
        updated_after: from.toISOString(),
        updated_before: now.toISOString(),
        offset: '0',
      });
      location.search = p.toString() ? '?' + p.toString() : '';
    }
    function applyRetrievalTimePreset(hours) {
      const now = new Date();
      const from = new Date(now.getTime() - hours * 3600 * 1000);
      const p = memoryExplorerParams({
        timestamp_after: from.toISOString(),
        timestamp_before: now.toISOString(),
        offset: '0',
      });
      location.search = p.toString() ? '?' + p.toString() : '';
    }
    function applyRunTimePreset(hours) {
      const now = new Date();
      const from = new Date(now.getTime() - hours * 3600 * 1000);
      const p = memoryExplorerParams({
        ended_after: from.toISOString(),
        ended_before: now.toISOString(),
        offset: '0',
      });
      location.search = p.toString() ? '?' + p.toString() : '';
    }
    const memoryHref = (id) => '/memories/' + encodeURIComponent(id) + (location.search || '');
    /** URL/API use UTC ISO strings; datetime-local uses the browser's local timezone. */
    const isoUtcToDatetimeLocal = (iso) => {
      if (!iso || !String(iso).trim()) return '';
      const d = new Date(String(iso).trim());
      if (Number.isNaN(d.getTime())) return '';
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };
    const datetimeLocalToIsoUtc = (raw) => {
      if (!raw || !String(raw).trim()) return '';
      const d = new Date(String(raw).trim());
      if (Number.isNaN(d.getTime())) return '';
      return d.toISOString();
    };
    const badge = (value) => {
      let cls = 'warning-badge';
      if (value === 'active') cls = 'active-badge';
      else if (value === 'contested') cls = 'contested-badge';
      else if (value === 'superseded') cls = 'superseded-badge';
      else if (value === 'deleted' || value === 'quarantined') cls = 'error-badge';
      return `<span class="badge ${cls}">${escapeHtml(value)}</span>`;
    };
    const memoryTypeHue = (str) => {
      let h = 0;
      const s = String(str || '');
      for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
      return h % 360;
    };
    const memoryTimelineBarHeight = (item) => {
      const s = item.salience;
      if (s != null && s !== '' && !Number.isNaN(Number(s))) return Math.max(28, 32 + Number(s) * 40);
      const c = item.confidence;
      if (c != null && c !== '' && !Number.isNaN(Number(c))) return Math.max(28, 32 + Number(c) * 28);
      return 36;
    };
    const memoryTimelineHighlight = (text, query) => {
      const t = String(text || '');
      const needle = (query || '').trim();
      if (!needle) return escapeHtml(t);
      const low = t.toLowerCase();
      const qi = low.indexOf(needle.toLowerCase());
      if (qi === -1) return escapeHtml(t);
      return (
        escapeHtml(t.slice(0, qi)) +
        '<mark class="timeline-mark">' +
        escapeHtml(t.slice(qi, qi + needle.length)) +
        '</mark>' +
        escapeHtml(t.slice(qi + needle.length))
      );
    };
    const buildMemoryTimelineHtml = (items, searchQuery) => {
      const sorted = [...items].sort((a, b) => {
        const ta = new Date(a.updated_at || 0).getTime();
        const tb = new Date(b.updated_at || 0).getTime();
        return tb - ta;
      });
      let lastDay = '';
      const parts = [];
      for (const item of sorted) {
        const d = new Date(item.updated_at || '');
        const hasTime = !Number.isNaN(d.getTime());
        const dayKey = hasTime
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : '_nodate';
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dayLabel = hasTime
            ? d.toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No date';
          parts.push(`<div class="mem-timeline-day">${escapeHtml(dayLabel)}</div>`);
        }
        const timeStr = hasTime
          ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
          : '—';
        const hue = memoryTypeHue(item.type || item.memory_id || 'x');
        const barH = memoryTimelineBarHeight(item);
        const barColor = `hsl(${hue} 55% 42%)`;
        const titleHtml = memoryTimelineHighlight(item.title || 'Untitled', searchQuery);
        const sumRaw = (item.summary || '').slice(0, 220);
        const sumHtml = memoryTimelineHighlight(sumRaw, searchQuery);
        parts.push(`<div class="mem-timeline-item">
          <div class="mem-timeline-time"><p>${escapeHtml(timeStr)}</p></div>
          <div class="mem-timeline-rail">
            <div class="mem-timeline-dot"></div>
            <div class="mem-timeline-bar" style="height:${barH}px;background:${barColor};"></div>
          </div>
          <div class="mem-timeline-body">
            <div class="t-meta">${badge(item.status)}
              <span class="muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.05em">${escapeHtml(
                item.type || ''
              )}</span>
              <span class="muted" style="font-size:11px">· ${escapeHtml(item.scope || '')}</span>
            </div>
            <div class="t-title"><a href="${memoryHref(item.memory_id)}">${titleHtml}</a></div>
            <div class="t-sum">${sumHtml || '<span class="muted">No summary</span>'}</div>
            <div class="t-id">${escapeHtml(item.memory_id || '')}</div>
          </div>
        </div>`);
      }
      return parts.join('') || '<p class="muted">No memories match.</p>';
    };
    const retrievalTimelineBarHeight = (item) => {
      const n = (item.selected_memory_ids || []).length;
      return Math.max(28, 32 + Math.min(n * 14, 72));
    };
    const buildRetrievalTimelineHtml = (items, searchQuery) => {
      const sorted = [...items].sort((a, b) => {
        const ta = new Date(a.timestamp || 0).getTime();
        const tb = new Date(b.timestamp || 0).getTime();
        return tb - ta;
      });
      let lastDay = '';
      const parts = [];
      for (const item of sorted) {
        const d = new Date(item.timestamp || '');
        const hasTime = !Number.isNaN(d.getTime());
        const dayKey = hasTime
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : '_nodate';
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dayLabel = hasTime
            ? d.toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No date';
          parts.push(`<div class="mem-timeline-day">${escapeHtml(dayLabel)}</div>`);
        }
        const timeStr = hasTime
          ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
          : '—';
        const hue = memoryTypeHue(item.query || item.id || 'x');
        const barH = retrievalTimelineBarHeight(item);
        const barColor = `hsl(${hue} 55% 42%)`;
        const n = (item.selected_memory_ids || []).length;
        const qRaw = item.query || '';
        const titleHtml = memoryTimelineHighlight(qRaw || '(no query)', searchQuery);
        const sumRaw = (item.summary || '').slice(0, 220);
        const sumHtml = sumRaw ? escapeHtml(sumRaw) : '<span class="muted">No summary</span>';
        parts.push(`<div class="mem-timeline-item">
          <div class="mem-timeline-time"><p>${escapeHtml(timeStr)}</p></div>
          <div class="mem-timeline-rail">
            <div class="mem-timeline-dot"></div>
            <div class="mem-timeline-bar" style="height:${barH}px;background:${barColor};"></div>
          </div>
          <div class="mem-timeline-body">
            <div class="t-meta">
              <span class="muted" style="font-size:11px" title="Memories included in the ranked result set for this retrieval">${n} selected</span>
              <span class="muted" style="font-size:11px">· retrieval</span>
            </div>
            <div class="t-title"><a href="${retrievalHref(item.id)}">${titleHtml}</a></div>
            <div class="t-sum">${sumHtml}</div>
            <div class="t-id">${escapeHtml(item.id || '')}</div>
          </div>
        </div>`);
      }
      return parts.join('') || '<p class="muted">No retrievals match.</p>';
    };
    const runEffectiveInstant = (item) => {
      const e = item && item.ended_at != null ? String(item.ended_at).trim() : '';
      if (e) return e;
      const s = item && item.started_at != null ? String(item.started_at).trim() : '';
      return s;
    };
    const buildRunTimelineHtml = (items, searchQuery) => {
      const sorted = [...items].sort((a, b) => {
        const ta = new Date(runEffectiveInstant(a) || 0).getTime();
        const tb = new Date(runEffectiveInstant(b) || 0).getTime();
        return tb - ta;
      });
      let lastDay = '';
      const parts = [];
      const needle = (searchQuery || '').trim().toLowerCase();
      for (const item of sorted) {
        const rawTs = runEffectiveInstant(item);
        const d = new Date(rawTs || '');
        const hasTime = !Number.isNaN(d.getTime());
        const dayKey = hasTime
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : '_nodate';
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dayLabel = hasTime
            ? d.toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No date';
          parts.push(`<div class="mem-timeline-day">${escapeHtml(dayLabel)}</div>`);
        }
        const timeStr = hasTime
          ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
          : '—';
        const hue = memoryTypeHue(item.type || item.run_id || 'x');
        const barH = Math.max(32, 36 + String(item.diff_text || '').length > 200 ? 48 : 36);
        const barColor = `hsl(${hue} 55% 42%)`;
        const rid = String(item.run_id || '');
        const hay = `${rid} ${item.type || ''} ${item.status || ''}`.toLowerCase();
        const hit = needle && hay.includes(needle);
        const titleRaw = `${item.type || 'run'} · ${item.status || ''}`;
        const titleHtml = hit
          ? memoryTimelineHighlight(titleRaw, searchQuery)
          : escapeHtml(titleRaw);
        parts.push(`<div class="mem-timeline-item">
          <div class="mem-timeline-time"><p>${escapeHtml(timeStr)}</p></div>
          <div class="mem-timeline-rail">
            <div class="mem-timeline-dot"></div>
            <div class="mem-timeline-bar" style="height:${barH}px;background:${barColor};"></div>
          </div>
          <div class="mem-timeline-body">
            <div class="t-meta">${badge(String(item.status || 'unknown'))}
              <span class="muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.05em">${escapeHtml(
                String(item.type || '')
              )}</span>
            </div>
            <div class="t-title"><a href="${runHref(rid)}" title="${escapeHtml(rid)}">${titleHtml}</a></div>
            <div class="t-sum"><span class="muted" style="font-size:12px">Started</span> ${escapeHtml(
              formatInstantLocal(item.started_at) || '—'
            )} · <span class="muted" style="font-size:12px">Ended</span> ${escapeHtml(formatInstantLocal(item.ended_at) || '—')}</div>
            <div class="t-id"><a href="${runHref(rid)}" title="Run id">${escapeHtml(rid)}</a></div>
          </div>
        </div>`);
      }
      return parts.join('') || '<p class="muted">No runs match.</p>';
    };
    window.odCopyApiUrl = function (btn) {
      var path = btn.getAttribute('data-api-path') || '';
      var method = btn.getAttribute('data-api-method') || 'GET';
      var line = method + ' ' + location.origin + path;
      void navigator.clipboard.writeText(line).catch(function () {});
    };
    const fetchJson = async (path, options={}) => {
      const response = await fetch(path, options);
      const bodyText = await response.text();
      if (!response.ok) {
        let msg = bodyText.slice(0, 800) || ('HTTP ' + response.status);
        try {
          const j = JSON.parse(bodyText);
          if (j && typeof j.error === 'string') msg = j.error;
        } catch (_e) {}
        const err = new Error(msg);
        err.status = response.status;
        throw err;
      }
      if (!bodyText.trim()) return {};
      return JSON.parse(bodyText);
    };
    const fsExpandSvg = '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>';
    const panel = (title, body, full=false, panelKey=null) => {
      if (!panelKey) {
        return '<section class="panel ' + (full ? 'full' : '') + '"><h2>' + title + '</h2>' + body + '</section>';
      }
      var safe = escapeHtml(title);
      return '<section class="panel panel-fs ' + (full ? 'full' : '') + '"><div class="panel-head"><h2 class="panel-title">' + safe + '</h2><button type="button" class="icon-btn panel-fs-open" data-fs-panel="' + panelKey + '" aria-label="Open ' + safe + ' in fullscreen" title="Fullscreen">' + fsExpandSvg + '</button></div><div class="panel-body-od" data-panel-body="' + panelKey + '" data-panel-title="' + safe + '">' + body + '</div></section>';
    };
    const pretty = (obj) => `<pre>${JSON.stringify(obj, null, 2)}</pre>`;
    async function runRender(label, fn) {
      closeOdPanelFullscreen();
      app.setAttribute('aria-busy', 'true');
      app.innerHTML = panel('Loading', `<p class="muted">${escapeHtml(label)}</p>`, true);
      try {
        await fn();
        var fr = document.getElementById('od-data-freshness');
        if (fr) {
          fr.textContent = 'Data loaded at ' + new Date().toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' });
        }
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        const status = err && err.status != null ? String(err.status) : '';
        const clipText = (status ? 'HTTP ' + status + '\\n' : '') + msg;
        const statusLine = status ? `<p class="muted" style="margin:0 0 8px 0">HTTP <strong>${escapeHtml(status)}</strong></p>` : '';
        app.innerHTML = [
          panel('Could not load', statusLine + `<p class="muted">${escapeHtml(msg)}</p><p class="row od-err-actions" style="gap:8px;align-items:center;flex-wrap:wrap"><button type="button" class="icon-btn od-api-copy-btn" id="od-retry-btn" aria-label="Retry" title="Retry"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg></button><button type="button" class="icon-btn od-api-copy-btn" id="od-copy-err-btn" aria-label="Copy error details" title="Copy error"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button></p>`, true),
        ].join('');
        const btn = document.getElementById('od-retry-btn');
        if (btn) btn.onclick = () => { void runRender(label, fn); };
        const copyErr = document.getElementById('od-copy-err-btn');
        if (copyErr) copyErr.onclick = function () { void navigator.clipboard.writeText(clipText).catch(function () {}); };
      } finally {
        app.removeAttribute('aria-busy');
      }
    }
    /** Human-readable instant in the viewer's locale and local timezone (Intl). */
    const formatInstantLocal = (input) => {
      if (input === undefined || input === null || input === '') return '';
      const d = new Date(input);
      if (Number.isNaN(d.getTime())) return String(input);
      const s = typeof input === 'string' ? input.trim() : '';
      const hasTime =
        (s && /T\\d{2}:\\d{2}/.test(s)) ||
        (s && /Z$/.test(s)) ||
        (s && /[+-]\\d{2}:?\\d{2}$/.test(s));
      if (s && !hasTime && /^\\d{4}-\\d{2}-\\d{2}$/.test(s)) {
        const [y, m, day] = s.split('-').map(Number);
        return new Intl.DateTimeFormat(undefined, {
          weekday: 'short',
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        }).format(new Date(y, m - 1, day));
      }
      /* Do not mix dateStyle/timeStyle with timeZoneName — throws in V8/ICU. */
      return new Intl.DateTimeFormat(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short',
      }).format(d);
    };
    const looksLikeIsoDateString = (v) =>
      typeof v === 'string' &&
      (/^\\d{4}-\\d{2}-\\d{2}T/.test(v) ||
        /^\\d{4}-\\d{2}-\\d{2}Z?$/.test(v) ||
        /^\\d{4}-\\d{2}-\\d{2}[+-]/.test(v) ||
        /^\\d{4}-\\d{2}-\\d{2}$/.test(v));
    const jsonStringifyWithLocalDates = (obj) =>
      JSON.stringify(
        obj,
        (_k, v) => {
          if (looksLikeIsoDateString(v)) {
            const d = new Date(v);
            if (!Number.isNaN(d.getTime())) return formatInstantLocal(v);
          }
          return v;
        },
        2
      );
    const formatMemoryDetailReadable = (d) => {
      const r = d.raw_json && typeof d.raw_json === 'object' ? d.raw_json : d;
      const line = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        let v = val;
        if (Array.isArray(v)) {
          if (v.length === 0) return '';
          v = v.join(', ');
        } else if (typeof v === 'object') {
          v = JSON.stringify(v);
        }
        return `<div class="mem-detail-field"><span class="mem-detail-label">${escapeHtml(label)}</span><span class="mem-detail-val">${escapeHtml(String(v))}</span></div>`;
      };
      const lineDate = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        const formatted = formatInstantLocal(val);
        if (!formatted) return '';
        return `<div class="mem-detail-field"><span class="mem-detail-label">${escapeHtml(label)}</span><span class="mem-detail-val">${escapeHtml(formatted)}</span></div>`;
      };
      let meta = '';
      meta += line('Memory ID', r.memory_id);
      meta += line('Type', r.type);
      meta += line('Scope', r.scope);
      meta += line('Status', r.status);
      if (r.salience != null && r.salience !== '') meta += line('Salience', Number(r.salience).toFixed(4));
      if (r.confidence != null && r.confidence !== '') meta += line('Confidence', Number(r.confidence).toFixed(4));
      meta += lineDate('Created', r.created_at);
      meta += lineDate('Updated', r.updated_at);
      if (r.valid_from) meta += lineDate('Valid from', r.valid_from);
      if (r.valid_to) meta += lineDate('Valid to', r.valid_to);
      if (d.retrieval_frequency != null) meta += line('Retrieval frequency', d.retrieval_frequency);
      if (Array.isArray(r.source_event_ids) && r.source_event_ids.length) meta += line('Source events', r.source_event_ids.join(', '));
      if (r.provenance_tier) meta += line('Provenance tier', r.provenance_tier);
      if (r.claim_class) meta += line('Claim class', r.claim_class);
      if (Array.isArray(r.workflow_steps) && r.workflow_steps.length) meta += line('Workflow steps', r.workflow_steps.join(' → '));

      const body = (r.body || '').trim();
      const bodyHtml = body
        ? `<div class="mem-detail-section"><h4 class="mem-detail-h">Body</h4><div class="mem-detail-body-text">${escapeHtml(body)}</div></div>`
        : '';

      const lin = d.lineage || {};
      const sup = lin.supersedes || r.supersedes;
      const con = lin.conflicts_with || r.conflicts_with;
      let linHtml = '';
      if (Array.isArray(sup) && sup.length) {
        linHtml += `<h4 class="mem-detail-h">Supersedes</h4><ul class="mem-detail-list">` + sup.map((id) => `<li><code>${escapeHtml(String(id))}</code></li>`).join('') + `</ul>`;
      }
      if (Array.isArray(con) && con.length) {
        linHtml += `<h4 class="mem-detail-h">Conflicts with</h4><ul class="mem-detail-list">` + con.map((id) => `<li><code>${escapeHtml(String(id))}</code></li>`).join('') + `</ul>`;
      }
      if (linHtml) linHtml = `<div class="mem-detail-section">${linHtml}</div>`;

      const anns = d.annotations || [];
      let annHtml = '';
      if (anns.length) {
        annHtml = `<div class="mem-detail-section"><h4 class="mem-detail-h">Annotations (${anns.length})</h4><ul class="mem-detail-list">`;
        for (const a of anns.slice(0, 25)) {
          annHtml += `<li><pre>${escapeHtml(jsonStringifyWithLocalDates(a))}</pre></li>`;
        }
        if (anns.length > 25) annHtml += `<li class="muted">… and ${anns.length - 25} more</li>`;
        annHtml += '</ul></div>';
      }

      const revs = d.manual_reviews || [];
      let revHtml = '';
      if (revs.length) {
        revHtml = `<div class="mem-detail-section"><h4 class="mem-detail-h">Manual reviews (${revs.length})</h4><ul class="mem-detail-list">`;
        for (const rr of revs.slice(0, 25)) {
          revHtml += `<li><pre>${escapeHtml(jsonStringifyWithLocalDates(rr))}</pre></li>`;
        }
        if (revs.length > 25) revHtml += `<li class="muted">… and ${revs.length - 25} more</li>`;
        revHtml += '</ul></div>';
      }

      return `<div class="mem-detail-meta">${meta}</div>${bodyHtml}${linHtml}${annHtml}${revHtml}`;
    };
    function memoryDetailToggle(which) {
      const fe = document.getElementById('mem-detail-formatted');
      const re = document.getElementById('mem-detail-raw');
      const bf = document.getElementById('mem-detail-btn-formatted');
      const br = document.getElementById('mem-detail-btn-raw');
      if (!fe || !re) return;
      if (which === 'formatted') {
        fe.style.display = '';
        re.style.display = 'none';
        if (bf) bf.classList.add('mem-view-active');
        if (br) br.classList.remove('mem-view-active');
      } else {
        fe.style.display = 'none';
        re.style.display = '';
        if (br) br.classList.add('mem-view-active');
        if (bf) bf.classList.remove('mem-view-active');
      }
    }

    const retrievalHref = (id) => '/retrievals/' + encodeURIComponent(id) + (location.search || '');
    const runHref = (id) => '/runs/' + encodeURIComponent(id) + (location.search || '');
    const sessionHref = (id) => '/sessions/' + encodeURIComponent(id) + (location.search || '');
    const contextHref = (id) => '/context/' + encodeURIComponent(id) + (location.search || '');
    const labelTip = (label, tip) =>
      tip
        ? `<span class="mem-detail-label" title="${escapeHtml(tip)}">${escapeHtml(label)}</span>`
        : `<span class="mem-detail-label">${escapeHtml(label)}</span>`;
    const formatRetrievalDetailReadable = (d) => {
      const line = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        let v = val;
        if (Array.isArray(v)) {
          if (v.length === 0) return '';
          v = v.join(', ');
        } else if (typeof v === 'object') {
          v = JSON.stringify(v);
        }
        return `<div class="mem-detail-field">${labelTip(label, '')}<span class="mem-detail-val">${escapeHtml(String(v))}</span></div>`;
      };
      const lineTip = (label, val, tip) => {
        if (val === undefined || val === null || val === '') return '';
        let v = val;
        if (Array.isArray(v)) {
          if (v.length === 0) return '';
          v = v.join(', ');
        } else if (typeof v === 'object') {
          v = JSON.stringify(v);
        }
        return `<div class="mem-detail-field">${labelTip(label, tip)}<span class="mem-detail-val">${escapeHtml(String(v))}</span></div>`;
      };
      const lineDate = (label, val, tip) => {
        if (val === undefined || val === null || val === '') return '';
        const formatted = formatInstantLocal(val);
        if (!formatted) return '';
        return `<div class="mem-detail-field">${labelTip(label, tip || '')}<span class="mem-detail-val">${escapeHtml(formatted)}</span></div>`;
      };
      const formatRetrievalWhyItem = (w) => {
        if (!w || typeof w !== 'object') return '<p class="muted">Invalid entry</p>';
        const mid = w.memory_id;
        const link = mid
          ? `<a href="${memoryHref(String(mid))}"><code>${escapeHtml(String(mid))}</code></a>`
          : '<span class="muted">—</span>';
        const sc = w && w.score != null && !Number.isNaN(Number(w.score)) ? Number(w.score).toFixed(4) : '—';
        const reason = w && w.reason != null ? escapeHtml(String(w.reason)) : '';
        return `<div class="ret-why-card"><div class="row" style="gap:10px;align-items:baseline;flex-wrap:wrap">${link}<span class="muted" style="font-size:12px">Rank score <strong>${escapeHtml(sc)}</strong> (combined retrieval score)</span></div><p style="margin:8px 0 0 0;font-size:13px;line-height:1.55">${reason}</p></div>`;
      };
      const formatRetrievalExplanation = (ex) => {
        if (!ex || typeof ex !== 'object') return '';
        const mid = ex.memory_id;
        const midLink = mid
          ? `<a href="${memoryHref(String(mid))}"><code>${escapeHtml(String(mid))}</code></a>`
          : '';
        const sc = ex.score != null && !Number.isNaN(Number(ex.score)) ? Number(ex.score).toFixed(4) : '—';
        const st = ex.status ? badge(String(ex.status)) : '';
        const tier = ex.provenance_tier
          ? `<span class="muted" style="font-size:11px">provenance: ${escapeHtml(String(ex.provenance_tier))}</span>`
          : '';
        let html = `<div class="ret-ex-card"><div class="row" style="flex-wrap:wrap;gap:8px;align-items:center">${midLink}<span class="muted" style="font-size:12px">Total score <strong>${escapeHtml(sc)}</strong></span>${st}${tier}</div>`;
        if (ex.why_included) {
          html += `<h5>Why included</h5><div class="mem-detail-body-text" style="margin-top:4px">${escapeHtml(String(ex.why_included))}</div>`;
        }
        const me = ex.matched_evidence || {};
        const lex = me.lexical_terms;
        const sem = me.semantic_terms;
        if ((Array.isArray(lex) && lex.length) || (Array.isArray(sem) && sem.length)) {
          html += `<h5>Matched evidence</h5>`;
          if (Array.isArray(lex) && lex.length) {
            html += `<p class="muted" style="font-size:11px;margin:0 0 4px 0">Lexical overlap (terms shared with the query)</p><div>${lex.map((t) => `<span class="ret-tag">${escapeHtml(String(t))}</span>`).join('')}</div>`;
          }
          if (Array.isArray(sem) && sem.length) {
            html += `<p class="muted" style="font-size:11px;margin:8px 0 4px 0">Semantic overlap (embedding-neighborhood terms)</p><div>${sem.map((t) => `<span class="ret-tag">${escapeHtml(String(t))}</span>`).join('')}</div>`;
          }
        }
        const scs = ex.score_contributions;
        if (scs && typeof scs === 'object' && Object.keys(scs).length) {
          html += `<h5>Score contributions</h5><p class="muted" style="font-size:11px;margin:0 0 6px 0">How much each term contributed to the total (lexical, embedding, priors, memory fields, relations).</p><dl class="ret-dl">`;
          for (const [k, v] of Object.entries(scs)) {
            const disp =
              typeof v === 'number' && !Number.isNaN(v)
                ? escapeHtml(String(v))
                : escapeHtml(JSON.stringify(v));
            html += `<dt>${escapeHtml(k)}</dt><dd>${disp}</dd>`;
          }
          html += `</dl>`;
        }
        const rn = ex.relation_notes;
        if (rn != null && rn !== '') {
          html += `<h5>Relation notes</h5>`;
          if (Array.isArray(rn)) {
            html += '<ul class="mem-detail-list">' + rn.map((x) => `<li>${typeof x === 'object' && x !== null ? escapeHtml(jsonStringifyWithLocalDates(x)) : escapeHtml(String(x))}</li>`).join('') + '</ul>';
          } else {
            html += `<div class="mem-detail-body-text">${escapeHtml(String(rn))}</div>`;
          }
        }
        html += `</div>`;
        return html;
      };
      const formatExcludedList = (exc) => {
        if (!Array.isArray(exc) || !exc.length) return '<p class="muted">None recorded.</p>';
        let h = '';
        for (const e of exc) {
          if (e && typeof e === 'object' && e.memory_id) {
            h += `<div class="ret-why-card ret-why-card--error"><div class="row"><a href="${memoryHref(String(e.memory_id))}"><code>${escapeHtml(String(e.memory_id))}</code></a></div>`;
            h += `<p style="margin:6px 0 0 0;font-size:13px;line-height:1.5">${escapeHtml(String(e.reason || ''))}</p></div>`;
          } else {
            h += `<pre class="mem-detail-inline-pre">${escapeHtml(jsonStringifyWithLocalDates(e))}</pre>`;
          }
        }
        return h;
      };
      const formatAssemblyOrder = (ord) => {
        if (!Array.isArray(ord) || !ord.length) return '<p class="muted">None.</p>';
        return `<ol style="margin:0;padding-left:1.2rem;font-size:13px;line-height:1.6">${ord.map((id) => `<li><a href="${memoryHref(String(id))}"><code>${escapeHtml(String(id))}</code></a></li>`).join('')}</ol>`;
      };

      let meta = '';
      meta += line('Retrieval ID', d.id);
      meta += line('Run ID', d.run_id);
      meta += lineDate(
        'Timestamp',
        d.timestamp,
        'When this retrieval audit was written (ISO instant from the store).'
      );
      if (d.summary) meta += line('Summary', d.summary);
      if (d.reranked !== undefined && d.reranked !== null) {
        meta += lineTip(
          'Reranked',
          String(d.reranked),
          'False if the fast path was used; true if ambiguity required a deeper rerank pass.'
        );
      }
      if (d.gated !== undefined && d.gated !== null) {
        meta += lineTip('Gated', String(d.gated), 'Whether retrieval was skipped or short-circuited (e.g. low content).');
      }
      const sel = d.selected_memory_ids || [];
      const lex = d.lexical_only_selected_memory_ids || [];
      meta += lineTip(
        'Selected count',
        String(sel.length),
        'Number of memories in the final ranked result set (top-k) returned to the caller for this query.'
      );
      meta += lineTip(
        'Lexical-only selected',
        String(lex.length),
        'How many memories would have ranked using lexical overlap alone (diagnostic; overlaps with the main selection).'
      );
      const provBits = [];
      if (d.query_source) provBits.push(String(d.query_source));
      if (d.caller_detail) provBits.push(String(d.caller_detail));
      meta += lineTip(
        'Query provenance',
        provBits.length ? provBits.join(' · ') : 'Not recorded',
        'Which pipeline invoked retrieve() for this audit (e.g. cli, prepare_context, evaluation). This does not by itself say whether a human or an agent typed the string — use caller_detail if your integration passes it. Older audits may omit this field.'
      );

      const glossaryHelp = `<details class="mem-detail-details">
        <summary>Glossary — how sections relate</summary>
        <p class="glossary-hint" style="margin-top:8px;margin-bottom:0"><em>Why these memories</em> is the short per-memory rationale and score. <em>Full scorer explanations</em> (collapsed by default) are the detailed breakdown. <em>Excluded &amp; order</em> lists near-misses and context stitch order.</p>
      </details>`;

      const queryHtml = (d.query && String(d.query).trim())
        ? `<div class="mem-detail-section"><h4 class="mem-detail-h">Query text</h4><div class="mem-detail-body-text">${escapeHtml(d.query)}</div></div>`
        : '';

      const why = d.why;
      let whyHtml = '';
      if (Array.isArray(why) && why.length) {
        whyHtml = `<div class="mem-detail-section"><h4 class="mem-detail-h">Why these memories</h4>
          <p class="muted" style="font-size:12px;margin:0 0 10px 0">One row per selected memory: inclusion rationale and the combined rank score at selection time.</p>`;
        for (const w of why.slice(0, 40)) {
          whyHtml += formatRetrievalWhyItem(w);
        }
        if (why.length > 40) whyHtml += `<p class="muted">… and ${why.length - 40} more</p>`;
        whyHtml += '</div>';
      }

      const selIds = sel.slice(0, 100);
      let selHtml = '';
      if (selIds.length) {
        const selOpen = sel.length <= 10 ? 'open' : '';
        selHtml = `<details class="mem-detail-details" ${selOpen}><summary>Selected memory IDs (${sel.length}) — expand for links</summary><ul class="mem-detail-list" style="margin-top:8px">`;
        for (const mid of selIds) {
          selHtml += `<li><a href="${memoryHref(String(mid))}"><code>${escapeHtml(String(mid))}</code></a></li>`;
        }
        if (sel.length > 100) selHtml += `<li class="muted">… and ${sel.length - 100} more</li>`;
        selHtml += '</ul></details>';
      }

      const expl = d.explanations;
      let explHtml = '';
      if (Array.isArray(expl) && expl.length) {
        explHtml = `<details class="mem-detail-details">
          <summary>Full scorer explanations (${expl.length}) — evidence, contributions, relation notes</summary>
          <p class="muted" style="font-size:12px;margin:10px 0 10px 0">Open when you need the full ranker breakdown. Same memories as above, with numeric detail.</p>`;
        for (const ex of expl.slice(0, 25)) {
          explHtml += formatRetrievalExplanation(ex);
        }
        if (expl.length > 25) explHtml += `<p class="muted">… and ${expl.length - 25} more</p>`;
        explHtml += '</details>';
      }

      const exc = d.excluded || [];
      const ord = d.final_context_assembly_order || [];
      const sideHtml = `<details class="mem-detail-details">
        <summary>Excluded (${exc.length}) &amp; context assembly order (${ord.length})</summary>
        <div class="mem-detail-section" style="margin-top:10px"><h4 class="mem-detail-h">Excluded candidates</h4>
        <p class="muted" style="font-size:12px;margin:0 0 10px 0">Considered but not in the top-k (e.g. no match, contested).</p>
        ${formatExcludedList(exc)}
        </div>
        <div class="mem-detail-section"><h4 class="mem-detail-h" title="Order used when assembling context text for the model">Assembly order</h4>
        <p class="muted" style="font-size:12px;margin:0 0 10px 0">Memory IDs in stitch order for the assembled context.</p>
        ${formatAssemblyOrder(ord)}
        </div>
      </details>`;

      return `<div class="mem-detail-meta">${meta}</div>${queryHtml}${whyHtml}${glossaryHelp}${selHtml}${explHtml}${sideHtml}`;
    };

    function retrievalDetailToggle(which) {
      const fe = document.getElementById('ret-detail-formatted');
      const re = document.getElementById('ret-detail-raw');
      const bf = document.getElementById('ret-detail-btn-formatted');
      const br = document.getElementById('ret-detail-btn-raw');
      if (!fe || !re) return;
      if (which === 'formatted') {
        fe.style.display = '';
        re.style.display = 'none';
        if (bf) bf.classList.add('mem-view-active');
        if (br) br.classList.remove('mem-view-active');
      } else {
        fe.style.display = 'none';
        re.style.display = '';
        if (br) br.classList.add('mem-view-active');
        if (bf) bf.classList.remove('mem-view-active');
      }
    }

    const formatRunDetailReadable = (d) => {
      const line = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        return `<div class="mem-detail-field"><span class="mem-detail-label">${escapeHtml(label)}</span><span class="mem-detail-val">${escapeHtml(
          String(val)
        )}</span></div>`;
      };
      const lineDate = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        const formatted = formatInstantLocal(val);
        if (!formatted) return '';
        return `<div class="mem-detail-field"><span class="mem-detail-label">${escapeHtml(label)}</span><span class="mem-detail-val">${escapeHtml(
          formatted
        )}</span></div>`;
      };
      let meta = '';
      meta += line('Run ID', d.run_id);
      meta += line('Type', d.type);
      meta += `<div class="mem-detail-field"><span class="mem-detail-label">Status</span><span class="mem-detail-val">${badge(
        String(d.status || 'unknown')
      )}</span></div>`;
      meta += lineDate('Started', d.started_at);
      meta += lineDate('Ended', d.ended_at);
      meta = `<div class="mem-detail-meta">${meta}</div>`;

      const warns = Array.isArray(d.warnings) ? d.warnings : [];
      let whtml = '';
      if (warns.length) {
        whtml = `<div class="mem-detail-section"><h4 class="mem-detail-h">Warnings</h4><ul class="mem-detail-list">${warns
          .map((w) => `<li>${escapeHtml(String(w))}</li>`)
          .join('')}</ul></div>`;
      }

      const phases = Array.isArray(d.phase_traces) ? d.phase_traces : [];
      let phaseHtml = '';
      if (phases.length) {
        phaseHtml = `<details class="mem-detail-details"><summary>Phase timeline (${phases.length})</summary><ol style="margin:8px 0 0 1.1rem;font-size:13px;line-height:1.55">`;
        for (const p of phases) {
          const one =
            typeof p === 'object' && p !== null ? jsonStringifyWithLocalDates(p) : String(p);
          const clipped = one.length > 1200 ? one.slice(0, 1200) + '\\n…' : one;
          phaseHtml += `<li><pre class="mem-detail-inline-pre" style="margin:6px 0">${escapeHtml(clipped)}</pre></li>`;
        }
        phaseHtml += '</ol></details>';
      }

      const ops = Array.isArray(d.operations) ? d.operations : [];
      const opsHtml = `<details class="mem-detail-details"><summary>Op log (${ops.length}) — structured operations</summary><pre class="mem-detail-inline-pre" style="margin-top:8px">${escapeHtml(
        jsonStringifyWithLocalDates(ops)
      )}</pre></details>`;

      const diff = d.diff_text != null ? String(d.diff_text) : '';
      const diffHtml = `<details class="mem-detail-details"><summary>Diff</summary><pre style="margin-top:8px;white-space:pre-wrap;word-break:break-word;font-size:12px;line-height:1.45">${escapeHtml(
        diff || 'No diff artifact.'
      )}</pre></details>`;

      return `${meta}${whtml}${phaseHtml}${opsHtml}${diffHtml}`;
    };

    function runDetailToggle(which) {
      const fe = document.getElementById('run-detail-formatted');
      const re = document.getElementById('run-detail-raw');
      const bf = document.getElementById('run-detail-btn-formatted');
      const br = document.getElementById('run-detail-btn-raw');
      if (!fe || !re) return;
      if (which === 'formatted') {
        fe.style.display = '';
        re.style.display = 'none';
        if (bf) bf.classList.add('mem-view-active');
        if (br) br.classList.remove('mem-view-active');
      } else {
        fe.style.display = 'none';
        re.style.display = '';
        if (br) br.classList.add('mem-view-active');
        if (bf) bf.classList.remove('mem-view-active');
      }
    }

    const sessionLastInstant = (item) => {
      let best = '';
      for (const ev of item.timeline || []) {
        const t = ev && ev.timestamp != null ? String(ev.timestamp) : '';
        if (t && (!best || t > best)) best = t;
      }
      return best;
    };

    const buildSessionTimelineFromDetail = (detail) => {
      const timeline = Array.isArray(detail.timeline) ? detail.timeline : [];
      const sorted = [...timeline].sort((a, b) => {
        const ta = new Date(a.timestamp || 0).getTime();
        const tb = new Date(b.timestamp || 0).getTime();
        return ta - tb;
      });
      let lastDay = '';
      const parts = [];
      const sid = detail.session_id != null ? String(detail.session_id) : '';
      parts.push(
        `<p class="muted" style="margin:0 0 10px 0">Session <code>${escapeHtml(sid)}</code> · ${sorted.length} event(s), chronological.</p>`
      );
      for (const ev of sorted) {
        const rawTs = ev.timestamp != null ? String(ev.timestamp) : '';
        const d = new Date(rawTs || '');
        const hasTime = !Number.isNaN(d.getTime());
        const dayKey = hasTime
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : '_nodate';
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dayLabel = hasTime
            ? d.toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No date';
          parts.push(`<div class="mem-timeline-day">${escapeHtml(dayLabel)}</div>`);
        }
        const timeStr = hasTime
          ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          : '—';
        const kind = ev.kind != null ? String(ev.kind) : '';
        const label = ev.label != null ? String(ev.label) : '';
        let linkExtra = '';
        if (kind === 'memory.context.assembled' && ev.object_id) {
          linkExtra = ` · <a href="${contextHref(String(ev.object_id))}">Open context</a>`;
        }
        const payload =
          ev.payload !== undefined && ev.payload !== null
            ? jsonStringifyWithLocalDates(ev.payload)
            : '{}';
        const clipped = payload.length > 8000 ? payload.slice(0, 8000) + '\\n…' : payload;
        parts.push(`<div class="mem-timeline-item">
          <div class="mem-timeline-time"><p>${escapeHtml(timeStr)}</p></div>
          <div class="mem-timeline-rail">
            <div class="mem-timeline-dot"></div>
            <div class="mem-timeline-bar" style="height:44px;background:hsl(${memoryTypeHue(kind)} 45% 40%);"></div>
          </div>
          <div class="mem-timeline-body">
            <div class="t-meta"><span class="muted" style="font-size:11px">${escapeHtml(kind)}</span>${linkExtra}</div>
            <div class="t-title">${escapeHtml(label)}${
              ev.object_id
                ? ` <span class="muted" style="font-size:11px"><code>${escapeHtml(String(ev.object_id))}</code></span>`
                : ''
            }</div>
            <details class="mem-detail-details" style="margin-top:6px"><summary>Payload</summary><pre class="mem-detail-inline-pre" style="margin-top:6px">${escapeHtml(
              clipped
            )}</pre></details>
          </div>
        </div>`);
      }
      return (
        `<div class="table-scroll"><div class="mem-timeline">` +
        (parts.join('') || '<p class="muted">No timeline events.</p>') +
        `</div></div>`
      );
    };

    const formatContextDetailReadable = (data) => {
      let meta = '';
      meta += `<div class="mem-detail-field"><span class="mem-detail-label">Context ID</span><span class="mem-detail-val"><code>${escapeHtml(
        String(data.context_id || '')
      )}</code></span></div>`;
      meta = `<div class="mem-detail-meta">${meta}</div>`;

      const sel = data.selected_memory_ids || [];
      let selHtml = '<div class="mem-detail-section"><h4 class="mem-detail-h">Selected memories</h4>';
      if (!sel.length) selHtml += '<p class="muted">None listed.</p>';
      else {
        selHtml += '<ol style="margin:0;padding-left:1.2rem;line-height:1.6;font-size:13px">';
        for (const mid of sel.slice(0, 200)) {
          selHtml += `<li><a href="${memoryHref(String(mid))}"><code>${escapeHtml(String(mid))}</code></a></li>`;
        }
        selHtml += '</ol>';
        if (sel.length > 200) selHtml += `<p class="muted">… and ${sel.length - 200} more</p>`;
      }
      selHtml += '</div>';

      const om = data.omission_reasons;
      let omitHtml = '<div class="mem-detail-section"><h4 class="mem-detail-h">Omission reasons</h4>';
      if (om && typeof om === 'object' && !Array.isArray(om) && Object.keys(om).length) {
        omitHtml += `<pre class="mem-detail-inline-pre">${escapeHtml(jsonStringifyWithLocalDates(om))}</pre>`;
      } else if (Array.isArray(om) && om.length) {
        omitHtml +=
          '<ul class="mem-detail-list">' +
          om
            .map((x) => {
              const s =
                typeof x === 'object' && x !== null ? jsonStringifyWithLocalDates(x) : String(x);
              return `<li><pre class="mem-detail-inline-pre">${escapeHtml(s)}</pre></li>`;
            })
            .join('') +
          '</ul>';
      } else {
        omitHtml += '<p class="muted">None recorded.</p>';
      }
      omitHtml += '</div>';

      const snap = data.startup_index_snapshot;
      let snapHtml = '<div class="mem-detail-section"><h4 class="mem-detail-h">Startup snapshot</h4>';
      if (snap && typeof snap === 'object' && Object.keys(snap).length) {
        snapHtml += `<details class="mem-detail-details"><summary>JSON (dates localized)</summary><pre class="mem-detail-inline-pre" style="margin-top:8px">${escapeHtml(
          jsonStringifyWithLocalDates(snap)
        )}</pre></details>`;
      } else {
        snapHtml += '<p class="muted">Not captured.</p>';
      }
      snapHtml += '</div>';

      return `${meta}${selHtml}${omitHtml}${snapHtml}`;
    };

    function contextDetailToggle(which) {
      const fe = document.getElementById('ctx-detail-formatted');
      const re = document.getElementById('ctx-detail-raw');
      const bf = document.getElementById('ctx-detail-btn-formatted');
      const br = document.getElementById('ctx-detail-btn-raw');
      if (!fe || !re) return;
      if (which === 'formatted') {
        fe.style.display = '';
        re.style.display = 'none';
        if (bf) bf.classList.add('mem-view-active');
        if (br) br.classList.remove('mem-view-active');
      } else {
        fe.style.display = 'none';
        re.style.display = '';
        if (br) br.classList.add('mem-view-active');
        if (bf) bf.classList.remove('mem-view-active');
      }
    }

    async function renderOverview() {
      const data = await fetchJson('/api/overview');
      const contestedN = Number(data.contested_memories) || 0;
      const memTotal = Number(data.memory_counts && data.memory_counts.total) || 0;
      const contestedCallout =
        contestedN > 0
          ? `<p class="glossary-hint" style="margin-top:12px;margin-bottom:0"><strong>${contestedN}</strong> contested memory record(s) may need review before agents should rely on them. <a href="/memories?status=contested">Open Memories (contested)</a> to triage.</p>`
          : '';
      const emptyNext =
        memTotal === 0
          ? `<div class="od-empty-nextsteps glossary-hint" role="status"><strong>No memories indexed yet.</strong> From your workspace directory (see project README):<pre class="mem-detail-inline-pre">opendream observe index --workspace "$PWD"
opendream observe serve --workspace "$PWD" --port 8000</pre>Open <code>/overview</code> on the same machine after capture. To consolidate durable memory from events, run <code>opendream maintain --workspace "$PWD"</code>.</div>`
          : '';
      const parts = [];
      if (memTotal === 0) parts.push(panel('Get started', emptyNext, true));
      parts.push(
        panel('Store Health', `
          <div class="metric"><div class="label">State</div><div class="value">${data.store_health.lock.present ? 'Locked' : 'Ready'}</div></div>
          <div class="metric"><div class="label">Memory Root</div><div class="value" style="font-size:16px">${data.store_health.memory_root}</div></div>
          <div class="metric"><div class="label">Contested</div><div class="value">${data.contested_memories}</div></div>
          ${contestedCallout}
        `),
        panel('Counts', `
          <div class="metric"><div class="label">Total Memories</div><div class="value">${data.memory_counts.total}</div></div>
          <div class="metric"><div class="label">Startup Entries</div><div class="value">${data.startup_index.entries}</div></div>
          <div class="metric"><div class="label">Retrieval Hit Rate</div><div class="value">${data.retrievals.total ? Math.round((data.retrievals.successful / data.retrievals.total) * 100) + '%' : '0%'}</div></div>
          <p class="muted" style="margin-top:12px;margin-bottom:0;font-size:12px">Read API: <code>${location.origin}/api/overview</code>
            <button type="button" class="icon-btn od-api-copy-btn" data-api-method="GET" data-api-path="/api/overview" onclick="odCopyApiUrl(this)" aria-label="Copy overview API request" title="Copy API URL"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
          </p>
        `),
        panel('Recent Runs', `<table><caption class="sr-only">Recent consolidation runs</caption><thead><tr><th scope="col">ID</th><th scope="col">Status</th><th scope="col">Type</th></tr></thead><tbody>${data.recent_runs.map(run => `<tr><td><a href="/runs/${run.run_id}">${run.run_id}</a></td><td>${run.status || ''}</td><td>${run.type}</td></tr>`).join('')}</tbody></table>`, true),
        panel('Recent Sessions', `<p class="muted" style="margin:0 0 10px 0">Session timelines and context IDs: see <a href="/sessions">Sessions</a> and <a href="/context">Context</a>.</p><table><caption class="sr-only">Recent capture sessions</caption><thead><tr><th scope="col">Session</th><th scope="col">Events</th><th scope="col">Ended</th></tr></thead><tbody>${data.recent_sessions.map(session => `<tr><td><a href="/sessions/${session.session_id}">${session.session_id}</a></td><td>${session.event_count}</td><td>${session.ended_at ? escapeHtml(formatInstantLocal(session.ended_at)) : ''}</td></tr>`).join('')}</tbody></table>`, true),
        panel('Fidelity Diagnostics', `<div class="split"><div>${pretty(data.signal_coverage)}</div><div>${pretty(data.activation_diagnostics)}</div></div>`, true),
      );
      app.innerHTML = parts.join('');
    }

    async function renderMemories(memoryId=null) {
      const params = new URLSearchParams(location.search);
      const q = (k, d='') => params.get(k) || d;
      const search = q('search');
      const type = q('type');
      const scope = q('scope');
      const status = q('status');
      const sort = q('sort', 'updated_at');
      const sortDir = q('sort_dir');
      const offset = q('offset', '0');
      const limit = q('limit', '50');
      const salienceMin = q('salience_min');
      const salienceMax = q('salience_max');
      const confidenceMin = q('confidence_min');
      const confidenceMax = q('confidence_max');
      const updatedAfter = q('updated_after');
      const updatedBefore = q('updated_before');
      const createdAfter = q('created_after');
      const createdBefore = q('created_before');
      const view = q('view', '');
      const isTimeline = view !== 'table';
      const apiParams = {};
      if (search) apiParams.search = search;
      if (type) apiParams.type = type;
      if (scope) apiParams.scope = scope;
      if (status) apiParams.status = status;
      apiParams.sort = sort;
      if (sortDir) apiParams.sort_dir = sortDir;
      apiParams.offset = offset;
      apiParams.limit = limit;
      if (salienceMin) apiParams.salience_min = salienceMin;
      if (salienceMax) apiParams.salience_max = salienceMax;
      if (confidenceMin) apiParams.confidence_min = confidenceMin;
      if (confidenceMax) apiParams.confidence_max = confidenceMax;
      if (updatedAfter) apiParams.updated_after = updatedAfter;
      if (updatedBefore) apiParams.updated_before = updatedBefore;
      if (createdAfter) apiParams.created_after = createdAfter;
      if (createdBefore) apiParams.created_before = createdBefore;
      const data = await fetchJson('/api/memories?' + qs(apiParams));
      const total = data.total;
      const off = parseInt(offset, 10) || 0;
      const lim = parseInt(limit, 10) || 50;
      const startIdx = total === 0 ? 0 : off + 1;
      const endIdx = off + data.items.length;
      const prevOff = Math.max(0, off - lim);
      const nextOff = off + lim;
      const hasPrev = off > 0;
      const hasNext = nextOff < total;
      const optSel = (val, cur) => (val === cur ? 'selected' : '');
      const memTypes = ['semantic_fact','procedural_workflow','user_preference','project_decision','environment_requirement','anti_pattern','pending_item','contested_fact','superseded_record'];
      const memScopes = ['user','project','agent','workspace','global'];
      const memStatuses = ['active','contested','superseded','quarantined','deleted'];
      const sortFields = [
        ['updated_at','Updated'],
        ['created_at','Created'],
        ['title','Title'],
        ['memory_id','ID'],
        ['type','Type'],
        ['scope','Scope'],
        ['status','Status'],
        ['salience','Salience'],
        ['confidence','Confidence'],
        ['retrieval_frequency','Retrievals'],
      ];
      const typeOpts = '<option value="">any type</option>' + memTypes.map(t => `<option value="${t}" ${optSel(t, type)}>${t}</option>`).join('');
      const scopeOpts = '<option value="">any scope</option>' + memScopes.map(s => `<option value="${s}" ${optSel(s, scope)}">${s}</option>`).join('');
      const statusOpts = '<option value="">any status</option>' + memStatuses.map(s => `<option value="${s}" ${optSel(s, status)}">${s}</option>`).join('');
      const sortOpts = sortFields.map(([v, lab]) => `<option value="${v}" ${optSel(v, sort)}>${lab}</option>`).join('');
      const dirAsc = sortDir === 'asc' ? 'selected' : '';
      const dirDesc = sortDir === 'desc' ? 'selected' : '';
      const dirDefault = !sortDir ? 'selected' : '';
      const lim25 = optSel('25', String(lim));
      const lim50 = optSel('50', String(lim));
      const lim100 = optSel('100', String(lim));
      let detailHtml = '<p class="muted">Select a memory record.</p>';
      if (memoryId) {
        const detail = await fetchJson('/api/memories/' + encodeURIComponent(memoryId));
        const readable = formatMemoryDetailReadable(detail);
        detailHtml = `
          <div class="row"><strong>${escapeHtml(detail.title || '')}</strong>${badge(detail.status)}</div>
          <p>${escapeHtml(detail.summary || '')}</p>
          <p class="muted">Sources: ${escapeHtml((detail.source_event_ids || []).join(', ') || 'none')}</p>
          <div class="mem-view-toggle mem-detail-toggle icon-toolbar" role="group" aria-label="Memory detail format">
            <button type="button" id="mem-detail-btn-formatted" class="icon-btn mem-view-active" onclick="memoryDetailToggle('formatted')" aria-label="Formatted detail" title="Formatted">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button type="button" id="mem-detail-btn-raw" class="icon-btn" onclick="memoryDetailToggle('raw')" aria-label="Raw JSON" title="Raw JSON">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            </button>
          </div>
          <div id="mem-detail-formatted" class="mem-detail-body">${readable}</div>
          <div id="mem-detail-raw" class="mem-detail-body" style="display:none">
            <div class="split">
              <div>${pretty(detail.raw_json)}</div>
              <div>${pretty({lineage: detail.lineage, annotations: detail.annotations, manual_reviews: detail.manual_reviews})}</div>
            </div>
          </div>
          <p class="muted" style="margin-top:10px;font-size:12px">Read API: <code>${location.origin}/api/memories/${encodeURIComponent(memoryId)}</code>
            <button type="button" class="icon-btn od-api-copy-btn" data-api-method="GET" data-api-path="/api/memories/${encodeURIComponent(memoryId)}" onclick="odCopyApiUrl(this)" aria-label="Copy memory API URL" title="Copy API URL"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
          </p>`;
      }
      const rows = data.items.map(item => {
        const sal = item.salience != null && item.salience !== '' ? Number(item.salience).toFixed(2) : '—';
        const conf = item.confidence != null && item.confidence !== '' ? Number(item.confidence).toFixed(2) : '—';
        const rf = item.retrieval_frequency != null ? String(item.retrieval_frequency) : '0';
        return `<tr>
          <td><a href="${memoryHref(item.memory_id)}">${escapeHtml(item.title || '')}</a></td>
          <td>${badge(item.status)}</td>
          <td>${escapeHtml(item.type || '')}</td>
          <td>${escapeHtml(item.scope || '')}</td>
          <td class="num">${escapeHtml(sal)}</td>
          <td class="num">${escapeHtml(conf)}</td>
          <td class="num">${escapeHtml(rf)}</td>
          <td>${escapeHtml(item.updated_at || '')}</td>
        </tr>`;
      }).join('');
      app.innerHTML = [
        panel('Memory Explorer', `
          <form class="memories-toolbar" id="memories-filter-form" onsubmit="event.preventDefault(); const f=this; const p = memoryExplorerParams({
            search: f.search.value,
            type: f.type.value,
            scope: f.scope.value,
            status: f.status.value,
            sort: f.sort.value,
            sort_dir: f.sort_dir.value,
            limit: f.limit.value,
            salience_min: f.salience_min.value,
            salience_max: f.salience_max.value,
            confidence_min: f.confidence_min.value,
            confidence_max: f.confidence_max.value,
            updated_after: datetimeLocalToIsoUtc(f.updated_after.value),
            updated_before: datetimeLocalToIsoUtc(f.updated_before.value),
            created_after: datetimeLocalToIsoUtc(f.created_after.value),
            created_before: datetimeLocalToIsoUtc(f.created_before.value),
            offset: '0',
            view: (f.mem_view && f.mem_view.value) ? f.mem_view.value : ''
          }); location.search = p.toString() ? '?' + p.toString() : '';">
            <input type="hidden" name="mem_view" value="${view === 'table' ? 'table' : ''}">
            <div class="row" style="align-items:flex-end">
              <label style="display:flex;flex-direction:column;gap:4px;min-width:180px;flex:1"><span class="muted" style="font-size:11px">Search</span>
                <input name="search" type="search" placeholder="title, summary, body, id" value="${escapeHtml(search)}"></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Type</span>
                <select name="type">${typeOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Scope</span>
                <select name="scope">${scopeOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Status</span>
                <select name="status">${statusOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Sort</span>
                <select name="sort">${sortOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Dir</span>
                <select name="sort_dir">
                  <option value="" ${dirDefault}>default</option>
                  <option value="asc" ${dirAsc}>asc</option>
                  <option value="desc" ${dirDesc}>desc</option>
                </select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Page size</span>
                <select name="limit">
                  <option value="25" ${lim25}>25</option>
                  <option value="50" ${lim50}>50</option>
                  <option value="100" ${lim100}>100</option>
                </select></label>
              <button type="submit" class="icon-btn" aria-label="Apply filters" title="Apply filters">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
            <div class="row" style="align-items:center;margin-top:4px">
              <span class="muted" style="font-size:11px">Updated time window:</span>
              <button type="button" class="icon-btn" onclick="applyMemoryTimePreset(24)" aria-label="Last 24 hours" title="Last 24 hours">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><span class="sr-only">24h</span>
              </button>
              <button type="button" class="icon-btn" onclick="applyMemoryTimePreset(168)" aria-label="Last 7 days" title="Last 7 days">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg><span class="sr-only">7d</span>
              </button>
            </div>
            <details>
              <summary>Advanced filters (salience, confidence, time)</summary>
              <p class="muted" style="font-size:12px;margin:8px 0 0 0">Date and time pickers use <strong>your browser timezone</strong>. Shared links still store UTC (<code>…Z</code>) in the URL so filters stay stable.</p>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Salience min</span>
                  <input name="salience_min" type="number" step="0.01" min="0" max="1" placeholder="0–1" value="${escapeHtml(salienceMin)}"></label>
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Salience max</span>
                  <input name="salience_max" type="number" step="0.01" min="0" max="1" placeholder="0–1" value="${escapeHtml(salienceMax)}"></label>
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Confidence min</span>
                  <input name="confidence_min" type="number" step="0.01" min="0" max="1" placeholder="0–1" value="${escapeHtml(confidenceMin)}"></label>
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Confidence max</span>
                  <input name="confidence_max" type="number" step="0.01" min="0" max="1" placeholder="0–1" value="${escapeHtml(confidenceMax)}"></label>
              </div>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Updated on or after</span>
                  <input name="updated_after" type="datetime-local" step="60" title="Local date and time; applied as UTC instant to the server filter" value="${escapeHtml(isoUtcToDatetimeLocal(updatedAfter))}"></label>
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Updated on or before</span>
                  <input name="updated_before" type="datetime-local" step="60" title="Local date and time; applied as UTC instant to the server filter" value="${escapeHtml(isoUtcToDatetimeLocal(updatedBefore))}"></label>
              </div>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Created on or after</span>
                  <input name="created_after" type="datetime-local" step="60" title="Local date and time; applied as UTC instant to the server filter" value="${escapeHtml(isoUtcToDatetimeLocal(createdAfter))}"></label>
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Created on or before</span>
                  <input name="created_before" type="datetime-local" step="60" title="Local date and time; applied as UTC instant to the server filter" value="${escapeHtml(isoUtcToDatetimeLocal(createdBefore))}"></label>
              </div>
            </details>
          </form>
          ${total === 0 ? '<div class="od-empty-nextsteps glossary-hint" role="status">No rows match your filters, or the store is empty. New workspace: <code>opendream observe index --workspace "$PWD"</code>, capture events, then <code>opendream maintain --workspace "$PWD"</code>. See <a href="/overview">Overview</a>.</div>' : ''}
          <div class="row" style="align-items:center;justify-content:space-between;flex-wrap:wrap;margin:10px 0 8px 0;gap:10px">
            <p class="muted" style="margin:0">Showing <strong>${startIdx}</strong>–<strong>${endIdx}</strong> of <strong>${total}</strong></p>
            <div class="mem-view-toggle icon-toolbar" role="group" aria-label="Result layout">
              <button type="button" class="icon-btn ${view === 'table' ? 'mem-view-active' : ''}" title="Table layout" aria-label="Table layout"
                onclick="(() => { const p = memoryExplorerParams({ view: 'table' }); location.search = '?' + p.toString(); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              </button>
              <button type="button" class="icon-btn ${isTimeline ? 'mem-view-active' : ''}" title="Timeline layout" aria-label="Timeline layout"
                onclick="(() => { const p = memoryExplorerParams({ view: '' }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
              </button>
            </div>
          </div>
          ${isTimeline ? `<p class="muted" style="font-size:12px;margin:0 0 10px 0">Timeline uses the same filters and pagination as the table. Items on this page are shown <strong>newest first</strong> and grouped by local day (by <code>updated_at</code>).</p>` : ''}
          ${isTimeline
            ? `<div class="table-scroll"><div class="mem-timeline">${buildMemoryTimelineHtml(data.items, search)}</div></div>`
            : `<div class="table-scroll">
            <table class="memories-table"><caption class="sr-only">Memory records matching current filters</caption><thead><tr>
              <th scope="col">Title</th><th scope="col">Status</th><th scope="col">Type</th><th scope="col">Scope</th>
              <th class="num" scope="col">Salience</th><th class="num" scope="col">Confidence</th><th class="num" scope="col">Retr.</th><th scope="col">Updated</th>
            </tr></thead><tbody>
              ${rows || '<tr><td colspan="8" class="muted">No memories match.</td></tr>'}
            </tbody></table>
          </div>`}
          <div class="pager">
            <button type="button" class="icon-btn" ${hasPrev ? '' : 'disabled'} aria-label="Previous page" title="Previous"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${prevOff}) }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <button type="button" class="icon-btn" ${hasNext ? '' : 'disabled'} aria-label="Next page" title="Next"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${nextOff}) }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
            <span class="muted">offset ${off}, limit ${lim}</span>
          </div>
        `, false, 'mem-explorer'),
        panel('Memory Detail', detailHtml, false, 'mem-detail'),
      ].join('');
    }

    async function renderRuns(runId=null) {
      const params = new URLSearchParams(location.search);
      const q = (k, d='') => params.get(k) || d;
      const search = q('search');
      const sort = q('sort', 'ended_at');
      const sortDir = q('sort_dir');
      const offset = q('offset', '0');
      const limit = q('limit', '50');
      const endedAfter = q('ended_after');
      const endedBefore = q('ended_before');
      const view = q('view', '');
      const isTimeline = view !== 'table';
      const apiParams = {};
      if (search) apiParams.search = search;
      apiParams.sort = sort;
      if (sortDir) apiParams.sort_dir = sortDir;
      apiParams.offset = offset;
      apiParams.limit = limit;
      if (endedAfter) apiParams.ended_after = endedAfter;
      if (endedBefore) apiParams.ended_before = endedBefore;
      const data = await fetchJson('/api/runs?' + qs(apiParams));
      const total = data.total;
      const off = parseInt(offset, 10) || 0;
      const lim = parseInt(limit, 10) || 50;
      const startIdx = total === 0 ? 0 : off + 1;
      const endIdx = off + data.items.length;
      const prevOff = Math.max(0, off - lim);
      const nextOff = off + lim;
      const hasPrev = off > 0;
      const hasNext = nextOff < total;
      const optSel = (val, cur) => (val === cur ? 'selected' : '');
      const sortFields = [
        ['ended_at', 'Ended'],
        ['started_at', 'Started'],
        ['run_id', 'Run ID'],
        ['type', 'Type'],
        ['status', 'Status'],
      ];
      const sortOpts = sortFields.map(([v, lab]) => `<option value="${v}" ${optSel(v, sort)}>${lab}</option>`).join('');
      const dirAsc = sortDir === 'asc' ? 'selected' : '';
      const dirDesc = sortDir === 'desc' ? 'selected' : '';
      const dirDefault = !sortDir ? 'selected' : '';
      const lim25 = optSel('25', String(lim));
      const lim50 = optSel('50', String(lim));
      const lim100 = optSel('100', String(lim));
      let detailHtml = '<p class="muted">Select a run.</p>';
      if (runId) {
        const detail = await fetchJson('/api/runs/' + encodeURIComponent(runId));
        const readable = formatRunDetailReadable(detail);
        detailHtml = `
          <div class="row" style="flex-wrap:wrap;gap:8px;align-items:center">
            <strong title="Run id">${escapeHtml(String(detail.run_id || ''))}</strong>
            <span class="muted">${escapeHtml(String(detail.type || ''))}</span>
            ${badge(String(detail.status || 'unknown'))}
          </div>
          <div class="mem-view-toggle mem-detail-toggle icon-toolbar" role="group" aria-label="Run detail format">
            <button type="button" id="run-detail-btn-formatted" class="icon-btn mem-view-active" onclick="runDetailToggle('formatted')" aria-label="Formatted detail" title="Formatted">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button type="button" id="run-detail-btn-raw" class="icon-btn" onclick="runDetailToggle('raw')" aria-label="Raw JSON" title="Raw JSON">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            </button>
          </div>
          <div id="run-detail-formatted" class="mem-detail-body">${readable}</div>
          <div id="run-detail-raw" class="mem-detail-body" style="display:none">${pretty(detail)}</div>`;
      }
      const rows = data.items
        .map((run) => {
          const t = formatInstantLocal(runEffectiveInstant(run));
          const rid = String(run.run_id || '');
          return `<tr>
          <td title="Effective sort time (ended_at, else started_at)">${escapeHtml(t || '—')}</td>
          <td title="${escapeHtml(rid)}">${escapeHtml(String(run.type || ''))}</td>
          <td>${badge(String(run.status || 'unknown'))}</td>
          <td class="muted" style="font-size:12px"><a href="${runHref(rid)}" title="${escapeHtml(rid)}">${escapeHtml(rid)}</a></td>
        </tr>`;
        })
        .join('');
      app.innerHTML = [
        panel(
          'Runs',
          `
          <form class="memories-toolbar" id="runs-filter-form" onsubmit="event.preventDefault(); const f=this; const p = memoryExplorerParams({
            search: f.search.value,
            sort: f.sort.value,
            sort_dir: f.sort_dir.value,
            limit: f.limit.value,
            ended_after: datetimeLocalToIsoUtc(f.ended_after.value),
            ended_before: datetimeLocalToIsoUtc(f.ended_before.value),
            offset: '0',
            view: f.list_view ? f.list_view.value : ''
          }); location.search = p.toString() ? '?' + p.toString() : '';">
            <input type="hidden" name="list_view" value="${view === 'table' ? 'table' : ''}">
            <div class="row" style="align-items:flex-end">
              <label style="display:flex;flex-direction:column;gap:4px;min-width:180px;flex:1"><span class="muted" style="font-size:11px">Search</span>
                <input name="search" type="search" placeholder="run id, type, status" value="${escapeHtml(search)}"></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Sort</span>
                <select name="sort">${sortOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Dir</span>
                <select name="sort_dir">
                  <option value="" ${dirDefault}>default</option>
                  <option value="asc" ${dirAsc}>asc</option>
                  <option value="desc" ${dirDesc}>desc</option>
                </select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Page size</span>
                <select name="limit">
                  <option value="25" ${lim25}>25</option>
                  <option value="50" ${lim50}>50</option>
                  <option value="100" ${lim100}>100</option>
                </select></label>
              <button type="submit" class="icon-btn" aria-label="Apply filters" title="Apply filters">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
            <div class="row" style="align-items:center;margin-top:4px">
              <span class="muted" style="font-size:11px">Run time window (ended_at, else started_at):</span>
              <button type="button" class="icon-btn" onclick="applyRunTimePreset(24)" aria-label="Last 24 hours" title="Last 24 hours">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><span class="sr-only">24h</span>
              </button>
              <button type="button" class="icon-btn" onclick="applyRunTimePreset(168)" aria-label="Last 7 days" title="Last 7 days">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg><span class="sr-only">7d</span>
              </button>
            </div>
            <details>
              <summary>Advanced filters (time bounds)</summary>
              <p class="muted" style="font-size:12px;margin:8px 0 0 0">Pickers use <strong>your local timezone</strong>; the URL stores UTC instants. Bounds apply to <code>ended_at</code> when set, otherwise <code>started_at</code>.</p>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Ended / effective on or after</span>
                  <input name="ended_after" type="datetime-local" step="60" title="Local time; filter is UTC instant" value="${escapeHtml(isoUtcToDatetimeLocal(endedAfter))}"></label>
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Ended / effective on or before</span>
                  <input name="ended_before" type="datetime-local" step="60" title="Local time; filter is UTC instant" value="${escapeHtml(isoUtcToDatetimeLocal(endedBefore))}"></label>
              </div>
            </details>
          </form>
          ${total === 0 ? '<div class="od-empty-nextsteps glossary-hint" role="status">No runs indexed yet, or none match your filters. Run <code>opendream observe index --workspace "$PWD"</code> and refresh.</div>' : ''}
          <div class="row" style="align-items:center;justify-content:space-between;flex-wrap:wrap;margin:10px 0 8px 0;gap:10px">
            <p class="muted" style="margin:0">Showing <strong>${startIdx}</strong>–<strong>${endIdx}</strong> of <strong>${total}</strong></p>
            <div class="mem-view-toggle icon-toolbar" role="group" aria-label="Run list layout">
              <button type="button" class="icon-btn ${view === 'table' ? 'mem-view-active' : ''}" title="Table layout" aria-label="Table layout"
                onclick="(() => { const p = memoryExplorerParams({ view: 'table' }); location.search = '?' + p.toString(); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              </button>
              <button type="button" class="icon-btn ${isTimeline ? 'mem-view-active' : ''}" title="Timeline layout" aria-label="Timeline layout"
                onclick="(() => { const p = memoryExplorerParams({ view: '' }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
              </button>
            </div>
          </div>
          ${isTimeline ? `<p class="muted" style="font-size:12px;margin:0 0 10px 0">Timeline matches filters and pagination. <strong>Newest first</strong>, grouped by local day (effective end/start time).</p>` : ''}
          ${isTimeline
            ? `<div class="table-scroll"><div class="mem-timeline">${buildRunTimelineHtml(data.items, search)}</div></div>`
            : `<div class="table-scroll">
            <table class="memories-table"><caption class="sr-only">Runs matching current filters</caption><thead><tr>
              <th scope="col" title="ended_at when present, otherwise started_at (local)">Time</th>
              <th scope="col" title="consolidation, dream, …">Type</th>
              <th scope="col">Status</th>
              <th scope="col" title="Stable run id">ID</th>
            </tr></thead><tbody>
              ${rows || '<tr><td colspan="4" class="muted">No runs match.</td></tr>'}
            </tbody></table>
          </div>`}
          <div class="pager">
            <button type="button" class="icon-btn" ${hasPrev ? '' : 'disabled'} aria-label="Previous page" title="Previous"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${prevOff}) }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <button type="button" class="icon-btn" ${hasNext ? '' : 'disabled'} aria-label="Next page" title="Next"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${nextOff}) }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
            <span class="muted">offset ${off}, limit ${lim}</span>
          </div>
        `,
          false,
          'runs-explorer',
        ),
        panel('Consolidation Inspector', detailHtml, false, 'runs-detail'),
      ].join('');
    }

    async function renderRetrievals(retrievalId=null) {
      const params = new URLSearchParams(location.search);
      const q = (k, d='') => params.get(k) || d;
      const search = q('search');
      const sort = q('sort', 'timestamp');
      const sortDir = q('sort_dir');
      const offset = q('offset', '0');
      const limit = q('limit', '50');
      const timestampAfter = q('timestamp_after');
      const timestampBefore = q('timestamp_before');
      const minSelected = q('min_selected');
      const maxSelected = q('max_selected');
      const view = q('view', '');
      const isTimeline = view !== 'table';
      const apiParams = {};
      if (search) apiParams.search = search;
      apiParams.sort = sort;
      if (sortDir) apiParams.sort_dir = sortDir;
      apiParams.offset = offset;
      apiParams.limit = limit;
      if (timestampAfter) apiParams.timestamp_after = timestampAfter;
      if (timestampBefore) apiParams.timestamp_before = timestampBefore;
      if (minSelected) apiParams.min_selected = minSelected;
      if (maxSelected) apiParams.max_selected = maxSelected;
      const data = await fetchJson('/api/retrievals?' + qs(apiParams));
      const total = data.total;
      const off = parseInt(offset, 10) || 0;
      const lim = parseInt(limit, 10) || 50;
      const startIdx = total === 0 ? 0 : off + 1;
      const endIdx = off + data.items.length;
      const prevOff = Math.max(0, off - lim);
      const nextOff = off + lim;
      const hasPrev = off > 0;
      const hasNext = nextOff < total;
      const optSel = (val, cur) => (val === cur ? 'selected' : '');
      const sortFields = [
        ['timestamp', 'Time'],
        ['id', 'ID'],
        ['query', 'Query'],
        ['selected_count', 'Selected count'],
      ];
      const sortOpts = sortFields.map(([v, lab]) => `<option value="${v}" ${optSel(v, sort)}>${lab}</option>`).join('');
      const dirAsc = sortDir === 'asc' ? 'selected' : '';
      const dirDesc = sortDir === 'desc' ? 'selected' : '';
      const dirDefault = !sortDir ? 'selected' : '';
      const lim25 = optSel('25', String(lim));
      const lim50 = optSel('50', String(lim));
      const lim100 = optSel('100', String(lim));
      let detailHtml = '<p class="muted">Select a retrieval record.</p>';
      if (retrievalId) {
        const detail = await fetchJson('/api/retrievals/' + encodeURIComponent(retrievalId));
        const readable = formatRetrievalDetailReadable(detail);
        detailHtml = `
          <div class="row"><strong>${escapeHtml(detail.query || '')}</strong></div>
          <div class="mem-view-toggle mem-detail-toggle icon-toolbar" role="group" aria-label="Retrieval detail format">
            <button type="button" id="ret-detail-btn-formatted" class="icon-btn mem-view-active" onclick="retrievalDetailToggle('formatted')" aria-label="Formatted detail" title="Formatted">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button type="button" id="ret-detail-btn-raw" class="icon-btn" onclick="retrievalDetailToggle('raw')" aria-label="Raw JSON" title="Raw JSON">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            </button>
          </div>
          <div id="ret-detail-formatted" class="mem-detail-body">${readable}</div>
          <div id="ret-detail-raw" class="mem-detail-body" style="display:none">${pretty(detail)}</div>`;
      }
      const rows = data.items.map((item) => {
        const n = (item.selected_memory_ids || []).length;
        const t = formatInstantLocal(item.timestamp);
        const qfull = item.query || '';
        const qtext = qfull.slice(0, 120);
        const qcell = qfull
          ? `<a href="${retrievalHref(item.id)}">${escapeHtml(qtext)}${qfull.length > 120 ? '…' : ''}</a>`
          : '<span class="muted">—</span>';
        return `<tr>
          <td>${escapeHtml(t || '—')}</td>
          <td>${qcell}</td>
          <td class="num">${n}</td>
          <td class="muted" style="font-size:12px"><a href="${retrievalHref(item.id)}">${escapeHtml(String(item.id))}</a></td>
        </tr>`;
      }).join('');
      app.innerHTML = [
        panel('Retrieval Explorer', `
          <form class="memories-toolbar" id="retrievals-filter-form" onsubmit="event.preventDefault(); const f=this; const p = memoryExplorerParams({
            search: f.search.value,
            sort: f.sort.value,
            sort_dir: f.sort_dir.value,
            limit: f.limit.value,
            timestamp_after: datetimeLocalToIsoUtc(f.timestamp_after.value),
            timestamp_before: datetimeLocalToIsoUtc(f.timestamp_before.value),
            min_selected: f.min_selected.value,
            max_selected: f.max_selected.value,
            offset: '0',
            view: f.list_view ? f.list_view.value : ''
          }); location.search = p.toString() ? '?' + p.toString() : '';">
            <input type="hidden" name="list_view" value="${view === 'table' ? 'table' : ''}">
            <div class="row" style="align-items:flex-end">
              <label style="display:flex;flex-direction:column;gap:4px;min-width:180px;flex:1"><span class="muted" style="font-size:11px">Search</span>
                <input name="search" type="search" placeholder="id, query, summary" value="${escapeHtml(search)}"></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Sort</span>
                <select name="sort">${sortOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Dir</span>
                <select name="sort_dir">
                  <option value="" ${dirDefault}>default</option>
                  <option value="asc" ${dirAsc}>asc</option>
                  <option value="desc" ${dirDesc}>desc</option>
                </select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Page size</span>
                <select name="limit">
                  <option value="25" ${lim25}>25</option>
                  <option value="50" ${lim50}>50</option>
                  <option value="100" ${lim100}>100</option>
                </select></label>
              <button type="submit" class="icon-btn" aria-label="Apply filters" title="Apply filters">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
            <div class="row" style="align-items:center;margin-top:4px">
              <span class="muted" style="font-size:11px">Retrieval time window:</span>
              <button type="button" class="icon-btn" onclick="applyRetrievalTimePreset(24)" aria-label="Last 24 hours" title="Last 24 hours">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><span class="sr-only">24h</span>
              </button>
              <button type="button" class="icon-btn" onclick="applyRetrievalTimePreset(168)" aria-label="Last 7 days" title="Last 7 days">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg><span class="sr-only">7d</span>
              </button>
            </div>
            <details>
              <summary>Advanced filters (time, selected count)</summary>
              <p class="muted" style="font-size:12px;margin:8px 0 0 0">Times use <strong>your browser timezone</strong> in the pickers; the URL stores UTC instants for stable filters.</p>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">On or after</span>
                  <input name="timestamp_after" type="datetime-local" step="60" title="Local time; filter is UTC instant" value="${escapeHtml(isoUtcToDatetimeLocal(timestampAfter))}"></label>
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">On or before</span>
                  <input name="timestamp_before" type="datetime-local" step="60" title="Local time; filter is UTC instant" value="${escapeHtml(isoUtcToDatetimeLocal(timestampBefore))}"></label>
              </div>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Min selected</span>
                  <input name="min_selected" type="number" min="0" step="1" placeholder="any" value="${escapeHtml(minSelected)}"></label>
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Max selected</span>
                  <input name="max_selected" type="number" min="0" step="1" placeholder="any" value="${escapeHtml(maxSelected)}"></label>
              </div>
            </details>
          </form>
          ${total === 0 ? '<div class="od-empty-nextsteps glossary-hint" role="status">No retrieval audits yet, or none match your filters. Ensure tooling records retrievals and <code>opendream observe index --workspace "$PWD"</code> has been run. See <a href="/overview">Overview</a>.</div>' : ''}
          <div class="row" style="align-items:center;justify-content:space-between;flex-wrap:wrap;margin:10px 0 8px 0;gap:10px">
            <p class="muted" style="margin:0">Showing <strong>${startIdx}</strong>–<strong>${endIdx}</strong> of <strong>${total}</strong></p>
            <div class="mem-view-toggle icon-toolbar" role="group" aria-label="Retrieval list layout">
              <button type="button" class="icon-btn ${view === 'table' ? 'mem-view-active' : ''}" title="Table layout" aria-label="Table layout"
                onclick="(() => { const p = memoryExplorerParams({ view: 'table' }); location.search = '?' + p.toString(); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              </button>
              <button type="button" class="icon-btn ${isTimeline ? 'mem-view-active' : ''}" title="Timeline layout" aria-label="Timeline layout"
                onclick="(() => { const p = memoryExplorerParams({ view: '' }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
              </button>
            </div>
          </div>
          <details class="mem-detail-details" style="margin-bottom:12px">
            <summary>Column tips</summary>
            <p class="glossary-hint" style="margin-top:8px;margin-bottom:0"><strong>Sel.</strong> = memories in the ranked top-k for that query. Open a row for <strong>Query provenance</strong> (which pipeline invoked retrieval). Hover headers for more.</p>
          </details>
          ${isTimeline ? `<p class="muted" style="font-size:12px;margin:0 0 10px 0">Timeline uses the same filters and pagination as the table. Items on this page are <strong>newest first</strong>, grouped by <strong>local calendar day</strong> (by retrieval <code>timestamp</code>).</p>` : ''}
          ${isTimeline
            ? `<div class="table-scroll"><div class="mem-timeline">${buildRetrievalTimelineHtml(data.items, search)}</div></div>`
            : `<div class="table-scroll">
            <table class="memories-table"><caption class="sr-only">Retrieval audit records matching current filters</caption><thead><tr>
              <th scope="col" title="When this retrieval was audited (shown in your local timezone in the cells below)">Time</th>
              <th scope="col" title="Query string passed to retrieve(). Who issued it is shown as Query provenance on the detail panel when the caller records it.">Query</th>
              <th class="num" scope="col" title="Number of memories in the final ranked top-k selection (len(selected_memory_ids))">Sel.</th>
              <th scope="col" title="Stable retrieval / run id (audit file key)">ID</th>
            </tr></thead><tbody>
              ${rows || '<tr><td colspan="4" class="muted">No retrievals match.</td></tr>'}
            </tbody></table>
          </div>`}
          <div class="pager">
            <button type="button" class="icon-btn" ${hasPrev ? '' : 'disabled'} aria-label="Previous page" title="Previous"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${prevOff}) }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <button type="button" class="icon-btn" ${hasNext ? '' : 'disabled'} aria-label="Next page" title="Next"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${nextOff}) }); const s = p.toString(); location.search = s ? ('?' + s) : ''; })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
            <span class="muted">offset ${off}, limit ${lim}</span>
          </div>
        `, false, 'ret-explorer'),
        panel('Retrieval Explainability', detailHtml, false, 'ret-detail'),
      ].join('');
    }

    async function renderReviews() {
      const data = await fetchJson('/api/reviews');
      const rows = (data.items || [])
        .map(
          (item) => `<tr>
          <td title="Queue category for routing actions">${escapeHtml(String(item.queue_item_type || ''))}</td>
          <td title="Target object id (memory, run, retrieval, …)">${escapeHtml(String(item.queue_item_id || ''))}</td>
          <td title="Why this item was queued">${escapeHtml(String(item.reason || ''))}</td>
        </tr>`
        )
        .join('');
      app.innerHTML = [
        panel(
          'Review Queue',
          `<details class="mem-detail-details" style="margin-bottom:12px">
            <summary>About this queue</summary>
            <p class="glossary-hint" style="margin-top:8px;margin-bottom:0">Items are derived from the observability index (contested memories, low confidence, suspicious retrievals, runs with warnings or diffs). Approve or annotate via the API from your workflows.</p>
          </details>
          <table class="memories-table"><caption class="sr-only">Items awaiting operator review</caption><thead><tr>
            <th scope="col" title="Queue category (memory vs run vs retrieval)">Type</th>
            <th scope="col" title="Stable id of the queued object">Item</th>
            <th scope="col" title="Human-readable reason this row appears">Reason</th>
          </tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">Queue is empty.</td></tr>'}</tbody></table>`,
          true,
        ),
      ].join('');
    }

    function loadScript(src) {
      return new Promise((resolve, reject) => {
        if (document.querySelector('script[src="' + src + '"]')) return resolve();
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = () => reject(new Error('failed to load ' + src));
        document.head.appendChild(s);
      });
    }

    async function renderGraph() {
      app.innerHTML = '<section class="panel full" style="padding:0;"><div id="graph-root"></div></section>';
      try {
        if (!window.__opendreamGraph) {
          const scripts = [
            '/static/vendor/graphology.umd.min.js',
            '/static/vendor/graphology-layout-forceatlas2.min.js',
            '/static/vendor/sigma.min.js',
            '/static/graph.js',
          ];
          for (const src of scripts) await loadScript(src);
        }
        window.__opendreamGraph.mount(document.getElementById('graph-root'));
      } catch (err) {
        const data = await fetchJson('/api/graph');
        app.innerHTML = [
          panel('Provenance Graph (fallback view \u2014 interactive renderer failed: ' + err.message + ')', `<div class="split"><div>${pretty(data.nodes)}</div><div>${pretty(data.edges)}</div></div>`, true),
        ].join('');
      }
    }

    async function renderEvals() {
      const data = await fetchJson('/api/evals');
      app.innerHTML = [
        panel(
          'Health / Evals',
          `<details class="mem-detail-details"><summary>Raw JSON</summary><div style="margin-top:10px">${pretty(data)}</div></details>`,
          true,
        ),
      ].join('');
    }

    async function renderExports() {
      const data = await fetchJson('/api/exports');
      app.innerHTML = [
        panel(
          'Exports',
          `<details class="mem-detail-details"><summary>Raw JSON</summary><div style="margin-top:10px">${pretty(data)}</div></details>`,
          true,
        ),
      ].join('');
    }

    async function renderSettings() {
      const data = await fetchJson('/api/overview');
      app.innerHTML = [
        panel(
          'Store metadata (read-only)',
          `<p class="muted" style="margin-top:0;line-height:1.55">This page is the <strong>raw store snapshot</strong>: lock state, memory root, startup index, and activation diagnostics as returned by the server. Use <a href="/overview">Overview</a> for counts, recent runs/sessions, and contested memory at a glance.</p>
          <h3 class="mem-detail-h" style="margin-top:16px">Structured fields</h3>
          <div class="mem-detail-meta">
            <div class="mem-detail-field"><span class="mem-detail-label">Memory root</span><span class="mem-detail-val">${escapeHtml(
              String((data.store_health && data.store_health.memory_root) || '')
            )}</span></div>
          </div>
          <details class="mem-detail-details" style="margin-top:14px"><summary>Raw JSON (store_health, startup_index, activation_diagnostics)</summary>
            <div style="margin-top:10px">${pretty({
              store_health: data.store_health,
              startup_index: data.startup_index,
              activation_diagnostics: data.activation_diagnostics,
            })}</div>
          </details>`,
          true,
        ),
      ].join('');
    }

    async function renderSessions(sessionId=null) {
      const data = await fetchJson('/api/sessions');
      let detailHtml = '<p class="muted">Select a session.</p>';
      if (sessionId) {
        const detail = await fetchJson('/api/sessions/' + encodeURIComponent(sessionId) + '/timeline');
        detailHtml = `${buildSessionTimelineFromDetail(detail)}
          <details class="mem-detail-details" style="margin-top:14px"><summary>Raw timeline JSON</summary>${pretty(detail)}</details>`;
      }
      const sessionRows = data.items
        .map((item) => {
          const sid = String(item.session_id || '');
          const last = sessionLastInstant(item);
          const lastDisp = last ? formatInstantLocal(last) : '—';
          return `<tr>
          <td><a href="${sessionHref(sid)}">${escapeHtml(sid)}</a></td>
          <td class="num">${item.event_count != null ? escapeHtml(String(item.event_count)) : '—'}</td>
          <td class="num">${item.context_count != null ? escapeHtml(String(item.context_count)) : '—'}</td>
          <td title="Latest timestamp from embedded timeline">${escapeHtml(lastDisp)}</td>
        </tr>`;
        })
        .join('');
      app.innerHTML = [
        panel(
          'Sessions',
          `<p class="muted" style="margin:0 0 10px 0">Context assemblies use opaque IDs. Use <a href="/context">Context</a> with an ID from your tooling, or <code>GET /api/context/&lt;id&gt;</code>.</p>
          <table class="memories-table"><caption class="sr-only">Capture sessions</caption><thead><tr>
            <th scope="col">ID</th>
            <th class="num" scope="col" title="Events captured in this session">Events</th>
            <th class="num" scope="col" title="Context assemblies linked to this session">Contexts</th>
            <th scope="col" title="Max timestamp from the session timeline embedded in the index (client-derived)">Last activity</th>
          </tr></thead><tbody>${sessionRows || '<tr><td colspan="4" class="muted">No sessions.</td></tr>'}</tbody></table>`,
        ),
        panel('Session Timeline', detailHtml, false, 'session-timeline'),
      ].join('');
    }

    async function renderContext(contextId) {
      if (!contextId || String(contextId).trim() === '') {
        app.innerHTML = [
          panel(
            'Context viewer',
            `<p class="muted">Context assemblies are keyed by an opaque ID (what was stitched for a specific capture).</p>
            <p class="muted">Obtain an ID from your session tooling or <code>GET /api/context/&lt;id&gt;</code>, then open <code>/context/&lt;id&gt;</code> in this UI. Recent sessions: <a href="/sessions">Sessions</a>.</p>`,
            true,
          ),
        ].join('');
        return;
      }
      const data = await fetchJson('/api/context/' + encodeURIComponent(contextId));
      const readable = formatContextDetailReadable(data);
      const asm = (data.assembled_text || '').trim();
      const asmBlock = asm
        ? `<div class="mem-detail-section"><h4 class="mem-detail-h">Assembled text</h4><div class="mem-detail-body-text">${escapeHtml(asm)}</div></div>`
        : '<p class="muted">No assembled text.</p>';
      app.innerHTML = [
        panel(
          'Context Viewer',
          `<div class="mem-view-toggle mem-detail-toggle icon-toolbar" role="group" aria-label="Context detail format">
            <button type="button" id="ctx-detail-btn-formatted" class="icon-btn mem-view-active" onclick="contextDetailToggle('formatted')" aria-label="Formatted" title="Formatted">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button type="button" id="ctx-detail-btn-raw" class="icon-btn" onclick="contextDetailToggle('raw')" aria-label="Raw JSON" title="Raw JSON">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            </button>
          </div>
          <div id="ctx-detail-formatted" class="mem-detail-body"><div class="split"><div>${readable}</div><div>${asmBlock}</div></div></div>
          <div id="ctx-detail-raw" class="mem-detail-body" style="display:none">${pretty(data)}</div>`,
          true,
          'ctx-viewer',
        ),
      ].join('');
    }

    async function renderWorkspaces() {
      const data = await fetchJson('/api/workspaces');
      const summary = data.summary;
      const entries = data.entries;
      const searchParams = new URLSearchParams(location.search);
      const q = (searchParams.get('q') || '').toLowerCase();
      const statusFilter = searchParams.get('status') || '';
      const filtered = entries.filter(e => {
        if (statusFilter && e.status_kind !== statusFilter) return false;
        if (q) {
          const hay = (e.workspace_path + ' ' + (e.workspace_name || '')).toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
      const rows = filtered.map(e => {
        const statusCls = e.status_kind === 'ok' ? 'active-badge' : (e.status_kind === 'stale' ? 'warning-badge' : 'error-badge');
        return `<tr>
          <td><a href="/workspaces/${encodeURIComponent(e.workspace_path)}">${e.workspace_name}</a><div class="muted" style="font-size:11px">${e.workspace_path}</div></td>
          <td><span class="badge ${statusCls}">${e.status_kind}</span></td>
          <td>${e.activation_state_summary || '<span class="muted">—</span>'}</td>
          <td>${e.service_state_summary || '<span class="muted">—</span>'}</td>
          <td>${e.memory_dir || '<span class="muted">—</span>'}</td>
          <td>${e.semantic_state_summary || '<span class="muted">—</span>'}</td>
          <td class="muted">${e.last_seen_at || ''}</td>
        </tr>`;
      }).join('');
      app.innerHTML = [
        panel('Workspaces Overview', `
          <div class="metric"><div class="label">Total</div><div class="value">${summary.total}</div></div>
          <div class="metric"><div class="label">Healthy</div><div class="value">${summary.ok}</div></div>
          <div class="metric"><div class="label">With Service</div><div class="value">${summary.with_service}</div></div>
          <div class="metric"><div class="label">Stale/Missing/Broken</div><div class="value">${summary.stale + summary.missing + summary.broken}</div></div>
        `, true),
        panel('Workspace Catalog', `
          <form class="row" onsubmit="event.preventDefault(); location.search = '?' + qs({q:this.q.value, status:this.status.value});">
            <input name="q" placeholder="search path/name" value="${q}">
            <select name="status">
              <option value="">any status</option>
              <option value="ok" ${statusFilter==='ok'?'selected':''}>ok</option>
              <option value="stale" ${statusFilter==='stale'?'selected':''}>stale</option>
              <option value="missing" ${statusFilter==='missing'?'selected':''}>missing</option>
              <option value="broken" ${statusFilter==='broken'?'selected':''}>broken</option>
            </select>
            <button type="submit">Filter</button>
            <span class="muted">${filtered.length} of ${entries.length} entries</span>
          </form>
          <table>
            <caption class="sr-only">Registered workspaces from local catalog</caption>
            <thead><tr><th scope="col">Workspace</th><th scope="col">Status</th><th scope="col">Activation</th><th scope="col">Service</th><th scope="col">Memory Dir</th><th scope="col">Semantic</th><th scope="col">Last Seen</th></tr></thead>
            <tbody>${rows || '<tr><td colspan="7" class="muted">No workspaces in the local catalog. Run <code>opendream workspace scan --root &lt;path&gt;</code> or initialize a workspace. For this UI against a workspace: <code>opendream observe index --workspace "$PWD"</code> then <code>opendream observe serve --workspace "$PWD" --port 8000</code>.</td></tr>'}</tbody>
          </table>
        `, true),
        panel('Privacy', `<p class="muted">This catalog is machine-local. Workspace <code>.opendream/</code> state remains canonical. Scans only run on explicitly configured roots.</p>`, true),
      ].join('');
    }

    async function renderWorkspaceDetail(rawPath) {
      const path = decodeURIComponent(rawPath);
      const data = await fetchJson('/api/workspaces/' + encodeURIComponent(path));
      if (data.status === 'missing') {
        app.innerHTML = [panel('Workspace Detail', `<p class="muted">No catalog entry for <code>${path}</code>.</p>`, true)].join('');
        return;
      }
      app.innerHTML = [
        panel('Workspace Detail', `
          <h3>${data.entry.workspace_name}</h3>
          <p class="muted">${data.entry.workspace_path}</p>
          ${pretty(data.entry)}
        `, true),
      ].join('');
    }

    if (route === '/' || route === '/overview') void runRender('Overview', renderOverview);
    else if (route === '/workspaces') void runRender('Workspaces', renderWorkspaces);
    else if (route.startsWith('/workspaces/')) void runRender('Workspace detail', () => renderWorkspaceDetail(route.split('/').pop()));
    else if (route === '/memories') void runRender('Memories', () => renderMemories());
    else if (route.startsWith('/memories/')) void runRender('Memories', () => renderMemories(route.split('/').pop()));
    else if (route === '/runs') void runRender('Runs', renderRuns);
    else if (route.startsWith('/runs/')) void runRender('Runs', () => renderRuns(route.split('/').pop()));
    else if (route === '/retrievals') void runRender('Retrievals', () => renderRetrievals());
    else if (route.startsWith('/retrievals/')) void runRender('Retrievals', () => renderRetrievals(route.split('/').pop()));
    else if (route === '/reviews') void runRender('Reviews', renderReviews);
    else if (route === '/graph') void runRender('Provenance graph', renderGraph);
    else if (route === '/evals') void runRender('Evals', renderEvals);
    else if (route === '/exports') void runRender('Exports', renderExports);
    else if (route === '/settings') void runRender('Settings', renderSettings);
    else if (route === '/sessions') void runRender('Sessions', () => renderSessions());
    else if (route.startsWith('/sessions/')) void runRender('Sessions', () => renderSessions(route.split('/').pop()));
    else if (route === '/context' || route === '/context/') void runRender('Context', () => renderContext(null));
    else if (route.startsWith('/context/')) void runRender('Context', () => renderContext(route.split('/').pop()));
    else void runRender('Overview', renderOverview);
  </script>
</body>
</html>"""


class ObservabilityHandler(BaseHTTPRequestHandler):
    store: MemoryStore

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/stream"):
            self._write_event_stream()
            return
        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path)
            return
        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed)
            return
        self._write_html(INDEX_HTML)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        try:
            if parsed.path == "/api/annotations":
                response = create_annotation(self.store, **payload)
            elif parsed.path == "/api/exports":
                response = create_export(self.store, **payload)
            elif parsed.path.startswith("/api/reviews/"):
                review_id = parsed.path.split("/")[3]
                action = parsed.path.split("/")[-1]
                response = create_review_decision(
                    self.store,
                    queue_item_type=str(payload.get("queue_item_type", "review")),
                    queue_item_id=review_id,
                    action=action,
                    rationale=str(payload.get("rationale", "")),
                    actor=str(payload.get("actor", "operator")),
                    now=payload.get("now"),
                )
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        index_observability(self.store)
        self._write_json(response)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _handle_api_get(self, parsed: Any) -> None:
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        index = load_or_build_index(self.store)
        entities = index["entities"]
        if parsed.path == "/api/overview":
            self._write_json(index["overview"])
            return
        if parsed.path == "/api/workspaces":
            self._write_json(_workspace_dashboard_payload())
            return
        if parsed.path.startswith("/api/workspaces/"):
            from urllib.parse import unquote

            workspace_arg = unquote(parsed.path[len("/api/workspaces/") :])
            entry = workspace_catalog.inspect_entry(workspace_arg)
            if entry is None:
                self._write_json({"status": "missing", "workspace": workspace_arg})
            else:
                self._write_json({"status": "ok", "entry": entry})
            return
        if parsed.path == "/api/memories":
            sort_dir_raw = (query.get("sort_dir") or "").strip().lower()
            sort_dir = sort_dir_raw if sort_dir_raw in ("asc", "desc") else None
            limit = _parse_query_int(
                query.get("limit"),
                50,
                minimum=1,
                maximum=_MEMORY_LIST_LIMIT_CAP,
            )
            offset = _parse_query_int(query.get("offset"), 0, minimum=0, maximum=10_000_000)
            result = query_memories(
                index,
                search=query.get("search", ""),
                filters={key: query.get(key, "") for key in ["type", "scope", "status"]},
                sort=query.get("sort", "updated_at"),
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
                salience_min=_parse_query_float(query.get("salience_min")),
                salience_max=_parse_query_float(query.get("salience_max")),
                confidence_min=_parse_query_float(query.get("confidence_min")),
                confidence_max=_parse_query_float(query.get("confidence_max")),
                updated_after=(query.get("updated_after") or "").strip() or None,
                updated_before=(query.get("updated_before") or "").strip() or None,
                created_after=(query.get("created_after") or "").strip() or None,
                created_before=(query.get("created_before") or "").strip() or None,
            )
            self._write_json(result)
            return
        if parsed.path.startswith("/api/memories/") and parsed.path.endswith("/lineage"):
            memory_id = parsed.path.split("/")[-2]
            memory = _find_by_id(entities["memories"], "memory_id", memory_id)
            self._write_json(memory.get("lineage", {}) if memory else {})
            return
        if parsed.path.startswith("/api/memories/"):
            memory_id = parsed.path.split("/")[-1]
            self._write_json(_find_by_id(entities["memories"], "memory_id", memory_id) or {})
            return
        if parsed.path == "/api/sessions":
            self._write_json({"items": entities["sessions"]})
            return
        if parsed.path.startswith("/api/sessions/") and parsed.path.endswith("/timeline"):
            session_id = parsed.path.split("/")[-2]
            session = _find_by_id(entities["sessions"], "session_id", session_id)
            self._write_json(session or {})
            return
        if parsed.path == "/api/runs":
            sort_dir_raw = (query.get("sort_dir") or "").strip().lower()
            sort_dir = sort_dir_raw if sort_dir_raw in ("asc", "desc") else None
            limit = _parse_query_int(
                query.get("limit"),
                50,
                minimum=1,
                maximum=_RUN_LIST_LIMIT_CAP,
            )
            offset = _parse_query_int(query.get("offset"), 0, minimum=0, maximum=10_000_000)
            result = query_runs(
                index,
                search=query.get("search", ""),
                sort=query.get("sort", "ended_at"),
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
                ended_after=(query.get("ended_after") or "").strip() or None,
                ended_before=(query.get("ended_before") or "").strip() or None,
            )
            self._write_json(result)
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/diff"):
            run_id = parsed.path.split("/")[-2]
            run = _find_by_id(entities["runs"], "run_id", run_id)
            self._write_json({"run_id": run_id, "diff_text": run.get("diff_text", "") if run else ""})
            return
        if parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[-1]
            self._write_json(_find_by_id(entities["runs"], "run_id", run_id) or {})
            return
        if parsed.path == "/api/retrievals":
            sort_dir_raw = (query.get("sort_dir") or "").strip().lower()
            sort_dir = sort_dir_raw if sort_dir_raw in ("asc", "desc") else None
            limit = _parse_query_int(
                query.get("limit"),
                50,
                minimum=1,
                maximum=_RETRIEVAL_LIST_LIMIT_CAP,
            )
            offset = _parse_query_int(query.get("offset"), 0, minimum=0, maximum=10_000_000)
            result = query_retrievals(
                index,
                search=query.get("search", ""),
                sort=query.get("sort", "timestamp"),
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
                timestamp_after=(query.get("timestamp_after") or "").strip() or None,
                timestamp_before=(query.get("timestamp_before") or "").strip() or None,
                min_selected=_parse_query_int(query.get("min_selected"), 0, minimum=0, maximum=1_000_000)
                if (query.get("min_selected") or "").strip()
                else None,
                max_selected=_parse_query_int(query.get("max_selected"), 0, minimum=0, maximum=1_000_000)
                if (query.get("max_selected") or "").strip()
                else None,
            )
            self._write_json(result)
            return
        if parsed.path.startswith("/api/retrievals/"):
            retrieval_id = parsed.path.split("/")[-1]
            self._write_json(_find_by_id(entities["retrievals"], "id", retrieval_id) or {})
            return
        if parsed.path.startswith("/api/context/"):
            context_id = parsed.path.split("/")[-1]
            self._write_json(_find_by_id(entities["contexts"], "context_id", context_id) or {})
            return
        if parsed.path == "/api/graph":
            self._write_json(
                build_graph(
                    index,
                    focus=query.get("focus"),
                    limit=int(query.get("limit", "24")),
                    depth=int(query.get("depth", "1")),
                    layout=query.get("layout", "hierarchical"),
                )
            )
            return
        if parsed.path == "/api/reviews":
            self._write_json({"items": entities["reviews"], "decisions": self.store.load_review_decisions()})
            return
        if parsed.path == "/api/evals":
            self._write_json({"health": entities["health"], "evals": entities["evals"]})
            return
        if parsed.path == "/api/exports":
            self._write_json({"items": entities["exports"]})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _write_json(self, payload: Any, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, request_path: str) -> None:
        relative = unquote(request_path[len("/static/"):])
        if not relative or ".." in relative.split("/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        candidate = (_STATIC_ROOT / relative).resolve()
        try:
            candidate.relative_to(_STATIC_ROOT)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime = _STATIC_MIME_TYPES.get(candidate.suffix, "application/octet-stream")
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def _write_event_stream(self) -> None:
        snapshot = {
            "status": self.store.status_snapshot(),
            "overview": load_or_build_index(self.store)["overview"],
        }
        body = (
            "event: status\n"
            f"data: {json.dumps(snapshot['status'])}\n\n"
            "event: overview\n"
            f"data: {json.dumps(snapshot['overview'])}\n\n"
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_server(store: MemoryStore, *, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    handler = type("BoundObservabilityHandler", (ObservabilityHandler,), {"store": store})
    return ThreadingHTTPServer((host, port), handler)


def serve_observability(store: MemoryStore, *, host: str = "127.0.0.1", port: int = 8000) -> dict[str, Any]:
    server = build_server(store, host=host, port=port)
    try:
        actual_host, actual_port = server.server_address
        return {"status": "serving", "host": actual_host, "port": actual_port, "url": f"http://{actual_host}:{actual_port}"}
    finally:
        server.server_close()


def _workspace_dashboard_payload() -> dict[str, Any]:
    """Build the read-model payload used by the /workspaces dashboard route.

    Uses the machine-local catalog for fast initial render; the dashboard
    can trigger re-probes via the CLI (``opendream workspace doctor``) rather
    than performing synchronous disk work inside the HTTP handler.
    """
    entries = workspace_catalog.list_entries()
    summary = {
        "total": len(entries),
        "ok": sum(1 for e in entries if e.get("status_kind") == "ok"),
        "stale": sum(1 for e in entries if e.get("status_kind") == "stale"),
        "missing": sum(1 for e in entries if e.get("status_kind") == "missing"),
        "broken": sum(1 for e in entries if e.get("status_kind") == "broken"),
        "with_service": sum(1 for e in entries if e.get("service_state_summary")),
        "with_semantic": sum(1 for e in entries if e.get("semantic_state_summary")),
    }
    return {
        "summary": summary,
        "entries": entries,
        "roots": workspace_catalog.list_roots(),
    }


def _find_by_id(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get(key, "")) == value:
            return row
    return None
