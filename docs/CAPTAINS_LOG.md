# Chief Engineer's Log - the MatrymLabs ship

> A running log of the work. Newest entry on top. Engineering reckoning, in the
> ship's own hand. *(The ship: **MatrymLabs**. The engine: **CodeForge**. A seed
> is a game.)* Earlier entries predate the naming cleanup and keep their original
> headers.

---

## Chief Engineer's Log - 2026-07-11 (ship's day 192, evening watch) - "The Storefront, the Trail, and the Machine Named"

**Ship's day 192, still the eleventh of July.** The morning's restoration behind us, the watch
ran long and turned outward: from how the ship reads, to what it can prove, to what it *is*.

First we cleaned the storefront, because a stranger judges the window before the workshop. A hard
look through a recruiter's eyes found the ship undercutting its own strong flagship: the test
count was stated four different ways and none of them right, on the one repo whose whole creed is
that a claim must match reality. We killed the drift at the root and let the badge be the only
number. We took the fancy dashes out of the most-read page, pulled a private repository out of the
featured slot where a cold visitor would have hit a locked door, and swept the weakest, oldest
repositories into the archive so the showroom holds only work we would want clicked. Then we
hardened the two flagships that remain: a code of conduct, branch protection, a first tagged
release where none had ever been cut, a coverage badge that is now *earned* rather than asserted,
and the vulnerability alerts that were quietly switched off, switched on. The self-audit scorecards
in both READMEs had themselves gone stale; the proof-tool caught its own storefront lying, and we
told the truth instead, up to the honest admission that the younger tool sits on the watchlist at
the highest bar and says so rather than inflate the grade.

Then we earned the one signal a solo builder cannot fake by asserting it: a real trail. An issue
opened, a branch cut, a pull request that closed it, all in the open. The feature it carried was
NPCs that fight back, and building it flushed a heron from the reeds: a latent flaw where the test
fixtures rebound a shared registry that four modules had aliased, so they could silently drift
apart under parallel runs. We did not paper over it. We found it, fixed it for the file at hand,
then chased the same pattern across every fixture that carried it and rooted it out, and filed the
follow-ups in the open. A bug surfaced by your own change, tracked and killed at its source, is
worth more than a suite that never admits one exists. And we made the fight real in the game the
combat was built for: the Gate boss now strikes back.

We strengthened the proving itself. The coverage gate now measures branches, not just lines,
because a line that ran is not the same as a decision tested both ways, and the stricter measure
made a hundred and eighty-one blind spots visible at once. The pytest harness now refuses a typo
where it used to shrug.

Last, and largest, we named the machine. The ship had grown many good systems and lost the single
sentence that says what it is. So we wrote it down and made the flagship say it: CodeForge is a
manufacturing platform with two products - an installable world you can play today, and a store of
reusable parts proven in that world and translated to real software. Then, because a vision is only
a vision until one part carries the whole idea on its back, we built that part. A workflow engine,
grown on a state machine we already trusted, now runs a quest inside the MUD and an employee's
onboarding through a plain interface outside it - one core, two lives, the same tests, cataloged as
a real part and shown on the wall. That single slice makes the whole vision legible without the
whole factory being finished. It is the proof that the machine is real.

The reckoning: better than a dozen changes merged to main, every one behind a green pipeline; two
flagships hardened and made to tell the truth about themselves; a bug found and buried at its root;
the test gate made stricter; the ship given one clear name and one working proof of it. Eight
hundred and one tests green. Nothing shipped that was not proven. Nothing claimed that was not run.

The storefront is honest, the trail is real, the machine is named. The forge is banked. The watch
stands relieved.

*- Chief Engineer, MatrymLabs*

---

## Chief Engineer's Log - 2026-07-11 (ship's day 192) - "The Frame Held: A Restoration, and the Keel Made Plain"

**Ship's day 192, the eleventh of July.** No new deck was raised today. We did the harder,
quieter work: we took the frame off the flagship and looked at it honestly, then put back only
what earned its place.

The restoration ran in eight numbered slices, each a controlled cut, never a reckless rewrite.
We taught the classification registry to notice its own blind spots - a completeness check that
names any code module nobody filed, so the index can no longer lie by omission. We walked the
docs against the code and pulled every stale number that had drifted out of true. We settled on
one name for the architecture-first doctrine instead of three. We gathered the readiness words -
pass, fail, watch, not-applicable - that four gates had each re-declared on their own, into one
shared vocabulary, so a gate and the board that reads it can never drift apart again. We deleted
a second TOML parser that a subsystem had grown, and pointed it at the one validated ledger
reader. We clarified the control panel so seven check-like buttons read as one ladder, and we
closed a real gap: the ritual had been skipping the integrity report, so "run the ritual" now
files every piece of evidence it should.

