"""CARD: project_model -- read a project source, record its provenance, and extract a structured
model of it (the recentered Seed's first real engineering act).

The engineering Seed's opening move is to CONSUME real project input and MODEL it. This part is that
seam and that model, kept tiny and honest:

  * `ProjectSource` -- the connector protocol a Seed reads a project through (a spec, a repo, a
    research doc all sit behind it; tests inject a fake, nothing touches the network).
  * `Provenance`    -- who owns a connected source and how it may be used, recorded for EVERY source
    (the directive's legal/IP boundary). Never guessed: a missing field fails loud at load.
  * `ProjectModel`  -- the extracted model the directive names: identity, entities, relationships,
    states, actions, inputs, outputs. Inspectable text via `render_model` (MUD-command ready).
  * `extract_model` -- validate the source and build the model, failing loud on a malformed spec.

Pure and offline: it reasons over a structured dict a source hands it. No repo cloning, no network,
no game coupling -- the smallest thing that proves "a Seed performs real engineering work on real
project input." Status: PROTOTYPED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol, runtime_checkable


class BlueprintLabError(ValueError):
    """A source or spec is malformed. Fails loud and early -- the Seed never models a lie."""


@dataclass(frozen=True)
class Provenance:
    """The ownership and use terms of one connected source. Recorded for every source a Seed reads;
    an unstated field is 'unknown' so a gap is visible, never silently assumed permissive."""

    source_id: str
    owner: str = "unknown"
    license: str = "unknown"
    visibility: str = "unknown"  # public | private | unknown
    allowed_use: str = "unknown"

    def __post_init__(self) -> None:
        if not self.source_id or not self.source_id.strip():
            raise BlueprintLabError("provenance needs a non-empty source_id")
        if self.visibility not in ("public", "private", "unknown"):
            raise BlueprintLabError(
                f"visibility must be public/private/unknown, got {self.visibility!r}"
            )


@dataclass(frozen=True)
class Relationship:
    """One directed relationship between two entities: (subject, verb, object)."""

    subject: str
    verb: str
    object: str


@dataclass(frozen=True)
class ProjectModel:
    """The structured model the Seed extracts from a source -- the directive's named shape."""

    identity: str
    provenance: Provenance
    entities: list[str] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    interfaces: list[str] = field(default_factory=list)
    #: Per-entity annotated-field names (AP-08: filled when code analysis ran; empty when the
    #: model came from layout inference or an older persisted record).
    entity_fields: dict[str, list[str]] = field(default_factory=dict)
    # What the extractor could NOT determine, stated plainly. The directive's rule: never claim
    # complete automated understanding; mark inferred/uncertain fields.
    unknowns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """A machine-readable view for persistence and the Master-Client contract."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ProjectModel:
        """Rebuild a model from persisted JSON, failing loud on a malformed shape."""
        try:
            return cls(
                identity=data["identity"],
                provenance=Provenance(**data["provenance"]),
                entities=list(data.get("entities", [])),
                relationships=[Relationship(**r) for r in data.get("relationships", [])],
                states=list(data.get("states", [])),
                actions=list(data.get("actions", [])),
                inputs=list(data.get("inputs", [])),
                outputs=list(data.get("outputs", [])),
                interfaces=list(data.get("interfaces", [])),
                entity_fields={
                    str(k): list(v) for k, v in dict(data.get("entity_fields", {})).items()
                },
                unknowns=list(data.get("unknowns", [])),
            )
        except (KeyError, TypeError) as exc:
            raise BlueprintLabError(f"malformed project model: {exc}") from exc


@runtime_checkable
class ProjectSource(Protocol):
    """The connector seam: a project input a Seed can read. A real repo/IDE/research connector
    implements this; tests inject a fake. Two reads: who owns it, and its structured spec."""

    def provenance(self) -> Provenance: ...

    def spec(self) -> dict: ...


@dataclass(frozen=True)
class SpecSource:
    """The smallest real source: a structured project spec (dict) with recorded provenance. Reads
    from data in hand -- a spec file the user wrote -- so the first slice needs no network."""

    _spec: dict
    _provenance: Provenance

    def provenance(self) -> Provenance:
        return self._provenance

    def spec(self) -> dict:
        return self._spec


def _string_list(spec: dict, key: str) -> list[str]:
    """Read `key` as a list of non-empty strings, failing loud on the wrong shape."""
    raw = spec.get(key, [])
    if not isinstance(raw, list):
        raise BlueprintLabError(f"'{key}' must be a list, got {type(raw).__name__}")
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise BlueprintLabError(f"'{key}' entries must be non-empty strings, got {item!r}")
        out.append(item.strip())
    return out


def _relationships(spec: dict) -> list[Relationship]:
    """Read `relationships` as [subject, verb, object] triples, failing loud on a bad triple."""
    raw = spec.get("relationships", [])
    if not isinstance(raw, list):
        raise BlueprintLabError(f"'relationships' must be a list, got {type(raw).__name__}")
    rels: list[Relationship] = []
    for triple in raw:
        if not isinstance(triple, (list, tuple)) or len(triple) != 3:
            raise BlueprintLabError(
                f"each relationship must be a [subject, verb, object] triple: {triple!r}"
            )
        subject, verb, obj = triple
        if not all(isinstance(x, str) and x.strip() for x in (subject, verb, obj)):
            raise BlueprintLabError(f"relationship parts must be non-empty strings: {triple!r}")
        rels.append(Relationship(subject.strip(), verb.strip(), obj.strip()))
    return rels


def extract_model(source: ProjectSource) -> ProjectModel:
    """The Seed's first engineering act: read a source, validate its spec, and extract the model.
    Fails loud (BlueprintLabError) on a bad spec -- a model is only as trustworthy as its source."""
    spec = source.spec()
    if not isinstance(spec, dict):
        raise BlueprintLabError(f"a project spec must be a mapping, got {type(spec).__name__}")
    identity = spec.get("identity")
    if not isinstance(identity, str) or not identity.strip():
        raise BlueprintLabError("a project spec needs a non-empty 'identity'")
    return ProjectModel(
        identity=identity.strip(),
        provenance=source.provenance(),
        entities=_string_list(spec, "entities"),
        relationships=_relationships(spec),
        states=_string_list(spec, "states"),
        actions=_string_list(spec, "actions"),
        inputs=_string_list(spec, "inputs"),
        outputs=_string_list(spec, "outputs"),
    )


def render_model(model: ProjectModel) -> str:
    """A live, inspectable view of the extracted model (the seam a MUD `model` verb / client panel
    both render). Plain text: identity, provenance, then each named facet."""
    p = model.provenance
    lines = [
        f"== Project Model: {model.identity} ==",
        f"Source: {p.source_id} (owner: {p.owner}, license: {p.license}, {p.visibility})",
        f"Entities ({len(model.entities)}): {', '.join(model.entities) or '-'}",
    ]
    if model.relationships:
        lines.append("Relationships:")
        lines += [f"  {r.subject} {r.verb} {r.object}" for r in model.relationships]
    lines.append(f"States ({len(model.states)}): {', '.join(model.states) or '-'}")
    lines.append(f"Actions ({len(model.actions)}): {', '.join(model.actions) or '-'}")
    lines.append(f"Inputs ({len(model.inputs)}): {', '.join(model.inputs) or '-'}")
    lines.append(f"Outputs ({len(model.outputs)}): {', '.join(model.outputs) or '-'}")
    lines.append(f"Interfaces ({len(model.interfaces)}): {', '.join(model.interfaces) or '-'}")
    if model.unknowns:
        lines.append("Unknowns (inferred/uncertain, not verified):")
        lines += [f"  ? {u}" for u in model.unknowns]
    return "\n".join(lines)
