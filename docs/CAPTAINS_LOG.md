# Chief Engineer's Log - the MatrymLabs ship

> A running log of the work. Newest entry on top. Engineering reckoning, in the
> ship's own hand. *(The ship: **MatrymLabs**. The engine: **CodeForge**. A seed
> is a game.)* Earlier entries predate the naming cleanup and keep their original
> headers.

---

## Chief Engineer's Log - 2026-07-15 (ship's day 196) - "Two Refactors Landed, a False Task Refused, and We Pruned the Front Door"

**Ship's day 196, the fifteenth of July.** This was not a day for new decks. The engine
is hireable and we know it, so the work turned to the quieter, harder trades:
correspondence and legibility. We finished cleaving the combat room in two. The leveling
engine, XP and JP and TP and the climb of the curves, had been tangled up with the damage
loop for no better reason than history; we lifted it out into its own part and left combat
to do the one thing combat is for. Then we found the seam we had walked past a dozen times:
the strike loop never advanced the combat clock, so a fighter could trade blows all day and
never thaw a cooldown. We did not fix it quietly. We laid the choice in front of the
Captain, ability-clock or action-clock, and he called it: a round is a round. The clock was
never the Engineer's to own, so it moved to a part of its own, and now every landed strike
turns it.

We proved a rule today that is worth more than any of the parts: **verify a claim against
the code before you act on it.** The bench said the gateway's brute-force throttle merely
re-hand-rolled the login guard, an easy consolidation. The code said otherwise. The gateway
counts failures in a sliding window and forgives a fumbling user the moment he succeeds; the
guard spends a token on every attempt and forgives nothing, because a stateless request has
no session to pardon. Two right answers to two different questions. To force them into one
would have deleted the forgiveness, punished the honest user, and broken a test that was
already standing watch. So we refused the task and wrote down why. A refused task, honestly
reasoned, is a deliverable.

Our own proof-tool caught us drifting the same day we shipped it. We had taught forge-audit
to grade a README on four essentials, and it promptly found gaps in our own storefront: two
scorecards that no longer matched the tool's output, a published part with no test section,
a guidance library with no install line. We closed every one of them, and the fleet now
grades clean end to end. No claim without correspondence, even about ourselves. We made the
collaboration signal clickable while we were there, so an interviewer can follow the loop
from issue to merge instead of taking our word.

And then, asked what I would do with an already-good repo, I said the honest thing: stop
building and prune the front door. The README had grown twenty co-equal headlines, and a
stranger's first five minutes drowned the strong signal, the playable engine and the layered
tests and the passing scorecard, under a hundred and fifty lines of meta-system. So we cut,
but we cut presentation, not substance. Not a verb, not a doc, not a line of code was
deleted; every link survived. We led with the product, folded the disciplines into one
"beyond the game" room, and shut the long tables behind a click. The Captain keeps that PR
to review, because the front door is his to hang. The deeper question, whether a MUD that
also keeps a compliance library and a career board is simply too much surface, we did not
answer. We only made it possible to see clearly enough to ask it.

The suite ended at 1415 green. VeritasGate says all our claims still correspond. The demo is
lit, the index page is live, every link on it holds. A good day's reckoning: less noise,
truer words, and one task we were wise enough not to do.

---

## Chief Engineer's Log - 2026-07-12 (ship's day 193) - "Two Parts Crossed the Fleet, and a Wall We Told the Truth About"

**Ship's day 193, the twelfth of July.** We stopped treating the fleet as a harbor of separate
hulls and started treating it as one ship. First we drew the chart: a fleet-architecture doctrine
that says plainly what the flagship is for and what every other deck owes it, and it named the real
frontier without flattering us - the back-room tools re-implement what CodeForge already proves.
Then we settled the standing question of how a private hull borrows a proven part from the public
one, and wrote it into law: harvest the pattern, record where it came from, no hard coupling.
Publish a shared package only when three parts are shared across three decks, and not one hour
before.

Then we proved the doctrine on real work, not slogans. CodeForge's retry mechanism crossed to the
log-triage service and to the guidance library - the same proven design, fitted twice to two
different error models: one that raises an exception, one that treats a dead link as data and never
raises at all. The circuit breaker followed it across: guarding the model boundary with a fast 503
when the upstream is truly down, and standing per-host watch over the federal endpoints so one dead
source can never silence a healthy one. Two parts now live on three decks. We stopped there on
purpose. A third was there for the taking, but no real gap called for it, and reaching for a part
only to move a number is the thing this ship refuses to do. Restraint is a deliverable, so we filed
the audit that says why we stopped.

The honest part of the day was a wall. We tried to raise the two back-room hulls to the highest
grade by adding CodeQL, the deep static scan - and it would not run. Code scanning wants GitHub
Advanced Security, and that is a public-water privilege; these hulls sail private. Worse, we had
already, too eagerly, written "advanced" into three logs before the scan proved out. So we walked
it back plank by plank: pulled the scan, set the grade honestly to intermediate, and made the
READMEs state exactly why the ceiling sits where it does, instead of painting a badge we did not
earn. The lesson is old and worth re-cutting into the beam: prove the gate green on one hull before
you write the victory into the log.

We swept the decks while we were at it - a hundred and forty-two spent branches struck from the
fleet, the long-dash glyph that reads as a machine's hand scrubbed from every tracked file, and the
community-health papers (how to contribute, what changed, how the work is graded) brought up to the
flagship's standard on both back-room hulls. And we told two design stories a stranger can follow:
why the log-triage service leans on a seam instead of a vendor, and why the guidance library trades
convenience for traceability at every turn - each showing that the seam built for honest tests was
the very seam that later made the boundary safe to harden.

Reckoning: every hull green, every tree clean, not one branch left adrift. The fleet reads as a
single organization tonight, and where it cannot reach a bar, it says so plainly, in its own hand.

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