Two slices we were told to execute, and did not. That is the part worth remembering. One asked
us to force seven check-shaped records under a single shared base; we looked, found they
genuinely differ - some carry a not-applicable state, some a plain boolean, some a blocking flag,
some none - and reported that a shared base would buy coupling for no behavior. The other asked
us to merge three research-to-build maps and four statements of the dependency rule; we found the
rule was already consolidated and the three maps were distinct, valuable, and simply undiscoverable
- so we indexed them as one family instead of flattening them into one file. A restoration keeps
the sound planks. Declining, with evidence, is the work too.

Then we made the keel plain. Two advanced skills - translating research into a tested system, and
designing an evaluator-guided search that stays human-final - had proof on the board but no
declared owner. The gate that guards ownership refuses any portfolio claim without a real keel
record on disk, and there were none. So we wrote them, from the actual build history: intent,
decision, what the AI built, what the human decided, the tests that stand behind it. The claims
are staged at the defendable level, and held at the gangway for the Captain's own word - the
first-person line is his to write, because no machine assigns a man's ownership for him.

We also re-ran the engine-tick benchmark, one hundred and thirteen thousand commands a second,
median under nine microseconds. Down about a tenth from the last reading, but the ship was under
its own load at the time, and the shape held - the honest label is noise, not a regression. A
wobble inside the measurement is not a fall.

The reckoning: seven changes merged to main behind green pipelines, an eighth open for the
Captain's signature; two things deliberately not done, each with its reasons filed; the truth
audit still clean. Nothing rebuilt that was already sound. Nothing claimed that was not proven.

The frame is back on, and it fits better than it did. The watch stands relieved.

*- Chief Engineer, MatrymLabs*

---

## Chief Engineer's Log - 2026-07-10 (ship's day 191) - "The Long Watch: Full-Stack, and the Forge That Builds Itself"

**Ship's day 191, the tenth of July.** The longest watch on record, and the flagship
changed shape.

We closed the full-stack loop end to end. The engine grew a typed HTTP contract and a live
dashboard that renders its own evidence - the career board, the quality gates, the hardware
store, a real benchmark - enhanced with HTMX so it refreshes without a reload, yet still
works with the browser's scripts switched off. That same typed contract became a second
flagship: a React and TypeScript console, its own repository, that consumes the API across a
network and draws it live. We proved that by standing both up in one `docker compose up` and
watching the console render the engine's real numbers across the container wall, no
demo-fallback banner in sight. The documentation now publishes itself to a public site on
every change.

Underneath, the data layer learned to speak PostgreSQL as fluently as SQLite - one seam, one
URL, the schema versioned by Alembic and exercised against a real database in the pipeline.
Configuration became typed and validated; every request became a structured log line and a
metric; a real browser drove the whole dashboard end to end.

We gave the Architect a second brain - a Claude-backed one, an API key away, behind the same
seam the local guide uses and mocked in every test so the pipeline never touches the network.
From it we forged the planning spine: an idea becomes a schema-enforced Blueprint,
re-validated through the same loud gate a human's plan passes, always a draft for a person to
review.

Then we climbed the hardest rung, and climbed it slowly. The Foundry: the engine may now
generate a file, but only as a proposal a human approves, only into a cordoned sandbox, never
overwriting, never escaping, never touching real source or the branch. The proof is in the
refusals - the tests that make sure it says no. And the arch: step through it, owner-only and
read-only, into the Proving Ground to review what was forged. The loop the ship was drawn
around - workshop, forge, arch, review, promote by hand - is real now, and safe by
construction.

We also took the borrowed names off the hull. Titles that were only ever concepts are gone
from the public flagship and the private contract alike, replaced with the ship's own words:
the Spiral Ascent, the Proving Ground. A portfolio should stand on its own inventions.

The reckoning: eighteen changes merged to the flagship's main, each behind a green pipeline;
a new front-end flagship raised, made public, and pinned; the docs site lit; the hardware
store grown to thirteen cross-domain parts; coverage held near ninety-two percent throughout;
and the truth audit still says every claim corresponds to reality. Nothing shipped that
wasn't proven. Nothing claimed that wasn't run.

The forge is banked. The watch stands relieved.

*- Chief Engineer, MatrymLabs*

---

## Stardate 2026.190 - "The Machine That Checks Itself"

**Captain's Log, Stardate 2026.190.** The ninth of July, ship's calendar. The longest
watch yet.

