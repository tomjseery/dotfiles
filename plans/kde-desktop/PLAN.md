# KDE wallpaper switching and consistent desktop

## Authority and ownership

Canonical plan: `/home/tommy/projects/dotfiles/plans/kde-desktop/PLAN.md`.
Repository: `/home/tommy/projects/dotfiles`.
Research assets and prior backups remain outside Git at
`/home/tommy/.local/state/dotfiles/trials/kde-theme-research/`.

This plan continues the original KDE research goal and records the user's later
corrections in the same owner. Latest request explicitly authorises adding
Firefox as the default browser and consistent native window controls to the
plan. Planning and read-only diagnosis are authorised for these additions;
this request does not authorise changing live browser defaults/preferences,
installing a switcher or applying a wallpaper yet. Earlier Kitty adjustments
and Konsole removal were separately authorised and completed below.

KDE-specific runtime integration belongs under `desktops/kde/`, the existing
KDE section in this repository. Shared behaviour and existing appearance files
retain their established owners; do not add competing configuration sources.
Hyprland remains a separate workstream and must not be changed.
Do not publish this plan or code without explicit delivery authority.

Current phase: bounded planning/diagnosis, lane L3, because the native Firefox
mechanism and restrained switcher integration require compatibility decisions.
No model switch or independent execution owner is claimed.

## Context

Arch Linux, KDE Plasma 6.8.2, Wayland, 2560 × 1080 ultrawide at scale 1.
Installed plasma-desktop/workspace/KWin match the Arch repository versions
checked on 2026-11-09. This does not establish switcher compatibility.

The current direction is a user-chosen anime wallpaper collection with a picker
and next/previous actions, a stable readable desktop and restrained optional
matching accents. There is no purple requirement and no dominant fixed theme.
Retain the bottom taskbar, familiar window controls and the accepted Kitty
appearance. Tommy selects artwork before any generated side extensions.

Firefox should become the default browser. Its window controls should match
the KDE decoration used by Kitty and other applications, with one authoritative
system style and supported application integration rather than copied button
icons or a collection of CSS overrides. User's screenshot shows differing
Firefox tab-strip controls, but the actual native-decoration result remains
to be tested.

Global `/home/tommy/AGENTS.md` and repository `AGENTS.md` apply. Root operations
use pkexec; no root operations are part of this planning update. Preserve
CLAUDE.md symlinks, unrelated changes, running sessions and browser data.

## Next Steps

Work in baby steps, one small reviewed change at a time. The video-inspired
panel refresh below is a deferred idea, not current implementation scope.

1. Review the browser/defaults and native-decoration proposal below with Tommy.
   Before live changes, resolve the existing delivery checkout and preserve
   unrelated KDE edits. Planning-only work stops before application.
2. Once implementation is authorised, validate Firefox's native-decoration
   path in a disposable profile on the current Plasma Wayland session. Confirm
   matching close/minimise/maximise controls and no duplicate button rows.
   Do not restart the user's real Firefox session without arranging it.
3. Implement the approved defaults and decoration integration declaratively,
   keeping KDE-only settings scoped to Plasma and generic preferences in their
   existing owner. Verify idempotence, rollback and no Hyprland regression.
4. Adapt the researched picker/collection model as a KDE-owned component:
   thumbnails plus next/previous wallpaper actions, optional native wallpaper
   accent, stable panel/window layout and Kitty contrast. Do not run the broad
   plasma-themer installer as-is. Verify against local Plasma 6.8.2.
5. Five wallpapers are now selected and their ultrawide files are prepared
   (see Selected collection below). Review the exports before live wallpaper
   application. No launcher replacement or switcher installation yet.

## Pickup

Research agent acknowledged this bounded task. Native terminal launch failed before opening; fallback in-session research agent owns only this folder. Current KDE appearance inspection started read-only.

## Research result

Completed read-only current-theme inspection, primary-source comparison and visual inspection of five public screenshots. Findings and direct preview links are in IDEAS.md. Recommended first comparisons: Nothing KDE for composed widgets/bottom dock, Mystical Blue for cool-blue app styling, Imperial Geass Noir for coordinated purple anime-inspired appearance and terminal profiles. Daemon2 and Bitpunk supplied as bolder cyberpunk alternatives. Exact local Plasma6.8.2 runtime compatibility remains untested. No live configuration, package, dotfiles or Hyprland edits were made. The native terminal launcher failed before creating a session; this bounded fallback research agent performed the work. Next action belongs to user: choose a visual direction before implementation is authorised.

## Delivery update from originating session
Native terminal launcher returned definite failure before opening (exit1,
base-agents → tj-agents marketplace name mismatch). No profile modification was
made. Fallback research agent completed IDEAS.md. User cancelled launcher repair
and requested a pasteable prompt; originating session supplied it. Future new
session should read existing ideas before repeating the search. No automatic
retry, settings migration or theme installation is authorised by this update.

