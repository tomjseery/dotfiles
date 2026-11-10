# Mouse behaviour

Middle clicks remain native unless an application is explicitly opted into
midscroll fallback and a current native compositor target confirms its recipient.
Native tab closing, link opening and application autoscroll therefore do not
require a browser window-class exception list.

## Ownership

- `upstream-revision` and `patches/native-routing.patch` compose one immutable
  upstream midscroll source. `src/midscroll_routing/` supplies gesture ownership,
  authenticated session helpers, source preparation and installation utilities.
- `package/usr/share/midscroll/native-default.conf` owns only `NATIVE_DEFAULT`
  and `FALLBACK_APPS` when upgrading an existing configuration. Other scroll
  tuning is preserved. A first installation uses the complete profile.
- `target-bridges/` exposes actual pointer focus for the exact supported KWin and
  Hyprland versions. See its [interface and timing contract](target-bridges/README.md).
- `apps/chromium/` owns the supported `middleclick-autoscroll` configuration and
  AUR dependency manifest. Its upstream helper discovers native engine flags;
  this module keeps no Chromium application-name list. Customized helper config
  must be reviewed before installation rather than overwritten.
- Gecko runtimes are discovered by their installed engine and browser archive,
  independently of application name. The installer adds application defaults for
  autoscroll and disables middle-button paste/URL loading. It preserves other
  preference files and all user profiles. An existing user preference overrides
  an application default; restart applications and check their settings.
- `settings/kconfig/kwinrc` enables only the target bridge. The independent
  `kwin-scroll-cursor/` effect and its existing activation preference are retained.
  The supported overlay CLI suppresses duplicate drawing only when that effect
  is loaded. Drawing components never grant routing authority.

Only registered session helpers can answer target requests. Missing endpoints,
observation gaps, invalid/stale replies, ambiguous authorities and unsupported
surfaces leave new button sequences native. A native press retains its native
release; consumed fallback presses retain their release ownership through target
changes and device resynchronization. Focus events revoke existing fallback
leases, including an A→B→A excursion between queries.

The bridge query describes the current compositor state. It cannot atomically
identify the recipient of an earlier physical event. IPC scheduling and guard
changes without public notifications remain acceptance limits; the implementation
does not claim universal input interception correctness.

## Prepare and check

Run as the desktop user from the repository root:

```sh
./install/mouse.sh --dry-run
./install/mouse.sh --prepare
```

Dry run writes nothing. Preparation runs Python checks and isolated regressions,
prepares pinned upstream source under the XDG cache, builds and inspects the real
Arch package, verifies a recovery package, and builds both native bridges. It
changes no installed packages, services or desktop configuration. Build outputs
and downloaded source stay outside version control.

Use Arch's installed Python 3.14+, `uv`, GCC, CMake/Ninja, matching compositor
headers and dependencies. The bridge README describes staging Vulkan headers
without root. Python/Arch metadata declares the `dbus-fast` runtime dependency.
Install the native application helper from `apps/chromium/aur-packages` before
applying a full configuration. Preparation assumes the existing workstation
midscroll installation: recovery refuses an unverified installed version.

The focused command is `./core/mouse/check`. Shell changes also require `bash -n`,
ShellCheck and `shfmt -d -i 2`. Tests exercise the prepared patched daemon and
actual Unix transport without physical devices. Installer tests use disposable
homes. Bubblewrap tests run root stages in a private user namespace with synthetic
package/service commands, then check automatic and explicit restoration. They
prove transaction ordering and file recovery; the separate real Arch build proves
package layout and system-interpreter imports. They do not simulate pacman's
internal database failures.

## Apply and recover

After source review and deployment approval:

```sh
./install/mouse.sh
```

The public installer serializes preparation, configuration and recovery through
one owner-only global lock directory under `/tmp`. An overlapping invocation or
a different account fails before mutation. Root-stage flags are internal calls
under that lock. Each invocation reads its own emitted recovery receipt; the
convenience `last-recovery` file is never a transaction handoff.

The root stage uses `pkexec` for native graphical authentication. It retains a
verified prior package, exact owned-file contents/modes and daemon enable/running
state under `/var/lib/dotfiles-mouse/recovery.*` (root-only). It installs the
prepared runtime and both bridges, merges owned policy, adds engine defaults and
restarts only the mouse services. Bridges activate on the next desktop session;
the installer never loads/unloads a plugin in the live compositor. Hyprland's
session startup imports its instance environment and loads its matching bridge.

A profile-owned systemd override, kept outside pacman's file list, starts the
daemon with `--native-default`. Replacing the package with an incompatible stock
version retains that guard and fails before grabbing input. Compositor upgrades
require a bridge rebuild and acceptance against the new exact API versions.

The user stage snapshots its overlay override, KWin configuration and native-app
helper config under `$XDG_STATE_HOME/dotfiles-mouse/recovery.*`. Failure restores
those files and the prior mouse-service running/enable states, then restores the
root stage. Recovery is retained if authentication is cancelled or restoration
fails. The final upstream native-app `apply` operation manages desktop-launcher
flags and its own watcher; those upstream-managed outputs are outside the owned
file snapshot. Repeating its supported apply operation repairs that separate
integration. No user profiles, input-remapper mappings or unrelated services are
rewritten or stopped.

For an explicitly selected system recovery, run `./install/mouse.sh --recover`
with the exact recorded root recovery directory, as the desktop user. It takes
the same transaction lock and invokes the internal root recovery through `pkexec`.
Its standalone recovery utility works even after removing the new Python package.
User file snapshots can be restored using the same checkout's installation
module and `--root "$HOME" restore SNAPSHOT`. Record paths before removing a
checkout; recovery directories must be kept until deployment acceptance.

`--configs-only` requires an installed native runtime. It merges session files and
writes the native-helper config, while omitting package operations, service
operations, bridge activation and the upstream helper's apply command.

## Acceptance status

Contained KWin and Hyprland sessions have exercised actual native target queries,
observation readiness, same-class root windows, A→B→A invalidation and empty-area
rejection. Physical devices and the live desktop were not involved. The bridge
acceptance harness records exact binaries and containment evidence separately.

Complete composed helper/daemon and real application acceptance remains necessary
before claiming the deployment works: native tab close, link/thumbnail opening,
native autoscroll, fallback start/stop, popups, lock/grabs/constraints, disconnects,
and multiple input devices on both supported desktops. Source tests and isolated
bridge acceptance do not substitute for that deployment gate.
