# Naming glossary - the forge voice

CodeForge names its parts in a deliberate voice: the invention energy of a
workshop, the deduction of a detective's case file, and the worlds-and-gates
motif of a climbable tower, wound through a spiral (seeds becoming systems). The
metaphor lives in the *code*; the *data contract* stays literal. This table maps
the vocabulary to plain English, and the [style guide](AI_WORKFLOW.md) explains
the philosophy and its hard limits. The [Naming Standard](naming_standard.md) is
the governing ruleset for all new names; the [Theme Alignment Report](theme_alignment_report.md)
is the subsystem-level audit behind it.

| Name | Kind | Plain-English meaning |
|------|------|-----------------------|
| **spark** | Entry point | The console command that ignites the multiplayer server. *"Every world begins as a spark."* |
| **`handle_command`** (the tick) | Engine core | One command in, one response out - the single door all drivers call. State mutates only here. |
| **Forge / `forge.py`** | Engine module | Home of the tick and the terminal driver. The workbench the world is hammered out on. |
| **Session** | Player state | One player's seat at the shared world: identity, location, liveness. |
| **Seed** | Content pack | A whole game as data (`seeds/<name>/*.yaml` + `splash.txt`). The spawn is the seed's first room, never a hardcoded label. |
| **Spark → Spiral → Forge → Gate → World** | Architecture arc | The build path: an idea ignites, loops into structure, is forged into systems, opens a gate, becomes a world. |
| **`ForgeGateServer` / gateway** | Driver | The TCP "front desk" - authenticate before the world; a thin caller of the tick. |
| **web_gateway / `_pump`** | Driver | The browser gate: play over a WebSocket; `_pump` is its single outbound mouth. |
| **the doorman** (`_turnaway_ledger`, `_gate_is_barred`, `_log_turnaway`) | Security | Per-address login rate-limiting at the front desk - who has been turned away, and whether the gate is barred. |
| **echo sink / `bind_echo` / `announce`** | Event bus | Each player binds a sink that delivers room events to them; `announce` fans an event out to everyone else present. |
| **`reforge_secret`** | Account | Re-hash an account's password (self-service `passwd`) - forge the secret anew. |
| **Archive / `open_archive_session`** | Persistence | The canonical store (SQLite) where character case files are kept and restored. |
| **`render_scene` / `render_room`** | Projection | Turn canonical state into the text a player sees. Projections never mutate state. |

## The engineering stack (the self-auditing filing layer)

Above the game, a second vocabulary names the parts that file, gate, and audit the
engine. Each maps to a real, tested module - the metaphor stays in the code; the
*designations* it files are the frozen data contract.

| Name | Kind | Plain-English meaning |
|------|------|-----------------------|
| **Designation / Classification Registry** (`parts/registry.py`) | Filing | Every object gets a unique designation `TYPE-DD.NNN`, keyed to its frozen runtime label - a hidden filing system beneath the fantasy. Additive metadata, never a rename. |
| **CommandSet / the command spine** (`parts/commands.py`) | Dispatch | Namespaced, rank-gated verbs: `CORE` bare words the engine owns, `ADMIN` under the reserved `@` sigil, `SEED` verbs each game owns. A seed can never shadow a reserved word. |
| **FailsafeRunner** (`parts/console.py`) | Safety | The safe command console: an allowlist runs only vetted checks - never raw shell. |
| **QualityGate / SafetyReview** (`parts/qualitygate.py`) | Readiness | Grade a filed object (purpose · file · tests · docs · maturity) → `pass\|watch\|fail`; rate its risk. Readiness, never compliance. |
| **ProjectControl / `pm status`** (`parts/pm.py`) | PM | The project dashboard, *computed* from the registry + QualityGate - no stored copy to drift. |
| **the Archivist / `library`** (`parts/library.py`) | Library | Read the guidance library's preserved documents, read-only. |
| **`@sg` / the generator** (`parts/generate.py`) | Admin | System item generation from filed data patterns (wizard+); refuses to conjure the unknown. |
| **the awareness lens / `law`** (`parts/law.py`) | Compliance-aware | Renders tracked sources through a legal-*awareness* boundary - never legal advice, always "human review required." |

## The two rules that keep it honest

1. **Clarity outranks poetry.** `reforge_secret` is good; `attune_the_arcane_ward`
   is not. A name that hides what the code does is wrong, however evocative.
2. **The data contract is frozen - the metaphor stops at the seam.** Persisted
   identifiers never take the voice: `lowercase_snake_case` room/item/npc/job keys,
   YAML seed keys, database column names, JSON record keys, account/character handle
   formats, CARD docstring names, and CLI verb strings (`serve`, `play`, `grant`,
   `migrate`, `passwd`). Renaming those would break save files, seeds, migrations,
   or the public interface. See the governing boundaries in
   [`AI_WORKFLOW.md`](AI_WORKFLOW.md).
