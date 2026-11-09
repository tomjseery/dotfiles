"""Exercise installations against disposable homes, without packages or services."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dotfiles-test-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_CURRENT_DESKTOP="")

    def install(self, name, *arguments, succeeds=True):
        result = subprocess.run([str(ROOT / "install" / name), *arguments],
                                cwd=ROOT, env=self.env, capture_output=True, text=True)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def snapshot(self):
        return {str(p.relative_to(self.home)):
                (p.read_bytes(), os.readlink(p) if p.is_symlink() else "")
                for p in self.home.rglob("*") if p.is_file()}

    def test_core_theme_and_repeated_install_preserve_behaviour(self):
        self.install("core.sh", "--configs-only")
        original = self.snapshot()
        self.install("core.sh", "--configs-only")
        self.assertEqual(self.snapshot(), original)
        settings = self.home / ".config/Code/User/settings.json"
        data = json.loads(settings.read_text())
        data["unrelated.setting"] = True
        settings.write_text(json.dumps(data))
        kwin = self.home / ".config/kwinrc"
        kwin.write_text(kwin.read_text().replace("midscrollcursorEnabled=true",
                                               "midscrollcursorEnabled=false") +
                        "\n[Unrelated]\nValue=keep-me\n")
        self.install("theme.sh")
        self.assertIn("midscrollcursorEnabled=true", kwin.read_text())
        self.assertIn("EnablePrimarySelection=false", kwin.read_text())
        self.assertIn("Value=keep-me", kwin.read_text())
        self.assertIn("MiddleClickPaste=false", (self.home / ".config/kdeglobals").read_text())
        data = json.loads(settings.read_text())
        self.assertTrue(data["unrelated.setting"])
        self.assertFalse(data["editor.selectionClipboard"])
        self.assertIn("workbench.colorTheme", data)
        self.assertTrue((self.home / ".config/kitty/theme.conf").is_file())
        themed = self.snapshot()
        self.install("theme.sh")
        self.install("core.sh", "--configs-only")
        self.assertEqual(self.snapshot(), themed)
        for script in ["core.sh", "theme.sh", "kde.sh"]:
            self.install(script, "--dry-run")
            self.assertEqual(self.snapshot(), themed)

    def test_existing_unmanaged_config_is_not_overwritten(self):
        target = self.home / ".config/kitty/kitty.conf"
        target.parent.mkdir(parents=True)
        target.write_text("# Existing personal file\n")
        original = self.snapshot()
        self.install("core.sh", "--configs-only", succeeds=False)
        self.assertEqual(self.snapshot(), original)

    def test_invalid_json_fails_before_any_config_changes(self):
        target = self.home / ".config/Code/User/settings.json"
        target.parent.mkdir(parents=True)
        target.write_text("// Commented JSON needs manual reconciliation\n{}")
        original = self.snapshot()
        self.install("core.sh", "--configs-only", succeeds=False)
        self.assertEqual(self.snapshot(), original)


if __name__ == "__main__":
    unittest.main()
