"""CARD: commands -- the command spine: verbs filed, rank-gated, namespaced.

Three namespaces keep the multiverse safe at scale:
  CORE  -- reserved bare words the engine owns (look, go, say, registry).
  ADMIN -- '@'-sigil verbs for owner/wizards (@grant, @sg); a seed can never use
           the sigil, so an admin verb can never collide with a seed verb.
  SEED  -- bare-word gameplay verbs each seed owns (forge, cast); validated at load
           so a seed can't shadow a core word or reach into the admin sigil.

A Command is data + a handler (composition, never a subclass tree). Every command is
also a CMD-* designation, so the command table is filed in the registry alongside the
nouns it acts on. Dispatch checks rank BEFORE running -- authorization before capability.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from parts.ranks import has_rank
from parts.session import Session

ADMIN_SIGIL = "@"

CORE = "core"
ADMIN = "admin"
SEED = "seed"
NAMESPACES = (CORE, ADMIN, SEED)


class CommandError(ValueError):
    """A command table is malformed -- fail loud (e.g. a seed shadows a reserved word)."""


@dataclass(frozen=True)
class Command:
    """One filed verb: the trigger phrase, its handler, the rank it needs, and the
    namespace it belongs to. The '@' sigil is reserved for ADMIN, by construction."""

    verb: str
    designation: str
    summary: str
    run: Callable[[Session, str], str]  # (session, argument) -> response
    namespace: str = SEED
    min_rank: str = "player"

    def __post_init__(self) -> None:
        if self.namespace not in NAMESPACES:
            raise CommandError(f"{self.verb}: namespace '{self.namespace}' not in {NAMESPACES}")
        wears_sigil = self.verb.startswith(ADMIN_SIGIL)
        if wears_sigil and self.namespace != ADMIN:
            raise CommandError(f"{self.verb}: only ADMIN verbs may use the '{ADMIN_SIGIL}' sigil")
        if self.namespace == ADMIN and not wears_sigil:
            raise CommandError(f"{self.verb}: an ADMIN verb must start with '{ADMIN_SIGIL}'")


@dataclass
class CommandSet:
    """A collection of commands with rank-gated, longest-verb-first dispatch. Returns
    None when nothing matches, so the legacy tick still handles the rest."""

    commands: list[Command] = field(default_factory=list)

    def add(self, command: Command) -> None:
        if any(c.verb.lower() == command.verb.lower() for c in self.commands):
            raise CommandError(f"duplicate verb: {command.verb}")
        self.commands.append(command)

    def _match(self, text: str) -> tuple[Command, str] | None:
        raw = text.strip()
        low = raw.lower()
        # longest verb first, so "registry show" wins over "registry"
        for cmd in sorted(self.commands, key=lambda c: -len(c.verb)):
            verb = cmd.verb.lower()
            if low == verb:
                return cmd, ""
            if low.startswith(verb + " "):
                return cmd, raw[len(cmd.verb) :].strip()  # preserve the argument's case
        return None

    def available_to(self, session: Session) -> list[Command]:
        """The commands this player's rank can actually reach."""
        return [c for c in self.commands if has_rank(session, c.min_rank)]

    def dispatch(self, session: Session, text: str) -> str | None:
        hit = self._match(text)
        if hit is None:
            return None  # not ours -- fall through to the legacy tick
        command, argument = hit
        if not has_rank(session, command.min_rank):
            if command.namespace == ADMIN:
                return f"[SYSTEM] Denied. That command requires {command.min_rank} authority."
            return "You don't have the authority for that."
        return command.run(session, argument)


def reserved_words(command_set: CommandSet) -> set[str]:
    """The bare CORE/ADMIN verbs' leading words -- what a seed may never claim."""
    words: set[str] = set()
    for c in command_set.commands:
        if c.namespace in (CORE, ADMIN):
            words.add(c.verb.lower().split(" ", 1)[0])
    return words


def guard_seed_verbs(seed_verbs: list[str], reserved: set[str]) -> None:
    """The scale safety net: a seed's verbs may not use the admin sigil or shadow a
    reserved core word. Fails loud at seed-load rather than colliding silently."""
    for verb in seed_verbs:
        low = verb.lower()
        if verb.startswith(ADMIN_SIGIL):
            raise CommandError(f"seed verb '{verb}' may not use the reserved '{ADMIN_SIGIL}' sigil")
        if low.split(" ", 1)[0] in reserved:
            raise CommandError(f"seed verb '{verb}' shadows a reserved word")
