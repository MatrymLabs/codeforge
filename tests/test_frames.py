"""Test twin for parts/frames.py -- typed, per-recipient event frames.

Acceptance: a SpeechFrame renders the same third-person line the old string bus produced, and
projects the speaker's label per the display-name rule. Refusal: an empty speaker or empty/blank
words fail loud at construction (a frame never carries a half-formed event); the base Frame refuses
to render until a subclass implements it.
"""

import pytest

from parts.frames import Frame, SpeechFrame

# --- acceptance --------------------------------------------------------------------------------


def test_speech_frame_renders_the_third_person_line():
    frame = SpeechFrame(speaker_id="matrym", words="hello there")
    assert frame.render_for("anyone") == 'Matrym says, "hello there"'


def test_speech_frame_projects_the_display_name():
    # identity stays lowercase_snake; the label is capitalized at render, per display_name.
    frame = SpeechFrame(speaker_id="iron_fist", words="hi")
    assert frame.render_for("viewer") == 'Iron Fist says, "hi"'


def test_speech_frame_is_frozen():
    frame = SpeechFrame(speaker_id="a", words="hi")
    with pytest.raises(AttributeError):
        frame.words = "changed"


# --- refusal / hostile -------------------------------------------------------------------------


def test_empty_words_fail_loud():
    with pytest.raises(ValueError, match="non-empty words"):
        SpeechFrame(speaker_id="a", words="")


def test_blank_words_fail_loud():
    with pytest.raises(ValueError, match="non-empty words"):
        SpeechFrame(speaker_id="a", words="   ")


def test_empty_speaker_fails_loud():
    with pytest.raises(ValueError, match="speaker_id"):
        SpeechFrame(speaker_id="", words="hi")


def test_the_base_frame_refuses_to_render():
    with pytest.raises(NotImplementedError, match="render_for"):
        Frame().render_for("anyone")
