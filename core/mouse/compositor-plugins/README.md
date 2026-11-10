# Compositor plugins for pointer targets

These two independent native modules expose a read-only snapshot of the
compositor's **current pointer input focus**. They do not intercept input, draw
a cursor, choose fallback applications, inject events or run another daemon.
The existing cursor effect is unchanged.

The native interfaces used here have no stable cross-version C++ ABI. The KWin
module requires **KWin 6.8.2** headers and its factory metadata identifies that
version. The Hyprland module requires **0.57.1** headers and refuses initialization
unless Hyprland's compositor/dependency ABI fingerprint matches its compiled
fingerprint. Rebuild and requalify the bridges after compositor upgrades; changing
the version check alone is not a compatibility fix.

## Query contract

Each endpoint returns one JSON value:

```json
{"session":"opaque bridge lifetime","surface":"opaque focused surface lifetime","app":"application id"}
```

`null` means no trustworthy supported target at query time. Missing endpoints,
transport errors, invalid JSON and invalid fields must also remain unknown in
the calling helper. Never substitute the active keyboard window or cached class.

`session` is new for each module lifetime, including unload/reload. `surface`
combines a compositor window identity with a generated token and the bridge's
focus generation. The generation advances on every actual pointer-focus
notification, including transitions through unknown surfaces. An A→B→A excursion
changes the token even when no query observed B. Destruction or an observed
unknown target also prevents token reuse. Consumers compare the opaque strings,
not their structure.
`app` is KWin's resource class or Hyprland's current application ID, with its
original spelling. Matching policy belongs to the consumer.

The initial supported target is a mapped root application-window surface.
Popups, subsurfaces, desktop/panel/layer surfaces, absent targets, session lock,
pointer constraints, drag-and-drop, existing held buttons and recognized
compositor interception return `null`. KWin additionally rejects decoration
focus, interactive movement/resizing, window selection, effects' mouse/keyboard
grabs and fullscreen effects. Hyprland rejects explicit seat grabs, kill mode
and active layout drags, and rejects non-content areas of the already-focused
root surface. Its rectangle check only rejects targets; it never chooses one.

The endpoint is a snapshot in the compositor event loop, **not an atomic answer
about an earlier physical button event**. A query token cannot change that fact.
Pointer movement, another device, application destruction or a session transition
can happen before or after the snapshot. The consumer must bound its query,
validate session/surface continuity, keep full button-sequence ownership and
retain native input on uncertainty. The invalidation stream described below is
required; querying periodically alone loses transitions between samples.
Neither bridge controls arbitrary third-party
plugins that might later consume events. Those combinations need explicit
acceptance; compilation does not establish their behavior.

## Endpoints

KWin effect ID: `mousetarget`. Session D-Bus service and interface:
`org.tomjseery.MouseTarget`; object `/MouseTarget`; zero-argument method `target`;
return type `s` containing the JSON value. Only a dedicated adaptor's query is
exported. The effect is disabled by default and paints nothing. A registration
conflict is reported to the compositor log and leaves the bridge unavailable.
The snapshot uses `PointerInterface::focusedSurface()`, the effective recipient,
and requires an attached focus subscription. The D-Bus adaptor emits
`changed(s session, t generation)` on every effective-focus transition. It also
invalidates on observed decoration-focus, session-lock, pointer-capability,
fullscreen-effect, drag start/end and the queried window's class changes. A final
invalidation precedes D-Bus service removal.

Hyprland module: `mouse_target_hyprland.so`. It registers the exact custom
hyprctl command `mouse-target`, which returns JSON in either output mode.
It also registers `mouse-target-observe TOKEN`, matched by the exact prefix
`mouse-target-observe ` with its trailing space. Unloading unregisters both
commands. It obtains `SeatManager` pointer focus,
resolves that exact resource to its owning root Window and reads that Window's
metadata. It never reconstructs the input target from the client list.
The plugin owns `pointerFocusChange` subscriptions and posts Socket2 lines:

```text
mouse-target-changed>>{"session":"opaque bridge lifetime","generation":1}
```

The generation is an unsigned integer. Socket2 is Hyprland's event stream under
the selected instance's `.socket2.sock`. The plugin also invalidates on observed
drag-focus, lock/unlock and application-class changes. It detaches its owned
listeners, emits final invalidation and then unregisters its query during normal
plugin exit. Hyprland 0.57.1 uses `IPC::Socket2::sock()->postEvent`, not the old
EventManager interface.

