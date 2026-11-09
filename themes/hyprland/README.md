# Hyprland visual presets

Both folders use the same desktop, controls, widgets, apps and terminal from
[`desktops/hyprland`](../../desktops/hyprland/README.md). `settings.json` is a native
visual overlay; `scheme.json` supplies its named palette. Switching uses the
existing shell Presets page, with no duplicate desktop stack.

| Preset | Appearance | Selected wallpaper |
| --- | --- | --- |
| Blue | Navy surfaces, violet/cyan/pink accents; opaque terminal and panels | Original robokoboto blue anime artwork |
| Charcoal | Dark grey, muted accents; 0.8 terminal opacity, frosted mini dashboards; subtle pale two-tone clock | Generated ultrawide adaptation of `kita.png`, with less zoom |

The Blue folder also retains an optional generated wider version; it is not the
selected wallpaper. Both generated images have their full prompts beside them.
The original Blue and Charcoal images are downloaded by the shared manifest rather
than copied into Git. `wallpaper.png` links are created during installation.

## Sources

- Blue original: [robokoboto artwork on Alpha Coders](https://wall.alphacoders.com/big.php?i=1358147),
  raw `https://images2.alphacoders.com/135/1358147.png`. The source lists personal
  use; artwork remains subject to its creator's terms.
- Charcoal original: [ViegPhunt Wallpaper Collection, kita.png](https://github.com/ViegPhunt/Wallpaper-Collection/blob/main/Wallpapers/kita.png).
  Visual inspiration from [ViegPhunt's Dotfiles](https://github.com/ViegPhunt/Dotfiles),
  including the 0.8 terminal opacity; that desktop stack was not installed.
- Widget layout/avatar inspiration: [pctrade Asuka V2](https://github.com/pctrade/end4-pCpresets/tree/main/presets/Asuka_V2).
- Generated adaptations: built-in image generation from the clean original artwork,
  retaining source and result separately. No video or desktop screenshot used as
  wallpaper input. Source artwork rights still apply.

User notes and prompt/source provenance stay with these presets. Shared controls,
dock pins, credentials and runtime state do not belong in appearance overlays.
