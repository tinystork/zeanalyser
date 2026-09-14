"""Small cross-platform path-containment helpers for file actions."""

from __future__ import annotations

import os
from typing import Optional


def resolved_normcase(path) -> Optional[str]:
    """Return an absolute, symlink-resolved, case-normalized filesystem path."""

    if path is None:
        return None
    try:
        value = os.fspath(path)
    except TypeError:
        return None
    if not value:
        return None
    try:
        return os.path.normcase(
            os.path.realpath(os.path.abspath(os.path.expanduser(value)))
        )
    except (OSError, TypeError, ValueError):
        return None


def source_is_within_root(source_path, root_path) -> bool:
    """Whether the resolved source is inside the resolved selected root.

    Resolution is deliberately conservative for mutating actions: a symlink
    located below the selected root is rejected when its target resolves
    outside that root. ``commonpath`` provides component-aware containment and
    handles drive mismatches by raising ``ValueError`` rather than falling back
    to an unsafe string-prefix comparison.
    """

    source = resolved_normcase(source_path)
    root = resolved_normcase(root_path)
    if source is None or root is None:
        return False
    try:
        return os.path.commonpath((source, root)) == root
    except (OSError, TypeError, ValueError):
        return False
