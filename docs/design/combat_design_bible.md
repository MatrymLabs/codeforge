# CodeForge Combat Design Bible

*A technical design review reverse-engineered from reference gameplay (an FF-themed MUD played in
Mudlet 4.19.1 with a 12-button MMO mouse). We copy no names, lore, UI, or abilities. We extract the
**why** behind the combat cadence and translate it into original CodeForge systems. Story, graphics,
and audio are ignored; only gameplay systems are analyzed.*

Reference basis: 73 seconds of round-based text combat against a foe ("Vermin"), a client
key-binding editor, and the player's hardware. Everything below is grounded in what was observed,
not invented. Where a number is estimated from the footage it is labelled *(est.)*.

---

## 1. Executive Summary

The reference combat is **round-based, input-light, and decision-dense**. The player does not press
many different buttons per second; they press **one bundled command** (`ss <target>`) roughly once
per round, and the round resolves a *stack* of actions: several auto-attack swings, a weaponskill, a
shot, and any queued reactions. Satisfaction comes not from twitch execution but from:

1. **A generous, forgiving cadence** — the game refuses over-fast input with flavour ("What's the
   rush?", "Whoa! Where's the fire?") instead of a hard error, so the player learns the round tempo
   without punishment.
2. **Legible, information-dense feedback** — one compact status line (`HP · MP · XPNL · APNL · FOE ·
   AFF`) is the entire HUD, updated every round.
3. **Variable multi-hit auto-attack** — a single round resolves 1 to 8 swings depending on
   speed/haste, so the *same* input produces a satisfyingly variable damage burst.
4. **A dual-currency reward** — every kill pays **XP** (character) *and* **AP** (job/ability points),
   so combat feeds two progression tracks at once.

The core loop is **Builder-light, Priority-heavy**: the player isn't building a combo meter; they're
choosing *which bundled action* to fire and *when* to break rhythm for a reaction (heal on
keypad-minus, a slow-arrow to control the foe). The reusable lesson for CodeForge: **make the common
case one keystroke and the interesting case a deliberate interrupt of the rhythm.**

---

## 2. Combat Loop

Observed loop, per round:

```
player fires ss <target>  ──►  round resolves:
    • auto-attack: N swings (1–8), one damage line
    • the bundled weaponskill (Sidewinder) lands
    • the bundled shot / mark lands
    • the foe acts (a DoT cast — Bio; a normal hit; or is dodged)
    • status line prints:  HP  MP  XPNL  APNL  FOE  AFF
  ──►  player reads the line, decides:
    • fire ss again (sustain), OR
    • break rhythm: heal (keypad-minus → cr), apply Slow, buff allies (holy regeneration)
  ──►  on kill:  XP + AP + gold, corpse fades, FOE clears
```

**CodeForge translation.** CodeForge already has the spine of this: `handle_command(session, text)`
is the tick, and after the player's command *the world takes its beat* (`menace` = aggressive foes
strike; `tick_zones`, `tick_burns`). That IS a round. The gap is **bundling**: today a player types
`attack <foe>` for one action. The reference shows the winning ergonomic — one verb that resolves a
*stack*. Recommendation: a `strike`/`engage` verb that, on each tick, resolves auto-attack swings
**plus** the player's equipped weaponskill if its resource/cooldown allows, printing one clean block.

---

## 3. Cadence Timeline (estimates)

| Quantity | Observed / estimated | Notes |
|---|---|---|
| Round length (≈ GCD) | ~2.0–2.5 s *(est.)* | Derived from the round-lock flavour firing on rapid repeat input |
| Player APM | **~20–40** *(est.)* | One bundled command per round + occasional reaction — deliberately low |
| Auto-attack swings / round | **1–8** (observed 1, 4, 6, 8) | Scales with haste/speed; a slowed foe or buffed player shifts it |
| Trash time-to-kill | **~3 rounds / ~6–8 s** *(est.)* | Vermin fell after two `ss` + auto-attacks |
| Per-round player damage | ~1,100–2,400 | vs a ~7,288-HP player pool |
| Enemy per-round damage | ~180–231 (DoT) + occasional hit | Far below player HP → high survivability vs trash |
| Reaction window (heal) | Any round the player chooses | Heal is a one-keystroke interrupt, not gated by the foe |

**Reading:** the cadence is *slow enough to think, fast enough to feel busy.* The player is never
forced to react inside a sub-second window against trash; the tension is resource-management and
rhythm, not reflex. Boss content (not in the footage) is where reaction windows would tighten.

**CodeForge translation.** Adopt an explicit, tunable **round length** as a data value (not
hard-coded), so trash rounds are forgiving and boss encounters can shorten the beat or add
telegraphed windows. CodeForge's `beat` already exists per command; formalize a *round clock* so
"how fast can I act" is a designed number, and echo a friendly refusal when a player spams faster
than the round is ready — mirroring "What's the rush?" (never a stack-trace-flavoured error).

