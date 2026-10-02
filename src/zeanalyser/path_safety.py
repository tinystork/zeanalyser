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


def resolve_reject_destination(source_path, reject_dir, input_dir_abs):
    """Compute a safe reject destination preserving the source's subpath.

    When ``source_path`` is inside ``input_dir_abs``, its relative path (with
    any subfolders) is preserved under ``reject_dir`` so that same-basename
    files from different subfolders never collide:

        root/light.fit    -> reject/light.fit   (flat-root compatibility)
        root/A/light.fit  -> reject/A/light.fit
        root/B/light.fit  -> reject/B/light.fit

    The relative path is component-aware and never escapes via ``..`` or an
    absolute component. A source already inside ``reject_dir`` is returned
    unchanged so callers treat it as already-at-destination (no
    ``reject/reject/...`` nesting). When no safe relative path can be derived
    (source outside the root), the flat basename form is used as a
    conservative fallback. Returns ``None`` only when no destination can be
    computed at all.
    """
    if not reject_dir:
        return None
    try:
        reject_abs = os.path.abspath(os.fspath(reject_dir))
        src_abs = os.path.abspath(os.fspath(source_path))
    except (OSError, TypeError, ValueError):
        return None

    # Already inside the reject dir => already at destination, no re-nesting.
    if source_is_within_root(src_abs, reject_abs):
        return src_abs

    rel = None
    if input_dir_abs:
        try:
            root_abs = os.path.abspath(os.fspath(input_dir_abs))
            rel = os.path.relpath(src_abs, root_abs)
        except (OSError, TypeError, ValueError):
            rel = None
    if (
        rel is None
        or rel == os.pardir
        or rel.startswith(os.pardir + os.sep)
        or os.path.isabs(rel)
    ):
        rel = os.path.basename(src_abs)
    return os.path.join(reject_abs, rel)
