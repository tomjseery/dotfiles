"""Inhibit automatic idle sleep only during unfinished coding-agent turns."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time


class Transcript:
    def __init__(self):
        self.offset = 0
        self.pending = b""
        self.busy = False
        self.identity = None
        self.boundary = b""

    def update(self, path):
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        if self.identity != identity or stat.st_size < self.offset:
            self.offset, self.pending, self.busy = 0, b"", False
        self.identity = identity
        with path.open("rb") as stream:
            if self.offset:
                stream.seek(max(0, self.offset - 64))
                if stream.read(min(self.offset, 64)) != self.boundary:
                    self.offset, self.pending, self.busy = 0, b"", False
            stream.seek(self.offset)
            data = self.pending + stream.read()
            self.offset = stream.tell()
            stream.seek(max(0, self.offset - 64))
            self.boundary = stream.read(min(self.offset, 64))
        lines = data.split(b"\n")
        self.pending = lines.pop()
        for line in lines:
            try:
                record = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                continue
            kind = record.get("type")
            if kind == "event_msg":
                event = record.get("payload", {}).get("type")
                if event == "task_started":
                    self.busy = True
                elif event in {"task_complete", "turn_aborted", "task_aborted", "task_failed"}:
                    self.busy = False
            elif kind == "user" and not record.get("isMeta"):
                # Claude user requests and tool results continue a turn.
                self.busy = True
            elif kind == "assistant":
                reason = record.get("message", {}).get("stop_reason")
                if reason in {"end_turn", "stop_sequence", "max_tokens", "refusal"}:
                    self.busy = False
                elif reason == "tool_use":
                    self.busy = True
            elif kind == "system" and record.get("subtype") in {"turn_duration", "stop_hook_summary"}:
                self.busy = False
        return self.busy


class ActivityMonitor:
    def __init__(self, home, stale_seconds=600):
        self.roots = [home / ".codex/sessions", home / ".claude/projects"]
        self.stale_seconds = stale_seconds
        self.transcripts = {}

    def busy(self, now=None):
        now = time.time() if now is None else now
        active = False
        seen = set()
        for root in self.roots:
            for path in root.rglob("*.jsonl"):
                try:
                    if now - path.stat().st_mtime > self.stale_seconds:
                        continue
                    seen.add(path)
                    transcript = self.transcripts.setdefault(path, Transcript())
                    active = transcript.update(path) or active
                except OSError:
                    # A session may disappear or become inaccessible during scanning.
                    continue
        self.transcripts = {p: t for p, t in self.transcripts.items() if p in seen}
        return active


class IdleInhibitor:
    def __init__(self):
        self.process = None

    def update(self, busy):
        if not busy:
            self.release()
        elif self.process is None or self.process.poll() is not None:
            self.process = subprocess.Popen([
                "systemd-inhibit", "--what=idle", "--mode=block", "--no-ask-password",
                "--who=agent-awake", "--why=AI agent turn is active", "sleep", "infinity",
            ])
            print("agent turn active: preventing automatic idle sleep", flush=True)

    def release(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process = None
        print("agent turns finished: idle sleep allowed", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report active/idle and exit without inhibiting")
    args = parser.parse_args()
    # The legacy quiet setting is now solely a stale/crashed-turn safety timeout.
    interval = float(os.environ.get("AGENT_AWAKE_INTERVAL", "5"))
    stale = float(os.environ.get("AGENT_AWAKE_QUIET_MINUTES", "10")) * 60
    if interval <= 0 or stale <= 0:
        parser.error("poll interval and stale timeout must be positive")
    monitor = ActivityMonitor(Path.home(), stale)
    if args.check:
        busy = monitor.busy()
        print("active" if busy else "idle")
        return 0 if busy else 1
    inhibitor = IdleInhibitor()

    def stop(_signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while True:
            inhibitor.update(monitor.busy())
            time.sleep(interval)
    finally:
        inhibitor.release()


if __name__ == "__main__":
    raise SystemExit(main())
