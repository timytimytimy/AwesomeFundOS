from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DISCLAIMER = "研究分析，不构成投资建议；不接真实交易，不自动下单。"
REPO_ROOT = Path(__file__).resolve().parents[1]


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
