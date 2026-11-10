# Contained native bridge acceptance

`run.py` builds a disposable Wayland client and exercises the **built native
bridges** in fresh compositor sessions. It never installs a plugin or connects to
the existing desktop. Run from the repository root, after building the bridges
as described in [their README](../README.md):

```sh
uv run --project core/mouse --no-sync python core/mouse/target-bridges/tests/run.py \
  --kwin-bridge core/mouse/target-bridges/build/dev/mousetarget.so \
  --hyprland-bridge core/mouse/target-bridges/build/dev/mouse_target_hyprland.so \
  --render-node /dev/dri/renderD128
```

Select `--backend kwin` or `--backend hyprland` for a single bridge. Both modes
require KWin, because Hyprland nests into an owned KWin virtual output. All bridge
paths and the render node are explicit arguments. `--artifacts NEW_DIRECTORY`
selects the retained result directory; the default is an ignored unique directory
under `tests/artifacts/`. The directory must not already exist. The harness does
not run package managers, modify services or change installed configuration.

## Prerequisites and containment

This harness targets the bridge versions KWin **6.8.2** and Hyprland **0.57.1**
(Aquamarine **0.16.0**), on Linux with unprivileged user namespaces enabled. The
bridges enforce their own version/ABI constraints. Required tools are Bubblewrap,
D-Bus, KWin, kdotool, CMake, Ninja, GCC/G++, pkg-config, Wayland client headers and
`wayland-scanner` **1.26+**. Hyprland mode additionally needs `Hyprland` and
`hyprctl`. Python **3.14+** with `dbus-fast` is required; the mouse project's uv
environment provides it. A usable OpenGL DRM render node accessible to the user
is required. No elevated privileges or physical input devices are required.
The first run downloads three protocol XML files over HTTPS; subsequent offline
runs can use `--protocol-dir PREVIOUS_ARTIFACTS/protocols` with the same hash checks.

Each backend gets a separate Bubblewrap user/PID/network/IPC/mount namespace,
private `/proc`, fresh `/dev`, `/run`, `/tmp`, HOME, XDG directories, runtime and
session bus. Only the explicitly selected DRM **render** node is device-bound;
card and input nodes are rejected. `/usr`, `/etc` and `/sys` are read-only. The
selected Python environment is mounted read-only when outside `/usr`. Host home,
Wayland sockets, session bus, logind and seatd sockets are absent. The generated
`launch.json` records the exact sandbox argv. Before starting either compositor,
`probe.py` records and asserts absence of `/dev/input`, `/dev/uinput`, the system
bus socket and seatd socket, the single render node and the private display/runtime.
These assertions and the mount construction are both part of containment.

KWin uses `--virtual` with explicit socket and no lockscreen/global shortcuts.
Its virtual output backend does not create a physical input backend. The fixture
uses KDE fake-input only on `/lab/runtime/mmb-parent-wayland`. Hyprland starts
inside the same sandbox with an owned KWin Wayland parent; its libseat logind
backend cannot reach the private nonexistent system bus. It uses a protocol-created
virtual pointer on the discovered **owned** Hyprland socket. The fixture refuses
inherited display selection and any socket outside `/lab/runtime/`.

Hyprland's exact version does not support an `AQ_BACKENDS=headless` override;
a standalone headless backend also lacks the required allocator/render FD here.
The tested path is contained Wayland nesting. KWin's virtual backend requires
OpenGL; forcing QPainter or `LIBGL_ALWAYS_SOFTWARE` is not a fallback implemented
by this harness. Missing renderer capability fails the run with retained logs.

## Assertions and artifacts

The probe separately records KWin bus/socket readiness, `/Effects` readiness,
plugin discovery and MouseTarget service readiness. It awaits the D-Bus AddMatch
reply before querying KWin. For Hyprland it connects Socket2 and requires the
matching random `mouse-target-ready` token after the observation command reply.
Two mapped xdg-shell roots share app id `mmb-native-probe`; both are configured
and synchronized before moving the synthetic pointer.

Each backend must produce:

- Initial empty target `null`, followed by an actual non-null root target with
  nonempty `{session,surface,app}` fields and the fixture's app id.
- An A→B→A excursion **without a query at B** that preserves session/app and
  changes A's opaque surface generation, with invalidations for both movements.
- Strictly increasing generations within the observed session.
- `null` on an empty area, a clean fixture exit and a final invalidation when
  the owned bridge is removed.

Window geometry is used only to place this test's synthetic pointer; production
recipient identity always comes from the bridge query. Logs include actual
configure sizes and queried window geometry. `result.json`, `containment.json`,
`artifacts.json` (bridge/client hashes), command output, compositor logs, client
logs and `launch.json` remain under each backend directory. `protocol-origins.json`
and build logs are shared in the enclosing run directory. A failing backend
stops the run with a nonzero exit code. Exact owned subprocesses are terminated
and reaped in `finally`; bounded host timeout kills Bubblewrap and its private PID
namespace. Generated schemas, protocol code, binaries and logs are ignored and
may be removed by deleting that run's printed artifact directory.

These are native endpoint and invalidation acceptance checks. They do **not**
test the input daemon, physical-event atomicity, lock/drag/decoration/layer/popup
eligibility transitions, every public compositor event, installation or the real
desktop. The bridge contract's documented snapshot/event limitations still apply.

## Immutable protocol inputs

`run.py` pins these revisions and verifies SHA-256 before calling the scanner;
XML and generated files are not vendored:

| Protocol | Immutable source | SHA-256 |
| --- | --- | --- |
| KDE fake-input v6 | [plasma-wayland-protocols 1db07441870d54157e937674b99380a7dcc0fb32](https://raw.githubusercontent.com/KDE/plasma-wayland-protocols/1db07441870d54157e937674b99380a7dcc0fb32/src/protocols/fake-input.xml) | `89f4ada4a1f09168a4528f47c0495e3f89dc2a25e8b23f4539ed3f5110eff708` |
| xdg-shell | [wayland-protocols 3eab2dccf4bfdd85c16d312a6c8c8fbc2a6e73a8 (1.50)](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/raw/3eab2dccf4bfdd85c16d312a6c8c8fbc2a6e73a8/stable/xdg-shell/xdg-shell.xml) | `8cd3980d0783e1f55d12901ac51533204af71487cc4dc69ee00bb7096647d9de` |
| wlr virtual-pointer | [Hyprland acc1aa0bfd4bd575dcb0f76c35ccf12b660a1ab9](https://raw.githubusercontent.com/hyprwm/Hyprland/acc1aa0bfd4bd575dcb0f76c35ccf12b660a1ab9/protocols/wlr-virtual-pointer-unstable-v1.xml) | `3ff6d540be0bc5228195bf072bde42117ea17945a5c2061add5d3cf97d6bb524` |

The first promoted-harness acceptance ran both backends successfully with GCC
16.2.1, CMake 4.4.5, Wayland 1.26.0 and Bubblewrap 0.13.1. Treat fresh result files,
including their hashes and compositor version output, as evidence for a particular
build rather than a guarantee about other compositor versions or renderers.
