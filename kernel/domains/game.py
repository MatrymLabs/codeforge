"""CARD: game -- the game domain module: Aethryn's real subsystems as a loadable DomainModule.

The symmetric proof to the education module. Where education is stdlib-only, the game module is the
case that legitimately DEPENDS on the game world (a domain module may touch its own domain). It
satisfies the neutral `kernel.seedlab.domain.DomainModule` contract and each capability advertised
maps to a REAL `kernel/world/` subsystem, so the claim is grounded, not decorative.

Crucially, the domain-neutral platform (kernel/seedlab) still never imports this: an import-linter
contract forbids it, and the game world is pulled in only lazily (via `subsystem`), so merely
registering the module does not load the whole world graph. The composition root that registers the
game module is the tick (forge.py), which already imports the world -- exactly where a
world-dependent module belongs.

Grammar before worlds, from the game side: a game Seed loads combat; a classroom Seed (which selects
`education`, not `game`) can never resolve this module. Status: PROTOTYPED (see
docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import ModuleType

from kernel.seedlab.domain import register_module
from kernel.seedlab.provision import DomainModuleRegistry

#: Each advertised capability maps to the REAL kernel/world module that provides it. String paths
#: (not imports) so loading this module stays light; the test twin proves every one imports.
_CAPABILITY_MODULES: dict[str, str] = {
    "combat": "kernel.world.combat",
    "items": "kernel.world.items",
    "callings": "kernel.world.jobs",
    "npcs": "kernel.world.npcs",
    "quests": "kernel.world.quest",
    "progression": "kernel.world.progression",
    "mortality": "kernel.world.mortality",
}


class GameError(Exception):
    """A game-module operation was refused (an unknown capability). Fails loud."""


@dataclass
class GameModule:
    """The Game domain module. Satisfies DomainModule (name / title / capabilities); `name` is the
    key a game BlueprintSpec selects and is FROZEN as "game". Its capabilities are the real Aethryn
    subsystems, each reachable (lazily) via `subsystem`."""

    name: str = "game"
    title: str = "Aethryn"
    capabilities: tuple[str, ...] = tuple(_CAPABILITY_MODULES)

    def subsystem(self, capability: str) -> ModuleType:
        """Lazily import the real kernel/world module backing a capability -- proof this module
        binds to live game code, not a stub. Fails loud on a capability this module does not
        advertise."""
        target = _CAPABILITY_MODULES.get(capability)
        if target is None:
            known = ", ".join(self.capabilities)
            raise GameError(f"game has no capability {capability!r}; has: {known}")  # noqa: TRY003
        return importlib.import_module(target)


def register_game_module(registry: DomainModuleRegistry) -> GameModule:
    """Register the game module into a DomainModuleRegistry under its own name and return it. Kept
    here (not in the neutral platform) because binding the game belongs to a world-aware layer; the
    caller is the composition root (the tick). The neutral platform types are lightweight (no
    world);
    only `subsystem` pulls the game world, and only when asked."""
    module = GameModule()
    register_module(registry, module)
    return module