For the Hyprland observation barrier, first connect and read Socket2, then issue
`mouse-target-observe TOKEN` using a fresh, unpredictable 32-character ASCII
hexadecimal token. The plugin validates the exact length and character set,
posts `mouse-target-ready>>TOKEN` to Socket2, and replies `ok` to the command.
Only receipt of the matching event on the helper's own event connection proves
that connection was accepted before the barrier. The command reply alone does
not establish observation readiness. Wrong, missing or late tokens leave the
helper unregistered and native input intact. Invalid tokens produce
`invalid observation token` without posting a ready event.

For KWin, install the D-Bus signal match and await the bus's successful AddMatch
reply before permitting the initial query. No extra bridge method is required.

Establish the relevant observation barrier before obtaining an initial snapshot
or registering the helper as a routing authority. Any event, including one
arriving after a query response, revokes the
current lease; a late event may conservatively cancel a newer valid lease.
Invalidate in-flight decisions too. Monitor D-Bus service-owner loss or Socket2
disconnection, malformed events and missing endpoints; do not retain permission
across an observation gap. Hyprland removes slow Socket2 clients after 64 queued
events, so reconnecting requires fresh observation and a new query.

Focus generations preserve transitions even when event delivery is delayed.
They do not make the separate query and event transports globally ordered or
eliminate IPC latency. Not every guard has an equivalent public change signal:
for example, pointer constraints, some non-fullscreen grabs and layout-drag
start may only be recognized by the next query. Their snapshot guards remain
fail-native. Those timing combinations need isolated acceptance and must not be
represented as universally immediate invalidation.

The session helper should use the current compositor's own IPC endpoint, under
the active desktop user's account. These endpoints do not establish authorization
for a root daemon; authenticated helper/seat selection remains that daemon's
responsibility.

## Build without activation

Use GCC 16 and the matching installed compositor development headers. KWin's
exported CMake target also requires its transitive development dependencies,
including Vulkan headers. Hyprland dependencies come from its installed
`hyprland.pc`; JSON encoding uses the installed `nlohmann_json` CMake target.

From this directory:

```sh
cmake --preset dev
cmake --build --preset dev
```

To build only one bridge, configure with `-DBUILD_KWIN_BRIDGE=OFF` or
`-DBUILD_HYPRLAND_BRIDGE=OFF`. Outputs are `build/dev/mousetarget.so` and
`build/dev/mouse_target_hyprland.so`. Build products are ignored. CMake provides
no installation or activation target.

For an isolated build when Vulkan headers are absent, stage the official Arch
`vulkan-headers` package outside the system and pass
`-DVulkan_INCLUDE_DIR=/absolute/staging/usr/include` to CMake. No root operation
or desktop restart is necessary for that build. The November 2026 development
check staged package `1:1.4.363.0-1` under ignored `build/dependencies`; its SHA-256
matched the local pacman sync database:
`574e320444b0eac2479f2c3441c6d030176db572bca8a783bf2a67b808a11ebd`.

Both modules compiled and linked against the installed versions above with GCC
16.2.1 and CMake 4.4.5. Their expected plugin entry points were inspected in the
built shared objects. Neither module was installed, loaded or queried in the
running desktop. Both passed native interface acceptance in contained disposable
compositors; see the [reproducible harness](tests/README.md). Physical input and
complete daemon/application acceptance remain separate gates.

## Acceptance still required

Use disposable compositor sessions to verify the actual endpoint, helper and
daemon together: distinct same-class windows; focus changes; root versus popup,
subsurface, panel and decoration targets; lock; grabs; constraints; drag-and-drop;
helper/module disconnect; module reload; and malformed or late replies. Verify
native tab-close, link-open and native autoscroll together with fallback start
and stop behavior. Physical KDE and Hyprland acceptance remains a separate gate.

## Source references

- [KWin 6.8.2 input focus and hover](https://github.com/KDE/kwin/blob/v6.8.2/src/input.h)
- [KWin 6.8.2 seat pointer focus](https://github.com/KDE/kwin/blob/v6.8.2/src/wayland/seat.h)
- [Hyprland 0.57.1 seat focus state](https://github.com/hyprwm/Hyprland/blob/acc1aa0bfd4bd575dcb0f76c35ccf12b660a1ab9/src/managers/SeatManager.hpp)
- [Hyprland native plugin API and ABI warning](https://github.com/hyprwm/Hyprland/blob/acc1aa0bfd4bd575dcb0f76c35ccf12b660a1ab9/src/plugins/PluginAPI.hpp)
