"""CARD: reference_seed -- register the Aethryn game as a reference Seed in the Kernel.

Stage 8 (first brick) of the Seed Platform directive: prove the recenter's core claim by making the
flagship GAME appear as one KIND of Seed, consuming the very same Seed Kernel as an engineering Seed
-- so `workspace list` shows Aethryn beside any engineering workspace.

The Kernel stays game-agnostic: this registers Aethryn using only the Kernel's standard fields
(name, owner, purpose, id); it adds NOTHING game-specific to the Kernel, honoring the directive's
rule "do not make Aethryn's game concepts mandatory for non-game Seeds." Registration is idempotent:
game is one stable Seed (`aethryn`), minted once and recovered thereafter. No `kernel/world/` import
(the game world is named, not loaded, so this stays cheap and decoupled). Status: PROTOTYPED.
"""

from __future__ import annotations

from parts.seedlab.kernel import SeedKernel, SeedNotFound, SeedRecord

AETHRYN_SEED_ID = "aethryn"
_NAME = "Aethryn"
_OWNER = "matrym"
_PURPOSE = "the flagship game world -- the reference Seed proving a game is one kind of Seed"


def ensure_reference_seed(kernel: SeedKernel, *, detail: str = "") -> SeedRecord:
    """Idempotently register the Aethryn game as a Seed; return the record (existing or freshly
    minted). Uses only standard Kernel fields, so the game adds nothing game-specific to it."""
    try:
        return kernel.get(AETHRYN_SEED_ID)
    except SeedNotFound:
        purpose = f"{_PURPOSE} ({detail})" if detail else _PURPOSE
        return kernel.create_seed(_NAME, _OWNER, purpose, seed_id=AETHRYN_SEED_ID)


def is_reference_seed(record: SeedRecord) -> bool:
    """True for the Aethryn reference Seed (so a renderer can mark the game distinctly)."""
    return record.identity.seed_id == AETHRYN_SEED_ID
