"""Shared icons preserve personal state and work across the scoped shell."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared_icons', ROOT / 'themes/shared/icons/apply.py')
icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icons)


class SharedIconsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / '.config'
        self.config.mkdir()
        self.runtime = self.home / '.local/share/dotfiles/end4-pc-trial/config'
        self.user = self.runtime / 'illogical-impulse/config.json'
        self.user.parent.mkdir(parents=True)
        self.saved = {'appearance': {'palette': {'namedScheme': 'charcoal_anime'},
                                    'icons': {'unrelated': 'keep'}},
                      'dock': {'pinnedApps': ['my-app']}}
        self.user.write_text(json.dumps(self.saved))
        (self.config / 'kdeglobals').write_text('[General]\nfont=MyFont\n[Icons]\nTheme=Old\n[KDE]\nOther=keep\n')

    def snapshot(self):
        return {str(p.relative_to(self.home)): p.read_bytes()
                for p in self.home.rglob('*') if p.is_file()}

    def test_apply_preserves_desktop_preferences_and_selected_preset(self):
        icons.apply(self.home)
        result = json.loads(self.user.read_text())
        self.assertEqual(result['appearance']['palette'], self.saved['appearance']['palette'])
        self.assertEqual(result['dock'], self.saved['dock'])
        self.assertEqual(result['appearance']['icons']['unrelated'], 'keep')
        self.assertEqual(result['appearance']['icons']['theme'], 'Papirus-Dark')
        self.assertFalse(result['appearance']['icons']['followScheme'])
        kde = (self.config / 'kdeglobals').read_text()
        self.assertIn('font=MyFont', kde)
        self.assertIn('Other=keep', kde)
        self.assertIn('Theme=Papirus-Dark', kde)
        self.assertIn('Theme=Papirus-Dark', (self.runtime / 'kdeglobals').read_text())
        for v in ['3.0', '4.0']:
            self.assertIn('gtk-icon-theme-name=Papirus-Dark',
                          (self.config / f'gtk-{v}/settings.ini').read_text())
        saved = self.snapshot()
        icons.apply(self.home)
        self.assertEqual(self.snapshot(), saved)
        icons.apply(self.home, dry_run=True)
        self.assertEqual(self.snapshot(), saved)

    def test_invalid_user_state_is_rejected_before_any_writes(self):
        self.user.write_text('{invalid JSON')
        saved = self.snapshot()
        with self.assertRaises(json.JSONDecodeError):
            icons.apply(self.home)
        self.assertEqual(self.snapshot(), saved)

    def test_launcher_reads_the_shared_live_choice(self):
        icons.apply(self.home)
        tools = self.home / 'bin'; tools.mkdir()
        qs = tools / 'qs'
        qs.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$QS_ICON_THEME"\n'
                      'kreadconfig6 --file "$XDG_CONFIG_HOME/kdeglobals" --group Icons --key Theme\n')
        qs.chmod(0o755)
        env = dict(os.environ, HOME=str(self.home), PATH=str(tools) + ':' + os.environ['PATH'])
        launcher = ROOT / 'desktops/hyprland/shared/end4-pc-trial'
        def run():
            return subprocess.check_output([str(launcher)], env=env, text=True).splitlines()
        self.assertEqual(run(), ['Papirus-Dark', 'Papirus-Dark'])
        path = self.config / 'kdeglobals'
        path.write_text(path.read_text().replace('Papirus-Dark', 'Another-Theme'))
        self.assertEqual(run(), ['Another-Theme', 'Another-Theme'])


if __name__ == '__main__':
    unittest.main()
