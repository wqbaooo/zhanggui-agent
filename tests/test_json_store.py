import json

import pytest

from models.json_store import DataCorruptionError, atomic_write_json, load_json


def test_atomic_write_keeps_previous_version_as_backup(tmp_path):
    path = tmp_path / "memory.json"
    atomic_write_json(path, {"version": 1})
    atomic_write_json(path, {"version": 2})

    assert load_json(path) == {"version": 2}
    assert json.loads((tmp_path / "memory.json.bak").read_text()) == {"version": 1}
    assert list(tmp_path.glob("*.tmp")) == []


def test_load_json_rejects_corrupt_existing_file(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text('{"broken":', encoding="utf-8")

    with pytest.raises(DataCorruptionError, match="已停止自动写入"):
        load_json(path)


def test_load_json_returns_none_only_when_file_is_missing(tmp_path):
    assert load_json(tmp_path / "missing.json") is None
