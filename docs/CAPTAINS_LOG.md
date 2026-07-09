# Captain's Log — the MatrymLabs ship

> A running log of the voyage. Newest entry on top. Engineering reckoning, in the
> ship's own hand. *(The ship: **MatrymLabs**. The engine: **CodeForge**. A seed
> is a game.)*

---

## Stardate 2026.189 — "The Forge Lights on Command"

**Captain's Log, Stardate 2026.189.** The eighth of July, ship's calendar.

We began the day with a discrepancy in the manifest: the ship's papers promised a
**Docker image** and a container smoke-test that main deck did not, in fact,
carry. Rather than amend the papers to match a lesser truth, we built the thing
the papers promised — a `python:3.13-slim` hull that runs the gateway as a
non-root hand named *smith*, state kept on a `/data` volume, the game selectable
at ignition. The old `feat/docker` branch, long adrift, was retired. The manifest
now tells the truth, and CI stands a `docker` watch to keep it that way.

We then brought the rest of the fleet alongside — `codeforge-evennia`, `learning`,
and the ship's colors — cloned into home port, each sealed out of the flagship's
hold so the decks stay clean.

**The ritual.** The Captain gave an order: *"When I say `start the ritual`, I want
the lights to come on."* So we wired it — one command that runs the gates, mirrors
GitHub, lights the forge, and opens the MUD window at the front desk. Its
counterpart, `complete the ritual`, secures the workshop at watch's end: banks any
forge still burning, stills the containers, and musters the day's uncommitted and
unpushed work with an honest tongue.

**The trouble at the front desk.** First contact with the login gate went poorly.
The Captain's password appeared *in the clear*, and the console filled with
negotiation static — the ship had fallen back to `nc`, which cannot dim a prompt.
We forged our own instrument: a small telnet-aware client, standard-issue parts
only, that goes dark on command. The password vanished as it should.

And then the true fault surfaced — the kind that only bites when you least expect
it. Login would reach the password, and the connection would **die without a
word**. It behaved perfectly when tested head-on, and only failed through the full
ritual. We cornered it the house way: a controlled reproduction under a
pseudo-terminal, driving the whole chain as a human would. The log told the tale —
`OSError: Bad file descriptor`. The ritual's own health-check had been *connecting
to the live gateway*, spawning ghost sessions whose dead channels lingered; the
next player's room-broadcast wrote to a corpse and took the living down with it.
**One dropped client could crash another.** A real hole in the hull, surfaced by a
convenience.

We sealed it three ways: the event bus now survives and prunes a dead channel, a
handler always unbinds its session even mid-failure, and the ritual watches the
log instead of knocking on its own door. Tests stand guard over all of it.

**Landfall.** At day's end the Captain walked through the gate for real —
`matrym@matlabs`, password hidden, and the console answered: **"Welcome back,
Matrym@matlabs."** The Broken Courtyard, the training dummy, the whole loop, alive
and holding. Two hundred and one tests green. CI green. The forge lit on command.

*A good day's work. The workshop is next: to build programs from inside the world,
and step through an owner-only arch into the holodeck to play what we built.*

— Logged by the Captain, MatrymLabs. End of entry.
