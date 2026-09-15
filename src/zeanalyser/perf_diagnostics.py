"""Disabled-by-default performance diagnostics for the analysis pipeline.

This module is intentionally dependency-free (stdlib only: ``json``, ``os``,
``time``) so it can be imported without PySide6/Qt. Instrumentation is a strict
no-op unless the environment variable ``ZEANALYSER_PERF_DIAG`` is truthy
(``1`` / ``true`` / ``yes``).

Output path resolution order:

1. ``ZEANALYSER_PERF_DIAG_OUT`` (explicit).
2. Derived from the analysis ``output_log`` (same directory, ``za_perf_diag.json``).
3. ``./za_perf_diag.json``.

The report is written best-effort and never raises.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone

_ENV_ENABLE = "ZEANALYSER_PERF_DIAG"
_ENV_OUT = "ZEANALYSER_PERF_DIAG_OUT"
_DEFAULT_OUT = "za_perf_diag.json"

_TRUTHY = {"1", "true", "yes"}


def _truthy(value):
    return str(value).strip().lower() in _TRUTHY


def _read_vmrss_kb():
    """Read VmRSS (resident set size) in kB from ``/proc/self/status`` (Linux)."""
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        return int(parts[1])
                    return 0
    except Exception:
        return 0
    return 0


class PerfDiagnostics:
    """Lightweight performance instrumentation collector.

    Every method is a no-op (immediate return) when ``enabled`` is False, so the
    disabled path performs no clock sampling, no list appends and no I/O.
    """

    def __init__(self, enabled=False, output_path=None):
        self.enabled = bool(enabled)
        self._output_path = output_path
        self._reset()

    @classmethod
    def from_env(cls):
        enabled = _truthy(os.environ.get(_ENV_ENABLE, ""))
        output_path = os.environ.get(_ENV_OUT) or None
        return cls(enabled=enabled, output_path=output_path)

    def _reset(self):
        self._started = False
        self._finished = False
        self._meta = {}
        self._start_wall = None
        self._stages = {}        # name -> cumulative seconds (perf_counter)
        self._stage_starts = {}  # name -> perf_counter at stage_start
        self._stage_fields = {}  # name -> merged **fields
        self._counters = {}      # name -> int
        self._events = []        # list of dicts
        self._image_completion = []  # perf_counter timestamps
        self._memory_samples = []    # list of dicts

    # -- lifecycle ---------------------------------------------------------

    def start_run(self, **meta):
        """Record wall/perf_counter start + baseline parent RSS."""
        if not self.enabled:
            return
        self._reset()
        self._started = True
        self._start_wall = time.perf_counter()
        self._meta = dict(meta)
        self._meta["iso_start"] = datetime.now(timezone.utc).isoformat()
        self._meta.setdefault("run_id", uuid.uuid4().hex[:8])
        self.sample_memory("start")

    def finish_run(self):
        """Flush the JSON report to the configured path (best-effort, idempotent)."""
        if not self.enabled or not self._started or self._finished:
            return
        self._finished = True
        wall_seconds = time.perf_counter() - self._start_wall
        report = {
            "meta": self._meta,
            "iso_end": datetime.now(timezone.utc).isoformat(),
            "wall_seconds": wall_seconds,
            "stages": {},
            "counters": dict(self._counters),
            "image_completion": list(self._image_completion),
            "memory_samples": list(self._memory_samples),
            "events": list(self._events),
        }
        for name in sorted(self._stages):
            stage = {"duration_seconds": self._stages[name]}
            fields = self._stage_fields.get(name)
            if fields:
                stage["fields"] = fields
            report["stages"][name] = stage
        path = self._resolve_output_path()
        if path is None:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2)
        except Exception:
            # Best-effort: never raise from diagnostics.
            pass

    def _resolve_output_path(self):
        if self._output_path:
            return self._output_path
        log_path = self._meta.get("output_log")
        if log_path:
            directory = os.path.dirname(os.path.abspath(str(log_path)))
            return os.path.join(directory, _DEFAULT_OUT)
        return None

    # -- instrumentation ---------------------------------------------------

    def stage_start(self, name):
        if not self.enabled:
            return
        self._stage_starts[name] = time.perf_counter()

    def stage_end(self, name, **fields):
        if not self.enabled:
            return
        start = self._stage_starts.pop(name, None)
        if start is None:
            return
        delta = time.perf_counter() - start
        self._stages[name] = self._stages.get(name, 0.0) + delta
        if fields:
            merged = dict(self._stage_fields.get(name) or {})
            merged.update(fields)
            self._stage_fields[name] = merged

    def counter(self, name, n=1):
        if not self.enabled:
            return
        self._counters[name] = self._counters.get(name, 0) + int(n)

    def event(self, name, **fields):
        if not self.enabled:
            return
        entry = {"name": name, "perf_counter": time.perf_counter()}
        entry.update(fields)
        self._events.append(entry)

    def completed_image(self):
        if not self.enabled:
            return
        self._image_completion.append(time.perf_counter())

    def sample_memory(self, label):
        if not self.enabled:
            return
        self._memory_samples.append({
            "label": label,
            "rss_kb": _read_vmrss_kb(),
            "perf_counter": time.perf_counter(),
        })


_DIAG = None


def get_diagnostics():
    """Return the module-level singleton, created lazily from the environment."""
    global _DIAG
    if _DIAG is None:
        _DIAG = PerfDiagnostics.from_env()
    return _DIAG
