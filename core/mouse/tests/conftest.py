import importlib.util
import os
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def engine() -> Any:
    source = Path(os.environ["MIDSCROLL_PREPARED_SOURCE"]) / "midscroll.py"
    spec = importlib.util.spec_from_file_location("tested_midscroll", source)
    assert spec is not None and spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.NATIVE_DEFAULT = True
    module.FALLBACK_APPS = ["kitty"]
    return module
