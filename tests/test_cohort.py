"""Test twin for kernel/shelf/cohort.py -- the transient membership-group primitive.

Acceptance: form a group, admit members up to the cap, read a member's group, leave with leadership
handoff, disband. Refusal (the map invariant): admitting a member already in a group or to a full
group fails loud; a bad max_size fails loud; leaving an ungrouped member is a clean no-op.
"""

from __future__ import annotations

import pytest

from kernel.shelf.cohort import Cohort, CohortError, CohortRegistry


def test_form_then_add_builds_a_group_led_by_the_founder():
    reg = CohortRegistry(max_size=3)
    band = reg.form("alia")
    reg.add(band, "bram")
    assert band.leader == "alia" and band.members == ["alia", "bram"]
    assert reg.cohort_of("bram") is band and reg.cohort_of("alia") is band


def test_leaving_hands_leadership_to_the_next_member():
    reg = CohortRegistry(max_size=3)
    band = reg.form("alia")
    reg.add(band, "bram")
    after, was_leader = reg.leave("alia")  # the leader leaves
    assert was_leader and after is band and after.leader == "bram"
    assert reg.cohort_of("alia") is None


def test_leaving_the_last_member_disbands_the_group():
    reg = CohortRegistry(max_size=3)
    reg.form("alia")
    after, _ = reg.leave("alia")
    assert after is None and reg.cohort_of("alia") is None


def test_disband_dissolves_the_group_for_all():
    reg = CohortRegistry(max_size=3)
    band = reg.form("alia")
    reg.add(band, "bram")
    former = reg.disband(band)
    assert set(former) == {"alia", "bram"}
    assert reg.cohort_of("alia") is None and reg.cohort_of("bram") is None


def test_cohort_membership_and_length_helpers():
    band = Cohort(["alia", "bram"])
    assert "alia" in band and "cade" not in band and len(band) == 2


# --- refusal: the member->group map invariant --------------------------------------------------
def test_admitting_someone_already_grouped_fails_loud():
    reg = CohortRegistry(max_size=3)
    a = reg.form("alia")
    reg.form("bram")  # bram leads his own group
    with pytest.raises(CohortError, match="already in a group"):
        reg.add(a, "bram")


def test_a_full_group_refuses_a_new_member():
    reg = CohortRegistry(max_size=2)
    band = reg.form("alia")
    reg.add(band, "bram")  # now full (2)
    with pytest.raises(CohortError, match="full"):
        reg.add(band, "cade")


def test_forming_while_already_grouped_fails_loud():
    reg = CohortRegistry(max_size=3)
    reg.form("alia")
    with pytest.raises(CohortError, match="already in a group"):
        reg.form("alia")


def test_a_zero_max_size_is_refused():
    with pytest.raises(CohortError, match="at least 1"):
        CohortRegistry(max_size=0)


def test_leaving_an_ungrouped_member_is_a_clean_no_op():
    reg = CohortRegistry(max_size=3)
    assert reg.leave("nobody") == (None, False)
