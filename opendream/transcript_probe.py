"""Grep-first transcript probing with bounded-window reads.

Transcript access uses orient → probe → bounded_read → escalation flow.
Full-corpus replay is disabled by default. Every probe run emits a report.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import TranscriptProbeReport
from .util import stable_id, to_iso, utc_now
from .validation import validate_document

DEFAULT_PROBE_BUDGETS: dict[str, int] = {
    "max_probes": 10,
    "max_total_bytes": 512_000,
    "max_hits_expanded": 20,
    "max_lines_per_window": 30,
}


def build_probe_anchors(
    orientation_tokens: list[str],
    *,
    query: str = "",
    max_anchors: int = 10,
) -> list[str]:
    """Generate grep anchors from orientation tokens and an optional query.

    Anchors are unique case-insensitive patterns to probe transcript files.
    """
    candidates: list[str] = []
    if query:
        words = re.findall(r"[a-zA-Z0-9_]+", query)
        candidates.extend(w for w in words if len(w) > 2)
    candidates.extend(t for t in orientation_tokens if len(t) > 2)
    seen: set[str] = set()
    anchors: list[str] = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            anchors.append(c)
        if len(anchors) >= max_anchors:
            break
    return anchors


def probe_transcript_files(
    paths: list[Path],
    *,
    anchors: list[str],
    budgets: dict[str, int] | None = None,
    run_id: str | None = None,
) -> tuple[list[dict[str, Any]], TranscriptProbeReport]:
    """Probe transcript files using grep-first strategy.

    Returns (windows, report) where each window is a dict of lines around a hit.
    """
    now = to_iso(utc_now())
    rid = run_id or stable_id("probe", now)
    cfg = {**DEFAULT_PROBE_BUDGETS, **(budgets or {})}
    max_probes = cfg["max_probes"]
    max_total_bytes = cfg["max_total_bytes"]
    max_hits_expanded = cfg["max_hits_expanded"]
    max_lines_per_window = cfg["max_lines_per_window"]

    probes_run: list[str] = []
    total_hits = 0
    total_windows = 0
    total_bytes = 0
    escalations = 0
    reasons: list[str] = []
    windows: list[dict[str, Any]] = []

    for anchor in anchors[:max_probes]:
        probes_run.append(anchor)
        pattern = re.compile(re.escape(anchor), re.IGNORECASE)

        for path in paths:
            if total_bytes >= max_total_bytes:
                reasons.append(f"byte budget exhausted ({total_bytes} >= {max_total_bytes})")
                break
            if total_windows >= max_hits_expanded:
                reasons.append(f"hit expansion budget exhausted ({total_windows} >= {max_hits_expanded})")
                break

            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            lines = text.splitlines()
            for i, line in enumerate(lines):
                if not pattern.search(line):
                    continue
                total_hits += 1
                if total_windows >= max_hits_expanded:
                    break

                # Extract bounded window.
                half = max_lines_per_window // 2
                start = max(0, i - half)
                end = min(len(lines), i + half + 1)
                window_lines = lines[start:end]
                window_text = "\n".join(window_lines)
                window_bytes = len(window_text.encode("utf-8"))
                total_bytes += window_bytes
                total_windows += 1
                windows.append({
                    "source_path": str(path),
                    "anchor": anchor,
                    "line_number": i + 1,
                    "start_line": start + 1,
                    "end_line": end,
                    "text": window_text,
                    "bytes": window_bytes,
                })

    # Check if escalation is needed (no hits at all).
    if total_hits == 0 and anchors:
        escalations = 1
        reasons.append("no hits found; escalation may be warranted")

    report = TranscriptProbeReport(
        run_id=rid,
        probes=probes_run,
        hits=total_hits,
        windows_read=total_windows,
        escalations=escalations,
        bytes_read=total_bytes,
        reasons=reasons,
    )
    validate_document("transcript-probe-report.schema.json", report.to_dict())
    return windows, report
