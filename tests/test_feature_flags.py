"""Test twin for parts/shelf/feature_flags.py -- runtime flags with override precedence."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from parts.shelf.feature_flags import FeatureFlagError, FlagRegistry


def _reg() -> FlagRegistry:
    r = FlagRegistry()
    r.register("new_ui", default=False)
    r.register("fast_path", default=True)
    return r


def test_a_flag_reads_its_default_until_overridden():
    r = _reg()
    assert r.is_on("new_ui") is False
    assert r.is_on("fast_path") is True


def test_enable_and_disable_override_the_default():
    r = _reg()
    r.enable("new_ui")
    assert r.is_on("new_ui") is True
    r.disable("fast_path")
    assert r.is_on("fast_path") is False


def test_reset_returns_to_the_default():
    r = _reg()
    r.enable("new_ui")
    r.reset("new_ui")
    assert r.is_on("new_ui") is False  # back to the registered default


def test_an_unknown_flag_is_an_error_never_silently_off():
    with pytest.raises(FeatureFlagError):
        _reg().is_on("does_not_exist")


def test_a_duplicate_registration_fails_loud():
    r = _reg()
    with pytest.raises(FeatureFlagError):
        r.register("new_ui")


def test_retire_removes_the_flag_entirely():
    r = _reg()
    r.retire("new_ui")
    with pytest.raises(FeatureFlagError):
        r.is_on("new_ui")


def test_snapshot_is_the_reproducible_current_state():
    r = _reg()
    r.enable("new_ui")
    assert r.snapshot() == {"fast_path": True, "new_ui": True}  # sorted, effective values


@pytest.mark.property
@given(default=st.booleans(), enable=st.booleans())
def test_both_paths_are_reachable_and_override_always_wins(default, enable):
    r = FlagRegistry()
    r.register("f", default=default)
    if enable:
        r.enable("f")
        assert r.is_on("f") is True
    else:
        r.disable("f")
        assert r.is_on("f") is False
    r.reset("f")
    assert r.is_on("f") is default  # after reset, the default governs
