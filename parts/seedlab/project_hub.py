"""CARD: project_hub -- the Seed's first functional location: render one Seed's project state as
both a text "look" and a versioned structured contract for the Master Client.

Stage 2 of the Seed Platform directive. A Seed created by the Kernel needs a place you can ENTER and
inspect. The Project Hub is that location: it composes a `SeedKernel`, reads a Seed's persisted
identity + lifecycle + audit, and pairs it with a `ProjectState` (the engineering facets a Seed
accumulates: sources, models, builds, tests, targets, risks, decisions). It renders both:

  * `render` / `command` -- the universal text fallback (the MUD `look` and its sub-verbs).
  * `contract`           -- the structured, versioned dict the Master Client consumes.

Both derive from ONE source (Kernel record + ProjectState), so text and contract never drift.

Honest by construction (No Vision Theater): the facets are empty until later stages build them, and
the Hub says so plainly ("none yet") rather than implying a capability that does not run.
`ProjectState` is the real contract shape those stages will fill; the Hub is proven to render both
the empty and the populated case. No `parts/world/` coupling. Status: PROTOTYPED (see
docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.seedlab.kernel import SeedKernel, SeedRecord

CONTRACT_VERSION = "seedlab.project_hub/1"

# The engineering facets a Seed's project accumulates, in the order the Hub lists them, each paired
# with the stage that first fills it -- so an empty facet reads as "not built yet", never as a lie.
_FACETS: tuple[tuple[str, str], ...] = (
    ("sources", "Stage 3: source connector"),
    ("models", "Stage 4: project model"),
    ("builds", "Stage 5: build/test orchestration"),
    ("tests", "Stage 5: build/test orchestration"),
    ("targets", "Stage 6: target generator"),
    ("risks", "noted as they are found"),
    ("decisions", "recorded as they are made"),
)


@dataclass(frozen=True)
class ProjectState:
    """The engineering facets attached to a Seed's project. Empty until later stages fill them; the
    real contract shape they will populate, kept separate from the Kernel's lifecycle record."""

    seed_id: str
    sources: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    builds: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    targets: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()

    def facet(self, name: str) -> tuple[str, ...]:
        """The values of one named facet (raises AttributeError on an unknown facet name)."""
        return getattr(self, name)


class ProjectHubError(Exception):
    """A Hub request was malformed (e.g. an unknown facet). Fails loud."""


@dataclass
class ProjectHub:
    """A Seed's functional Project Hub. Reads persisted Seed state via the Kernel; renders it and
    attached project facets. Stateless beyond the Kernel it composes: a pure projection."""

    kernel: SeedKernel

    def _state(self, seed_id: str, state: ProjectState | None) -> ProjectState:
        if state is not None and state.seed_id != seed_id:
            raise ProjectHubError(
                f"project state is for {state.seed_id!r}, not the requested {seed_id!r}"
            )
        return state or ProjectState(seed_id)

    # --- the structured client contract --------------------------------------------------------
    def contract(self, seed_id: str, state: ProjectState | None = None) -> dict:
        """The versioned, structured view the Master Client renders. Single source of truth with
        `render`; a GUI panel and a text terminal both project from this."""
        record: SeedRecord = self.kernel.get(seed_id)
        st = self._state(seed_id, state)
        i = record.identity
        return {
            "contract_version": CONTRACT_VERSION,
            "seed": {
                "id": i.seed_id,
                "name": i.name,
                "owner": i.owner,
                "version": i.version,
                "status": record.status,
                "purpose": i.purpose,
                "created_at": i.created_at,
            },
            "project": {name: list(st.facet(name)) for name, _ in _FACETS},
            "activity": [
                {"when": e.when, "actor": e.actor, "action": e.action, "detail": e.detail}
                for e in record.audit[-10:]
            ],
        }

    # --- the text fallback (the MUD `look` and its sub-verbs) -----------------------------------
    def render(self, seed_id: str, state: ProjectState | None = None) -> str:
        """The Project Hub's `look`: identity, purpose, status, each facet (with an honest count or
        'none yet'), and recent activity."""
        record = self.kernel.get(seed_id)
        st = self._state(seed_id, state)
        i = record.identity
        lines = [
            f"== Project Hub :: {i.name}  [{i.seed_id}] ==",
            f"owner: {i.owner}  status: {record.status.upper()}  version: {i.version}",
            f"purpose: {i.purpose or '-'}",
            "",
        ]
        for name, hint in _FACETS:
            values = st.facet(name)
            if values:
                lines.append(f"{name.capitalize()} ({len(values)}): {', '.join(values)}")
            else:
                lines.append(f"{name.capitalize()} (0): none yet ({hint})")
        lines.append("")
        lines.append("Recent activity:")
        for e in record.audit[-5:]:
            lines.append(f"  {e.when}  {e.actor}  {e.action}")
        return "\n".join(lines)

    # --- command dispatch (the Seed location's verbs) ------------------------------------------
    def command(self, seed_id: str, text: str, state: ProjectState | None = None) -> str:
        """Dispatch a Project Hub command to its text projection. Verbs mirror the directive:
        look · show status · list <facet> · show risks · show history. Unknown verbs return help."""
        verb = " ".join(text.lower().split())
        if verb in ("", "look", "inspect project", "inspect"):
            return self.render(seed_id, state)
        if verb in ("show status", "status"):
            record = self.kernel.get(seed_id)
            return f"{record.identity.name} [{seed_id}] :: {record.status.upper()}"
        if verb in ("show history", "history"):
            record = self.kernel.get(seed_id)
            return "\n".join(
                f"{e.when}  {e.actor}  {e.action}  {e.detail}".rstrip() for e in record.audit
            )
        if verb.startswith("list "):
            facet = verb[len("list ") :].strip()
            return self._render_facet(seed_id, facet, state)
        if verb in ("show risks", "risks"):
            return self._render_facet(seed_id, "risks", state)
        if verb in ("show decisions", "decisions"):
            return self._render_facet(seed_id, "decisions", state)
        return (
            "Project Hub commands: look · show status · "
            "list <sources|models|builds|tests|targets> · show risks · show history"
        )

    def _render_facet(self, seed_id: str, facet: str, state: ProjectState | None) -> str:
        valid = {name for name, _ in _FACETS}
        if facet not in valid:
            return f"unknown facet {facet!r}; try one of: {', '.join(sorted(valid))}"
        st = self._state(seed_id, state)
        hint = dict(_FACETS)[facet]
        values = st.facet(facet)
        if not values:
            return f"{facet}: none yet ({hint})"
        return f"{facet} ({len(values)}):\n" + "\n".join(f"  - {v}" for v in values)
