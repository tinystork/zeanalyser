"""Platform-specific helpers for cross-OS behaviors."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Union


PathLike = Union[str, os.PathLike]


def open_path_with_default_app(target: PathLike) -> None:
    """Open *target* with the OS default application.

    The helper normalizes paths, verifies existence, and uses the
    appropriate launcher per platform:
    - Windows: ``os.startfile``.
    - macOS: ``open`` command.
    - Linux/others: ``xdg-open``.

    Raises
    ------
    FileNotFoundError
        If the target does not exist.
    RuntimeError
        If no suitable opener is available on the current platform.
    """

    target_path = Path(target).expanduser()
    if not target_path.exists():
        raise FileNotFoundError(target_path)

    system_name = platform.system()
    if system_name == "Windows":
        os.startfile(target_path)  # type: ignore[attr-defined]
        return

    opener = "open" if system_name == "Darwin" else "xdg-open"
    opener_path = shutil.which(opener)
    if opener_path:
        subprocess.run([opener_path, str(target_path)], check=False)
        return

    raise RuntimeError(f"No system opener available for platform '{system_name}'.")
