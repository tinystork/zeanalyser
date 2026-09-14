from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

import pytest

from zeanalyser import analyse_logic, organizer_module
from zeanalyser.path_safety import source_is_within_root


class _ImmediateExecutor:
    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def submit(self, _function, path):
        future = Future()
        future.set_result(
            {
                "path": path,
                "snr": 20.0,
                "sky_bg": 1.0,
                "sky_noise": 1.0,
                "signal_pixels": 10,
                "starcount": 5,
                "exposure": 10.0,
                "filter": "LP",
                "temperature": 0.0,
                "eqmode": 2,
                "sitelong": None,
                "sitelat": None,
                "telescope": "Seestar",
                "date_obs": "2026-09-14T00:00:00",
                "error": None,
                "fwhm": 2.0,
                "ecc": 0.5,
                "n_star_ecc": 5,
                "ra": None,
                "dec": None,
            }
        )
        return future

    def shutdown(self, wait=True, *, cancel_futures=False):
        return None


def _options(root: Path, include_subfolders: bool) -> dict:
    return {
        "include_subfolders": include_subfolders,
        "analyze_snr": False,
        "detect_trails": False,
        "move_rejected": False,
        "delete_rejected": False,
        "use_bortle": False,
        "analyse_fwhm": False,
        "analyse_ecc": False,
        "output_root": str(root),
    }


def _callbacks(logs=None):
    logs = logs if logs is not None else []
    return {
        "is_cancelled": lambda: False,
        "progress": lambda *_args, **_kwargs: None,
        "status": lambda *_args, **_kwargs: None,
        "log": lambda key, **kwargs: logs.append((key, kwargs)),
    }


def _build_discovery_tree(tmp_path: Path):
    parent = tmp_path / "project_parent"
    root = parent / "selected_project"
    session_a = root / "session_A"
    session_b_deep = root / "session_B" / "deep"
    session_a.mkdir(parents=True)
    session_b_deep.mkdir(parents=True)
    outside = parent / "outside_parent_image.fit"
    root_file = root / "root_image.fit"
    child_a = session_a / "child_image.fit"
    child_b = session_b_deep / "child_image_2.fit"
    for path in (outside, root_file, child_a, child_b):
        path.touch()
    return root, outside, root_file, child_a, child_b


def _discover(root: Path, include_subfolders: bool, monkeypatch):
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _ImmediateExecutor,
    )
    rows = analyse_logic.perform_analysis(
        str(root),
        str(root / "analyse_resultats.log"),
        _options(root, include_subfolders),
        _callbacks(),
    )
    return {Path(row["path"]).resolve() for row in rows}


def test_discovery_root_only_excludes_children_and_true_parent(tmp_path, monkeypatch):
    root, outside, root_file, child_a, child_b = _build_discovery_tree(tmp_path)

    found = _discover(root, False, monkeypatch)

    assert found == {root_file.resolve()}
    assert outside.resolve() not in found
    assert child_a.resolve() not in found
    assert child_b.resolve() not in found


def test_discovery_with_subfolders_includes_root_and_all_descendants_only(tmp_path, monkeypatch):
    root, outside, root_file, child_a, child_b = _build_discovery_tree(tmp_path)

    found = _discover(root, True, monkeypatch)

    assert found == {root_file.resolve(), child_a.resolve(), child_b.resolve()}
    assert outside.resolve() not in found