## Current state — 2026-11-09
Tommy authorised and accepted the Kitty-only appearance changes after browser comparison: KDE-only Dracula palette, opaque image-free background, JetBrains Mono Medium for ordinary text and Bold for emphasis, original 12 pt size. Settings were reloaded, backed up, checked with Kitty’s parser, and committed in dotfiles. Hyprland parsed settings remained unchanged.

He separately authorised uninstalling Konsole: both native and system Flatpak copies are now absent; Kitty remains installed and is the configured KDE default terminal. Saved Konsole profiles/data were retained. Dolphin/Kate integrations that require Konsole are optional.

A generated extension of the Plastic Memories wallpaper was produced too early and rejected as a direction, not adopted. Current explicit correction: research online anime-girl choices and discuss them FIRST; user selects before further generation or desktop changes. Existing wallpaper and launcher remain unchanged. The new gallery contains five unedited originals from port19x/Wallpapers and dharmx/walls, with dimensions, source links, restrained-purple notes and possible launcher directions. No new wallpaper or launcher has been applied.

## Switcher research — current direction
User rejected the initial five-artwork gallery, requested browsing links, then removed the purple requirement. Latest preference is a wallpaper/theme switcher for a small personally chosen collection, with restrained styling rather than a dominant fixed theme.

Primary-source research identified:
- https://github.com/envy-vain/plasma-themer — MIT, Plasma 6 Wayland, keyboard-driven picker, per-theme background collections and next/previous commands. Inspected commit `9864a9330f5a636aaedfc545b00e77f06ea2c7dc`. Best assembly reference, but broad default targets include login screen, Firefox and many apps; even `themer bg` invokes login-screen and Firefox handlers. Do not run unmodified as wallpaper-only.
- https://github.com/Xzzz0/KDE-Wallpaper-Picker — small Python/PyQt6 carousel and category picker using plasma-apply-wallpaperimage. Inspected commit `07710a49d60b40a00f0676c4f06d0b2177f7b11b`. Author-specific hardcoded paths, global /tmp cache/socket, README claims MIT but no separate licence file in the tree. Needs adaptation and a licensing check before vendoring.
- https://github.com/avinashsingh192/PlasmaWall — two-file Python/PyQt6 project with image/video library, search/favourites and optional pywal. Inspected metadata/tree at `8aa753f26ead0ed3b5c83e6d723319bcba7ef7c0`. Very small project; no explicit licence detected. Suitable feature reference, not yet selected for installation.
- https://github.com/luisbocanegra/kde-material-you-colors — Plasma 6 colour generation with colourfulness/brightness control and app integration. Broader than needed if native accent extraction suffices.

KDE’s official Colors documentation confirms native accent extraction from wallpaper independently of the optional whole-scheme tint. Preferred restrained design uses a stable dark scheme and no whole-desktop recolouring. Screenshot of plasma-themer’s real picker saved under switcher-research/plasma-themer-picker.png. Nothing from these switcher projects was executed or installed. Exact local 6.8.2 compatibility remains untested.

## Firefox default and consistent window controls

### Observed state

- Native Firefox 159.0.1 is installed; a Flatpak Firefox also exists from earlier
  inspection. Resolve the running installation and intended desktop ID before
  switching defaults; do not pick a package blindly or remove either copy.
- `xdg-settings get default-web-browser` returns `google-chrome.desktop`.
- Live KDE General/BrowserApplication and
  `core/config/kde/settings/kconfig/kdeglobals` both select `google-chrome.desktop`.
- KWin uses `org.kde.klassy`; controls are on the right with
  `ButtonsOnRight=IAX` and an empty left side. This is the existing decoration
  owner to retain, not a reason to replace the desktop theme.
- No live Firefox preference, default-browser or decoration change was made
  during this planning update.

### Planned behaviour and ownership

1. Make the selected Firefox installation the default for HTTP, HTTPS and HTML,
   as well as KDE's preferred browser. Preserve Chrome for explicit use and
   preserve bookmarks, profiles, extensions, accounts and sessions.
2. Persist the generic browser preference through the established dotfiles
   browser/KConfig/MIME owners. Add Firefox application integration in
   `core/config/apps/firefox/` if needed; avoid duplicating the same preference
   in several managed layers. Do not commit profile databases or credentials.
3. Keep one system decoration style in KWin. Prefer Firefox's supported native
   Title Bar integration so KWin draws the buttons. This normally adds a
   separate native titlebar above the tab strip; review this visual tradeoff
   before applying it to the real profile.
