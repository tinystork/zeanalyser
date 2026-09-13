"""Stable cross-platform application identity for ZeAnalyser.

These identifiers are deliberately version-independent. Desktop packagers may
install the bundled Linux desktop entry and icon under ``LINUX_DESKTOP_ID``;
the application itself never modifies system or user desktop configuration.
"""

from __future__ import annotations

import platform

APPLICATION_NAME = "ZeAnalyser"
APPLICATION_DISPLAY_NAME = "ZeAnalyser"
ORGANIZATION_NAME = "ZeSeestarStacker"
WINDOWS_APP_USER_MODEL_ID = "ZeSoftware.ZeAnalyser"
LINUX_DESKTOP_ID = "io.github.tinystork.ZeAnalyser"
LINUX_DESKTOP_FILENAME = f"{LINUX_DESKTOP_ID}.desktop"


def configure_qt_application(app, *, system_name: str | None = None) -> None:
    """Apply stable Qt process identity before the first window is created."""

    app.setOrganizationName(ORGANIZATION_NAME)
    app.setApplicationName(APPLICATION_NAME)
    if hasattr(app, "setApplicationDisplayName"):
        app.setApplicationDisplayName(APPLICATION_DISPLAY_NAME)

    current_system = system_name or platform.system()
    if current_system == "Linux" and hasattr(app, "setDesktopFileName"):
        # Qt exposes this as the Wayland app_id / desktop-entry association.
        # The matching distributable file is LINUX_DESKTOP_FILENAME.
        app.setDesktopFileName(LINUX_DESKTOP_ID)
