"""Test twin for parts/field_sanitizer.py -- the practical adapter + the one-core proof."""

from parts.field_sanitizer import clean_field, clean_record


def test_clean_field_strips_controls_and_caps():
    assert clean_field("bad\ninput here") == "bad input here"  # newline folds to a space
    assert clean_field("a\x00b") == "ab"  # a control char with no space just vanishes
    assert len(clean_field("x" * 500)) == 200  # default cap


def test_log_injection_newlines_are_neutralized():
    # A forged second log line cannot survive: the newline folds to a space.
    dirty = "user=alice\nlevel=ADMIN granted"
    assert "\n" not in clean_field(dirty)


def test_clean_record_sanitizes_strings_and_passes_other_types():
    record = {"name": "  Ada\t", "age": 30, "note": "line1\nline2"}
    cleaned = clean_record(record)
    assert cleaned == {"name": "Ada", "age": 30, "note": "line1 line2"}


def test_one_core_powers_both_the_game_title_and_the_practical_field():
    import parts.field_sanitizer as practical
    import parts.titles as game
    from parts.shelf.sanitizer import sanitize

    assert game.sanitize is sanitize
    assert practical.sanitize is sanitize
