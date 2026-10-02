"""Regression tests for safe reject destinations (REWORK-2 data-loss fix).

Same-basename files in different subfolders must never collide when moved to a
reject directory: the source subpath is preserved under the reject dir, parent
dirs are created, and an existing destination is never overwritten (the move is
refused with an explicit collision state and the source left intact).
"""
import os

import pytest

from zeanalyser import analyse_logic
from zeanalyser.path_safety import resolve_reject_destination


def _row(name, path, reason, action):
    return {
        "file": name,
        "path": str(path),
        "status": "ok",
        "rejected_reason": reason,
        "action": action,
        "action_comment": "",
    }


_NOOP = lambda *a, **k: None


# (helper_name, pending_reason, pending_action, moved_action)
REJECT_CASES = [
    ("snr", "low_snr_pending_action", "pending_snr_action", "moved_snr"),
    ("trail", "trail_pending_action", "pending_trail_action", "moved_trail"),
    ("reco", "not_in_recommendation", "pending_reco_action", "moved_reco"),
]

HELPERS = {
    "snr": analyse_logic.apply_pending_snr_actions,
    "trail": analyse_logic.apply_pending_trail_actions,
    "reco": analyse_logic.apply_pending_reco_actions,
}


# ---------------------------------------------------------------------------
# resolve_reject_destination (pure)
# ---------------------------------------------------------------------------

def test_resolve_reject_destination_preserves_subpath():
    assert resolve_reject_destination("/root/light.fit", "/root/reject", "/root") == (
        os.path.join("/root/reject", "light.fit")
    )
    assert resolve_reject_destination("/root/A/light.fit", "/root/reject", "/root") == (
        os.path.join("/root/reject", "A", "light.fit")
    )
    assert resolve_reject_destination("/root/B/light.fit", "/root/reject", "/root") == (
        os.path.join("/root/reject", "B", "light.fit")
    )
    # external destination preserves the relpath from the input root too
    assert resolve_reject_destination("/root/A/light.fit", "/ext/rej", "/root") == (
        os.path.join("/ext/rej", "A", "light.fit")
    )
    # source already inside reject dir => unchanged (no re-nesting)
    assert resolve_reject_destination("/root/reject/A/light.fit", "/root/reject", "/root") == (
        "/root/reject/A/light.fit"
    )
    # no reject dir => None
    assert resolve_reject_destination("/root/light.fit", None, "/root") is None


# ---------------------------------------------------------------------------
# move_to_reject_destination (shared by immediate + deferred paths)
# ---------------------------------------------------------------------------

def test_move_to_reject_destination_statuses(tmp_path):
    root = tmp_path / "root"
    (root / "A").mkdir(parents=True)
    (root / "B").mkdir(parents=True)
    reject = tmp_path / "reject"

    src_a = root / "A" / "light.fit"
    src_a.write_text("content-A")
    dest_a = resolve_reject_destination(str(src_a), str(reject), str(root))
    assert analyse_logic.move_to_reject_destination(str(src_a), dest_a) == "moved"
    assert (reject / "A" / "light.fit").read_text() == "content-A"

    # already at destination
    assert analyse_logic.move_to_reject_destination(dest_a, dest_a) == "already"

    # collision: existing destination (different source) is never overwritten
    src_b = root / "B" / "light.fit"
    src_b.write_text("content-B")
    dest_b = resolve_reject_destination(str(src_b), str(reject), str(root))
    (reject / "B").mkdir(parents=True, exist_ok=True)
    (reject / "B" / "light.fit").write_text("pre-existing")
    assert analyse_logic.move_to_reject_destination(str(src_b), dest_b) == "collision"
    assert (reject / "B" / "light.fit").read_text() == "pre-existing"
    assert src_b.exists()  # source intact


# ---------------------------------------------------------------------------
# Deferred helpers: same basename in two subfolders never collide
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("helper_name,reason,pending_action,moved_action", REJECT_CASES)
def test_reject_no_basename_collision(tmp_path, helper_name, reason, pending_action, moved_action):
    helper = HELPERS[helper_name]
    root = tmp_path / "project"
    (root / "A").mkdir(parents=True)
    (root / "B").mkdir(parents=True)
    reject_dir = tmp_path / "reject"

    a = root / "A" / "light.fit"
    b = root / "B" / "light.fit"
    a.write_text("content-A")
    b.write_text("content-B")

    rows = [
        _row("light.fit", a, reason, pending_action),
        _row("light.fit", b, reason, pending_action),
    ]

    count = helper(rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))

    assert count == 2
    dest_a = reject_dir / "A" / "light.fit"
    dest_b = reject_dir / "B" / "light.fit"
    assert dest_a.exists() and dest_b.exists()
    assert dest_a.read_text() == "content-A"
    assert dest_b.read_text() == "content-B"
    assert not a.exists() and not b.exists()
    assert rows[0]["path"] == str(dest_a)
    assert rows[1]["path"] == str(dest_b)
    assert rows[0]["path"] != rows[1]["path"]
    assert rows[0]["action"] == moved_action
    assert rows[1]["action"] == moved_action


@pytest.mark.parametrize("helper_name,reason,pending_action,moved_action", REJECT_CASES)
def test_reject_collision_refuses_overwrite(tmp_path, helper_name, reason, pending_action, moved_action):
    helper = HELPERS[helper_name]
    root = tmp_path / "project"
    root.mkdir()
    reject_dir = tmp_path / "reject"
    reject_dir.mkdir()

    f = root / "light.fit"
    f.write_text("source-content")
    existing = reject_dir / "light.fit"
    existing.write_text("existing-content")

    rows = [_row("light.fit", f, reason, pending_action)]

    count = helper(rows, str(reject_dir), False, True, _NOOP, _NOOP, _NOOP, str(root))

    assert count == 0
    assert f.exists() and f.read_text() == "source-content"  # source intact
    assert existing.read_text() == "existing-content"        # never overwritten
    # pending state preserved exactly (retryable), never finalized/errored
    assert rows[0]["action"] == pending_action
    assert rows[0]["rejected_reason"] == reason
    assert "Collision" in rows[0]["action_comment"]
