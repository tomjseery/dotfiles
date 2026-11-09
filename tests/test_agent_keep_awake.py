"""Regression checks for idle-only inhibition and existing-home migration."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "core/agents/keep-awake"
spec = importlib.util.spec_from_file_location("agent_activity", MODULE / ".local/lib/agent-keep-awake/activity.py")
activity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activity)


def event(kind):
    return {"type": "event_msg", "payload": {"type": kind}}


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.path = self.home / ".codex/sessions/session.jsonl"
        self.path.parent.mkdir(parents=True)
        self.monitor = activity.ActivityMonitor(self.home)

    def append(self, *records):
        with self.path.open("a") as stream:
            for record in records:
                stream.write(json.dumps(record) + "\n")

    def test_completed_turn_is_idle_even_with_a_fresh_transcript(self):
        self.append(event("task_started"), event("token_count"))
        self.assertTrue(self.monitor.busy())
        self.append(event("task_complete"), event("token_count"), event("thread_settings_applied"))
        self.assertFalse(self.monitor.busy())
        self.append(event("task_started"))
        self.assertTrue(self.monitor.busy())
        self.append(event("turn_aborted"))
        self.assertFalse(self.monitor.busy())

    def test_partial_records_rotation_and_crashed_turn_timeout(self):
        self.path.write_text('{"type":"event_msg","payload":{"type":"task_started"}}')
        self.assertFalse(self.monitor.busy())
        with self.path.open("a") as stream:
            stream.write("\n")
        self.assertTrue(self.monitor.busy())
        self.path.write_text(json.dumps(event("task_complete")) + "\n")
        self.assertFalse(self.monitor.busy())
        self.path.write_text(json.dumps(event("task_started")) + "\n")
        os.utime(self.path, (time.time() - 1000,) * 2)
        self.assertFalse(self.monitor.busy())

    def test_all_sessions_must_finish_and_claude_end_turn_releases(self):
        self.append(event("task_started"))
        claude = self.home / ".claude/projects/project/session.jsonl"
        claude.parent.mkdir(parents=True)
        claude.write_text(json.dumps({"type": "user", "message": {"content": "work"}}) + "\n")
        self.assertTrue(self.monitor.busy())
        self.append(event("task_complete"))
        self.assertTrue(self.monitor.busy())
        with claude.open("a") as stream:
            stream.write(json.dumps({"type": "assistant", "message": {"stop_reason": "end_turn"}}) + "\n")
        self.assertFalse(self.monitor.busy())

    def test_inhibitor_never_blocks_manual_sleep_and_releases_on_completion(self):
        process = Mock()
        process.poll.return_value = None
        with patch.object(activity.subprocess, "Popen", return_value=process) as spawn:
            inhibitor = activity.IdleInhibitor()
            inhibitor.update(True)
            inhibitor.update(True)
            self.assertEqual(spawn.call_count, 1)
            arguments = spawn.call_args.args[0]
            self.assertIn("--what=idle", arguments)
            self.assertNotIn("--what=idle:sleep", arguments)
            self.assertIn("--no-ask-password", arguments)
            inhibitor.update(False)
            process.terminate.assert_called_once()
            process.wait.assert_called_once()
            self.assertIsNone(inhibitor.process)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / ".config"))
        self.paths = [".local/bin/agent-awake", ".config/systemd/user/agent-awake.service"]

    def install(self, *args):
        return subprocess.run([str(ROOT / "install/agents.sh"), "--configs-only", *args],
                              env=self.env, capture_output=True, text=True)

    def legacy_links(self):
        for name in self.paths:
            target = self.home / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(ROOT / "core/configs/agent-awake" / name)

    def test_fresh_install_and_owned_legacy_migration_are_repeatable(self):
        for legacy in [False, True]:
            with self.subTest(legacy=legacy):
                if legacy:
                    for name in self.paths:
                        (self.home / name).unlink()
                    self.legacy_links()
                result = self.install()
                self.assertEqual(result.returncode, 0, result.stderr)
                links = {name: os.readlink(self.home / name) for name in self.paths}
                for name in self.paths:
                    self.assertEqual((self.home / name).resolve(), MODULE / name)
                result = self.install()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(links, {name: os.readlink(self.home / name) for name in self.paths})
                helper = self.home / ".local/lib/agent-keep-awake/activity.py"
                self.assertTrue(helper.is_file())
                self.assertFalse((self.home / "README.md").exists())
                self.assertFalse((helper.parent / "__pycache__").exists())

    def test_legacy_dry_run_preserves_links_and_conflicts_fail_before_migration(self):
        self.legacy_links()
        before = os.readlink(self.home / self.paths[0])
        result = self.install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(self.home / self.paths[0]), before)
        service = self.home / self.paths[1]
        service.unlink()
        service.write_text("unrelated user configuration")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(os.readlink(self.home / self.paths[0]), before)
        self.assertEqual(service.read_text(), "unrelated user configuration")


if __name__ == "__main__":
    unittest.main()
