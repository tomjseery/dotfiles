import importlib.util
import os
import stat
from pathlib import Path
from typing import Any

import pytest


def test_gui_writer_preserves_native_policy_during_speed_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(os.environ["MIDSCROLL_PREPARED_SOURCE"]) / "midscroll-apply.py"
    spec = importlib.util.spec_from_file_location("tested_apply", source)
    assert spec is not None and spec.loader is not None
    apply: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(apply)
    config = tmp_path / "midscroll.conf"
    config.write_text(
        "NATIVE_DEFAULT = true\nFALLBACK_APPS = kitty, org.kde.konsole\n",
        encoding="utf-8",
    )
    apply.CONFIG_PATH = str(config)
    real_stat, real_fstat = os.stat, os.fstat

    def root_stat(path: Any, *args: Any, **kwargs: Any) -> Any:
        result = real_stat(path, *args, **kwargs)
        if path == str(tmp_path):
            values = list(result)
            values[stat.ST_UID] = 0
            return os.stat_result(values)
        return result

    def root_fstat(fd: int) -> Any:
        result = real_fstat(fd)
        values = list(result)
        values[stat.ST_UID] = 0
        return os.stat_result(values)

    # Simulate only root-owned disposable configuration, never real /etc.
    monkeypatch.setattr(apply.os, "stat", root_stat)
    monkeypatch.setattr(apply.os, "fstat", root_fstat)
    monkeypatch.setattr(apply, "keyboards_enabled", lambda: False)
    previous_umask = os.umask(0o077)
    try:
        apply.main(["--no-restart", "SPEED_MULT=0.02"])
    finally:
        os.umask(previous_umask)
    changed = config.read_text(encoding="utf-8")
    assert "NATIVE_DEFAULT = true" in changed
    assert "FALLBACK_APPS = kitty, org.kde.konsole" in changed
    assert "SPEED_MULT = 0.02" in changed
    before = config.read_bytes()
    try:
        with pytest.raises(SystemExit):
            apply.main(["--no-restart", "FALLBACK_APPS=browser"])
    finally:
        os.umask(previous_umask)
    assert config.read_bytes() == before