---

## 4. Ability Philosophy

Observed abilities and their design jobs:

| Observed | Category | Design purpose |
|---|---|---|
| `Sidewinder` (weaponskill, ranged, **needs a target** — "Use Sidewinder at who?") | Direct burst | The payoff of the bundle; explicit targeting forces intent |
| Screeching arrow → **"Vermin slows down!"** | Ranged + Slow (CC proc) | Rhythm control: reduce the foe's swings, buy rounds |
| `Regen` ("restoring 370 HP") | Self HoT | Sustain woven into the loop, not a panic button |
| **"You bless your allies with holy regeneration!"** | Party HoT / aura | Group sustain — one action helps the whole party |
| Enemy `Bio` ("231 poison damage") | Enemy DoT | Steady attrition pressure the player must out-heal |

Design principles extracted:

- **Every ability answers a question the round poses** — not "more damage" but "control the foe's
  tempo," "keep the party topped," "convert a shot into a debuff." (The prompt's own rule: *avoid ten
  versions of "deal damage."*)
- **Explicit targeting is a feature, not friction** — "Use Sidewinder at who?" makes the player
  *declare* their priority target, which is a decision, not a chore.
- **Sustain is ambient** — Regen ticks in the background so healing is a *rhythm*, not a scramble.

**CodeForge translation.** CodeForge already types every blow with an **element** (FIR/ICE/LGT/WND/
ERT/WTR/HLY/DRK/PSN/CRS) and foes carry a **resistance grid** (Weak/Resist/Immune/Absorb) — so
"read the foe, bring the right element" is our native version of "read the round." Extend abilities to
carry the reference's *shapes*: a DoT (like our `burn`), a Slow (a beat-delay debuff — we already have
`daze`), a self-HoT, and a party aura. The lesson: **each ability should change a variable the round
tracks** (foe swings, your HP-over-time, the foe's element-affliction), not just the damage number.

---

## 5. Enemy Philosophy

Observed enemy behaviour (Vermin, trash):

- **Attrition, not spikes** — a DoT (`Bio`, ~200/round) and light hits (~182), well under the
  player's HP pool. The threat is *cumulative*, answered by ambient Regen.
- **Occasional whiff** — "You easily dodge Vermin's attack!" — the foe is not a metronome; evasion
  creates small positive surprises that keep the loop from feeling deterministic.
- **Telegraphed flavour** — "Vermin releases a cloud of noxious gas throughout the air!" precedes the
  Bio damage — a one-line *tell* before the effect lands.

Design principle: **trash exists to teach the rhythm and feed the currencies**, not to threaten.
Its danger is a slow bleed you manage with one ambient tool.

**CodeForge translation.** Our `menace` (aggressive foes strike on the beat) is the spine. Add two
things the reference shows: (1) a **telegraph line one beat before** a foe's special (we already do
this for some bosses — generalize it), and (2) **enemy evasion** as an occasional whiff so combat
isn't a fixed subtraction. Trash foes (the wildlands bestiary) should apply light DoT-style pressure
the player out-sustains, reserving spike damage for elites/bosses.

---

## 6. Boss Philosophy

*(Not directly in the footage — trash only — so this is principle, not observation.)* The reference's
cadence implies the boss design: where trash is forgiving attrition, a boss **tightens the round**.
The tools already present scale up naturally:

- The **telegraph → effect** gap becomes a real **reaction window** (interrupt / move / shield /
  break line of sight — the prompt lists nine answers to one dangerous cast).
- The **Slow/CC** the player used on trash becomes *the boss's* tempo weapon against the party.
- **Soft enrage**: a boss whose per-round damage climbs, forcing the burst window before attrition
  wins.

**CodeForge translation.** CodeForge bosses are `tier: boss`, often `lethal` (fall to one and you're
sent home at full HP, not killed — a built-in *recovery opportunity*). Layer on: a **telegraphed
special every N rounds** with a legible one-line tell and a *menu of counters* (our elements, a
future interrupt verb, positioning), and a **soft-enrage** ramp so a fight has a burst-window shape
rather than a flat DPS check. Never a single mandatory answer — multiple jobs must each have *an*
answer (interrupt, shield, displace, out-heal).

---

## 7. Party Dynamics

Observed: **"You bless your allies with holy regeneration!"** — a single action buffs the whole party.
The reference is played solo here, but the party hooks are visible: party HoT auras, and the
`FOE:` count in the status line implies multi-target/add management.

Design principle: **party value is a broadcast, not a babysit** — one command improves everyone, so
support play is about *timing a shared beat*, not spamming per-ally.

