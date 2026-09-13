# Linux desktop integration

ZeAnalyser uses the stable Linux desktop/application identifier:

```text
io.github.tinystork.ZeAnalyser
```

At runtime Qt receives this identifier through `setDesktopFileName()` before
the first window is created. This is distinct from `setWindowIcon()`: under
Wayland, the compositor normally resolves the dock/task-switcher icon through
a matching installed desktop entry.

The package includes:

- `zeanalyser/resources/io.github.tinystork.ZeAnalyser.desktop`
- `zeanalyser/icon/zeanalyz_icon.png`

A Linux distributor or desktop installer should install those resources as:

```text
${prefix}/share/applications/io.github.tinystork.ZeAnalyser.desktop
${prefix}/share/icons/hicolor/512x512/apps/io.github.tinystork.ZeAnalyser.png
```

For a per-user installation, `${prefix}` is normally `~/.local`; for a system
package it is normally `/usr`. The desktop entry launches the public
`zeanalyser` GUI entry point. Runtime startup never copies these files, writes
to desktop configuration, requires privileges, or depends on ZeAlfie.

`StartupWMClass=ZeAnalyser` preserves X11/XWayland matching, while the desktop
file basename and Qt desktop file name provide the Wayland application ID.
