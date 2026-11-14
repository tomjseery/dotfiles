"""Focused checks for scoped Hyprland capture; upstream tests use local pinned caches."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hyprland_prepare', ROOT / 'desktops/hyprland/prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class HyprlandPresets(unittest.TestCase):
    def test_visual_overlays_do_not_own_shared_controls(self):
        for slug, opacity in [('blue', 1), ('charcoal', .92)]:
            data = json.loads((ROOT / 'themes/hyprland' / slug / 'settings.json').read_text())
            self.assertEqual(set(data), {'appearance', 'background', 'sidebar', '_presetMeta'})
            self.assertEqual(data['appearance']['wallpaperTheming']['terminalGenerationProps']['backgroundOpacity'], opacity)
            self.assertEqual(data['background']['widgets']['glass']['enable'], slug == 'charcoal')
            self.assertFalse(data['appearance']['wallpaperTheming']['enableQtApps'])

    def test_reinstall_does_not_reset_selected_theme_or_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            runtime = home / prepare.RUNTIME
            cfg = runtime / 'config/illogical-impulse/config.json'
            cfg.parent.mkdir(parents=True)
            saved = {'appearance': {'palette': {'namedScheme': 'charcoal_anime'}},
                     'dock': {'pinnedApps': ['my-personal-app']}}
            cfg.write_text(json.dumps(saved))
            (runtime / '.dotfiles-managed').write_text(prepare.fingerprint() + '\n')
            with patch.object(prepare, 'fetch_sources', side_effect=AssertionError('Unneeded rebuild')):
                prepare.install(home)
            self.assertEqual(json.loads(cfg.read_text()), saved)

    def test_update_keeps_custom_presets_and_replaces_managed_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build, live = root / 'build', root / 'live'
            build.mkdir(); live.mkdir()
            (build / 'Blue.json').symlink_to('../managed.json')
            (live / 'Blue.json').symlink_to('../old.json')
            (live / 'My_Custom.json').write_text('{"my": "preset"}')
            (build / 'shared.conf').write_text('updated')
            (live / 'shared.conf').write_text('old')
            prepare.overlay_tree(build, live)
            prepare.overlay_tree(build, live)
            self.assertEqual((live / 'Blue.json').readlink(), Path('../managed.json'))
            self.assertEqual((live / 'My_Custom.json').read_text(), '{"my": "preset"}')
            self.assertEqual((live / 'shared.conf').read_text(), 'updated')

    def test_gallery_changes_do_not_trigger_configuration_reinstall(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            component = repo / 'desktops/hyprland'
            theme = repo / 'themes/hyprland/blue'
            component.mkdir(parents=True); theme.mkdir(parents=True)
            (component / 'shared.conf').write_text('shared configuration')
            (theme / 'scheme.json').write_text('{}')
            with patch.object(prepare, 'REPO', repo), patch.object(prepare, 'COMPONENT', component):
                before = prepare.fingerprint()
                (theme / 'README.md').write_text('New preset guide')
                (theme / 'screenshots').mkdir()
                (theme / 'screenshots/desktop.png').write_bytes(b'new preview')
                (component / 'README.md').write_text('Updated install guide')
                self.assertEqual(prepare.fingerprint(), before)
                (theme / 'scheme.json').write_text('{"new": "palette"}')
                self.assertNotEqual(prepare.fingerprint(), before)

    def test_existing_unrelated_startup_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            loader = home / '.config/hypr/hyprland.lua'
            loader.parent.mkdir(parents=True)
            loader.write_text('-- Someone else owns this startup\n')
            with self.assertRaisesRegex(RuntimeError, 'unrelated'):
                prepare.install(home)
            self.assertEqual(loader.read_text(), '-- Someone else owns this startup\n')

    def test_reconstruct_from_pinned_sources_for_another_home(self):
        caches = {k: Path.home() / '.cache/dotfiles' / v['cache']
                  for k, v in prepare.MANIFEST['sources'].items()}
        if not all((cache / '.git').is_dir() for cache in caches.values()):
            self.skipTest('Fetch pinned source caches with installer to run integration check')
        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory) / 'build'
            prepare.reconstruct(build, Path('/tmp/another-user'), caches)
            for filename in ['config/kitty/kitty.conf', 'config/matugen/config.toml',
                             'config/hypr/hypridle.conf', 'presets/blue/settings.json']:
                text = (build / filename).read_text()
                self.assertNotIn('/home/tommy', text)
                self.assertNotIn('@HOME@', text)
                self.assertIn('/tmp/another-user', text)
            cfg = json.loads((build / 'config/illogical-impulse/config.json').read_text())
            self.assertIn('no_blur = false', (build / 'config/hypr/custom/rules.lua').read_text())
            self.assertEqual(cfg['hyprland']['decoration']['blur']['size'], 8)
            self.assertIn('blur = { size = 8 }', (build / 'config/hypr/hyprland/shellOverrides/main.lua').read_text())
            self.assertEqual(cfg['appearance']['icons']['theme'], 'Papirus-Dark')
            self.assertFalse(cfg['bar']['bottom'])
            self.assertEqual(cfg['dock']['position'], 'bottom')
            self.assertEqual(len(cfg['dock']['pinnedApps']), 8)
            self.assertIn('hyprland-x', cfg['dock']['pinnedApps'])
            self.assertTrue((build / 'config/illogical-impulse/schemes/charcoal_anime.json').is_file())
            shell = build / 'config/quickshell/ii'
            self.assertNotIn('ConflictKiller.load();', (shell / 'shell.qml').read_text().replace('// ConflictKiller.load();', ''))
            self.assertIn('end4pc-kitty-', (shell / 'scripts/colors/applycolor.sh').read_text())
            self.assertFalse((build / 'state').exists())
            self.assertFalse((build / 'presets/blue/README.md').exists())
            self.assertFalse((build / 'presets/blue/screenshots').exists())
            # Native imports must not replace the shared application icon theme.
            import os
            import subprocess
            preset = build / 'presets/blue/settings.json'
            overlay = json.loads(preset.read_text())
            overlay['appearance']['icons'] = {'theme': 'Wrong-Theme'}
            preset.write_text(json.dumps(overlay))
            (shell / 'scripts/colors/switchwall.sh').write_text('#!/usr/bin/env bash\nexit 0\n')
            env = dict(os.environ, XDG_CONFIG_HOME=str(build / 'config'),
                       XDG_STATE_HOME=str(build / 'state'), XDG_CACHE_HOME=str(build / 'cache'))
            subprocess.run(['bash', str(shell / 'scripts/presets.sh'), '--apply', 'Blue_Anime'],
                           env=env, check=True, capture_output=True)
            applied = json.loads((build / 'config/illogical-impulse/config.json').read_text())
            self.assertEqual(applied['appearance']['icons']['theme'], 'Papirus-Dark')


if __name__ == '__main__':
    unittest.main()
