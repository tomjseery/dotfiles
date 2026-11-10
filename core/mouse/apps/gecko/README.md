# Native autoscroll cursor

`native-cursor.cfg` observes Gecko's actual browser-chrome autoscroll popup.
It hides the popup's paint and applies the current theme's original
up/down/left/right cursor images through a temporary user cursor stylesheet. Native cancellation restores
the previous popup opacity and normal cursor stylesheet. It neither intercepts middle clicks
nor replaces scrolling, link handling or tab handling.

Installation uses Mozilla's native AutoConfig startup mechanism with a root-owned
configuration and bootstrap under each discovered Gecko browser engine. Its
unsandboxed mode permits browser-chrome UI access; the file is trusted local code,
not web content. Existing unrelated AutoConfig is refused. Profiles, cookies,
accounts and sessions are preserved. Changes activate at browser startup.

The discovery requires the installed engine, application metadata and browser
archive, without a browser-name list. Chromium/Electron retain their native
panning cursors; the existing KWin effect continues handling generic fallback.

Apply only the cursor configuration to an already installed runtime:

```sh
./core/mouse/install --cursor-only
```

The existing installation recovery directory receives `native-cursor.json` before
changes. Configuration writes are atomic and a failed write restores the snapshot.
Full mouse installation/recovery also composes this stage.

Run a disposable real-browser check, with remote/system access enabled only for
that test process and temporary profile:

```sh
uv run --directory core/mouse python tests/gecko_cursor_acceptance.py
uv run --directory core/mouse python tests/gecko_cursor_acceptance.py --installed
```

The check verifies native link opening, native tab closing, native scroll progress,
popup transparency, direction changes and trusted Escape cleanup. Its test profile
uses main-thread scrolling for deterministic headless execution. Physical appearance
and the normal application's APZ path still require user acceptance.

Native interfaces were verified with Firefox 159.0.1. Missing/changed native state
leaves the ordinary browser indicator intact. Requalify the observer after engine
UI changes. The script uses event observation, not browser executable/prototype
patching.

`midscroll_routing.cursor` reads the existing Xcursor images and hotspots, renders
inline PNGs, and writes the runtime configuration outside Git. It preserves the
original glyphs and does not modify the cursor theme.
