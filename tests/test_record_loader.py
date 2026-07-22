"""Test twin for parts/shelf/record_loader.py -- the shared JSON-record loader (from a clone)."""

import pytest

from parts.shelf.record_loader import load_dir, load_record


class _Err(ValueError):
    """A caller's domain error."""


def _parse(raw: object) -> int:
    if not isinstance(raw, dict) or "v" not in raw:
        raise _Err("needs 'v'")
    return int(raw["v"])


def test_load_record_parses_a_valid_file(tmp_path):
    path = tmp_path / "r.json"
    path.write_text('{"v": 42}')
    assert load_record(path, _parse, error=_Err) == 42


def test_unreadable_file_fails_loud_as_the_given_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ not json")
    with pytest.raises(_Err) as err:
        load_record(path, _parse, error=_Err, label="widget")
    assert "unreadable widget" in str(err.value)


def test_missing_file_fails_loud(tmp_path):
    with pytest.raises(_Err):
        load_record(tmp_path / "nope.json", _parse, error=_Err)


def test_parse_error_propagates(tmp_path):
    path = tmp_path / "r.json"
    path.write_text('{"nope": 1}')
    with pytest.raises(_Err):
        load_record(path, _parse, error=_Err)


def test_load_dir_is_empty_when_missing(tmp_path):
    assert load_dir(tmp_path / "nope", _parse, error=_Err) == []


def test_load_dir_flat_and_sorted(tmp_path):
    (tmp_path / "b.json").write_text('{"v": 2}')
    (tmp_path / "a.json").write_text('{"v": 1}')
    assert load_dir(tmp_path, _parse, error=_Err) == [1, 2]  # sorted by path


def test_load_dir_recursive(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.json").write_text('{"v": 1}')
    (tmp_path / "top.json").write_text('{"v": 9}')
    assert load_dir(tmp_path, _parse, error=_Err) == [9]  # non-recursive: top only
    assert sorted(load_dir(tmp_path, _parse, error=_Err, recursive=True)) == [1, 9]
