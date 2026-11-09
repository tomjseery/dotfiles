import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_login", ROOT / "themes/login/astronaut/prepare.py")
prepare_login = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_login)


class LoginThemeTests(unittest.TestCase):
    def test_preset_overrides_metadata_and_repeat_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            component = root / "component"
            component.mkdir()
            (component / "upstream.json").write_text(json.dumps({"commit": "a" * 40, "preset": "chosen"}))
            overrides = component / "overrides.conf"
            overrides.write_text('[General]\nFont="Readable"\nTranslateSessionSelection="Desktop"\n')
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode="w") as stream:
                for name, content in {
                    "Main.qml": "import QtQuick\nItem {}",
                    "Themes/chosen.conf": '[General]\nFont="Original"\nLiteral="50%"\n',
                    "metadata.desktop": '[SddmGreeterTheme]\nConfigFile=Themes/other.conf\nTheme-Id=original\n',
                }.items():
                    value = content.encode()
                    info = tarfile.TarInfo(name)
                    info.size = len(value)
                    stream.addfile(info, io.BytesIO(value))
            with patch.object(prepare_login.subprocess, "check_output", return_value=data.getvalue()) as archive:
                theme = prepare_login.prepare(root / "repository", component, root / "output")
                config = prepare_login.read_config(theme / "theme.conf")
                self.assertEqual(config["General"]["Font"], '"Readable"')
                self.assertEqual(config["General"]["Literal"], '"50%"')
                self.assertEqual(config["General"]["TranslateSessionSelection"], '"Desktop"')
                metadata = prepare_login.read_config(theme / "metadata.desktop")
                self.assertEqual(metadata["SddmGreeterTheme"]["ConfigFile"], "theme.conf")
                self.assertEqual(metadata["SddmGreeterTheme"]["Theme-Id"], theme.name)
                self.assertEqual(prepare_login.prepare(root / "repository", component, root / "output"), theme)
                self.assertEqual(archive.call_count, 1)
                overrides.write_text('[General]\nFont="Another font"\n')
                updated = prepare_login.prepare(root / "repository", component, root / "output")
                self.assertNotEqual(updated, theme)
                self.assertEqual(config["General"]["Font"], '"Readable"')

    def test_default_optional_autologin_and_restore_are_dry_run_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, HOME=directory)
            for arguments, expected in [([], "--login-screen"), (["--autologin"], "--autologin"), (["--restore"], "restore")]:
                result = subprocess.run([str(ROOT / "install/login.sh"), *arguments, "--dry-run"],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, result.stdout)
                self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
