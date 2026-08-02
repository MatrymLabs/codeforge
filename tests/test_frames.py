"""Test twin for kernel/world/frames.py -- typed, per-recipient event frames.

Acceptance: a SpeechFrame renders the same third-person line the old string bus produced, and
projects the speaker's label per the display-name rule. Refusal: an empty speaker or empty/blank
words fail loud at construction (a frame never carries a half-formed event); the base Frame refuses
to render until a subclass implements it.
"""

import pytest

from kernel.world.frames import Frame, SpeechFrame, StrikeFrame, from_wire, to_wire

# --- acceptance --------------------------------------------------------------------------------


def test_speech_frame_renders_the_third_person_line():
    frame = SpeechFrame(speaker_id="matrym", words="hello there")
    assert frame.render_for("anyone") == 'Matrym says, "hello there"'


def test_strike_frame_renders_the_third_person_blow():
    frame = StrikeFrame(attacker_name="The brawler", verb="lunges", target_id="iron_fist", amount=5)
    assert frame.render_for("anyone") == "The brawler lunges at Iron Fist for 5."


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


def test_strike_frame_without_a_target_fails_loud():
    with pytest.raises(ValueError, match="target_id"):
        StrikeFrame(attacker_name="The brawler", verb="lunges", target_id="", amount=5)


def test_strike_frame_needs_a_positive_blow():
    with pytest.raises(ValueError, match="positive blow"):
        StrikeFrame(attacker_name="The brawler", verb="lunges", target_id="matrym", amount=0)


def test_strike_frame_needs_a_verb():
    with pytest.raises(ValueError, match="verb"):
        StrikeFrame(attacker_name="The brawler", verb="  ", target_id="matrym", amount=3)


# --- the wire registry: a frame round-trips over the bus as JSON (Phase 5) ----------------------


def test_a_speech_frame_round_trips_over_the_wire():
    frame = SpeechFrame(speaker_id="matrym", words="hello there")
    wire = to_wire(frame)
    assert wire == {
        "type": "SpeechFrame",
        "fields": {"speaker_id": "matrym", "words": "hello there"},
    }
    restored = from_wire(wire)
    assert isinstance(restored, SpeechFrame)
    assert restored.render_for("anyone") == 'Matrym says, "hello there"'


def test_a_strike_frame_round_trips_over_the_wire():
    frame = StrikeFrame(attacker_name="The brawler", verb="lunges", target_id="matrym", amount=4)
    restored = from_wire(to_wire(frame))
    assert isinstance(restored, StrikeFrame)
    assert restored == frame  # frozen dataclass equality: every field survived


def test_from_wire_rejects_an_unknown_frame_type():
    with pytest.raises(ValueError, match="unknown frame type"):
        from_wire({"type": "GhostFrame", "fields": {}})


def test_from_wire_rejects_a_missing_field_set():
    with pytest.raises(ValueError, match="missing its fields"):
        from_wire({"type": "SpeechFrame"})


def test_from_wire_revalidates_the_reconstructed_frame():
    # A malformed wire frame (blank words) must fail the same loud validation as construction,
    # so a garbled event never renders as noise on the far process.
    with pytest.raises(ValueError, match="non-empty words"):
        from_wire({"type": "SpeechFrame", "fields": {"speaker_id": "matrym", "words": "  "}})


def test_to_wire_refuses_an_unregistered_frame():
    class RogueFrame(Frame):
        def render_for(self, viewer_id: str) -> str:
            return "rogue"

    with pytest.raises(ValueError, match="not registered"):
        to_wire(RogueFrame())
