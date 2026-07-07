"""Safe JSON persistence primitives for real store data."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


class DataCorruptionError(RuntimeError):
    """Raised when an existing store-data file cannot be decoded."""


def load_json(
    path: Path,
    expected_type: type | tuple[type, ...] = dict,
) -> Any | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DataCorruptionError(
            f"门店数据文件无法读取，已停止自动写入以保护原数据：{path}"
        ) from exc
    if not isinstance(payload, expected_type):
        raise DataCorruptionError(f"门店数据文件结构不符合预期：{path}")
    return payload


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)

        if path.exists():
            shutil.copy2(path, path.with_suffix(f"{path.suffix}.bak"))
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