We built the flagship a spine it did not have - a hidden **Classification Registry**,
a filing system beneath the fantasy, and upon it a **command spine** with a reserved
`@` sigil so no seed can ever collide with the ship's own verbs. Then we proved the
engine composes: a **QualityGate** that reads the registry and grades every filed
object, a **project dashboard** computed from both - part upon part, no second copy to
drift. The Captain asked whether the engine could take *(part + part)*. It can:
`qa gate all` audits the ship from parts already aboard.

We taught the forge to make things on command - `@sg`, owner-gated, data-driven,
refusing to conjure the unknown - to read the guidance library in-game, and to confirm
a regulation's date against its own source. The ritual grew teeth: a **WARDS** phase
that will not light the forge on a known SAST finding, and a **READINESS** phase where
the ship audits itself before the gate opens. We walked the whole engine end to end
over a live socket - start, log in, look, do, log out, bank the forge - and in the
walking found the ship had been **stalling ~40ms on every command** for want of one
line. We struck Nagle from the gateway; the lag fell to near nothing.

Twice the Captain called for truth over comfort. An audit found the papers claiming a
test count three times stale; we corrected them, then made the claim one that *cannot*
lie. We drew a line between the shop window and the back room, and put the compliance
work behind glass.

**A reckoning, in the ship's own hand:** building the **RepoIntegrityRitual** - the
machine that checks the machine - the Captain's own mistake surfaced. We merged on
`make check` alone; the security watch caught a false alarm we had not run, and main
stood red for four minutes. We fixed it forward, loudly, and filed the lesson: *the
check gate is not the whole gate.* Integrity-first cuts toward the one at the wheel.

The recommendations are saved in the project log. The machine is honest, and greener
for the day.

---

## Stardate 2026.189 - "The Forge Lights on Command"

**Captain's Log, Stardate 2026.189.** The eighth of July, ship's calendar.

We began the day with a discrepancy in the manifest: the ship's papers promised a
**Docker image** and a container smoke-test that main deck did not, in fact,
carry. Rather than amend the papers to match a lesser truth, we built the thing
the papers promised - a `python:3.13-slim` hull that runs the gateway as a
non-root hand named *smith*, state kept on a `/data` volume, the game selectable
at ignition. The old `feat/docker` branch, long adrift, was retired. The manifest
now tells the truth, and CI stands a `docker` watch to keep it that way.

We then brought the rest of the fleet alongside - `codeforge-evennia`, `learning`,
and the ship's colors - cloned into home port, each sealed out of the flagship's
hold so the decks stay clean.

**The ritual.** The Captain gave an order: *"When I say `start the ritual`, I want
the lights to come on."* So we wired it - one command that runs the gates, mirrors
GitHub, lights the forge, and opens the MUD window at the front desk. Its
counterpart, `complete the ritual`, secures the workshop at watch's end: banks any
forge still burning, stills the containers, and musters the day's uncommitted and
unpushed work with an honest tongue.

**The trouble at the front desk.** First contact with the login gate went poorly.
The Captain's password appeared *in the clear*, and the console filled with
negotiation static - the ship had fallen back to `nc`, which cannot dim a prompt.
We forged our own instrument: a small telnet-aware client, standard-issue parts
only, that goes dark on command. The password vanished as it should.

And then the true fault surfaced - the kind that only bites when you least expect
it. Login would reach the password, and the connection would **die without a
word**. It behaved perfectly when tested head-on, and only failed through the full
ritual. We cornered it the house way: a controlled reproduction under a
pseudo-terminal, driving the whole chain as a human would. The log told the tale -
`OSError: Bad file descriptor`. The ritual's own health-check had been *connecting
to the live gateway*, spawning ghost sessions whose dead channels lingered; the
next player's room-broadcast wrote to a corpse and took the living down with it.
**One dropped client could crash another.** A real hole in the hull, surfaced by a
convenience.

We sealed it three ways: the event bus now survives and prunes a dead channel, a
handler always unbinds its session even mid-failure, and the ritual watches the
log instead of knocking on its own door. Tests stand guard over all of it.

**Landfall.** At day's end the Captain walked through the gate for real -
`matrym@matlabs`, password hidden, and the console answered: **"Welcome back,
Matrym@matlabs."** The Broken Courtyard, the training dummy, the whole loop, alive
and holding. Two hundred and one tests green. CI green. The forge lit on command.

*A good day's work. The workshop is next: to build programs from inside the world,
and step through an owner-only arch into the proving ground to play what we built.*

- Logged by the Captain, MatrymLabs. End of entry.
