"""Test twin for kernel/world/search.py + the CORE `search` verb.

Acceptance: the index finds rooms/items/NPCs by relevance and the verb is reachable through the
engine tick. Refusal/robustness: an empty query and a no-match query answer cleanly, and a query
with FTS5 punctuation cannot inject (tokens are sanitized).
"""

from forge import handle_command
from kernel.world import search as world_search_mod
from kernel.world.session import Session


def setup_function() -> None:
    world_search_mod.reset()  # drop any cached index so each test builds fresh


# --- the index / adapter ---------------------------------------------------


def test_search_finds_content_by_relevance():
    hits = world_search_mod._get_index().search("forge")
    assert hits, "expected at least one world thing matching 'forge'"
    assert all(h.doc_id.split(":", 1)[0] in {"room", "item", "npc"} for h in hits)


def test_empty_query_returns_nothing():
    assert world_search_mod._get_index().search("") == []


def test_scores_are_ordered_best_first():
    hits = world_search_mod._get_index().search("forge")
    assert hits == sorted(hits, key=lambda h: -h.score)


def test_punctuation_query_does_not_raise():
    # FTS5 MATCH metacharacters must be sanitized away, not executed.
    hits = world_search_mod._get_index().search('forge" OR docs MATCH "x')
    assert isinstance(hits, list)


def test_substring_fallback_works_when_fts5_absent():
    # If the host sqlite has no FTS5, the index degrades to a substring scan that
    # still finds and ranks content (ADR-0010 fallback ethos).
    corpus = [
        ("room:forge", "The Forge", "smiths hammer ember steel at the anvil"),
        ("item:relic", "Frost Relic", "an ancient shard of ice"),
    ]
    fallback = world_search_mod._WorldIndex(corpus, allow_fts=False)
    assert fallback._fts is False
    hits = fallback.search("ember steel")
    assert hits and hits[0].doc_id == "room:forge"
    assert fallback.search("") == []
    assert fallback.search("zzznope") == []


# --- the verb, through the engine tick -------------------------------------


def test_search_verb_is_tick_reachable():
    out = handle_command(Session(player_id="matrym"), "search forge")
    assert "World search for 'forge'" in out


def test_search_verb_reports_no_match():
    out = handle_command(Session(player_id="matrym"), "search zzznomatchqqq")
    assert "Nothing in the known world matches" in out


def test_search_verb_prompts_on_empty():
    out = handle_command(Session(player_id="matrym"), "search")
    assert "Search for what" in out
