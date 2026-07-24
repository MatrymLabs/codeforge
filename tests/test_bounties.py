"""Test twin for parts.world.bounties: the hunt-contract generator (side-content at volume)."""

from parts.world.bounties import BOUNTY_PREFIX, generate_bounties, is_bounty


def _foe(hp=10, level=None, name="a rat"):
    npc = {"name": name, "hp": hp, "keywords": ["rat"], "location": "cell"}
    if level is not None:
        npc["level"] = level
    return npc


def test_a_bounty_is_generated_for_every_combatant_levelled_foe():
    npcs = {
        "wolf": _foe(hp=15, level=3, name="a wolf"),
        "boss": _foe(hp=80, level=20, name="the Boss"),
        "dummy": _foe(hp=20, level=None, name="a dummy"),  # levelless -> no bounty
        "sage": _foe(hp=0, level=5, name="a sage"),  # peaceful (hp 0) -> no bounty
    }
    bounties = generate_bounties(npcs)
    ids = {b["id"] for b in bounties}
    assert ids == {"bounty_wolf", "bounty_boss"}  # only the two combatant, levelled foes


def test_a_bounty_completes_on_the_foes_defeat_and_scales_its_reward():
    b = generate_bounties({"boss": _foe(hp=80, level=20, name="the Boss")})[0]
    assert is_bounty(b["id"]) and b["id"].startswith(BOUNTY_PREFIX)
    assert b["reward_xp"] == 20 * 12  # foe level x the per-level reward
    step = b["steps"][0]
    assert step["on_defeat"] == "boss" and step["effect"] == "award_xp"  # felling it collects it
    assert b["terminal"] == ["collected"]


def test_generation_is_deterministic_and_ordered():
    npcs = {"z_foe": _foe(level=5), "a_foe": _foe(level=5)}
    a = generate_bounties(npcs)
    b = generate_bounties(npcs)
    assert [x["id"] for x in a] == [x["id"] for x in b] == ["bounty_a_foe", "bounty_z_foe"]


def test_the_flagship_generates_a_real_board_of_contracts():
    # aethryn's combatant foes yield side-quest VOLUME -- the point of the generator.
    from pathlib import Path

    from parts.world.seed import load_npcs

    seeds = Path(__file__).resolve().parent.parent / "seeds"
    board = generate_bounties(load_npcs(seeds / "aethryn" / "npcs.yaml"))
    assert len(board) >= 10 and all(is_bounty(b["id"]) for b in board)


def test_contracts_view_lists_a_bounty_and_a_defeat_collects_it(monkeypatch):
    # inject one bounty into the live engine (the test seed has no levelled foes), then prove the
    # board lists it, the story view counts it, and felling the foe collects the contract.
    from parts.world import quest
    from parts.world.bounties import _bounty_for
    from parts.world.jobs import bind_calling
    from parts.world.session import Session

    spec = _bounty_for("brawler", {"name": "the brawler", "hp": 30, "level": 5})
    wf, name, xp = quest._from_seed(spec)
    monkeypatch.setitem(quest._QUESTS, spec["id"], quest._Quest(wf, name, xp, spec))
    monkeypatch.setitem(quest._EVENT_ROUTES, ("defeat", "brawler"), [spec["id"]])
    quest.reset_quests()
    s = Session(player_id="hunter", location="courtyard")
    bind_calling(s, "vanguard")
    assert "brawler" in quest.contracts_view(s)  # on the board
    assert "hunt-contracts on the board" in quest._list_all(s)  # counted in the story view
    line = quest.on_event(s, "defeat", "brawler")
    assert line is not None and "Bounty collected" in line  # felling it collects the contract
