"""CARD: aethryn_runtime -- read-only runtime adapters for compiled Aethryn world signals.

Compiled packets are static deployment artifacts. This adapter makes their schedules, economy
flows, ecology flows, and quest pressures visible to the live room renderer without asking the
runtime to regenerate content or mutate canonical records. The world clock supplies the only
changing input, so the same package and beat produce the same projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from kernel.world.aethryn_population import (
    ambient_presence,
    crowd,
    population_profile,
    roaming_route,
)


class AethrynRuntimeError(ValueError):
    """A compiled runtime package is malformed or contradictory."""


@dataclass(frozen=True)
class RuntimeSignal:
    """One read-only signal projected from compiled world records."""

    category: str
    text: str


@dataclass(frozen=True)
class RuntimeContext:
    """Deterministic signals relevant to one room at one world beat."""

    signals: tuple[RuntimeSignal, ...] = ()

    def render(self) -> str:
        if not self.signals:
            return ""
        lines = ["WORLD SIGNALS"]
        for signal in self.signals:
            lines.append(f"  {signal.category}: {signal.text}")
        return "\n".join(lines)


@dataclass(frozen=True)
class RuntimeCatalog:
    """Immutable index of generated Aethryn records used by runtime adapters."""

    records: Mapping[str, tuple[Mapping[str, Any], ...]]
    by_id: Mapping[str, Mapping[str, Any]]

    def context_for(
        self,
        room_id: str,
        beat: int,
        state_values: Mapping[str, str] | None = None,
    ) -> RuntimeContext:
        signals = [
            *self._schedule_signals(room_id, beat),
            *self._economy_signals(room_id),
            *self._ecology_signals(room_id),
            *self._pressure_signals(room_id, state_values),
            *self._population_signals(room_id, beat, state_values),
        ]
        return RuntimeContext(signals=tuple(signals))

    def _schedule_signals(self, room_id: str, beat: int) -> list[RuntimeSignal]:
        signals: list[RuntimeSignal] = []
        for record in self.records.get("npcs", ()):
            if record.get("location") != room_id:
                continue
            schedule = tuple(str(entry) for entry in record.get("schedule", ()))
            if not schedule:
                continue
            index = beat % len(schedule)
            name = str(record.get("display_name", record.get("name", record.get("id", "NPC"))))
            signals.append(RuntimeSignal("routine", f"{name} is on {schedule[index]}."))
        return signals

    def _economy_signals(self, room_id: str) -> list[RuntimeSignal]:
        signals: list[RuntimeSignal] = []
        for flow in self.records.get("economy_flows", ()):
            endpoints = self._endpoint_rooms(flow.get("source"), flow.get("sink"))
            if room_id not in endpoints:
                continue
            name = str(flow.get("display_name", flow.get("id", "trade flow")))
            resource = str(flow.get("resource", "resource"))
            purpose = str(flow.get("purpose", "local use"))
            signals.append(RuntimeSignal("trade", f"{name}: {resource} supports {purpose}."))
        return signals

    def _ecology_signals(self, room_id: str) -> list[RuntimeSignal]:
        signals: list[RuntimeSignal] = []
        for flow in self.records.get("ecology_flows", ()):
            creature = self.by_id.get(str(flow.get("creature", "")), {})
            if creature.get("location") != room_id:
                continue
            name = str(flow.get("display_name", flow.get("id", "ecology pressure")))
            pressure = str(flow.get("pressure", "local habitat pressure"))
            signals.append(RuntimeSignal("ecology", f"{name}: {pressure}."))
        return signals

    def _pressure_signals(
        self, room_id: str, state_values: Mapping[str, str] | None
    ) -> list[RuntimeSignal]:
        signals: list[RuntimeSignal] = []
        for pressure in self.records.get("quest_pressures", ()):
            state_gate = pressure.get("state_gate")
            if isinstance(state_gate, Mapping) and state_values is not None:
                state_key = str(state_gate.get("key", ""))
                active_values = {str(value) for value in state_gate.get("active_values", ())}
                if state_key and active_values and state_values.get(state_key) not in active_values:
                    continue
            affected = pressure.get("affected_records", ())
            if not any(room_id == self._record_room(str(record_id)) for record_id in affected):
                continue
            name = str(pressure.get("display_name", pressure.get("id", "local pressure")))
            detail = str(pressure.get("pressure", "local pressure is active"))
            signals.append(RuntimeSignal("pressure", f"{name}: {detail}."))
        return signals

    def _population_signals(
        self, room_id: str, beat: int, state_values: Mapping[str, str] | None
    ) -> list[RuntimeSignal]:
        """Project aggregate life without creating persistent NPCs or combat targets."""
        signals: list[RuntimeSignal] = []
        state = state_values or {}
        for row in self.records.get("crowd_specs", ()):
            spec = crowd(row)
            if room_id not in spec.rooms:
                continue
            activity = (
                spec.schedule[beat % len(spec.schedule)] if spec.schedule else "ordinary work"
            )
            description = (
                spec.collective_description or "The area carries the movement of a working crowd."
            )
            accessible = spec.accessibility_description or description
            signals.append(RuntimeSignal("crowd", f"{description} {activity}; {accessible}"))
        for row in self.records.get("ambient_presence", ()):
            ambient = ambient_presence(row)
            rooms = ambient.rooms or ((ambient.room,) if ambient.room else ())
            if room_id not in rooms or (
                ambient.state_conditions
                and not all(
                    str(state.get(key)) in {str(value) for value in values}
                    for key, values in ambient.state_conditions.items()
                )
            ):
                continue
            if ambient.probability <= 0.0 or _roll_for_record(row, beat) <= ambient.probability:
                text = ambient.text or (
                    ambient.activity_lines[beat % len(ambient.activity_lines)]
                    if ambient.activity_lines
                    else "Signs of nearby life mark the room."
                )
                signals.append(RuntimeSignal(ambient.evidence_type, text))
        for row in self.records.get("population_profiles", ()):
            profile = population_profile(row)
            if room_id not in profile.candidate_rooms:
                continue
            if profile.state_conditions and not all(
                str(state.get(key)) in {str(value) for value in values}
                for key, values in profile.state_conditions.items()
            ):
                continue
            if (
                profile.direct_presence_probability > 0
                and _roll_for_record(row, beat) < profile.direct_presence_probability
            ):
                name = str(row.get("display_name", row.get("creature_id", profile.stable_id)))
                signals.append(RuntimeSignal("population", f"{name} is present in the habitat."))
            elif (
                profile.ambient_evidence_probability > 0
                and _roll_for_record(row, beat + 17) < profile.ambient_evidence_probability
            ):
                name = str(row.get("display_name", row.get("creature_id", profile.stable_id)))
                signals.append(
                    RuntimeSignal("evidence", f"Signs of {name} mark the nearby habitat.")
                )
        for row in self.records.get("roaming_routes", ()):
            route = roaming_route(row)
            if not route.rooms or room_id not in route.rooms or beat % route.movement_interval:
                continue
            if (
                route.population_cap == 0
                or _roll_for_record(row, beat) <= route.movement_probability
            ):
                signals.append(
                    RuntimeSignal(
                        "movement",
                        "A group travelling for "
                        f"{', '.join(route.destination_needs) or 'local business'} passes through.",
                    )
                )
        for row in self.records.get("encounter_groups", ()):
            spawn = row.get("spawn_rules", {}) or {}
            rooms = spawn.get("rooms", spawn.get("candidate_rooms", ()))
            if room_id in rooms and _roll_for_record(row, beat) <= float(
                spawn.get("probability", 0.0)
            ):
                formation = str(row.get("formation", "group")).replace("_", " ")
                signals.append(
                    RuntimeSignal("encounter", f"A {formation} is moving together nearby.")
                )
        return signals

    def _endpoint_rooms(self, source: object, sink: object) -> set[str]:
        return {room for endpoint in (source, sink) if (room := self._record_room(str(endpoint)))}

    def _record_room(self, record_id: str) -> str:
        record = self.by_id.get(record_id, {})
        location = record.get("location") or record.get("source_room")
        return str(location) if location else (record_id if record_id in self._room_ids() else "")

    def _room_ids(self) -> set[str]:
        return {str(record.get("id")) for record in self.records.get("rooms", ())}


def _read_package(path: Path) -> dict[str, tuple[Mapping[str, Any], ...]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise AethrynRuntimeError(f"compiled records {path} must contain a mapping")
    records: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for kind, rows in raw.items():
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise AethrynRuntimeError(
                f"compiled records {path}: {kind!r} must be a list of mappings"
            )
        records[str(kind)] = tuple(rows)
    return records


def load_catalog(generated_root: Path) -> RuntimeCatalog | None:
    """Load all compiled sidecars in stable package order, or None when none are published."""
    merged: dict[str, list[Mapping[str, Any]]] = {}
    by_id: dict[str, Mapping[str, Any]] = {}
    by_kind_id: dict[tuple[str, str], Mapping[str, Any]] = {}
    package_paths = sorted(generated_root.glob("*/records.yaml"))
    for package_path in package_paths:
        package_records = _read_package(package_path)
        for kind, rows in package_records.items():
            merged.setdefault(kind, []).extend(rows)
            for row in rows:
                record_id = str(row.get("id", ""))
                if not record_id:
                    raise AethrynRuntimeError(
                        f"compiled records {package_path}: {kind} contains an idless record"
                    )
                kind_key = (str(kind), record_id)
                previous = by_kind_id.get(kind_key)
                if previous is not None and dict(previous) != dict(row):
                    raise AethrynRuntimeError(
                        f"compiled runtime record {record_id!r} differs across packages in "
                        f"record kind {kind!r}; "
                        "rebuild or retire one package"
                    )
                by_kind_id[kind_key] = row
                # Different record kinds may intentionally share a domain id, such as an item and
                # the material it is made from. Runtime room lookup remains backward-compatible by
                # retaining the first stable record, while same-kind disagreements still fail loud.
                by_id.setdefault(record_id, row)
    if not merged:
        return None
    return RuntimeCatalog(
        records={kind: tuple(rows) for kind, rows in merged.items()},
        by_id=by_id,
    )


def configured_runtime(seed_name: str) -> RuntimeCatalog | None:
    """Find static Aethryn sidecars without creating files or invoking generation."""
    if seed_name != "aethryn":
        return None
    root = Path(__file__).resolve().parents[2]
    return load_catalog(root / "content" / "seeds" / "aethryn" / "generated")


def project_runtime_context(
    room_id: str,
    beat: int,
    catalog: RuntimeCatalog | None,
    state_values: Mapping[str, str] | None = None,
) -> str:
    """Render read-only compiled signals for a live room."""
    if catalog is None:
        return ""
    return catalog.context_for(room_id, beat, state_values).render()


def _roll_for_record(record: Mapping[str, Any], beat: int) -> float:
    """Stable local roll; generation seed is packet data, never a runtime model call."""
    import hashlib

    seed = int(record.get("generation_seed", 0))
    key = str(record.get("id", record.get("stable_id", "")))
    digest = hashlib.sha256(f"{seed}:{key}:{beat}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)