4. Test the official titlebar option/preference (`browser.tabs.inTitlebar=0`)
   and, for a KDE-only launch path where appropriate, the supported
   `MOZ_GTK_TITLEBAR_DECORATION=system` mechanism. Mozilla source recognises
   `system`, `client` and `none`. These are candidate mechanisms, not a claim
   that setting an environment variable alone has been verified on this host.
5. Do not write a shared Firefox profile preference that changes Hyprland's
   decoration behaviour. Keep the KDE-specific environment/launch integration
   under `desktops/kde/`; select the smallest supported mechanism that the
   disposable-profile experiment demonstrates works.
6. Avoid userChrome.css button replacements, duplicated icon sets, forced
   cross-session GTK overrides or broad window rules as the initial solution.
   A compositor cannot universally replace controls drawn inside arbitrary
   client applications. Inventory real exceptions and use supported native
   decoration settings where available, rather than promising a global switch
   that every program obeys.
7. Keep wallpaper switching independent of Firefox's default-browser and
   decoration preferences. Upstream plasma-themer's Firefox recolouring should
   not silently become another configuration owner.

### Acceptance checks

- HTTP/HTTPS/HTML and KDE preferred-browser queries resolve to the chosen
  Firefox desktop entry. A local test link opens that installation.
- Firefox, Kitty, Chrome and Dolphin use the same KDE button geometry, order
  and style when native decorations are enabled; check normal, maximised,
  snapped and fullscreen states, with no duplicated controls.
- Close/minimise/maximise and window dragging/snapping work normally. Firefox
  tabs and browser toolbar remain usable with the chosen titlebar arrangement.
- Reapplying dotfiles keeps the result without duplicate entries, resets or
  overwritten application data; a documented restore returns prior settings.
- Hyprland settings and behaviour remain unchanged. Any unsupported app is an
  explicit tested exception, not silently covered by a vague universal claim.

### Primary-source references

- Mozilla's supported Title Bar control:
  https://support.mozilla.org/en-US/kb/customize-firefox-controls-buttons-and-toolbars
- Mozilla GTK decoration selection implementation:
  https://github.com/mozilla-firefox/firefox/blob/main/widget/gtk/nsWindow.cpp
  (`GetSystemGtkWindowDecoration`).

### Current gate

The user requested this addition to the plan. Browser migration and live
window-decoration changes remain unapplied. First execution action after
approval: resolve the active Firefox package, then verify native KDE controls
with a separate disposable profile before changing the user's browser.

## Deferred idea: cleaner Catppuccin panel

Reference supplied by Tommy:
https://www.youtube.com/watch?v=ZyPSlm8D9ZQ
("Aesthetic & Productive: My KDE Plasma Desktop Workflow", Lau).

Tommy likes its calmer, more minimal appearance, especially the cleaner
taskbar. Keep Catppuccin as a possible base and borrow only selected details;
this is not a request to reproduce or install the complete setup. The actual
panel details have not been visually verified here. User explicitly deferred
this investigation and asked for baby steps. Do not change the panel now;
revisit this reference only when that small work item is selected.

## Selected collection — 2026-11-09

Tommy explicitly selected the following five Alpha Coders images and asked to
make them ultrawide. This authorises downloading the originals and generating
side extensions; it does not authorise installing the switcher, changing the
panel/browser/launcher, or applying a live wallpaper.

| Source ID | Title | Artist credited by source |
| --- | --- | --- |
| [1359466](https://wall.alphacoders.com/big.php?i=1359466) | Skybound Serenity | robokoboto |
| [1407458](https://wall.alphacoders.com/big.php?i=1407458) | Hatsune Miku Glitch | hwancat |
| [1358147](https://wall.alphacoders.com/big.php?i=1358147) | Anime Girl in Blue | robokoboto |
| [1384235](https://wall.alphacoders.com/big.php?i=1384235) | Aesthetic Gaming Lofi | patrika |
| [1314137](https://wall.alphacoders.com/big.php?i=1314137) | Serene Anime Girl at Train Station | 葛城ナコモ |

Files stay outside Git in `/home/tommy/Pictures/Wallpapers/selected/`:
- `originals/`: unmodified source downloads.
- `ultrawide/`: five AI side extensions, exported and dimension-checked at 2560 × 1080.
- `collection.json`: titles, source URLs, credited artists, original/generated file paths and SHA-256 checksums.
- `SOURCES.md` and `PROMPTS.md`: attribution and generation notes.
- `index.html`: local review gallery with Original/Ultrawide comparison and full-size image links; it does not apply wallpapers.

The third selection was thought to be saved already. Exact-byte and approximate
visual checks in Pictures/Downloads found no matching prior copy. All originals
were therefore retained in the curated collection; nothing pre-existing was
removed. The train-station artwork is nearly square and required substantially
more side extension than the other four. Generated subjects and scenes were
visually checked; originals remain available for comparison. No live desktop,
Firefox, launcher or Hyprland configuration was changed by this preparation.