**CodeForge translation.** CodeForge already broadcasts to a room (`announce`) and has multi-session
rooms. A party layer should favour **room-wide auras** (a Bard-song / Cleric-blessing that ticks for
everyone in the room on the beat) over per-target micromanagement — cheap to implement on our beat,
and it makes support a *rhythm* role, matching the 30-job campaign's Bard/Cleric/Warlord identities.

---

## 8. Risk vs Reward

Observed reward per trash kill: **14,000 XP + 30 AP + 733 gold.** Two progression currencies from one
kill. The risk against trash is low (attrition you out-heal), so the *reward-per-risk* is high but
capped by the round clock — you can't kill faster than the rounds allow.

Design principles:

- **Dual currency** — XP (character power) and AP (job/ability mastery) advance on the *same* action,
  so no activity feels like it only feeds one track.
- **Rate-limited farming** — the round clock and the "What's the rush?" refusal prevent input-spam
  from trivializing progression (the job campaign explicitly wants this: *prevent trivial farming*).

**CodeForge translation.** CodeForge kills already award XP scaled by the **challenge curve** (fight
up = more, greys = nothing) via `reward_curve`. Add an **AP-equivalent** (job/ability points) awarded
on the *same* kill, banked per-job, spent on the 30-job progression. Keep the challenge curve as the
anti-farm governor: greys pay no AP either, so zero-risk grinding doesn't advance a job.

---

## 9. Resource Systems

Observed resources on the status line: **HP** (~7,288 max), **MP** (~972 max), and two *progress*
bars — **XPNL** (XP-to-next-level %) and **APNL** (AP-to-next-level %). Abilities spend MP (casts) or
are weaponskill/stamina-driven (the multi-hit auto-attack). Regen restores HP over time; the loop is
"spend MP on control/heals, let auto-attack and Regen carry sustain."

Design principle: **the status line is the resource UI** — every managed value is one glance away, and
*progress toward the next level* is a resource too (it tells you whether to push or move on).

**CodeForge translation.** CodeForge has HP/MP pools and a score sheet. Adopt the reference's
**single-line combat prompt** as an optional compact HUD: `HP x/y · MP x/y · XP→ % · AP→ % · foe ·
afflictions`. It's cheap (a render function on the beat) and it's the single biggest "feel" upgrade —
the reference proves a text game's entire HUD can be one legible line. The 30-job campaign's
per-job resources (Rage, Combo, Blood, Runes…) each get one token on that line only if they *drive a
decision* (the campaign's own rule).

---

## 10. Timing Windows

Observed windows:

- **The round-lock** — inputting before the round is ready yields "What's the rush?" / "Whoa! Where's
  the fire?". This is a *soft* global cooldown: the window to act opens each round, and early input is
  refused kindly.
- **The heal interrupt** — `heal` on keypad-minus (`cr`) can be fired any round; healing is a
  *rhythm-break the player chooses*, not a foe-gated window.
- **The debuff setup** — the slow-arrow before a burst round changes how many swings the foe gets;
  timing it *before* pressure spikes is the skill expression.

**CodeForge translation.** Make the **round clock** explicit and surface *"the beat isn't ready"* as
friendly flavour (never an error). Reaction abilities (the 30-job campaign's Reaction slot) fire on
**events on the beat** — took damage, blocked, fell below a threshold — with an **internal cooldown**
so they can't loop (the campaign's hard rule: *no reaction may trigger itself indefinitely*). Our
existing beat is the perfect substrate: reactions are just beat-events with a per-source throttle.

---

## 11. Encounter Design

Observed: a single-foe grind encounter with ambient attrition, plus a `FOE:` counter implying
multi-add fights elsewhere. The *client* side reveals the real encounter meta-game: **zone
speedwalks** (aliased routes to Figaro Desert, Mt Ordeals, Opera House, Dactyl Nest, Enhasa) and
**spell-up trigger groups** (`ss Soul/Revenant/Bone/Lilith/Spirit`) — the player pre-scripts
buff/route sequences so the *encounter* is what they think about, not the plumbing.

Design principle: **let players automate the boring, so the fight is the game.** Keybinds, aliases,
and triggers are not cheating — they are the MUD's *ergonomics layer*, and a good MUD is designed
knowing players will build one.

**CodeForge translation.** This is a direct nod to **codeforge-console** / **codeforge-client** (our
own terminal MUD client with timers, triggers, auto-map, an AI co-pilot). The engine should *reward*
this: stable, scriptable command names (we already freeze `lowercase_snake_case` verbs), a clean
one-line prompt to trigger on, and **noun/`ss`-style bundled verbs** so a single alias/mouse-button is
a full round. Design the server assuming a scripted client — the reference proves that's the native
MUD experience.

---

## 12. MMO Lessons (keep)

1. **One-button rounds.** The `ss` bundle is the whole insight: collapse the common case to a single
   input so the *decisions* (when to break rhythm) are what the player spends attention on.
2. **Forgiving cadence with flavour.** "What's the rush?" teaches tempo without punishing — a
   friendlier global cooldown than a greyed-out button.
3. **One-line HUD.** The entire resource/progress/foe/affliction state in a single prompt line.
4. **Dual progression from one kill.** XP + AP means every fight advances both character and job.
5. **Ambient sustain.** Regen ticking in the background makes healing a rhythm, not a panic.
6. **Read-the-round, not twitch.** Threat is attrition and tempo; skill is *sequencing* (slow, then
   burst), which suits a text game's input latency.
7. **Design for the scripted client.** Aliases/triggers/keybinds are the ergonomics layer; embrace
   them with stable verbs and a triggerable prompt.

---

## 13. Lessons to Avoid

1. **Don't require twitch reactions a text client can't deliver.** Sub-second dodge windows are unfair
   over a MUD's input/round latency — keep reaction windows a *round* wide, tighten via telegraphs not
   milliseconds.
2. **Don't let one bundled command trivialize *all* content.** If `ss` is always optimal, combat is a
   one-button game. Bosses must pose questions `ss` doesn't answer (interrupt, move, cleanse) so the
   bundle is the *baseline*, not the *whole game*.
3. **Don't gate progression behind pure spam.** Without the round clock + challenge curve, AP/XP
   farming becomes mindless — keep greys worthless and the round rate-limited.
4. **Don't hide costs.** The reference always prints what happened ("restoring 370 HP", "for 231
   poison damage"). Every effect is legible in the log; avoid silent modifiers.
5. **Don't make unique job resources for flavour alone** (the job campaign's own rule) — a resource
   earns its token on the HUD only if it changes a decision.

