# ruff: noqa: E501

"""Structured Aethryn quest development and validation.

This module is deliberately an authoring/adapter layer.  The live quest state machine remains
``kernel.world.quest`` and still owns player progress and event advancement.  Packet records are
normalised here, checked against the current world, and then adapted into that existing workflow.
No runtime content generation or model call is performed.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

QUEST_EVENTS = {
    "enter",
    "leave",
    "talk",
    "ask",
    "examine",
    "read",
    "take",
    "acquire",
    "possess",
    "give",
    "deliver",
    "use",
    "operate",
    "open",
    "close",
    "repair",
    "gather",
    "craft",
    "equip",
    "defeat",
    "assist_defeat",
    "cull",
    "forage",
    "survive",
    "escort_arrive",
    "escort_lost",
    "protect",
    "interact",
    "state_changed",
    "reputation_reached",
    "timer_elapsed",
    "public_contribution",
    "party_event",
    "choose",
    "accept",
    "begin",
    "finish",
}

GRAMMAR_NAMES = {
    "discovery",
    "retrieval",
    "delivery",
    "hunt",
    "repair",
    "defense",
    "escort",
    "rescue",
    "investigation",
    "crafting_commission",
    "gathering_commission",
    "diplomacy",
    "infiltration",
    "dungeon_objective",
    "faction_contract",
    "public_event",
    "repeatable_contract",
    "tutorial",
}

LEGACY_TRIGGER_MAP = {
    "on_defeat": "defeat",
    "on_take": "take",
    "on_enter": "enter",
    "on_cull": "cull",
    "on_forage": "forage",
    "on_craft": "craft",
}

CANON_LADDER = {"CANON_LOCKED", "CANON_WORKING", "AUTHORED_LOCAL", "GENERATED_LOCAL", "RUMOR"}
LOCKED_TERMS = (
    "divine strike was accidental",
    "natural-born god",
    "netharion survived",
    "netharion was evil",
    "netharion was benevolent",
    "forge metaphysics",
    "ember metaphysics",
    "unforging metaphysics",
)


@dataclass(frozen=True)
class QuestValidationFinding:
    code: str
    quest_id: str
    message: str
    path: str = ""
    source: str = ""
    action: str = ""
    severity: str = "error"


@dataclass(frozen=True)
class QuestValidationReport:
    findings: tuple[QuestValidationFinding, ...] = ()

    @property
    def verdict(self) -> str:
        return "FAIL" if any(f.severity == "error" for f in self.findings) else "CLEAN"

    @property
    def errors(self) -> tuple[QuestValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "error")


@dataclass(frozen=True)
class PublicEventState:
    event_id: str
    state: str
    contributions: Mapping[str, int] = field(default_factory=dict)
    tick: int = 0


class ConsequenceStore:
    """Scoped, serializable local world effects; immutable canon records are never targets."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str], dict[str, Any]] = {}

    def apply(self, effect: Mapping[str, Any], *, scope_id: str = "world") -> dict[str, Any]:
        target = str(effect.get("target", ""))
        if not target:
            raise ValueError("world consequence requires a target")
        if str(effect.get("scope", "personal")) in {"regional", "global"} and bool(
            effect.get("immutable", False)
        ):
            raise ValueError(f"world consequence cannot mutate immutable canon target {target!r}")
        scope = str(effect.get("scope", "personal"))
        key = (scope, scope_id if scope in {"personal", "party", "instance"} else "world")
        current = dict(self._values.get(key, {}))
        current[target] = {
            "effect_type": str(effect.get("effect_type", "state_changed")),
            "value": effect.get("value", effect.get("to", True)),
            "duration": str(effect.get("duration", "")),
            "persistence": str(effect.get("persistence", "session")),
            "reversible": bool(effect.get("reversible", False)),
            "source_quest_id": str(effect.get("source_quest_id", "")),
        }
        self._values[key] = current
        return dict(current[target])

    def get(
        self, target: str, *, scope: str = "personal", scope_id: str = "world"
    ) -> dict[str, Any] | None:
        key = (scope, scope_id if scope in {"personal", "party", "instance"} else "world")
        value = self._values.get(key, {}).get(target)
        return dict(value) if isinstance(value, dict) else None

    def snapshot(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {
            f"{scope}:{scope_id}": dict(values)
            for (scope, scope_id), values in sorted(self._values.items())
        }

    def restore(self, raw: Mapping[str, Any]) -> None:
        self._values.clear()
        for key, values in raw.items():
            if ":" not in str(key) or not isinstance(values, Mapping):
                continue
            scope, scope_id = str(key).split(":", 1)
            self._values[(scope, scope_id)] = {
                str(target): dict(value)
                for target, value in values.items()
                if isinstance(value, Mapping)
            }

    def reset(self, scope: str | None = None) -> None:
        if scope is None:
            self._values.clear()
        else:
            self._values = {key: values for key, values in self._values.items() if key[0] != scope}


def party_credit(
    participants: Iterable[str],
    *,
    required: int = 1,
    contributions: Mapping[str, int] | None = None,
) -> tuple[str, ...]:
    """Return only party/public participants that made the declared contribution."""
    values = contributions or {}
    return tuple(
        sorted(
            str(participant)
            for participant in participants
            if int(values.get(participant, 0)) >= required
        )
    )


def _finding(
    findings: list[QuestValidationFinding],
    code: str,
    quest_id: str,
    message: str,
    path: str,
    source: str,
    action: str,
    severity: str = "error",
) -> None:
    findings.append(QuestValidationFinding(code, quest_id, message, path, source, action, severity))


def normalize_quest_record(raw: Mapping[str, Any], *, source: str = "") -> dict[str, Any]:
    """Return an extended record while preserving every legacy field and id."""
    row = dict(raw)
    row.setdefault("id", row.get("stable_id", ""))
    row.setdefault("display_name", row.get("name", row.get("id", "").replace("_", " ").title()))
    row.setdefault("canon_status", "GENERATED_LOCAL")
    row.setdefault("quest_type", row.get("type", "authored"))
    row.setdefault("scope", "personal")
    row.setdefault("repeatability", "one_shot")
    row.setdefault("start_state", row.get("start", "offered"))
    row.setdefault("terminal_states", row.get("terminal", []))
    if "steps" in row and "transitions" not in row:
        transitions: list[dict[str, Any]] = []
        for step in row.get("steps", []):
            if not isinstance(step, Mapping):
                continue
            transition = {
                "from": step.get("state"),
                "event": step.get("event"),
                "to": step.get("to"),
                "effect": step.get("effect"),
            }
            for key, event_type in LEGACY_TRIGGER_MAP.items():
                if step.get(key):
                    transition["target_id"] = step[key]
                    transition["event_type"] = event_type
            transitions.append(transition)
        row["transitions"] = transitions
    row.setdefault("objectives", [])
    row.setdefault("triggers", [])
    row.setdefault(
        "rewards",
        ([{"type": "xp", "amount": row["reward_xp"]}] if row.get("reward_xp") is not None else []),
    )
    row.setdefault("consequences", row.get("world_effects", []))
    row.setdefault("provenance", {"source": source} if source else {})
    if row.get("pressure_id") is None:
        row["pressure_id"] = ""
    return row


def _graph(row: Mapping[str, Any]) -> tuple[str, set[str], list[tuple[str, str, str]]]:
    start = str(row.get("start_state", row.get("start", "")))
    states: set[str] = {start} if start else set()
    edges: list[tuple[str, str, str]] = []
    transitions = row.get("transitions", [])
    for transition in transitions:
        if not isinstance(transition, Mapping):
            continue
        src = str(
            transition.get("from", transition.get("source_state", transition.get("state", "")))
        )
        dst = str(transition.get("to", transition.get("destination_state", "")))
        event = str(transition.get("event", transition.get("event_type", "")))
        if src:
            states.add(src)
        if dst:
            states.add(dst)
        edges.append((src, event, dst))
    for state in row.get("states", []) or []:
        if isinstance(state, Mapping):
            states.add(str(state.get("id", state.get("stable_id", ""))))
        else:
            states.add(str(state))
    return start, states, edges


def _terminal(row: Mapping[str, Any]) -> set[str]:
    values = row.get("terminal_states", row.get("terminal", [])) or []
    return {str(value.get("id")) if isinstance(value, Mapping) else str(value) for value in values}


def validate_quest_spec(
    raw: Mapping[str, Any], *, source: str = "", references: Mapping[str, set[str]] | None = None
) -> QuestValidationReport:
    """Validate one legacy or extended quest with actionable, source-aware findings."""
    row = normalize_quest_record(raw, source=source)
    quest_id = str(row.get("id", ""))
    findings: list[QuestValidationFinding] = []
    required = ("id", "display_name", "canon_status", "quest_type", "scope", "start_state")
    for name in required:
        if not str(row.get(name, "")).strip():
            _finding(
                findings,
                f"missing_{name}",
                quest_id,
                f"quest lacks {name}",
                name,
                source,
                f"add {name} to the quest record",
            )
    status = str(row.get("canon_status", ""))
    if status not in CANON_LADDER:
        _finding(
            findings,
            "invalid_canon_status",
            quest_id,
            f"{status!r} is not on the canon ladder",
            "canon_status",
            source,
            "use CANON_LOCKED, CANON_WORKING, AUTHORED_LOCAL, GENERATED_LOCAL, or RUMOR",
        )
    if status == "GENERATED_LOCAL" and row.get("authorization") in {
        "CANON_LOCKED",
        "CANON_WORKING",
    }:
        _finding(
            findings,
            "generated_canon_promotion",
            quest_id,
            "generated quest attempts to promote itself",
            "canon_status",
            source,
            "keep generated quests GENERATED_LOCAL",
        )
    quest_type = str(row.get("quest_type", ""))
    if quest_type and quest_type not in GRAMMAR_NAMES and quest_type != "authored":
        _finding(
            findings,
            "unknown_grammar",
            quest_id,
            f"unsupported quest grammar {quest_type!r}",
            "quest_type",
            source,
            f"use one of {sorted(GRAMMAR_NAMES)}",
        )
    if not row.get("pressure_id") and not row.get("legacy", False) and "steps" not in raw:
        _finding(
            findings,
            "missing_pressure",
            quest_id,
            "extended quest has no originating world pressure",
            "pressure_id",
            source,
            "reference a credible quest_pressures record or retain this as a legacy authored quest",
        )
    start, states, edges = _graph(row)
    terminals = _terminal(row)
    if not start:
        _finding(
            findings,
            "missing_start_state",
            quest_id,
            "quest graph has no start state",
            "start_state",
            source,
            "declare start_state",
        )
    if not terminals:
        _finding(
            findings,
            "missing_terminal_state",
            quest_id,
            "quest graph has no terminal state",
            "terminal_states",
            source,
            "declare at least one completion or failure terminal",
        )
    for index, (src, event, dst) in enumerate(edges):
        path = f"transitions[{index}]"
        if src not in states or dst not in states:
            _finding(
                findings,
                "invalid_transition",
                quest_id,
                f"transition {src!r} -> {dst!r} references an unknown state",
                path,
                source,
                "declare both states before adding the transition",
            )
        if event not in QUEST_EVENTS:
            _finding(
                findings,
                "missing_event_type",
                quest_id,
                f"event {event!r} is not supported",
                path,
                source,
                "use a current natural-play event name",
            )
    adjacency: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    for src, _event, dst in edges:
        adjacency[src].add(dst)
        reverse[dst].add(src)
    reachable = {start}
    todo = [start]
    while todo:
        current = todo.pop()
        for nxt in adjacency[current]:
            if nxt not in reachable:
                reachable.add(nxt)
                todo.append(nxt)
    for state in sorted(states - reachable):
        _finding(
            findings,
            "unreachable_state",
            quest_id,
            f"state {state!r} cannot be reached from start",
            f"states.{state}",
            source,
            "remove the dormant state or add a reachable transition",
        )
    can_finish = set(terminals)
    todo = list(terminals)
    while todo:
        current = todo.pop()
        for previous in reverse[current]:
            if previous not in can_finish:
                can_finish.add(previous)
                todo.append(previous)
    for state in sorted(states & reachable - can_finish):
        _finding(
            findings,
            "dead_state",
            quest_id,
            f"state {state!r} cannot reach a terminal state",
            f"states.{state}",
            source,
            "add a completion/failure edge or declare the state ongoing",
        )
    if str(row.get("repeatability", "one_shot")) not in {
        "repeatable",
        "contract",
        "public_event",
        "ongoing",
    } and any(_has_cycle(adjacency, src, set(), set()) for src in adjacency):
        _finding(
            findings,
            "invalid_cycle",
            quest_id,
            "quest contains a cycle",
            "transitions",
            source,
            "mark the quest repeatable or remove the cycle",
        )
    for index, objective in enumerate(row.get("objectives", []) or []):
        if not isinstance(objective, Mapping) or not objective.get(
            "id", objective.get("stable_id")
        ):
            _finding(
                findings,
                "missing_objective",
                quest_id,
                "objective has no stable id",
                f"objectives[{index}]",
                source,
                "declare objective id, type, and target references",
            )
        elif not objective.get("type", objective.get("objective_type")):
            _finding(
                findings,
                "missing_objective_type",
                quest_id,
                "objective has no type",
                f"objectives[{index}]",
                source,
                "use visit, discover, examine, acquire, deliver, gather, craft, repair, defeat, escort, or another supported type",
            )
    if references:
        for field_name, kind in (
            ("room_ids", "rooms"),
            ("rooms", "rooms"),
            ("npc_ids", "npcs"),
            ("creature_ids", "creatures"),
            ("item_ids", "items"),
            ("faction_ids", "factions"),
            ("recipe_ids", "recipes"),
            ("target_ids", "rooms"),
        ):
            for value in row.get(field_name, []) or []:
                if str(value) not in references.get(kind, set()):
                    _finding(
                        findings,
                        "missing_reference",
                        quest_id,
                        f"{kind} reference {value!r} does not resolve",
                        field_name,
                        source,
                        f"add {value!r} to the active {kind} records or correct the quest",
                    )
    if (
        "steps" not in raw
        and quest_type not in {"tutorial", "discovery"}
        and not row.get("consequences")
    ):
        _finding(
            findings,
            "missing_consequence",
            quest_id,
            "extended quest has no declared world or scoped consequence",
            "consequences",
            source,
            "declare a visible effect or explicitly keep this as a discovery-only record",
        )
    for index, reward in enumerate(row.get("rewards", []) or []):
        if not isinstance(reward, Mapping):
            _finding(
                findings,
                "invalid_reward",
                quest_id,
                "reward must be a mapping",
                f"rewards[{index}]",
                source,
                "declare type and amount or item_id",
            )
        elif str(row.get("repeatability", "one_shot")) in {"repeatable", "contract"} and reward.get(
            "unique"
        ):
            _finding(
                findings,
                "unique_reward_on_repeatable",
                quest_id,
                "repeatable quest offers a unique reward",
                f"rewards[{index}]",
                source,
                "use a repeatable-safe reward or make the quest one-shot",
            )
    prose = row.get("prose", {})
    if prose and isinstance(prose, Mapping):
        for key in ("title", "summary", "journal", "success"):
            if not str(prose.get(key, "")).strip() and "steps" not in raw:
                _finding(
                    findings,
                    "missing_prose",
                    quest_id,
                    f"prose lacks {key}",
                    f"prose.{key}",
                    source,
                    "write state-aware player-facing text",
                )
    searchable = json.dumps(row, sort_keys=True).casefold()
    for term in LOCKED_TERMS:
        if term in searchable:
            _finding(
                findings,
                "canon_leak",
                quest_id,
                f"quest presents locked lore as fact: {term}",
                "records",
                source,
                "rewrite as rumor, disputed testimony, or incomplete evidence",
            )
    return QuestValidationReport(tuple(findings))


def _reachable_from(graph: Mapping[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    todo = [start]
    while todo:
        node = todo.pop()
        if node in seen:
            continue
        seen.add(node)
        todo.extend(graph.get(node, ()))
    return seen


def _has_cycle(graph: Mapping[str, set[str]], node: str, active: set[str], done: set[str]) -> bool:
    if node in active:
        return True
    if node in done:
        return False
    active.add(node)
    if any(_has_cycle(graph, nxt, active, done) for nxt in graph.get(node, ())):
        return True
    active.remove(node)
    done.add(node)
    return False


def validate_quest_records(
    records: Mapping[str, Iterable[Mapping[str, Any]]], *, source: str = ""
) -> QuestValidationReport:
    rows = list(records.get("quests", records.get("quest_specs", records.get("quest", ()))))
    findings: list[QuestValidationFinding] = []
    ids: set[str] = set()
    available = {
        kind: {str(row.get("id")) for row in values if row.get("id")}
        for kind, values in records.items()
    }
    for index, row in enumerate(rows):
        normalized = normalize_quest_record(row, source=f"{source}:quests[{index}]")
        quest_id = str(normalized.get("id", ""))
        if quest_id in ids:
            _finding(
                findings,
                "duplicate_quest_id",
                quest_id,
                "quest id appears more than once",
                f"quests[{index}].id",
                source,
                "give each quest one stable id",
            )
        ids.add(quest_id)
        findings.extend(
            validate_quest_spec(
                normalized, source=f"{source}:quests[{index}]", references=available
            ).findings
        )
        pressure_id = str(normalized.get("pressure_id", ""))
        if pressure_id and pressure_id not in available.get("quest_pressures", set()):
            _finding(
                findings,
                "missing_pressure_reference",
                quest_id,
                f"pressure {pressure_id!r} does not resolve",
                "pressure_id",
                f"{source}:quests[{index}]",
                "add the pressure record before publishing",
            )
    # The richer pressure contract is required when a packet opts into structured quests. Existing
    # ecology/economy packets may still carry the older pressure summary and remain load-compatible.
    if rows or records.get("quest_arcs"):
        for index, pressure in enumerate(records.get("quest_pressures", ())):
            pressure_id = str(pressure.get("id", ""))
            required = (
                "pressure_type",
                "pressure",
                "cause",
                "current_severity",
                "duration",
                "recurrence",
                "stakeholders",
                "beneficiaries",
                "opposing_interests",
                "valid_grammars",
                "escalation_behavior",
                "resolution_conditions",
                "partial_resolution_conditions",
            )
            for field_name in required:
                value = pressure.get(field_name)
                if value is None or value == "" or value == []:
                    _finding(
                        findings,
                        "incomplete_pressure",
                        pressure_id,
                        f"pressure lacks {field_name}",
                        f"quest_pressures[{index}].{field_name}",
                        source,
                        "describe the active cause, stakeholders, recurrence, valid grammar, and resolution",
                    )
    quest_ids = {str(row.get("id")) for row in rows}
    for index, arc in enumerate(records.get("quest_arcs", ())):
        arc_id = str(arc.get("id", ""))
        for member in arc.get("quest_ids", ()) or ():
            if str(member) not in quest_ids:
                _finding(
                    findings,
                    "missing_arc_quest",
                    arc_id,
                    f"arc references missing quest {member!r}",
                    f"quest_arcs[{index}].quest_ids",
                    source,
                    "add the quest or correct the arc",
                )
    return QuestValidationReport(tuple(findings))


def deterministic_contract_preview(
    template: Mapping[str, Any], seed: int, *, history: Iterable[str] = ()
) -> dict[str, Any]:
    """Select a bounded contract from a template.  Same template/seed/history means same output."""
    rng = random.Random(int(seed))
    history_set = set(history)

    def choose(key: str, fallback: str = "") -> str:
        values = [str(value) for value in template.get(key, []) if str(value) not in history_set]
        if not values:
            values = [str(value) for value in template.get(key, [])]
        return rng.choice(values) if values else fallback

    target = choose("target_pool")
    objective = choose("objective_pool", "investigate")
    variant = choose("narrative_variants", "A recurring local pressure needs a bounded response.")
    raw_id = (
        f"{template.get('id', template.get('stable_id', 'contract'))}:{seed}:{target}:{objective}"
    )
    contract_id = "contract_" + hashlib.sha256(raw_id.encode()).hexdigest()[:16]
    return {
        "id": contract_id,
        "display_name": variant,
        "quest_type": "repeatable_contract",
        "pressure_type": choose("pressure_types", "local_need"),
        "objective": objective,
        "target_id": target,
        "cooldown": int(template.get("cooldown", 0)),
        "canon_status": "GENERATED_LOCAL",
        "generation_seed": int(seed),
        "generator_version": str(template.get("generator_version", "aethryn-quest-v1")),
        "provenance": {
            "template_id": str(template.get("id", template.get("stable_id", ""))),
            "seed": int(seed),
        },
    }


class ContributionLedger:
    """Small deterministic ledger used by party/public quest adapters; it stores contributions, not NPCs."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def add(
        self, participant_id: str, amount: int = 1, *, kind: str = "progress", event_id: str = ""
    ) -> None:
        if amount <= 0:
            return
        self._records.append(
            {
                "participant_id": participant_id,
                "amount": int(amount),
                "kind": kind,
                "event_id": event_id or f"{kind}:{len(self._records)}",
            }
        )

    def totals(self) -> dict[str, int]:
        totals: dict[str, int] = defaultdict(int)
        for record in self._records:
            totals[str(record["participant_id"])] += int(record["amount"])
        return dict(sorted(totals.items()))

    def qualified(self, minimum: int = 1) -> tuple[str, ...]:
        return tuple(
            participant for participant, amount in self.totals().items() if amount >= minimum
        )

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(record) for record in self._records)


def simulate_public_event(
    spec: Mapping[str, Any], contributions: Mapping[str, int] | None = None, *, ticks: int = 1
) -> PublicEventState:
    total = sum(int(value) for value in (contributions or {}).values())
    success = int(spec.get("success_threshold", 1))
    failure = int(spec.get("failure_threshold", 0))
    state = str(spec.get("active_state", "active"))
    if total >= success:
        state = str(spec.get("success_state", "success"))
    elif failure and total <= failure and ticks >= int(spec.get("failure_after_ticks", 0)):
        state = str(spec.get("failure_state", "failure"))
    return PublicEventState(
        str(spec.get("id", spec.get("stable_id", ""))),
        state,
        dict(sorted((contributions or {}).items())),
        int(ticks),
    )


def simulate_quest(spec: Mapping[str, Any], events: Iterable[str] = ()) -> dict[str, Any]:
    """Walk a quest graph for builder previews without mutating a player or world state."""
    row = normalize_quest_record(spec)
    start, _states, edges = _graph(row)
    terminal = _terminal(row)
    requested = list(events)
    current = start
    path = [current]
    consumed = 0
    while current not in terminal and consumed < max(1, len(edges) + 1):
        candidates = [(event, dst) for src, event, dst in edges if src == current]
        if not candidates:
            break
        event, destination = candidates[0]
        if requested:
            requested_event = requested.pop(0)
            match = next(
                (
                    (candidate_event, candidate_dst)
                    for candidate_event, candidate_dst in candidates
                    if candidate_event == requested_event
                ),
                None,
            )
            if match is None:
                break
            event, destination = match
        path.append(destination)
        current = destination
        consumed += 1
    return {
        "quest_id": str(row.get("id", "")),
        "states": path,
        "current_state": current,
        "complete": current in terminal,
        "events": [edge[1] for edge in edges],
    }


def format_validation_report(report: QuestValidationReport) -> str:
    if not report.findings:
        return "quest-check: CLEAN"
    lines = [f"quest-check: {report.verdict}"]
    for finding in report.findings:
        location = f" {finding.source}:{finding.path}" if finding.source or finding.path else ""
        lines.append(
            f"- {finding.code} [{finding.quest_id}]{location}: {finding.message}; action: {finding.action}"
        )
    return "\n".join(lines)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
