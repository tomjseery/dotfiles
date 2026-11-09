"""Check the optional installer's boundaries using a cached application fixture."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class QswitchInstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="qswitch-install-test-")
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_CONFIG_HOME=str(self.home / ".config"),
                        XDG_DATA_HOME=str(self.home / ".local/share"),
                        XDG_CACHE_HOME=str(self.home / ".cache"))
        fakebin = self.home / "bin"
        fakebin.mkdir()
        for name in ["git", "go", "qs"]:
            command = fakebin / name
            command.write_text("#!/bin/sh\nprintf '%s\\n' '" + name + "'\" $*\" >> \"$HOME/calls.log\"\n")
            command.chmod(0o755)
        self.env["PATH"] = str(fakebin) + ":" + os.environ["PATH"]
        component = ROOT / "components/qswitch"
        revision = json.loads((component / "upstream.json").read_text())["commit"]
        digest = hashlib.sha256((component / "compat.patch").read_bytes()).hexdigest()[:12]
        runtime = self.home / ".local/share/dotfiles/qswitch" / (revision + "-" + digest)
        (runtime / "quickshell").mkdir(parents=True)
        (runtime / "quickshell/shell.qml").write_text("import Quickshell\nShellRoot {}\n")
        (runtime / "qswitch").write_text("#!/bin/sh\nexit 0\n")
        (runtime / "qswitch").chmod(0o755)
        (self.home / ".cache/dotfiles/qswitch/.git").mkdir(parents=True)
        self.personal = self.home / ".config/hypr/personal.lua"
        self.personal.parent.mkdir(parents=True)
        self.personal.write_text("-- my settings stay here\n")

    def install(self, *arguments):
        return subprocess.run([str(ROOT / "install/qswitch.sh"), *arguments],
                              env=self.env, cwd=ROOT, capture_output=True, text=True)

    def test_reinstall_preserves_registered_profiles_and_core(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        registry = self.home / ".config/qswitch/config.json"
        self.assertEqual(json.loads(registry.read_text())["flavours"], [])
        custom = '{"flavours":["external"],"keybinds":{"external":"default"},"unbinds":false}\n'
        registry.write_text(custom)
        state = self.home / ".switch_state"
        state.write_text("external\n")
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(registry.read_text(), custom)
        self.assertEqual(state.read_text(), "external\n")
        self.assertEqual(self.personal.read_text(), "-- my settings stay here\n")
        calls = (self.home / "calls.log").read_text()
        self.assertNotIn("clone", calls)
        self.assertNotIn("go ", calls)
        before = {str(p): os.readlink(p) for p in self.home.rglob("*") if p.is_symlink()}
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(registry.read_text(), custom)
        self.assertEqual(before, {str(p): os.readlink(p) for p in self.home.rglob("*") if p.is_symlink()})
        for arguments in [["exp-setup"], ["--itrustmyself", "autofix"]]:
            result = subprocess.run([str(self.home / ".local/bin/qswitch"), *arguments],
                                    env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("managed by dotfiles", result.stderr)

    def test_existing_gui_directory_is_preserved(self):
        existing = self.home / ".config/quickshell/qswitch/shell.qml"
        existing.parent.mkdir(parents=True)
        existing.write_text("// pre-existing GUI\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to overwrite", result.stderr)
        self.assertEqual(existing.read_text(), "// pre-existing GUI\n")
        self.assertEqual(self.personal.read_text(), "-- my settings stay here\n")


if __name__ == "__main__":
    unittest.main()