def test_containment_is_component_aware_and_normalizes_traversal(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    inside = root / "session" / ".." / "light.fit"
    sibling_prefix = tmp_path / "project-old" / "light.fit"

    assert source_is_within_root(inside, root) is True
    assert source_is_within_root(sibling_prefix, root) is False
    assert source_is_within_root(root / ".." / "outside.fit", root) is False


def _pending_row(path: Path, reason: str = "low_snr_pending_action") -> dict:
    return {
        "file": path.name,
        "path": str(path),
        "rel_path": path.name,
        "status": "ok",
        "action": "pending_snr_action",
        "rejected_reason": reason,
        "action_comment": "",
    }


def test_outside_source_is_never_deleted(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.fit"
    outside.touch()
    logs = []
    row = _pending_row(outside)

    count = analyse_logic.apply_pending_snr_actions(
        [row], None, True, False,
        _callbacks(logs)["log"], None, None, str(root),
    )

    assert count == 0
    assert outside.exists()
    assert row["action"] == "skipped_outside_project"
    assert any(key == "logic_source_outside_project" for key, _kwargs in logs)


def test_move_allows_inside_source_and_explicit_external_destination(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "inside.fit"
    source.touch()
    external_destination = tmp_path / "external-rejected"
    row = _pending_row(source)

    count = analyse_logic.apply_pending_snr_actions(
        [row], str(external_destination), False, True,
        None, None, None, str(root),
    )

    assert count == 1
    assert not source.exists()
    assert (external_destination / source.name).exists()
    assert row["action"] == "moved_snr"


def test_mixed_move_rows_process_inside_and_skip_outside(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    inside = root / "inside.fit"
    outside = tmp_path / "outside.fit"
    inside.touch()
    outside.touch()
    destination = tmp_path / "reject"
    rows = [_pending_row(inside), _pending_row(outside)]

    count = analyse_logic.apply_pending_snr_actions(
        rows, str(destination), False, True,
        None, None, None, str(root),
    )

    assert count == 1
    assert (destination / inside.name).exists()
    assert outside.exists()
    assert rows[1]["action"] == "skipped_outside_project"


def test_symlink_to_outside_is_not_a_mutable_in_project_source(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.fit"
    outside.touch()
    link = root / "link.fit"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    row = _pending_row(link)

    count = analyse_logic.apply_pending_snr_actions(
        [row], None, True, False,
        None, None, None, str(root),
    )

    assert count == 0
    assert link.exists()
    assert outside.exists()
    assert row["action"] == "skipped_outside_project"


@pytest.mark.parametrize(
    ("helper_name", "reason", "pending_action"),
    [
        ("apply_pending_snr_actions", "low_snr_pending_action", "pending_snr_action"),
        ("apply_pending_trail_actions", "trail_pending_action", "pending_trail_action"),
        ("apply_pending_reco_actions", "not_in_recommendation", "pending_reco_action"),
    ],
)
@pytest.mark.parametrize("delete", [False, True])
def test_all_deferred_move_and_delete_helpers_refuse_outside_sources(
    tmp_path, helper_name, reason, pending_action, delete
):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / f"outside-{helper_name}-{delete}.fit"
    outside.touch()
    row = _pending_row(outside, reason)
    row["action"] = pending_action
    helper = getattr(analyse_logic, helper_name)

    count = helper(
        [row],
        str(tmp_path / "external-reject"),
        delete,
        not delete,
        None,
        None,
        None,
        str(root),
    )

    assert count == 0
    assert outside.exists()
    assert row["action"] == "skipped_outside_project"


def test_pending_organization_refuses_outside_source_but_allows_external_destination(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    inside = root / "inside.fit"
    outside = tmp_path / "outside.fit"
    inside.touch()
    outside.touch()
    external = tmp_path / "organized"
    rows = [
        {
            "path": str(inside),
            "filepath_dst": str(external / "inside.fit"),
            "status": "ok",
            "action": "kept",
            "action_comment": "",
        },
        {
            "path": str(outside),
            "filepath_dst": str(external / "outside.fit"),
            "status": "ok",
            "action": "kept",
            "action_comment": "",
        },
    ]

    count = analyse_logic.apply_pending_organization(rows, input_dir_abs=str(root))

    assert count == 1
    assert (external / "inside.fit").exists()
    assert outside.exists()
    assert not (external / "outside.fit").exists()
    assert rows[1]["action"] == "skipped_outside_project"


def test_immediate_delete_refuses_symlink_whose_target_is_outside(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.fit"
    outside.touch()
    link = root / "linked.fit"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    monkeypatch.setattr(
        analyse_logic.concurrent.futures,
        "ProcessPoolExecutor",
        _ImmediateExecutor,
    )
    options = _options(root, False)
    options.update(
        analyze_snr=True,
        snr_selection_mode="threshold",
        snr_selection_value="100",
        delete_rejected=True,
        apply_snr_action_immediately=True,
    )

    rows = analyse_logic.perform_analysis(
        str(root), str(root / "analyse_resultats.log"), options, _callbacks()
    )

    assert link.exists()
    assert outside.exists()
    assert rows[0]["action"] == "skipped_outside_project"


def test_organizer_apply_refuses_injected_outside_entry(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.fit"
    outside.touch()
    destination = tmp_path / "organized" / "outside.fit"
    entries = [
        {
            "src_abs": str(outside),
            "dst_abs": str(destination),
            "status": "ok",
        }
    ]

    summary = organizer_module.apply_plan(
        entries,
        move_files=True,
        dry_run=False,
        callbacks={},
        source_root_abs=str(root),
    )

    assert summary["moved"] == 0
    assert summary["skipped"] == 1
    assert outside.exists()
    assert not destination.exists()
    assert entries[0]["status"] == "skipped_outside_project"