---

## 14. Original CodeForge Recommendations

Each is an *original* mechanic inspired by the design philosophy — not a copy.

| # | Observation | Principle | CodeForge adaptation (original) | Improvement over reference |
|---|---|---|---|---|
| R1 | `ss <target>` bundles a round | Collapse the common case to one input | A `strike`/`engage` verb: on each beat, resolve auto-attack swings + the equipped weaponskill if its element/resource allows, in one clean block | Make the bundle *element-aware* — it auto-fires the weaponskill only when the foe isn't Immune, nudging players to swap elements |
| R2 | "What's the rush?" round-lock | Forgiving cadence, no punishment | An explicit data-driven **round clock**; early input echoes a friendly "the beat isn't ready" (in the forge voice), never an error | Show a tiny *beat-ready* tell in the prompt so timing is learnable, not guessed |
| R3 | One-line `HP·MP·XPNL·APNL·FOE·AFF` | The HUD is one legible line | An optional compact combat prompt rendered on the beat, tokens only for values that drive a decision | Colour-code by our elements/afflictions; let the console client trigger on it |
| R4 | `XP + AP + gold` per kill | Dual progression from one action | Award **AP (job points)** alongside XP on every challenge-curve-valid kill, banked per-job for the 30-job system | Greys pay no AP (anti-farm) — tie AP directly to the challenge curve we already ship |
| R5 | Regen HoT ambient sustain | Sustain as rhythm, not panic | Generalize our `burn` DoT into a symmetric **over-time** effect family (heal-over-time, poison, bleed) ticking on the beat | One code path for all over-time effects, data-typed by element |
| R6 | Screeching arrow → Slow | Abilities change a round variable | A **beat-delay** debuff (extend our `daze`): a slowed foe acts every *other* beat, so control buys rounds | Make Slow *stack toward* a stun at a threshold — a legible control ramp |
| R7 | "bless your allies" party HoT | Party value is a broadcast | Room-wide **auras** (Bard-song / Cleric-blessing) that tick for everyone in the room on the beat | Auras carry an element so a party can pre-condition a fight (a Radiant aura vs a DRK boss) |
| R8 | Zone speedwalks + trigger groups | Design for the scripted client | Stable scriptable verbs + a triggerable prompt so codeforge-client aliases/timers are first-class | Ship *official* alias packs as Hardware-Store parts, versioned with the engine |

**North star.** The reference feels good because it makes the *common* action one keystroke and the
*interesting* action a deliberate break in rhythm, then reports everything in one legible line and
pays two currencies for the trouble. CodeForge already owns the substrate — the beat-driven tick, the
element/resistance grid, the challenge curve, `lethal` bosses with a built-in recovery, and a
scriptable client. The work is not to copy the MUD; it is to **bundle the round, formalize the round
clock, add the AP currency, and give every ability a round-variable to change.**

---

*Grounded in reference footage (Mudlet 4.19.1, 73 s, round-based text combat). No names, lore, UI,
assets, or abilities were copied; the analysis extracts design principles only.*
