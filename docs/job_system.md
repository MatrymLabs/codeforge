# The CodeForge Job System (canonical design)

This is the canonical design for the CodeForge Job System: a modular character framework
inspired by the role-modularization philosophy of tactical RPGs, but wholly original in its
lore, mechanics, terminology, progression, and implementation. It is the design spec that the
engine's data-driven job schema realizes.

> **Status, honestly labelled.** This document is the **design** (the intended, complete
> system). The engine already ships the data-driven substrate it targets: the `Job` loadout
> schema in `parts/world/seed.py`, real-time combat ticks, per-tick resource regen, and independent
> job levels (see [`character_system.md`](character_system.md)). A subset of jobs is realized in
> `seeds/*/jobs.yaml` today (the Engineer is the reference implementation); the remaining jobs
> here are designed for future implementation as seed data. Nothing below claims to be shipped
> code. A job becomes real when its data lands in a seed and its abilities are wired as
> components, without touching the core combat loop.

## Why this system exists

Most job systems force a choice between depth (hundreds of classes, unmaintainable) and breadth
(a handful of stereotypes: tank, healer, damage). CodeForge takes a third path: a **small set of
deeply distinct jobs** combined through **independent, hot-swappable build slots**, so twenty
jobs produce hundreds of viable, legible builds. Every job solves battlefield problems
*differently*, not just *harder*, and the combat engine never learns any job's name.

---

## 1. Combat model (what every ability is designed around)

CodeForge combat is **persistent world state**, not alternating turns. A fight begins when a
combatant engages and continues until **Victory, Defeat, Escape, Surrender, or a scripted
encounter end**. It advances through continuous **combat ticks** (about one per second). Each
tick the engine resolves, in order: auto attacks, cooldowns, status effects, resource
regeneration, NPC AI, and environmental effects. Players issue commands *continuously*
throughout, not in a queue that waits for a turn.

Every ability in this system is therefore built for a real-time cadence. There is no "your
turn." The design levers are:

- **Cooldowns** (seconds) - the primary economy of when you can act again.
- **Cast / channel** - an ability that takes time and can be **interrupted** mid-cast, making
  interrupts and stagger real counterplay.
- **Duration and per-tick effects** - damage-over-time, heal-over-time, buffs, and fields that
  resolve each tick.
- **Positioning** - range bands (melee, near, far), lines, and area shapes matter every tick.
- **Preparation** - stances, marks, traps, and charges set now to pay off later.
- **Resource generation** - most jobs pay for their power with a resource they must *build*.

An ability that assumes it gets a clean, uninterrupted turn is wrong for this engine.

---

## 2. Character build structure

Every character is the composition of these slots. Jobs supply the parts; the player assembles
the build.

| Slot | What it is | How it is set |
|---|---|---|
| **Player Level** | Global level (XP), cap 255 | Rises with total XP; drives stat-point allocation. |
| **Primary Job** | The defining discipline | Determines stat growth, equipment affinity, core abilities, and mastery. |
| **Secondary Job** | A borrowed discipline | Contributes **only its learned active abilities** (not its passives, stats, or equipment). |
| **Individual Job Levels** | One level per job, cap 30 | Each job levels independently (JP), unlocking that job's components in order. |
| **Reaction Ability** | One equipped reaction | Chosen freely from any reaction the character has unlocked. |
| **Support Doctrine** | One equipped passive | Chosen freely from any passive the character has unlocked. |
| **Movement Technique** | One equipped movement | Chosen freely from any movement the character has unlocked. |
| **Signature Ability** | One equipped signature | The capstone identity move of a mastered job. |
| **Equipment** | Weapon, armor, offhand, trinkets | Gated by the Primary Job's equipment proficiencies. |
| **Profession** | A non-combat craft/gather identity | Orthogonal to combat; feeds equipment and consumables. |

The engine already models this: `Job` carries `role_tags`, `abilities`, `automatic_attack`,
`counter` (reaction), `movement`, `inherent` (a passive), `signature`, `resistances`,
`power_cells` + `power_regen` (a custom resource), and `milestone_perks` (ordered passive
unlocks). This design fills those fields for twenty jobs; it invents no new engine machinery.

**The combinatorics.** With 20 primaries x 19 possible secondaries x an unlocked pool of
reactions, supports, movements, and signatures, the viable-build space is in the thousands well
before content expands. A Vanguard who borrows Chronomancer haste plays nothing like a Vanguard
who borrows Saboteur toxins, and both are still recognizably Vanguards.

---

## 3. Attributes

Six attributes, shared across all jobs (the engine's `DEFAULT_JOB_STATS`). A job's Primary and
Secondary Attributes decide its stat growth and equipment affinity.

| Attribute | Governs |
|---|---|
| **Strength (STR)** | Melee and thrown weapon power; carry and stagger. |
| **Speed (SPD)** | Action rate (how fast cooldowns and auto attacks cycle) and evasion. |
| **Magic (MAG)** | Spell and device power; maximum MP. |
| **Stamina (STA)** | Maximum HP and physical endurance; resistance to physical status. |
| **Wisdom (WIS)** | Resource regeneration, resistance, and the potency of support and healing. |
| **Luck (LUCK)** | Critical chance, proc chance, and rare favorable outcomes. |

SPD is deliberately load-bearing in a real-time engine: it is the tempo stat, not a dump stat.

---

## 4. Resource systems

Every job runs on **HP** (life, `BASE_HP` + STA) and **MP** (spell and technique fuel,
`BASE_MP` + MAG). On top of that, each job defines **one original custom resource** (the engine's
`power_cells` slot, with a per-tick behavior via `power_regen`). The custom resource is the
mechanical heart of the job's identity: it decides *when* the job is dangerous.

Custom resources are built from a small set of **generation archetypes** (each job picks one and
names it originally):

- **Builder** - starts empty, accrues from landing actions, is spent in bursts. Rewards
  aggression and uptime (for example a martial momentum meter).
- **Reservoir** - starts full, drains as you spend, refills slowly at rest or out of combat.
  Rewards pacing and disengagement windows (for example a prepared-charge bank).
- **Swing meter** - a two-pole bar that slides between opposite states, each pole enabling
  different abilities. Rewards rhythm and deliberate tilting (for example a stance or aspect
  meter).
- **Heat** - rises as you use the kit and punishes overheating (a soft cap with a penalty band),
  bleeding off per tick. Rewards restraint and burst timing.
- **Upkeep** - a pool that persistent summons, wards, or fields continuously drain; running dry
  dismisses them. Rewards board management (for example a summoner's binding pool).
- **Foresight / stock** - a bank of discrete charges predicted or stored ahead of time, spent to
  pre-empt events. Rewards reading the fight.

Resources are configurable data, not code: a job declares its pool size, regen, and the archetype
its abilities read against. New archetypes can be added without changing the combat loop.

---

## 5. Equipment matrix

Equipment is independent of jobs; a job declares which **proficiencies** it may use, and its
Primary Attributes decide how much affinity it gets. The proficiency vocabulary:

**Weapons:** Blade, Great Weapon, Polearm, Fist, Bow, Crossbow, Thrown, Focus (arcane implement),
Sidearm (engineered), Instrument, Natural (unarmed or beast-form).

**Armor:** Heavy Plate, Mail, Brigandine, Leather, Cloth/Robe, Ward (arcane weave), Rig
(engineered harness).

**Offhand / tools:** Shield, Buckler, Trinket, Kit (tools/consumables), Totem.

| Family | Typical weapons | Typical armor | Typical offhand |
|---|---|---|---|
| Martial | Blade, Great Weapon, Polearm, Fist | Heavy Plate, Mail, Brigandine | Shield, Buckler |
| Precision | Bow, Crossbow, Thrown, Blade | Leather, Brigandine | Kit, Trinket, Buckler |
| Arcane | Focus, Blade | Cloth/Robe, Ward | Trinket, Totem |
| Divine | Focus, Polearm, Blade, Instrument | Mail, Cloth/Robe, Ward | Shield, Totem |
| Engineering | Sidearm, Fist, Thrown | Rig, Brigandine | Kit, Buckler |
| Nature | Natural, Instrument, Polearm | Leather, Ward | Totem, Trinket |

Equipment carries flat and proc modifiers that fold into derived stats through the existing
`ModifierStack` (see `parts/world/equipment.py`), so gear tunes a build without the job knowing about
any specific item.

---

## 6. Progression and mastery

Two independent tracks, already implemented (`parts/world/progression.py`):

- **Player Level (XP -> PLvl, cap 255).** Global. Grants stat points to allocate (capped at 3
  per stat per level), raising the six attributes toward a build's identity.
- **Job Level (JP -> Job Lvl, cap 30).** Per job, earned by fighting *in* that job. A job's
  components unlock in order as it levels: early actives first, then the passives, reactions,
  movements, and finally the signature and mastery at the top of the track.

**A suggested unlock cadence per job (data-tunable):**

| Job Lvl | Unlocks |
|---|---|
| 1 | Auto attack, first 2 active abilities, the job's custom resource. |
| 3, 5, 8 | Active abilities 3-6. |
| 6, 10 | Passive Support Doctrines 1-2. |
| 12, 15 | Active abilities 7-8; Reaction abilities 1-2. |
| 18, 21 | Active abilities 9-10; Movement techniques 1-2; Passive 3. |
| 24, 27 | Reaction abilities 3-5; Movement 3; Passives 4-5. |
| 29 | Signature ability. |
| 30 | **Job Mastery Bonus** (a permanent, build-defining reward, listed per job). |

**Mastery.** Reaching Job Lvl 30 grants that job's Mastery Bonus *and* certifies its Signature as
equippable on any character. Because reactions, supports, and movements are chosen from the whole
unlocked pool, a mastered job permanently widens every future build, not just builds that run it
as Primary. This is the engine of long-tail replay: you master jobs to enrich other jobs.

---

## 7. Ability, passive, reaction, and movement taxonomies

Every component is tagged from one shared vocabulary, so a build can be read at a glance and the
engine can reason about it generically.

**Ability tags:** `damage`, `heal`, `buff`, `debuff`, `cc` (crowd control), `interrupt`,
`counter`, `mobility`, `area` (area control), `resource` (generation), `prep` (preparation),
`position` (positioning), `support`, `synergy`.

**Active Abilities** (ten per job). Commands the player issues, each with a cost and a cooldown,
some with a cast or channel. This is the job's moment-to-moment play.

**Passive Support Doctrines** (five per job). Always-on effects; one is equipped in the Support
slot at a time. Doctrines shape *how* a job's numbers behave rather than adding a button.

**Reaction Abilities** (five per job). Each has a **trigger** (a condition the engine checks, for
example "when struck by a melee hit," "when a foe begins a cast," "on falling below a health
threshold") and a cooldown. One is equipped in the Reaction slot. Reactions are the counterplay
layer: they turn the enemy's actions into your opportunities without a turn to spend.

**Movement Techniques** (three per job). Repositioning and mobility tools (dashes, blinks,
disengages, gap-closers) on cooldowns. One is equipped in the Movement slot. In a real-time,
positional engine, movement is a first-class ability, not flavor.

**Signature Ability** (one per job). The capstone that only that job, mastered, can grant. A
signature is build-defining and usually has a long cooldown and a dramatic effect.

---

## 8. The twenty jobs

The jobs are organized into six families. A family shares a thematic and structural space, but
every job within it solves problems differently. Each job below is specified to the full
template: purpose, lore, combat role, attributes, equipment, resource, identity, strengths and
weaknesses, progression, mastery, ten actives, five passives, five reactions, three movements,
one signature, secondary synergies, and example builds.

### Martial family

The Martial family are close-quarters specialists who win fights through positioning, timing, and
pressure rather than raw numbers, each converting a different battlefield truth into advantage.
Where the Vanguard turns held ground into escalating crowd control, the Duelist wins isolated
exchanges by baiting and punishing reads, the Sentinel protects allies by intercepting and
reflecting harm, and the Berserker spends its own safety to buy runaway power. Four bodies in the
front line, four completely different questions asked of the enemy.

#### Vanguard
- **Purpose:** Hold the front line and convert sustained enemy pressure into battlefield control.
- **Lore:** Forged from the shield-walls that once bought time for a retreating column, Vanguards learn that an inch of held ground is worth a mile of charge. They read the crush of a melee like a tide chart, letting the enemy's own momentum set the hook for the clamp that follows.
- **Combat Role:** A control-tank who does not just soak damage but weaponizes staying put: the longer a Vanguard occupies a spot, the more it locks down, snares, and redirects clustered foes, punishing anyone who tries to flow past the line.
- **Primary / Secondary Attributes:** STA, STR / WIS, SPD.
- **Equipment Proficiencies:** Polearm, Great Weapon, Blade / Heavy Plate, Mail / Shield, Totem.
- **Resource System:** HP (high pool). MP (small, feeds utility). **Bulwark** (0-100): builds +6/tick while the Vanguard stands within 1 tile of its "anchor" spot and takes or blocks a hit; decays -10/tick if it moves more than 1 tile from anchor. Spent in bursts to fuel clamp and area-lock abilities; at 100 Bulwark all your CC durations gain +1s.
- **Unique Identity:** Can plant an Anchor point that grows a widening zone of control the longer it is held, the only job whose power scales with immobility.
- **Strengths:** Best sustained area crowd control; converts being focused into resource; excellent at protecting a chokepoint.
- **Weaknesses:** Weak once forced to move; low burst damage; Bulwark starves in open, mobile fights.
- **Job Progression:** L1 Anchor + Bulwark; L5 first area snare; L10 reaction unlock (Braced Answer); L15 Bulwark cap raised, movement tech Line Shift; L20 area Root access; L25 signature; L30 mastery.
- **Job Mastery Bonus (Lvl 30):** Anchor's control zone gains a permanent +1 tile radius and Bulwark decay while off-anchor is halved.
- **Signature Ability:** **Tidebreak Wall** [70 Bulwark / 40s] - slam a barrier across your facing line: enemies crossing it are Rooted 2s and Weakened 6s. `[cc][area][control][debuff]`

**Ten Active Abilities:**
1. Anchor Set [10 MP / 12s] - plant/refresh your anchor; while standing on it Bulwark builds double. `[prep][resource][position]`
2. Grasping Sweep [20 Bulwark / 6s] - hit all adjacent foes, Snare 3s. `[damage][area][cc]`
3. Shieldpin [15 Bulwark / 8s] - single target, Root 2s + Mark. `[cc][debuff]`
4. Bracing Shout [12 MP / 15s] - allies within 2 tiles gain Guard 5s. `[buff][support][area]`
5. Crush Line [25 Bulwark / 10s] - cone strike, Bleed 4s + knock toward you. `[damage][cc][position]`
6. Hold the Gap [15 MP / 20s] - enemies attempting to pass your tile are Snared until they stop trying. `[cc][area][control]`
7. Weight of the Wall [30 Bulwark / 14s] - the more enemies adjacent, the higher the damage; Vulnerable 5s to all hit. `[damage][area][debuff][synergy]`
8. Iron Reproach [18 Bulwark / 9s] - taunt-Mark up to 3 foes for 6s, drawing their attacks. `[debuff][cc][support]`
9. Settling Stance [8 MP / 18s] - gain Regen 8s while on anchor. `[heal][buff]`
10. Groundquake [40 Bulwark / 25s] - Stun all adjacent 1.5s. `[cc][area][interrupt]`

**Five Passive Support Doctrines:**
- Rooted Resolve - immune to being pushed off your anchor tile.
- Tidewise - Bulwark generation +25% while three or more foes are within 2 tiles.
- Steadfast Frame - take 15% less damage while Bulwark is above 50.
- Line Discipline - your CC on Marked targets lasts +1s.
- Deep Footing - MP regen +20% while stationary.

**Five Reaction Abilities:**
- Braced Answer [on taking a melee hit; 8s] - reduce that damage 40% and gain 10 Bulwark. `[counter][resource]`
- Countertide [on being Rooted/Stunned; 20s] - break it and Snare the attacker 2s. `[counter][cc]`
- Reprisal Wall [on ally within 2 tiles taking a hit; 12s] - Weaken the attacker 4s. `[counter][debuff][support]`
- Immovable [on being knocked/pulled; 15s] - negate the movement, gain Guard 3s. `[counter][position]`
- Anvil's Return [on blocking with Shield; 6s] - reflect 20% of blocked damage. `[counter][damage]`

**Three Movement Techniques:**
- Line Shift [10s] - slide up to 2 tiles and replant anchor at the destination without losing Bulwark. `[mobility][position]`
- Wedge Step [14s] - dash into an enemy, swapping places and Snaring it 2s. `[mobility][cc]`
- Set and Hold [18s] - short teleport back to your last anchor, cleansing Snare/Root. `[mobility][position]`

**Secondary Job Synergies:**
- Sentinel: pairs anchor-control with intercept protection to make a chokepoint nearly impassable.
- Berserker: borrow escalation strikes to add real damage to a job that otherwise only controls.
- Duelist: import a counter-read package to punish the one foe who tries to break your line.

**Example Builds:**
- *Chokepoint Warden:* Vanguard / Sentinel, reaction Braced Answer, support Steadfast Frame, movement Line Shift, signature Tidebreak Wall; Polearm + Heavy Plate + Shield. Holds a corridor and reflects harm onto whoever pushes.
- *Clamp Bruiser:* Vanguard / Berserker, reaction Anvil's Return, support Tidewise, movement Wedge Step; Great Weapon + Mail + Totem. Locks a cluster, then adds Berserker escalation for kills.

#### Duelist
- **Purpose:** Win isolated one-on-one exchanges by reading, baiting, and punishing enemy actions.
- **Lore:** Duelists trained in the ring-courts where a single misread ends the bout, learning to sell a weakness as a lure. They speak of the fight as a conversation, and every parry is a question asked to learn the enemy's next word.
- **Combat Role:** A precision single-target specialist who thrives when the fight narrows to one opponent, building "reads" off enemy behavior to unlock devastating punishes, but fading in chaotic multi-target scrums.
- **Primary / Secondary Attributes:** SPD, LUCK / STR, WIS.
- **Equipment Proficiencies:** Blade, Fist, Sidearm / Leather, Brigandine / Buckler, Trinket.
- **Resource System:** HP (moderate). MP (small). **Tempo** (0-5 stacks): gain 1 stack when you successfully parry, dodge, or land a hit on a Marked foe; lose 1 stack per 4s out of combat with your Marked target. Spent to empower punish abilities (each stack raises damage/effect); per-tick it does not decay in active melee, rewarding staying locked on one dance partner.
- **Unique Identity:** Only job that reads a specific enemy: placing a Duelist's Mark builds Tempo exclusively against that target and unlocks escalating punishes tied to what the target does.
- **Strengths:** Highest single-target burst on a read; strong self-evasion and counter-play; converts enemy mistakes into damage.
- **Weaknesses:** Falls off hard versus groups; low area presence; nearly toothless before Tempo is built.
- **Job Progression:** L1 Duelist's Mark + Tempo; L5 first parry-punish; L10 reaction Riposte Read; L15 Tempo cap raised; L20 feint tools; L25 signature; L30 mastery.
- **Job Mastery Bonus (Lvl 30):** Tempo caps at 7 and your first punish each fight is guaranteed to crit.
- **Signature Ability:** **Closing Sentence** [5 Tempo / 45s] - a single strike whose damage scales with Tempo spent; if it kills, refund all Tempo. `[damage]`

**Ten Active Abilities:**
1. Duelist's Mark [8 MP / 10s] - Mark one target as your duel partner; Tempo only builds off it. `[prep][debuff][resource]`
2. Read Cut [1 Tempo / 4s] - strike; if target is attacking, +50% damage. `[damage][counter]`
3. Baited Opening [10 MP / 12s] - drop your Guard visibly; next enemy melee is auto-parried, granting 2 Tempo. `[prep][counter][resource]`
4. Wristbind [2 Tempo / 14s] - Silence the Marked target 3s. `[cc][debuff][interrupt]`
5. Lunge Pierce [1 Tempo / 6s] - gap-close strike, Bleed 5s. `[damage][mobility]`
6. Off-Foot Feint [12 MP / 10s] - fake a strike; if target reacts (blocks/dodges), Weaken it 5s. `[debuff][prep]`
7. Twin Answer [2 Tempo / 9s] - two rapid hits; second is guaranteed crit if the first landed. `[damage]`
8. Disarming Turn [3 Tempo / 20s] - reduce Marked target's damage 30% for 6s. `[debuff]`
9. Measure the Range [6 MP / 15s] - gain Haste 5s and +evasion vs the Marked target. `[buff][mobility]`
10. Punish Chain [4 Tempo / 25s] - if the target has acted twice since your last hit, massive strike + Vulnerable 5s. `[damage][debuff]`

**Five Passive Support Doctrines:**
- Duel Focus - +20% damage to your Marked target, -15% to all others.
- Tempo Read - parries and dodges grant +1 extra Tempo.
- Light Feet - evasion +15% while a Mark is active.
- Killer's Patience - critical hit chance +2% per Tempo stack.
- Follow-Through - abilities that spend Tempo cost 1 less on a critical hit.

**Five Reaction Abilities:**
- Riposte Read [on parrying; 6s] - counterstrike for bonus damage and gain 1 Tempo. `[counter][damage][resource]`
- Slip Turn [on being hit by melee; 10s] - 50% chance to convert it to a graze (75% reduced). `[counter]`
- Called Shot [on Marked target casting; 12s] - interrupt it and Silence 2s. `[interrupt][cc]`
- Mirror Step [on target moving away; 8s] - dash to stay in melee range. `[mobility][position]`
- Second Wind Parry [on dropping below 30% HP; 25s] - next parry heals you 15%. `[counter][heal]`

**Three Movement Techniques:**
- Shadow the Mark [8s] - short blink to your Marked target's flank. `[mobility][position]`
- Sidestep [10s] - lateral dodge that avoids the next melee entirely. `[mobility][counter]`
- Retreat and Read [14s] - hop back 2 tiles, gaining evasion and 1 Tempo. `[mobility][resource]`

**Secondary Job Synergies:**
- Berserker: borrow escalation for even higher punish ceilings once Tempo is maxed.
- Sentinel: import intercepts to survive the group phase until you can isolate a target.
- Vanguard: use Shieldpin/Root to keep your dance partner from fleeing the duel.

**Example Builds:**
- *Ring-Court Assassin:* Duelist / Berserker, reaction Riposte Read, support Killer's Patience, movement Shadow the Mark, signature Closing Sentence; Blade + Leather + Buckler. Snowballs one target into a lethal punish.
- *Counter-Fencer:* Duelist / Vanguard, reaction Called Shot, support Light Feet, movement Sidestep; Fist + Brigandine + Trinket. Locks a caster down and Silences its every attempt.

#### Sentinel
- **Purpose:** Shield allies by intercepting incoming harm and turning it back on attackers.
- **Lore:** Sentinels swore the Longwatch oath: no ward-brother falls while the Sentinel still stands between. Their armor is scored with the marks of blows meant for others, worn like medals rather than wounds.
- **Combat Role:** A guardian-protector who does not tank by holding aggro but by physically intercepting hits aimed at allies and reflecting a portion back, best when a fragile ally needs a body between them and the enemy.
- **Primary / Secondary Attributes:** STA, WIS / STR, LUCK.
- **Equipment Proficiencies:** Great Weapon, Polearm, Fist / Heavy Plate, Ward / Shield, Totem.
- **Resource System:** HP (high). MP (moderate, feeds Guard buffs). **Aegis** (0-100): builds +8 whenever you intercept or block a hit meant for a warded ally; drains -4/tick while any Guard you cast is active. Spent to project shields and reflect damage; at 0 Aegis your intercepts still work but do not reflect.
- **Unique Identity:** Can bind a Ward-link to an ally and physically take hits aimed at them, the only job that redirects another target's incoming damage onto itself and reflects it.
- **Strengths:** Uniquely protects a chosen fragile ally; strong damage reflection; excellent peel and interrupt.
- **Weaknesses:** Little self-sufficient offense; Aegis dries up if no ally is warded; overwhelmed if forced to guard many at once.
- **Job Progression:** L1 Ward-Link + Aegis; L5 first intercept; L10 reaction Guardian's Debt; L15 second Ward-Link slot; L20 reflect burst; L25 signature; L30 mastery.
- **Job Mastery Bonus (Lvl 30):** Can maintain two Ward-Links simultaneously and reflected damage increases by 50%.
- **Signature Ability:** **Oathbound Wall** [60 Aegis / 40s] - for 6s, intercept every hit against all allies within 2 tiles and reflect 25% back. `[counter][support][area]`

**Ten Active Abilities:**
1. Ward-Link [10 MP / 8s] - bind an ally; you may intercept hits aimed at them. `[prep][support]`
2. Interpose [15 Aegis / 5s] - step in and take the next hit meant for your warded ally, reflecting 20%. `[counter][support][position]`
3. Guard Grant [12 MP / 10s] - give warded ally Guard 6s. `[buff][support]`
4. Retribution Plate [20 Aegis / 12s] - for 5s your blocks reflect an extra 30%. `[buff][counter]`
5. Shielding Step [15 MP / 14s] - dash to your ward and grant both of you Guard 4s. `[mobility][support][buff]`
6. Break the Blow [10 MP / 9s] - interrupt an enemy's cast targeting your ward. `[interrupt][support]`
7. Aegis Burst [30 Aegis / 18s] - project a shield absorbing damage on all allies within 2 tiles for 5s. `[buff][area][support]`
8. Warding Reproach [18 Aegis / 10s] - Mark and Weaken the enemy that last hit your ward. `[debuff][support]`
9. Longwatch Stance [8 MP / 20s] - gain Regen 8s and Aegis builds +50% for its duration. `[heal][resource]`
10. Reflected Judgment [40 Aegis / 25s] - release stored harm as a strike scaling with Aegis spent. `[damage][counter]`

**Five Passive Support Doctrines:**
- Longwatch - intercepting a hit reduces its damage to you by 20%.
- Bound Oath - warded allies take 10% less damage from all sources.
- Reflective Aegis - reflected damage +15%.
- Watchful Guard - MP regen +25% while an ally is warded.
- Shared Footing - when you gain Guard, your ward gains 2s of it too.

**Five Reaction Abilities:**
- Guardian's Debt [on warded ally being hit; 6s] - reflect 20% of that damage to the attacker. `[counter][support]`
- Oath Answer [on warded ally dropping below 30% HP; 20s] - instantly grant them Guard 4s and pull aggro. `[support][cc]`
- Bulwark Reflex [on being hit while shielding; 8s] - gain 8 Aegis. `[resource][counter]`
- Interrupt Vow [on enemy casting at your ward; 12s] - free interrupt. `[interrupt][support]`
- Standfast [on being Stunned; 25s] - reduce its duration 50% and keep intercepting. `[counter]`

**Three Movement Techniques:**
- Ward Rush [8s] - blink to your warded ally's side. `[mobility][support][position]`
- Cover Slide [12s] - slide into the path between ally and nearest enemy. `[mobility][position]`
- Oath Recall [16s] - teleport your ward and yourself 2 tiles back, cleansing Snare on both. `[mobility][support]`

**Secondary Job Synergies:**
- Vanguard: combine anchor-control with intercepts to fortify a static line.
- Duelist: add real single-target punish so you are not purely reactive.
- Berserker: borrow escalation to convert stored Aegis into meaningful kill pressure.

**Example Builds:**
- *Longwatch Guardian:* Sentinel / Vanguard, reaction Guardian's Debt, support Bound Oath, movement Ward Rush, signature Oathbound Wall; Polearm + Ward + Shield. Keeps a backline caster alive and punishes the focus.
- *Reflect Bruiser:* Sentinel / Berserker, reaction Bulwark Reflex, support Reflective Aegis, movement Cover Slide; Great Weapon + Heavy Plate + Totem. Banks Aegis, then unloads Reflected Judgment.

#### Berserker
- **Purpose:** Trade defense and safety for escalating, runaway offensive power.
- **Lore:** Berserkers took the pyre-vow: burn hot and burn now, for a life spent cautiously is a life half-lived. They welcome their own wounds as kindling, each cut stoking a fire that only death or victory can bank.
- **Combat Role:** A risk-engine glass cannon whose damage escalates the more punishment it takes and deals, punishing careful opponents by becoming more dangerous as the fight turns bloody, but risking self-destruction if the escalation is mismanaged.
- **Primary / Secondary Attributes:** STR, STA / SPD, LUCK.
- **Equipment Proficiencies:** Great Weapon, Blade, Thrown / Brigandine, Leather / Trinket, Kit.
- **Resource System:** HP (large but constantly spent). MP (minimal). **Fury** (0-100, "heat"): rises +5/tick while in melee and +extra when you take damage; at 70+ your damage ramps hard but you take +20% damage (overheat); Fury drains -3/tick out of combat. Spent by "venting" abilities that convert Fury into burst; if Fury pins at 100 for 3s straight you suffer Burn on yourself (the overheat punish).
- **Unique Identity:** Only job whose offensive output escalates with its own Fury heat and its own missing HP, deliberately courting danger to peak.
- **Strengths:** Highest raw escalation ceiling; damage grows as HP drops; strong self-sustain via lifesteal on kills.
- **Weaknesses:** Very fragile at high Fury (overheat vulnerability); no real CC or team support; self-damage risk if Fury is mismanaged.
- **Job Progression:** L1 Fury + first vent; L5 lifesteal strike; L10 reaction Bloodstoked; L15 overheat control tool; L20 low-HP escalation passive; L25 signature; L30 mastery.
- **Job Mastery Bonus (Lvl 30):** Overheat vulnerability drops to +10% and below 25% HP your damage gains an additional +30%.
- **Signature Ability:** **Pyre Vow** [80 Fury / 60s] - unleash a strike whose damage scales with Fury spent and missing HP; heals you for 30% of damage dealt. `[damage][heal]`

**Ten Active Abilities:**
1. Kindling Strike [0 / 3s] - basic melee that builds +10 Fury on hit. `[damage][resource]`
2. Reckless Cleave [20 Fury / 6s] - hit all adjacent foes; you take 5% self-damage. `[damage][area]`
3. Bloodletting Blow [15 Fury / 8s] - Bleed 6s; you heal for the Bleed you inflict. `[damage][heal][debuff]`
4. Vent Fury [40 Fury / 12s] - massive single strike, damage scales with current Fury; drains Fury to 20. `[damage][resource]`
5. Stoke the Fire [5 HP% / 15s] - spend 5% of current HP to gain 25 Fury instantly. `[resource][prep]`
6. Overhead Ruin [25 Fury / 10s] - heavy strike, Vulnerable 5s. `[damage][debuff]`
7. Frenzied Rush [10 Fury / 9s] - three fast hits; each adds 5 Fury. `[damage][resource]`
8. Last Ember [30 Fury / 20s] - damage doubled if you are below 30% HP. `[damage]`
9. Cauterize [20 Fury / 18s] - convert Fury to a burst self-heal of 15% HP; ends any Bleed on you. `[heal]`
10. Immolating Throw [15 Fury / 7s] - ranged Thrown strike, Burn 4s. `[damage][debuff]`

**Five Passive Support Doctrines:**
- Bloodheat - damage +1% per 3 Fury above 40.
- Wounded Beast - damage +25% while below 30% HP.
- Kindled Blood - 15% of damage dealt by Bleed heals you.
- Heat Tolerance - overheat vulnerability reduced from +20% to +15%.
- Pyre Momentum - kills refund 20 Fury and heal 8% HP.

**Five Reaction Abilities:**
- Bloodstoked [on taking damage; 4s] - gain Fury equal to 10% of damage taken. `[resource][counter]`
- Spite Swing [on dropping below 40% HP; 15s] - free heavy strike at the attacker. `[counter][damage]`
- Ember Guard [on Fury hitting 100; 20s] - convert the overheat Burn into a damage buff instead. `[counter][buff]`
- Death's Refusal [on a hit that would kill you; 90s] - survive at 1 HP and gain 50 Fury. `[counter]`
- Backdraft [on being interrupted; 12s] - deal Fury-scaled damage to the interrupter. `[counter][damage]`

**Three Movement Techniques:**
- Charging Roar [10s] - rush a target, building 15 Fury on arrival. `[mobility][resource]`
- Reckless Leap [14s] - leap 3 tiles to a spot, taking small self-damage. `[mobility]`
- Bloodscent Dash [12s] - dash to the lowest-HP enemy in range. `[mobility][position]`

**Secondary Job Synergies:**
- Duelist: pair single-target reads with escalation for an oppressive one-on-one killer.
- Sentinel: borrow one intercept/heal to survive long enough to peak Fury.
- Vanguard: use Snare/Root to pin foes in melee so Fury keeps climbing.

**Example Builds:**
- *Pyre-Vow Reaver:* Berserker / Duelist, reaction Bloodstoked, support Wounded Beast, movement Charging Roar, signature Pyre Vow; Great Weapon + Brigandine + Trinket. Snowballs Fury and missing HP into a single lethal strike.
- *Bleed Engine:* Berserker / Sentinel, reaction Death's Refusal, support Kindled Blood, movement Bloodscent Dash; Blade + Leather + Kit. Sustains through Bleed lifesteal while courting the low-HP damage band.
### Precision family

The Precision family turns positioning, patience, and probability into lethality: these jobs never
trade blows fairly, they arrange the fight so the enemy loses before the killing strike lands.
Every job here leans SPD (action rate, evasion) and LUCK (crit, proc), converting information and
setup into damage that heavy jobs cannot brute-force. Where a frontline job wants to be hit, a
Precision job wants to choose the ground, the moment, and the wound.

#### Ranger
- **Purpose:** Own a lane of the battlefield with sustained fire, layered traps, and area denial so the enemy fights on the Ranger's terms.
- **Lore:** The first Rangers were kiln-wardens who learned that a forge left unwatched becomes a wildfire, and that the same eye which reads a rising flame reads a charging line. They stake a piece of ground, seed it with snares and marked kill-lines, and let the field do half the killing. A Ranger measures a battle in yardage held, not blows struck.
- **Combat Role:** Ranged zone-controller. Sustained single-target and area pressure, terrain denial through traps, and reliable soft crowd control that shapes enemy movement rather than bursting it down.
- **Primary / Secondary Attributes:** SPD (fire rate + evasion) / LUCK (crit + trap proc).
- **Equipment Proficiencies:** Bow, Crossbow, Thrown, Sidearm / Leather, Brigandine, Rig / Kit, Trinket, Quiver-Buckler.
- **Resource System:** HP (moderate; survives on distance and evasion, not soak). MP (small pool fueling trap arming and marks; WIS regen). **Anchor** (0-100, a stationary tempo stack): +6/tick while the Ranger holds position and fires, +0 while moving; heavy shots and traps cost 20-40 Anchor. At 60+ Anchor, shots gain +1 tick of Bleed and traps arm 1s faster; decays 10/tick for 2s after any Movement technique. Standing still is the engine of the kit.
- **Unique Identity:** The only job whose power grows the longer it refuses to move, trading the safety of repositioning for escalating output on a chosen line.
- **Strengths:** Best-in-family sustained ranged pressure and area denial; traps convert prep into free damage and control; excellent at anchoring a chokepoint or objective.
- **Weaknesses:** Anchor collapses when forced to kite, gutting output on the move; weak burst; poor in cramped melee where distance and trap lines cannot form.
- **Job Progression:** L1 `Piercing Draw` + Anchor; L5 first trap (`Bramble Snare`), Reaction slot; L10 `Sighted Volley`, Movement slot; L15 Marks online (`Range Mark`); L20 signature `Killing Lane`; L25 traps pre-seedable out of combat (hold 2); L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Warden's Field:** While Anchor is above 60, all traps within the Ranger's line refresh 25% faster and marked targets take +15% ranged damage.
- **Signature Ability - Killing Lane:** Designate a straight corridor for 12s; enemies inside take escalating ranged damage each second they remain, and traps in the lane cannot be disarmed. `[damage][area][control]`

**Ten Active Abilities:**
1. `Piercing Draw [8 MP / 3s]` - single-target shot that applies Bleed on crit. `[damage][debuff]`
2. `Sighted Volley [14 MP / 8s]` - cone of arrows dealing area damage and applying Snare. `[damage][area][cc]`
3. `Bramble Snare [20 Anchor / 6s]` - arm a ground trap that Roots the first enemy to cross it. `[cc][prep][area]`
4. `Splitshot [12 MP / 5s]` - fire at two nearby targets, refunding 10 Anchor if both hit. `[damage][resource]`
5. `Range Mark [6 MP / 4s]` - mark a target Vulnerable for 10s, stacking up to 3. `[debuff][prep]`
6. `Concussion Bolt [16 MP / 12s]` - heavy shot that Stuns 1.5s and interrupts casting. `[damage][cc][interrupt]`
7. `Caltrop Line [24 Anchor / 10s]` - seed an area that applies Slow and Bleed to walkers. `[area][debuff][cc]`
8. `Steady Barrage [30 Anchor / 14s]` - channel 4s of rapid fire on a fixed arc, immobile. `[damage]`
9. `Pinning Shot [10 MP / 9s]` - shot that Snares and reduces target evasion for 6s. `[debuff][cc]`
10. `Reclaim Ordnance [0 / 20s]` - detonate all active traps early for burst area damage. `[area][damage][resource]`

**Five Passive Support Doctrines:**
- Rooted Aim - ranged crit chance rises the longer Anchor is held above 40.
- Field Discipline - traps cost 15% less Anchor and last 3s longer.
- Long Eye - damage increases with distance to target.
- Overwatch Instinct - first shot on any newly-arrived enemy always applies Mark.
- Salvage Kit - detonated or expired traps refund a portion of their MP.

**Five Reaction Abilities:**
- Snap Loose [on being struck in melee; 15s] - instantly fire a point-blank shot that Snares the attacker. `[counter][cc]`
- Held Ground [on losing 20% HP in 2s; 25s] - gain Guard and +30 Anchor for 4s. `[counter][resource]`
- Tripwire Reflex [when an enemy enters an armed trap; 8s] - the trap also applies Weaken. `[counter][debuff]`
- Counter-Volley [on being interrupted; 18s] - immediately loose an uninterruptible shot. `[counter][damage]`
- Break Contact [on being Rooted; 20s] - cleanse Root and drop a Snare where you stood. `[counter][cc]`

**Three Movement Techniques:**
- Sidestep Roll [6s] - short lateral dash that preserves 50% of current Anchor. `[mobility]`
- Vault Line [12s] - leap backward over a trap, arming it as you pass. `[mobility][prep]`
- Reset Ground [18s] - blink to any active trap's location and rebuild Anchor to 40. `[mobility][resource]`

**Secondary Job Synergies:**
- Saboteur: stacks toxin devices under trap lines for a compounding denial field.
- Scout: Scout marks feed Range Mark stacks, opening with maximum Vulnerable applied.

**Example Builds:**
- *Chokepoint Warden:* max STA/WIS gear, Steady Barrage + Killing Lane + Caltrop Line to hold a doorway indefinitely.
- *Marksman Anchor:* LUCK/SPD stacking, Rooted Aim + Long Eye + Range Mark for high-crit sustained single-target from max range.

#### Scout
- **Purpose:** Read the enemy, expose its weaknesses, and reposition the entire fight so allies strike where it hurts.
- **Lore:** Scouts trace their craft to the trailblazers who mapped the Spiral's first floors, learning that the one who sees the room first never dies in it. They fight as living lenses: they name a foe's flaw aloud so the whole party can aim at it, then vanish to the next vantage before a blade finds them. A Scout's deadliest weapon is a shared truth about the enemy.
- **Combat Role:** Information and mobility specialist. Debuff-application and target-priority control, hyper-mobile skirmishing, and force-multiplier support that raises the whole party's accuracy against a marked foe.
- **Primary / Secondary Attributes:** SPD (action rate + evasion) / WIS (resource regen + support potency).
- **Equipment Proficiencies:** Blade, Bow, Thrown, Sidearm / Leather, Cloth/Robe, Rig / Trinket, Kit, Buckler.
- **Resource System:** HP (low-moderate; relies on evasion and never being where the enemy expects). MP (moderate; powers scans and exploit strikes, WIS regen). **Intel** (0-10 stacks): +1 per scan, per flank strike (rear arc), and per Movement technique used; exploit abilities consume 1-3 stacks for amplified debuffs, support abilities convert stacks into party buffs. Stacks do not decay in combat but reset to 0 on death. Intel rewards constant motion and angle, the opposite of the Ranger's stillness.
- **Unique Identity:** The only Precision job whose resource is generated by repositioning and information rather than by dealing damage, making mobility itself the fuel for everything the Scout does.
- **Strengths:** Unmatched mobility and disengage, dictates the fight's geometry; turns the whole party into precision damage against a marked target; reveals enemy weaknesses for the team.
- **Weaknesses:** Very low personal burst; fragile; Intel resets on death, so a single mistake wipes accumulated setup.
- **Job Progression:** L1 `Read Foe` + Intel; L5 `Flank Cut` + rear-arc bonus, Reaction slot; L10 `Call the Weakness`, Movement slot; L15 scans reveal cast bars and resistances to party; L20 signature `Perfect Read`; L25 Intel cap 12, Movement refunds Intel; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Total Vantage:** While holding 6+ Intel, the Scout and nearby allies gain +10% crit against the Scout's marked target, and the mark cannot be cleansed.
- **Signature Ability - Perfect Read:** Instantly reveal a target's lowest resistance and apply matching Vulnerable for 15s; the next ally hit of that type is guaranteed to crit. `[debuff][support][synergy]`

**Ten Active Abilities:**
1. `Read Foe [6 MP / 4s]` - scan a target to reveal HP, cast state, grant 1 Intel. `[support][resource][prep]`
2. `Flank Cut [8 MP / 3s]` - strike that deals bonus damage and +1 Intel from the rear arc. `[damage][resource][position]`
3. `Call the Weakness [2 Intel / 8s]` - mark a target Vulnerable to the whole party for 12s. `[debuff][support][synergy]`
4. `Expose Gap [1 Intel / 6s]` - apply Weaken and reduce the target's evasion for 8s. `[debuff][cc]`
5. `Ghost Step Strike [10 MP / 9s]` - blink behind a target and hit, always counting as rear arc. `[damage][mobility][position]`
6. `Signal Flare [12 MP / 14s]` - Blind a target and reveal all enemies in the area to allies. `[cc][support][area]`
7. `Pressure Point [3 Intel / 12s]` - high-damage strike scaling with the target's active debuffs. `[damage][synergy]`
8. `Rally Read [2 Intel / 20s]` - grant nearby allies Haste and +accuracy for 8s. `[buff][support][area]`
9. `Disrupting Throw [10 MP / 10s]` - thrown blade that Silences 2s and grants 1 Intel. `[interrupt][cc][resource]`
10. `Vanishing Cut [1 Intel / 16s]` - strike then break line of sight, dropping enemy target lock. `[damage][mobility][position]`

**Five Passive Support Doctrines:**
- Trailsense - gain 1 Intel the first time each enemy is struck.
- Shared Sightline - the Scout's marks also grant allies vision of the target through cover.
- Light Footing - evasion rises for 3s after any Movement technique.
- Analyst's Edge - exploit abilities cost 1 less Intel when the target has 2+ debuffs.
- Momentum Reader - action rate increases slightly per stack of Intel held.

**Five Reaction Abilities:**
- Slip the Blow [on being targeted by a melee hit; 12s] - raise evasion sharply for 1.5s and gain 1 Intel. `[counter][resource]`
- Counter-Read [on an enemy beginning a cast; 15s] - reveal the cast to allies and reduce its target's resistance. `[counter][support]`
- Escape Note [on dropping below 30% HP; 25s] - blink to the nearest ally and drop enemy target lock. `[counter][mobility]`
- Opportune Mark [when an ally crits your marked target; 8s] - refund 1 Intel and refresh the mark. `[resource][synergy]`
- Reflex Scan [on being flanked; 10s] - instantly Read the attacker and gain evasion. `[counter][resource]`

**Three Movement Techniques:**
- Dart Line [5s] - fast dash that grants 1 Intel on arrival. `[mobility][resource]`
- Wall Vantage [12s] - leap to elevated cover, granting party vision and 2 Intel. `[mobility][support]`
- Fade Route [18s] - untargetable sprint for 1.5s, dropping all enemy locks. `[mobility][counter]`

**Secondary Job Synergies:**
- Shadowblade: Scout mobility and marks set up the assassin's opener.
- Ranger: Scout marks stack Range Marks and Signal Flare denies the enemy the eyes to counter a held lane.

**Example Builds:**
- *Party Lens:* WIS/SPD support gear, Call the Weakness + Rally Read + Perfect Read to multiply an entire group's damage.
- *Skirmish Reader:* SPD/LUCK evasion stacking, Ghost Step Strike + Pressure Point + Fade Route for a self-sufficient flanking harasser.

#### Shadowblade
- **Purpose:** Convert stealth and setup into one overwhelming lethal opening, then survive the aftermath long enough to do it again.
- **Lore:** Shadowblades are said to have learned their art from the gaps between torchlight, where a patient hand can end a thing before it knows it is threatened. They stalk the edge of a fight, feeding on darkness until a single strike carries the weight of every unspent second. To a Shadowblade, the perfect kill is the one the target never saw begin.
- **Combat Role:** Burst assassin. Explosive single-target opener from concealment, execute-range finishers, and a high-risk reset loop that trades sustained output for one decisive window.
- **Primary / Secondary Attributes:** LUCK (crit + proc) / SPD (action rate + evasion).
- **Equipment Proficiencies:** Blade, Fist, Thrown, Sidearm / Leather, Cloth/Robe, Rig / Trinket, Buckler, Kit.
- **Resource System:** HP (low; everything is staked on the opener). MP (small; powers stealth entries and finishers, WIS regen). **Shade** (0-100, a concealment charge): +8/tick while stealthed or unseen, +3/tick while out of the enemy's front arc, +0 while openly engaged; openers and finishers consume 40-100 Shade for burst multipliers. At 100 Shade the next opener is guaranteed to crit; taking damage drains 25 Shade instantly. Shade rewards patience and punishes exposure.
- **Unique Identity:** The only job that stores its damage as a spendable stealth charge, so a Shadowblade's power is measured by how much darkness it banked before the strike, not by a sustained rotation.
- **Strengths:** Highest single-target burst in the family from a full Shade opener; reliable executes; strong self-repositioning to re-enter stealth and reset the loop.
- **Weaknesses:** Extremely fragile once Shade is spent and stealth is broken; damage cliffs in sustained fights; telegraphed to alert enemies who can pre-empt the opener.
- **Job Progression:** L1 `Slip Into Dark` + Shade; L5 `Opening Cut`, Reaction slot; L10 `Sever` execute, Movement slot; L15 re-stealth via `Smoke Fold`; L20 signature `Killing Moment`; L25 openers apply Vulnerable; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Perfect Shadow:** Spending a full 100 Shade opener refunds 40 Shade and refreshes one Movement technique.
- **Signature Ability - Killing Moment:** From stealth, strike for massive burst scaling with current Shade; if the hit reduces the target below 30% HP, immediately execute it. `[damage]`

**Ten Active Abilities:**
1. `Slip Into Dark [12 MP / 20s]` - enter stealth for 6s, rapidly generating Shade. `[prep][resource][position]`
2. `Opening Cut [40 Shade / 3s]` - stealth-only strike dealing heavy burst and applying Bleed. `[damage][debuff]`
3. `Sever [10 MP / 8s]` - finisher dealing bonus damage scaling inversely with target HP. `[damage]`
4. `Shadow Flurry [30 Shade / 6s]` - rapid multi-hit that builds Bleed stacks. `[damage][debuff]`
5. `Throat Line [60 Shade / 14s]` - Silence and heavy damage from concealment. `[damage][cc][interrupt]`
6. `Nightbrand [8 MP / 5s]` - apply Mark that increases all your damage to the target for 8s. `[debuff][prep]`
7. `Backstep Cut [10 MP / 9s]` - strike then dash out of the front arc, gaining 20 Shade. `[damage][mobility][resource]`
8. `Veil Toss [12 MP / 16s]` - throw a smoke cloud that Blinds enemies in an area. `[cc][area]`
9. `Exsanguinate [20 Shade / 12s]` - detonate all Bleed stacks on a target for burst damage. `[damage][synergy]`
10. `Ghost Reset [0 / 25s]` - break target lock and gain 30 Shade if not seen for 2s. `[resource][position][mobility]`

**Five Passive Support Doctrines:**
- Dusk Affinity - Shade generation rises while below 50% HP.
- First Cut Deepest - openers from full Shade cannot be dodged.
- Bleedcraft - Bleed applied by this job stacks one higher and ticks faster.
- Silent Tread - entering stealth is 3s faster if no enemy is in the front arc.
- Executioner's Eye - finisher execute threshold rises to 35% against marked targets.

**Five Reaction Abilities:**
- Fade on Contact [on being struck while stealthed; 18s] - preserve stealth and lose only 10 Shade instead of breaking. `[counter]`
- Riposte Nick [on dodging a melee attack; 10s] - counter with a Bleed-applying strike. `[counter][damage]`
- Death's Refusal [on dropping below 20% HP; 30s] - blink to safety and enter stealth for 2s. `[counter][mobility]`
- Shadow Recoil [on being interrupted; 15s] - gain 25 Shade and immunity to the next interrupt. `[counter][resource]`
- Opening Instinct [when a nearby enemy begins casting; 12s] - next Opening Cut against it also Silences. `[counter][interrupt]`

**Three Movement Techniques:**
- Dark Dash [6s] - short blink that stays out of enemy front arcs on arrival. `[mobility][position]`
- Smoke Fold [16s] - vanish and re-emerge up to a lane away, generating 30 Shade. `[mobility][resource]`
- Wall Shadow [12s] - cling to cover for 2s, untargetable and banking Shade rapidly. `[mobility][resource]`

**Secondary Job Synergies:**
- Scout: Scout marks and vantage set up a guaranteed-crit opener.
- Saboteur: pre-applied toxins let Exsanguinate and finishers detonate a stacked debuff for lethal combined burst.

**Example Builds:**
- *One-Cut Assassin:* LUCK-max crit gear, Slip Into Dark + Killing Moment + Ghost Reset for a delete-and-vanish loop against priority targets.
- *Bleed Reaper:* Bleedcraft + Shadow Flurry + Exsanguinate, converting sustained Bleed into detonation bursts when re-stealth is impossible.

#### Saboteur
- **Purpose:** Win the slow war through layered toxins, mechanical devices, and area denial that grind an enemy down before it can close the distance.
- **Lore:** Saboteurs are the ship's quiet engineers of misfortune, brewers and tinkerers who decided the best defense is a battlefield that fights for you. They read a fight like a failing machine, finding the one bolt to loosen, the one dose to administer, so that the enemy's own momentum becomes the thing that kills it. A Saboteur rarely lands the final blow, because by then the poison already has.
- **Combat Role:** Trap and toxin engineer. Damage-over-time stacking, sustained debuff and crowd control, and mechanical area denial that punishes movement and rewards patience over burst.
- **Primary / Secondary Attributes:** LUCK (proc + crit on toxin ticks) / WIS (resource regen + debuff potency).
- **Equipment Proficiencies:** Crossbow, Thrown, Sidearm, Fist / Brigandine, Leather, Rig / Kit, Trinket, Totem.
- **Resource System:** HP (moderate; outlasts rather than out-tanks). MP (moderate; powers device arming and dispersal, WIS regen). **Doses** (0-8 charges, a prepared toxin economy): +1 every 3s passively (WIS shortens the interval), +1 when a device is triggered by an enemy; toxins and devices consume 1-3 Doses. Doses do not decay but cap at 8, so the Saboteur must spend to keep brewing. Unlike the Ranger's positional Anchor, Doses accrue by time and denial, not by stillness or motion.
- **Unique Identity:** The only job that banks pre-brewed charges over time and spends them to reshape the ground, making the Saboteur a slow-burn controller whose strongest moment is the one it prepared for minutes earlier.
- **Strengths:** Deepest debuff and damage-over-time stacking in the family; devices deny terrain without direct risk; excellent sustained attrition against tanky targets.
- **Weaknesses:** Almost no burst; weak against fast, high-mobility foes; setup-dependent, thin when caught unprepared.
- **Job Progression:** L1 `Coat Blade` + Doses; L5 first device (`Snare Charge`), Reaction slot; L10 `Corrode`, Movement slot; L15 toxins can layer; L20 signature `Cascade Failure`; L25 devices pre-armable out of combat (hold 3); L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Compounding Rot:** Every distinct debuff on a target amplifies all others by 5% each, so a fully layered victim decays faster the more the Saboteur has stacked.
- **Signature Ability - Cascade Failure:** Detonate every debuff and device on a target at once, converting remaining toxin duration into immediate area damage and applying Weaken to nearby enemies. `[damage][area][debuff][synergy]`

**Ten Active Abilities:**
1. `Coat Blade [1 Dose / 2s]` - next 3 strikes apply a stacking Bleed toxin. `[damage][debuff][prep]`
2. `Snare Charge [2 Doses / 8s]` - arm a device that Roots and applies Slow when triggered. `[cc][prep][area]`
3. `Corrode [1 Dose / 6s]` - apply Vulnerable and reduce target armor for 10s. `[debuff]`
4. `Nausea Draft [2 Doses / 12s]` - thrown flask that applies Weaken and Blind in an area. `[cc][debuff][area]`
5. `Creeping Toxin [1 Dose / 5s]` - apply a spreading poison that jumps to a nearby enemy on tick. `[damage][debuff][area]`
6. `Shock Mine [3 Doses / 16s]` - device that Stuns and applies Shock to the first target in range. `[cc][interrupt][prep]`
7. `Solvent Cloud [2 Doses / 14s]` - area that steadily strips buffs and applies Snare. `[debuff][cc][area]`
8. `Purge Vial [1 Dose / 9s]` - detonate one toxin on the target for burst plus refresh the rest. `[damage][synergy]`
9. `Rig Tripwire [2 Doses / 10s]` - connect two devices so triggering one arms the other. `[prep][synergy][area]`
10. `Slow Kill [0 / 20s]` - amplify all damage-over-time on a target by 40% for 6s. `[debuff][synergy]`

**Five Passive Support Doctrines:**
- Steady Hand - Doses generate 1s faster and toxins last 3s longer.
- Layered Chemistry - each distinct debuff on a target adds a small crit chance to your toxin ticks.
- Field Engineer - devices cost 1 less Dose and arm 1s faster.
- Residue - expired toxins leave a lingering ground hazard for 4s.
- Measured Doses - at 6+ Doses banked, all applied debuffs gain +1 stack.

**Five Reaction Abilities:**
- Reflex Coat [on being struck in melee; 12s] - the attacker is coated with a Bleed toxin. `[counter][debuff]`
- Backup Charge [when a device is destroyed; 15s] - instantly refund its Doses and arm a Snare Charge nearby. `[counter][resource]`
- Chemical Guard [on dropping below 30% HP; 25s] - release a Blind cloud and gain Guard for 3s. `[counter][cc]`
- Counter-Brew [on being Silenced; 18s] - cleanse and apply Silence back to the source. `[counter][cc]`
- Trigger Discipline [when an enemy enters a device; 8s] - that device also applies Corrode. `[counter][debuff]`

**Three Movement Techniques:**
- Slip Away [7s] - short dash that drops a Slow toxin cloud where you stood. `[mobility][area]`
- Relocate Rig [14s] - blink to any active device and re-arm it with a fresh stack. `[mobility][prep]`
- Foul Retreat [18s] - sprint back through a Solvent Cloud, gaining 2 Doses. `[mobility][resource]`

**Secondary Job Synergies:**
- Ranger: device fields nested under trap lines create a compounding kill-zone no fast approach survives.
- Shadowblade: pre-stacked toxins make Exsanguinate and finishers detonate for lethal combined burst.

**Example Builds:**
- *Attrition Warden:* WIS/STA gear, Creeping Toxin + Corrode + Cascade Failure to melt tanky targets over a long fight.
- *Denial Engineer:* LUCK/WIS device build, Snare Charge + Rig Tripwire + Shock Mine to lock down a chokepoint and punish every crossing.
### Arcane family

The Arcane family channels raw magic through disciplined economy: each job runs its own custom
pool that rewards preparation, timing, and battlefield reading over button-mashing. They lean MAG
(spell power and MP) and WIS (regen, resistance, support), favoring Focus implements, Robes, and
Wards, but no two of them spend their power the same way. Master one and you learn burst windows,
terrain control, tempo, or command, four different answers to the question "what does a caster do
between ticks?"

#### Arcanist
- **Purpose:** A precision spell-weaver who hoards and detonates its own cast economy for scheduled burst windows.
- **Lore:** The first Arcanists were archivists who learned that a spell half-spoken is not wasted but banked, its syllables coiling in the air like a held breath. They call the discipline Cadence: the art of stacking incantations until the moment they resolve as one. An Arcanist who loses count of their own rhythm is just a loud librarian.
- **Combat Role:** Ranged nuke controller. Builds pressure quietly, then unloads a scripted burst chain in a 3-5 second window.
- **Primary / Secondary Attributes:** Magic (MAG) / Wisdom (WIS).
- **Equipment Proficiencies:** Focus, Sidearm, Thrown (glyph-stones) / Cloth/Robe, Ward / Trinket, Kit.
- **Resource System:** HP (low; squishy back-liner). MP (high, MAG-scaled; WIS regen). **Resonance** (0-100): every completed cast adds Resonance (bigger casts add more); passive +2/tick out of channel. Burst finishers consume Resonance for scaling damage; at 100 the next finisher gains a free critical. Above 90 Resonance the Arcanist gains +1 stack of self-Haste but bleeds 1 Resonance/tick (overflow decay), pushing you to spend or lose it.
- **Unique Identity:** The only Arcane job that treats casting as a savings account: slow, deliberate prep followed by a detonation that other jobs cannot match in a single window.
- **Strengths:** Highest single-window burst damage in the family; self-sufficient Haste ramp from Resonance overflow; long-range safety and pre-cast setup.
- **Weaknesses:** Very low HP, punished hard if the burst window is interrupted; ramp-dependent, weak early; Resonance decays if unspent, so idle time is actively costly.
- **Job Progression:** L1 Resonance + `Splinter Bolt`; L5 finisher `Detonate Cadence`; L10 overflow Haste ramp; L15 cast times reduced 15% while above 50 Resonance; L20 finishers stop breaking your own channels; L25 `Detonate Cadence` gains area splash at full Resonance; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Perfect Cadence:** spending 100 Resonance in one finisher refunds 40 Resonance and grants 3s of uninterruptible casting.
- **Signature Ability - Grand Recital:** channel 4s, then unleash a Resonance-scaled multi-hit barrage across the front line; consumes all Resonance, damage scales per point spent. `[damage][area][synergy]`

**Ten Active Abilities:**
1. `Splinter Bolt [8 MP / 0s; cast 1.5s]` - core nuke, +6 Resonance on completion. `[damage][resource]`
2. `Detonate Cadence [15 MP / 4s; instant]` - consume up to 60 Resonance for scaling burst on one target. `[damage]`
3. `Glyphmark [12 MP / 6s; cast 1s]` - apply Mark; your next 3 casts against it deal bonus damage. `[debuff][prep]`
4. `Static Weave [10 MP / 8s; cast 2s]` - Shock + Vulnerable on target for 6s. `[debuff][cc]`
5. `Silencing Verse [18 MP / 20s; cast 1s]` - Silence one caster for 3s. `[interrupt][cc]`
6. `Resonant Font [20 MP / 30s; instant]` - instantly bank +40 Resonance, then no passive gen for 4s. `[resource][prep]`
7. `Arc Cascade [22 MP / 12s; cast 2.5s]` - chained bolt hitting up to 3 targets; +4 Resonance per hit. `[damage][area][resource]`
8. `Warding Syllable [14 MP / 18s; instant]` - self Guard for 5s, reduces cast-interrupt chance. `[buff][counter]`
9. `Overload Lens [16 MP / 25s; instant]` - next cast within 5s cannot be interrupted and gains +25% power. `[buff][prep]`
10. `Null Pulse [25 MP / 45s; cast 1s]` - area Weaken + strip one enemy buff in a small radius. `[debuff][area][cc]`

**Five Passive Support Doctrines:**
- Held Breath - Resonance decays 50% slower during enemy stun on you.
- Archivist's Ear - +10% damage to Marked targets.
- Deep Pool - +15% max MP.
- Steady Hand - taking damage below 10% max HP does not interrupt casts.
- Compounding Rhythm - every 3rd consecutive completed cast grants +5 bonus Resonance.

**Five Reaction Abilities:**
- `Counterspell Snap [enemy begins hostile cast; 20s]` - interrupt it and bank +15 Resonance. `[interrupt][counter]`
- `Feedback Ward [interrupted while casting; 30s]` - reflect Silence back onto the interrupter (2s). `[counter][cc]`
- `Reflex Splinter [struck in melee; 12s]` - free instant Splinter Bolt at the attacker. `[damage][counter]`
- `Cadence Guard [HP below 25%; 60s]` - gain Guard 4s and +30 Resonance. `[buff][counter]`
- `Echo Refund [your finisher kills a target; 10s]` - refund 25 Resonance. `[resource]`

**Three Movement Techniques:**
- `Phase Step [10s]` - short blink, keeps channel if under Overload Lens. `[mobility]`
- `Drift Cast [15s]` - next cast may be performed while moving one step. `[mobility][position]`
- `Recoil Glide [8s]` - hop back one tile after a finisher, gaining 2s Haste. `[mobility][position]`

**Secondary Job Synergies:**
- Chronomancer: borrow Haste/scheduling to hit burst windows more often.
- Elementalist: terrain control buys the safe seconds an Arcanist needs to ramp.

**Example Builds:**
- *Detonation Sniper:* Arcanist / Chronomancer; stack MAG, run Overload Lens into Grand Recital during a Haste window.
- *Marked Executioner:* Arcanist; Glyphmark a priority target, ramp Resonance, delete it with `Detonate Cadence` + Perfect Cadence refund.

#### Elementalist
- **Purpose:** A battlefield controller who reshapes terrain and space with persistent elemental zones, swapping schools on the fly.
- **Lore:** Elementalists do not throw fire; they teach a room to burn. Their tradition holds that the world is four tempers waiting to be argued with, and mastery is knowing which temper the ground already wants. A veteran leaves a fight looking like the terrain itself changed sides.
- **Combat Role:** Area-denial controller. Wins through zones, terrain effects, and forced positioning rather than single-target damage.
- **Primary / Secondary Attributes:** Magic (MAG) / Wisdom (WIS).
- **Equipment Proficiencies:** Focus, Totem, Thrown / Cloth/Robe, Ward, Leather / Totem, Trinket.
- **Resource System:** HP (low-medium). MP (high; MAG-scaled, WIS regen). **Attunement** (Ember / Frost / Gale / Stone, a 4-way dial): casting a school's spell fills that school's segment (+10) and drains the opposite (-5); passive slow drift toward neutral. Zones cost the attuned school's segment to place and sustain; an active zone drains 2 of its school's Attunement per tick; a fully-attuned school (100) makes its zones 30% larger.
- **Unique Identity:** The only job that spends its pool into the environment: its power lives on the map as lingering zones, not on a target's health bar.
- **Strengths:** Best area control and terrain denial in the family; flexible school-swapping answers many damage types; zones persist without concentration, freeing casts.
- **Weaknesses:** Weak raw single-target burst; zones are stationary; overspending one temper starves its opposite.
- **Job Progression:** L1 Attunement + `Ember Font`; L5 Frost and Gale; L10 Stone (all four); L15 zones persist +3s; L20 overlapping different-school zones create Fusion effects; L25 zone placement range +50%; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Living Terrain:** one zone per fight becomes permanent (no per-tick drain) and follows a target you Mark.
- **Signature Ability - Fourfold Convergence:** channel 5s, then drop all four elemental zones stacked on one area, creating a Fusion maelstrom (Burn + Chill + Shock + Root pulses). `[area][cc][debuff][synergy]`

**Ten Active Abilities:**
1. `Ember Font [18 MP / 6s; cast 2s]` - place a Burn zone; enemies inside take DoT. `[damage][area]`
2. `Frost Field [18 MP / 6s; cast 2s]` - place a Chill zone; enemies inside get Slow. `[cc][area]`
3. `Gale Corridor [16 MP / 8s; cast 2s]` - place a wind lane that pushes enemies one tile per tick. `[cc][area][position]`
4. `Stone Wall [20 MP / 14s; cast 1.5s]` - raise blocking terrain for 8s, splitting the field. `[area][position]`
5. `Cinder Lash [10 MP / 3s; cast 1s]` - single-target Burn, fills Ember +10. `[damage][resource]`
6. `Rimeshard [10 MP / 3s; cast 1s]` - single-target Chill, fills Frost +10. `[cc][resource]`
7. `Static Front [22 MP / 12s; cast 2.5s]` - moving Shock zone that drifts toward nearest enemy. `[damage][area][cc]`
8. `Tremor Snare [16 MP / 10s; cast 1s]` - Root all enemies on Stone-attuned terrain for 2s. `[cc][area]`
9. `Temper Swap [6 MP / 4s; instant]` - instantly shift 20 Attunement between two chosen schools. `[resource][prep]`
10. `Elemental Veil [20 MP / 25s; instant]` - self + allies in a zone gain resistance matched to that zone's school for 6s. `[buff][support][area]`

**Five Passive Support Doctrines:**
- Rooted Practice - your own zones grant you Guard while you stand in them.
- Temper Reading - +15% zone size on terrain matching your highest Attunement.
- Slow Burn - zone DoTs tick 10% harder each second they persist (cap 3s).
- Weathered - +10% resistance to Burn/Chill/Shock/Root.
- Fusion Sense - overlapping-zone Fusions cost no extra Attunement.

**Five Reaction Abilities:**
- `Backdraft [enemy enters your Burn zone; 8s]` - small knockback + refresh the zone. `[cc][counter][area]`
- `Frostbite Guard [struck in melee; 15s]` - Chill the attacker 3s. `[cc][counter]`
- `Grounding [hit by Shock; 20s]` - convert it to Stone Attunement +25, no damage taken. `[counter][resource]`
- `Gale Answer [enemy dashes toward you; 18s]` - Gale-push them back one tile. `[cc][counter][position]`
- `Terrain Recall [your zone is dispelled; 30s]` - re-place a weaker copy for free. `[counter][area]`

**Three Movement Techniques:**
- `Ash Stride [10s]` - dash through your own Burn zone, leaving a trailing flame line. `[mobility][area]`
- `Glide on Gale [12s]` - ride a Gale Corridor two tiles instantly. `[mobility][position]`
- `Stone Anchor [20s]` - become immovable (immune to displacement) for 4s. `[position][counter]`

**Secondary Job Synergies:**
- Summoner: summons hold ground inside zones, converting area denial into a killbox.
- Chronomancer: Slow fields plus tempo debuffs make zones near-inescapable.

**Example Builds:**
- *Zone Tyrant:* Elementalist / Summoner; Stone Wall + Frost Field funnel enemies onto a summon.
- *Fusion Bomber:* Elementalist; ramp two opposing schools, overlap for Fusion, cap with Fourfold Convergence.

#### Chronomancer
- **Purpose:** A tempo manipulator who bends real-time speed and schedules delayed effects to control the fight's cadence.
- **Lore:** Chronomancers do not stop time, a heresy their order punishes; they negotiate with it, borrowing seconds here to repay them there. Their signature is the delayed strike: a spell spoken now that resolves later, planted like a mine in the flow of the fight. To duel one is to fight an opponent who always seems to move exactly one beat sooner than you.
- **Combat Role:** Tempo support-controller. Manipulates Haste, Slow, cooldowns, and delayed detonations to warp the pace of allies and enemies.
- **Primary / Secondary Attributes:** Wisdom (WIS) / Magic (MAG).
- **Equipment Proficiencies:** Focus, Instrument, Sidearm / Cloth/Robe, Ward / Trinket, Kit.
- **Resource System:** HP (medium). MP (high; WIS-scaled regen is strong). **Echo Bank** (0-8 charges, a store of scheduled seconds): applying Haste or Slow banks +1 Echo; a completed cast banks +1 (cap 8). Delayed-effect abilities cost Echoes to schedule a later resolution; Echoes can reduce an ally ability's cooldown. A "primed" delayed spell counts down 1s/tick and resolves automatically when its timer hits zero, even if you are stunned.
- **Unique Identity:** The only job whose power lands on a delay: it plants scheduled effects and adjusts everyone's cadence, playing the clock instead of the target.
- **Strengths:** Unmatched tempo control (team Haste, enemy Slow, cooldown reduction); delayed effects resolve through your own crowd control; strong sustain via high WIS regen.
- **Weaknesses:** Low immediate damage, power is always "later"; Echo Bank is fragile to burst; setup-heavy, mistimed schedules waste Echoes.
- **Job Progression:** L1 Echo Bank + `Delayed Bolt`; L5 team Haste `Quicken`; L10 cooldown-reduction spend on allies; L15 primed effects resolve through your own Stun/Silence; L20 Echo cap 6 to 8, Haste stacks to 2; L25 delayed spells can be re-primed once; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Borrowed Beat:** once per fight, instantly reset the cooldowns of all abilities on one ally by spending 4 Echoes.
- **Signature Ability - Convergent Hour:** channel 3s to prime a field detonation that resolves in 4s, dealing area damage scaled by every Echo banked and applying Slow. `[damage][area][cc][prep]`

**Ten Active Abilities:**
1. `Delayed Bolt [10 MP / 2s; cast 1s]` - prime a bolt that resolves in 3s; +1 Echo. `[damage][prep][resource]`
2. `Quicken [16 MP / 12s; cast 1s]` - grant an ally Haste 6s; +1 Echo. `[buff][support][resource]`
3. `Drag [14 MP / 8s; cast 1s]` - Slow one enemy 5s; +1 Echo. `[debuff][cc][resource]`
4. `Rewind Wound [20 MP / 25s; cast 2s]` - schedule a heal that resolves in 3s, healing missing HP over that window. `[heal][prep][support]`
5. `Stutter Field [22 MP / 18s; cast 2.5s]` - area intermittent Snare (pulses every other tick) for 6s. `[cc][area]`
6. `Timeslip [18 MP / 30s; instant]` - spend 2 Echoes to cut one ally ability's cooldown by 10s. `[support][resource]`
7. `Primed Detonation [12 MP / 6s; instant]` - resolve one of your primed effects immediately. `[damage][synergy]`
8. `Second Wind Loop [24 MP / 40s; cast 1.5s]` - ally gains Regen 8s; when it ends, Regen re-applies once at half strength. `[heal][buff][support]`
9. `Lag Spike [20 MP / 22s; cast 1s]` - Silence + Slow one enemy caster for 3s. `[interrupt][cc][debuff]`
10. `Overclock [26 MP / 60s; cast 1s]` - spend 4 Echoes: party-wide Haste 5s. `[buff][area][support][resource]`

**Five Passive Support Doctrines:**
- Steady Metronome - +20% MP regen while any effect is primed.
- Anticipation - your Haste buffs also grant +5% resistance.
- Debt Collector - Slowed enemies take +8% damage from your primed effects.
- Persistence of Timing - primed effects are immune to dispel.
- Efficient Scheduling - every 4th Echo banked is doubled (+2).

**Five Reaction Abilities:**
- `Rewind Step [HP below 30%; 45s]` - restore HP to its value 3s ago (banked snapshot). `[heal][counter]`
- `Preempt [enemy begins hostile cast; 18s]` - Slow them, adding 1s to their cast. `[interrupt][cc][counter]`
- `Echo Ripple [ally ability goes on cooldown near you; 10s]` - shave 2s off it. `[support][counter]`
- `Deja Strike [your primed effect resolves; 8s]` - re-prime a free half-power copy. `[damage][counter][synergy]`
- `Buffer [struck by a Stun; 60s]` - the Stun is delayed 2s instead of applying now. `[counter][cc]`

**Three Movement Techniques:**
- `Skip Beat [8s]` - blink one tile and gain 2s Haste; +1 Echo. `[mobility][resource]`
- `Slipstream [14s]` - move at Haste speed for 4s, ignoring Snare. `[mobility][counter]`
- `Recall Position [25s]` - return to where you stood 4s ago. `[mobility][position]`

**Secondary Job Synergies:**
- Arcanist: feed Haste and cooldown resets into the Arcanist's burst windows for repeated detonations.
- Summoner: Haste your summons and reduce their upkeep drain via faster cycles.

**Example Builds:**
- *Tempo Anchor:* Chronomancer / Arcanist; chain Overclock into an ally's burst, then Borrowed Beat to do it twice.
- *Delay Warden:* Chronomancer; stack primed detonations behind Stutter Field, resolve them all with Convergent Hour.

#### Summoner
- **Purpose:** A commander who fields persistent summoned entities and manages their upkeep as its core economy.
- **Lore:** Summoners bind not creatures but agreements: each Effigy is a pact that lasts exactly as long as the Summoner keeps paying its price. The old teachers say a Summoner alone is only half a fighter, and half a fool, the other half is always on the field, listening. A great one commands like a conductor, and dies the instant the music stops.
- **Combat Role:** Pet commander. Wins through persistent summons providing damage, tanking, and utility, at the cost of constant upkeep management.
- **Primary / Secondary Attributes:** Magic (MAG) / Wisdom (WIS).
- **Equipment Proficiencies:** Focus, Totem, Instrument / Cloth/Robe, Ward, Brigandine / Totem, Trinket.
- **Resource System:** HP (medium). MP (high; MAG-scaled, WIS regen). **Pact Reserve** (0-100, the upkeep pool): passive +4/tick; +10 when a summon lands a kill. Summoning costs a lump of Pact; each active summon drains upkeep per tick. If Pact Reserve hits 0, the newest summon is dismissed. Overloading yourself with too many Effigies is the core risk.
- **Unique Identity:** The only job that fights through delegated bodies: its damage and durability live in persistent summons it must continuously fund or lose.
- **Strengths:** Persistent multi-body pressure, hard to fully shut down; flexible summon roster covers tank, damage, and utility; strong action economy.
- **Weaknesses:** Fragile if pets are killed faster than they can be re-summoned; upkeep drain punishes greedy over-summoning; ramp time, an empty field means near-zero output.
- **Job Progression:** L1 Pact Reserve + `Cinder Hound`; L5 `Bulwark Effigy`; L10 `Mending Wisp`; L15 field cap 2; L20 summons inherit 10% resistances, upkeep -15%; L25 field cap 3, summon command abilities; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Unbroken Pact:** once per fight, all active summons become upkeep-free and gain Haste for 10s.
- **Signature Ability - Grand Convocation:** channel 5s to summon a temporary Colossus Effigy (huge HP, area slam) for 12s at double upkeep; auto-dismisses when the timer or Pact ends. `[summon][area][damage][synergy]`

**Ten Active Abilities:**
1. `Summon Cinder Hound [30 Pact / 8s; cast 2s]` - field a fast melee damage Effigy (Burn on hit). `[summon][damage]`
2. `Summon Bulwark [35 Pact / 10s; cast 2.5s]` - field a tanky Effigy that taunts nearby enemies. `[summon][position]`
3. `Summon Mending Wisp [30 Pact / 12s; cast 2s]` - field a healer Effigy applying Regen to allies. `[summon][heal][support]`
4. `Command: Rend [8 MP / 4s; instant]` - order all summons to focus one target with a bonus strike. `[damage][synergy]`
5. `Command: Rally [10 MP / 15s; instant]` - summons gain Haste + Guard for 5s. `[buff][support][synergy]`
6. `Empower Effigy [16 MP / 20s; cast 1s]` - one summon gains +30% damage 8s; upkeep +50% for the duration. `[buff][resource]`
7. `Consume Pact [0 MP / 10s; instant]` - dismiss one summon to instantly restore 40 Pact and heal yourself. `[resource][heal]`
8. `Bind Snare [14 MP / 12s; cast 1s]` - summons project a shared Root on enemies adjacent to them (2s). `[cc][area][synergy]`
9. `Soul Tether [20 MP / 25s; cast 1.5s]` - link to a summon; damage it takes is halved and split to you. `[support][buff]`
10. `Overpact [24 MP / 45s; instant]` - ignore upkeep drain entirely for 6s (Pact still cannot be spent). `[resource][buff]`

**Five Passive Support Doctrines:**
- Steady Pacts - +2 passive Pact regen per active summon.
- Shared Instinct - summons inherit 15% of your MAG as their power.
- Conductor's Presence - allies near your summons gain +5% resistance.
- Efficient Binding - first summon each fight costs half Pact.
- Loyal Echo - when a summon dies, you regain 15 Pact.

**Five Reaction Abilities:**
- `Recall Effigy [a summon drops below 15% HP; 20s]` - dismiss it safely, refunding 25 Pact. `[resource][counter]`
- `Guardian Reflex [you are struck in melee; 12s]` - nearest summon body-blocks the next hit. `[counter][position]`
- `Vengeful Pact [a summon is killed; 15s]` - all remaining summons gain +20% damage 6s. `[buff][counter][synergy]`
- `Emergency Bind [field is empty and you take damage; 40s]` - instantly summon a weak Stun-on-arrival Effigy. `[summon][cc][counter]`
- `Pact Surge [Pact Reserve hits 0; 60s]` - prevent the auto-dismiss once and restore 20 Pact. `[resource][counter]`

**Three Movement Techniques:**
- `Swap Places [12s]` - instantly trade positions with a summon. `[mobility][position]`
- `Shepherd Step [8s]` - move and pull all summons to your new position. `[mobility][position][support]`
- `Effigy Dash [18s]` - ride a summon's charge two tiles, both gaining Haste 3s. `[mobility][synergy]`

**Secondary Job Synergies:**
- Elementalist: park summons inside zones so they hold a killbox while the terrain does damage.
- Chronomancer: Haste summons and cut re-summon cooldowns, smoothing the upkeep economy.

**Example Builds:**
- *Effigy Warlord:* Summoner / Elementalist; Bulwark holds a Frost Field, Cinder Hounds finish, Grand Convocation for burst.
- *Sustain Commander:* Summoner / Chronomancer; Mending Wisp + Soul Tether + Timeslip keep a wall of durable, Hasted summons standing.
### Divine family

The Divine jobs are the Radiant Order: an oath-bound circle that channels the Radiance, an
impersonal tide of ordering light that answers preparation, not prayer. Where other families spend
the present, the Divine trade in what has not happened yet, damage prevented, an enemy read a beat
early, a promise kept under fire, ground made unpassable. Each solves protection and recovery on a
different axis: the Cleric prevents, the Oracle foresees, the Templar leverages, the Warden
anchors.

#### Cleric
- **Purpose:** A proactive sustainer who spends effort before wounds land, keeping a team upright by shielding and seeding recovery rather than topping-up after the fact.
- **Lore:** Clerics learn the Radiance as a household craft: bank the light while calm, spend it the instant before the blow. Their creed is a single line carved on every kit, "the wound you prevent needs no cure."
- **Combat Role:** Pre-emptive protector and healer. She reads incoming pressure and answers with shields, heal-over-time, and triaged bursts, converting acts of care into a Devotion economy that fuels her strongest saves. Her power is highest a moment early and wasted a moment late.
- **Primary / Secondary Attributes:** Wisdom / Stamina.
- **Equipment Proficiencies:** Focus, Instrument, Sidearm / Cloth/Robe, Ward, Mail / Totem, Kit, Trinket.
- **Resource System:** HP (moderate). MP (large, WIS-scaled regen; funds routine shields and heals). **Devotion** (0-100): +3 per heal or shield that lands on an ally, +1/tick while a Regen or Guard she cast is active; her strongest saves and mass-shields consume Devotion instead of MP. Bleeds 1/tick out of combat, so it is a "spend it on the team" meter, not a hoard.
- **Unique Identity:** The only Divine job whose best output comes from acting before the hit; every heal doubles as fuel for a bigger heal later.
- **Strengths:** Highest pre-emptive mitigation in the family; scales up the more allies she tends; strong sustained-fight economy.
- **Weaknesses:** Weak burst-reaction if caught flat (Devotion may be empty); low personal damage; shields wasted when timed wrong give her nothing back.
- **Job Progression:** L1 Devotion; L5 heal-over-time stacks a second application; L10 shields leave a small Regen when they break; L15 mass abilities gain +1 target; L20 Devotion stops bleeding while any ally is below half HP; L25 overheal converts to a temporary shield; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Kept Light:** the first save-tier ability each fight costs no Devotion, and her shields land 1 tick faster (harder to out-time).
- **Signature Ability - Aegis Cascade:** shields the lowest-HP ally, and each time that shield absorbs a hit it jumps to the next-lowest ally, chaining up to four times. `[buff][support][synergy]`

**Ten Active Abilities:**
1. `Mendlight [8 MP / 3s]` - a triaged burst heal, healing more the lower the target's HP. `[heal]`
2. `Wardweave [12 MP / 6s]` - lay a damage-absorbing shield on an ally. `[buff][prep]`
3. `Emberpatch [10 MP / 5s]` - apply Regen heal-over-time for 10s. `[heal][buff]`
4. `Grace Font [20 MP / 12s]` - area heal-over-time centered on you for 8s. `[heal][area]`
5. `Bulwark Hymn [25 Devotion / 18s]` - shield every ally in range at once. `[buff][area][synergy]`
6. `Soothe Chains [15 MP / 10s]` - cleanse Bleed/Burn/Chill from an ally and heal the removed damage. `[heal][support]`
7. `Radiant Rebuke [14 MP / 8s]` - Focus bolt that deals damage and applies Weaken. `[damage][debuff]`
8. `Stillpoint [18 MP / 14s]` - lock an ally at their current HP for 4s (cannot drop below 1). `[buff][counter]`
9. `Lantern Vow [30 Devotion / 30s]` - the next lethal hit on the chosen ally within 12s is survived at 1 HP. `[prep][counter]`
10. `Convocation [40 Devotion / 60s]` - large instant party heal plus a short party Guard. `[heal][area][buff]`

**Five Passive Support Doctrines:**
- Frugal Hands - heals that hit a full-HP ally refund half their MP.
- Warm Reserve - +Devotion generation while three or more allies are in range.
- Steady Creed - Regen you apply cannot be dispelled by Weaken.
- Anointed Focus - your Focus attacks build 1 Devotion on hit.
- Kept Watch - shields on allies below half HP last 50% longer.

**Five Reaction Abilities:**
- `Reflex Ward [ally drops below 30% HP; 12s]` - auto-cast a small shield on them. `[counter][support]`
- `Backlash Grace [you take a critical hit; 20s]` - gain a short self Guard and 15 Devotion. `[counter][resource]`
- `Interject Light [an ally would be Stunned; 25s]` - convert the Stun into Slow instead. `[counter][cc]`
- `Second Breath [you fall below 20% HP; 30s]` - instant self heal-over-time burst. `[counter][heal]`
- `Mercy Snap [an ally dies in range; 45s]` - heal all nearby allies for a portion of that ally's max HP. `[counter][heal][area]`

**Three Movement Techniques:**
- `Lightstep [8s]` - short blink toward a targeted ally, cleansing Snare on arrival. `[mobility][support]`
- `Processional [16s]` - brief party Haste aura as you move. `[mobility][buff]`
- `Ward Slide [10s]` - sidestep that leaves a lingering shielded tile for 4s. `[mobility][area]`

**Secondary Job Synergies:**
- Warden: Warden zones plus Cleric shields make a fortress patch; Devotion stays fed inside a denial field.
- Templar: a Templar soaking hits generates heavy Devotion for the Cleric, funding Bulwark Hymn on cadence.

**Example Build:**
- *Front-Anchor Medic:* Cleric / Warden, reaction Reflex Ward, movement Processional. Park inside a ward, pre-shield the line, spend Devotion on Bulwark Hymn and Lantern Vow.

#### Oracle
- **Purpose:** A foresight controller who reads the enemy a beat early and pre-empts it, interrupting casts, denying openers, and banking predicted events into hard counters.
- **Lore:** The Oracle does not see the future so much as overhear it: the Radiance leaves a faint wake ahead of every action, and a trained eye reads the ripple before the stone lands. They speak in odds and omens, and are almost always right about the next three seconds.
- **Combat Role:** Real-time predict-and-interrupt control. She samples enemy intent, stores it as Omens, and spends those Omens on precise interrupts, pre-placed counters, and debuffs timed to land the instant before an ability fires. The best heal is the hit that never happened.
- **Primary / Secondary Attributes:** Wisdom / Luck.
- **Equipment Proficiencies:** Focus, Thrown, Sidearm / Cloth/Robe, Ward, Leather / Trinket, Totem, Kit.
- **Resource System:** HP (low-moderate). MP (moderate, WIS-scaled regen; funds scrying and debuffs). **Omen** (a bank of up to 5): +1 whenever an enemy begins a cast or telegraphs an ability within her sight; +1 on a correctly predicted interrupt. Interrupts, pre-emptive counters, and foresight buffs each consume 1-2 Omens. No decay, but caps at 5, so unread futures are lost.
- **Unique Identity:** The only job that generates resource from enemy actions and spends it to erase those actions before they resolve.
- **Strengths:** Best single-target interrupt uptime in the family; strong anti-caster and anti-burst denial; converts enemy aggression into her own economy.
- **Weaknesses:** Fragile if her reads run dry; low direct healing; heavily punished by Silence and Blind.
- **Job Progression:** L1 Omen bank (cap 3); L5 cap 4; L10 interrupts also apply a brief Silence; L15 cap 5; L20 predicted hits can be pre-shielded for an ally; L25 correct interrupts refund half their MP; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Read the Wake:** enemy telegraphs are visible ~1 tick sooner and generate +1 Omen, sharply raising interrupt and counter uptime.
- **Signature Ability - Foreclosed Fate:** mark an enemy; the next ability it attempts within 8s is cancelled outright and rebounds as a Weaken on the caster. `[interrupt][cc][debuff]`

**Ten Active Abilities:**
1. `Cut the Thread [1 Omen / 6s]` - interrupt an enemy cast in progress. `[interrupt][cc]`
2. `Illwind Omen [12 MP / 5s]` - throw a debuff that applies Vulnerable for 8s. `[debuff]`
3. `Presage Guard [2 Omen / 14s]` - pre-shield an ally against a predicted incoming hit. `[buff][prep][counter]`
4. `Scry Pulse [10 MP / 8s]` - reveal and Mark all enemies in an area for 10s. `[debuff][area][prep]`
5. `Stutter Hex [14 MP / 10s]` - apply Slow and extend the enemy's next cooldown. `[debuff][cc]`
6. `Omen Bolt [8 MP / 3s]` - Focus bolt; deals bonus damage to a Marked target. `[damage][synergy]`
7. `Fracture Intent [2 Omen / 16s]` - Silence an enemy for 3s and drain 1 of its buffs. `[interrupt][debuff][cc]`
8. `Foresight Veil [16 MP / 20s]` - grant an ally a predicted-dodge (next hit within 6s misses). `[buff][counter][support]`
9. `Cascade Warning [3 Omen / 24s]` - area interrupt: cancel every enemy cast in range. `[interrupt][area][cc]`
10. `Convergence [5 Omen / 45s]` - lock an enemy out of all abilities for 4s (hard Silence + Root). `[cc][interrupt][area]`

**Five Passive Support Doctrines:**
- Wake-Reader - see enemy telegraphs slightly earlier than other jobs.
- Told-You-So - a successful interrupt applies Weaken to the caster for free.
- Lucky Read - Luck raises the chance an interrupt also refunds an Omen.
- Quiet Mind - reduced duration of Silence and Blind on yourself.
- Shared Sight - Marks you place let allies deal slightly more damage to the target.

**Five Reaction Abilities:**
- `Snap Foretell [an enemy begins a burst cast; 10s]` - auto-interrupt if you hold an Omen. `[interrupt][counter]`
- `Averted Blow [you are about to be hit; 18s]` - spend 1 Omen to make the hit miss. `[counter]`
- `Echo Back [you are Silenced; 30s]` - reflect the Silence onto its source. `[counter][cc]`
- `Preread [an ally is Marked by an enemy; 20s]` - grant that ally a predicted-dodge. `[counter][support]`
- `Omen Surge [your Omen bank empties; 25s]` - instantly bank 2 Omens. `[resource][counter]`

**Three Movement Techniques:**
- `Sidestep Fate [8s]` - short dodge-blink that guarantees evasion of the next hit during it. `[mobility][counter]`
- `Foreknown Path [14s]` - move at Haste for 3s along a pre-read route, ignoring Snare. `[mobility]`
- `Ghoststep [12s]` - phase briefly, untargetable for 1s mid-move. `[mobility]`

**Secondary Job Synergies:**
- Cleric: Presage Guard plus Cleric shields stack prevention on the same predicted hit for near-total denial.
- Templar: the Oracle calls the enemy opener; the Templar answers it with a punish before it lands.

**Example Build:**
- *Anti-Caster Lockdown:* Oracle / Cleric, reaction Snap Foretell, movement Sidestep Fate. Bank Omens off enemy casters, chain Cut the Thread and Fracture Intent, close with Convergence.

#### Templar
- **Purpose:** A frontline oath-bound who turns the act of protecting others into offense: the more damage she intercepts for allies, the harder she hits back.
- **Lore:** The Templar swears a standing oath to a chosen name and stands between that name and harm; the Radiance rewards the kept vow with force. Their armor is scored with the tally of oaths honored, and a Templar with a full ledger is a genuinely dangerous thing.
- **Combat Role:** Protective bruiser and vow-punisher. She taunts and body-blocks, redirecting harm onto herself, then converts absorbed and intercepted damage into Zeal that powers heavy retaliations and short party saves.
- **Primary / Secondary Attributes:** Wisdom / Strength.
- **Equipment Proficiencies:** Great Weapon, Polearm, Blade / Heavy Plate, Mail, Ward / Shield, Totem, Trinket.
- **Resource System:** HP (high; built to be hit). MP (small, WIS-scaled; funds oaths and cleanses). **Zeal** (0-100, rises in danger): +2 per hit intercepted or taken while an oath is active, +1/tick while below half HP; retaliation strikes and party saves spend it. Decays 2/tick once out of combat or once she stops taking hits, a "stay in the fire" meter.
- **Unique Identity:** The only healer/protector whose damage output scales with how much punishment she willingly absorbs.
- **Strengths:** Highest personal durability in the family; converts enemy focus-fire into her own damage; strong single-target peel and taunt.
- **Weaknesses:** Poor at range and against spread pressure; low MP throttles her utility; Zeal starves if the enemy ignores her.
- **Job Progression:** L1 Zeal + oath mechanic; L5 taunt also applies Weaken; L10 intercepted damage is reduced before it hits you; L15 retaliations gain bonus damage scaled by Zeal; L20 oath can cover two allies; L25 falling below 25% HP grants a burst of Zeal and brief Guard; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Unbroken Oath:** while an oath is active she cannot be crowd-controlled below 40% HP, and Zeal decay pauses entirely in combat.
- **Signature Ability - Vow of the Kept Name:** bind to an ally for 15s; all damage they take is split to you, and each split hit builds double Zeal and adds to your next strike. `[buff][support][synergy]`

**Ten Active Abilities:**
1. `Oathstrike [10 Zeal / 4s]` - Great Weapon blow dealing bonus damage per point of Zeal spent. `[damage]`
2. `Standfast Oath [8 MP / 12s]` - bind an ally; redirect a share of their damage to you for 10s. `[buff][support][prep]`
3. `Challenge Roar [6 MP / 8s]` - taunt enemies in front and apply Weaken. `[cc][debuff][area]`
4. `Interpose [0 / 10s]` - body-block the next hit aimed at a bound ally, taking it yourself. `[counter][support]`
5. `Retribution [20 Zeal / 6s]` - strike all adjacent enemies for damage scaled by Zeal. `[damage][area]`
6. `Guardian's Word [30 Zeal / 20s]` - grant a bound ally a short Guard and heal-over-time. `[heal][buff][support]`
7. `Bleeding Sunder [12 MP / 9s]` - Polearm thrust applying Bleed and Vulnerable. `[damage][debuff]`
8. `Bulwark Stance [10 MP / 16s]` - self Guard for 6s; Zeal generation doubled while it holds. `[buff][resource]`
9. `Chastening Blow [15 Zeal / 10s]` - heavy strike that Stuns for 1.5s and interrupts. `[damage][cc][interrupt]`
10. `Last Ledger [50 Zeal / 60s]` - instantly shield every bound and nearby ally and heal them for a share of your missing HP. `[heal][buff][area][synergy]`

**Five Passive Support Doctrines:**
- Tallied Vows - each active oath raises your damage slightly.
- Ironkeeper - Heavy Plate converts a portion of blocked damage into Zeal.
- Held Ground - you cannot be knocked back while an ally is bound to you.
- Zealous Recovery - a portion of Zeal spent on retaliation heals you.
- Sworn Focus - Silence cannot stop your oaths (they are vows, not casts).

**Five Reaction Abilities:**
- `Kept Vow [a bound ally would take a killing blow; 40s]` - fully intercept it and gain 30 Zeal. `[counter][support]`
- `Punish Opening [an enemy near you finishes a cast; 12s]` - auto Oathstrike that target. `[counter][damage]`
- `Wrathguard [you drop below 30% HP; 25s]` - brief Guard and a burst of Zeal. `[counter][resource]`
- `Riposte Oath [you block or are Guarded through a hit; 15s]` - counter-strike the attacker. `[counter][damage]`
- `Unmoved [you would be Stunned; 30s]` - resist it and apply Weaken to the source. `[counter][debuff]`

**Three Movement Techniques:**
- `Vanguard Charge [12s]` - rush to an enemy, applying Snare on arrival. `[mobility][cc]`
- `Shieldrush [16s]` - dash to a bound ally and body-block the next hit on them. `[mobility][support]`
- `Anchor Step [10s]` - short reposition that cannot be interrupted or rooted. `[mobility][position]`

**Secondary Job Synergies:**
- Cleric: the Cleric feeds shields onto the Templar so she survives intercepting more, which floods her Zeal.
- Warden: the Warden's denial fields funnel enemies into the Templar's taunt and cleave.

**Example Build:**
- *Oath Bruiser:* Templar / Cleric, reaction Kept Vow, movement Shieldrush. Bind the squishiest ally, stand in the fire, dump Zeal into Retribution and Last Ledger.

#### Warden
- **Purpose:** A zone-warden who anchors ground with wards and denial fields, making chosen space safe for allies and hostile for enemies.
- **Lore:** The Warden binds the Radiance into standing wards, lines and circles laid on the ground that hold long after they are set. They think in terrain: where the team stands, where the enemy must not, and the seam between the two.
- **Combat Role:** Area-control sustainer. Rather than following allies, she shapes the battlefield: healing gardens, warded lines, snaring fields, and no-go zones. Protection and recovery are positional: stand in her light and be mended, cross her line and be punished.
- **Primary / Secondary Attributes:** Wisdom / Stamina.
- **Equipment Proficiencies:** Focus, Polearm, Instrument / Ward, Cloth/Robe, Brigandine / Totem, Kit, Shield.
- **Resource System:** HP (moderate). MP (large, WIS-scaled; funds ongoing fields). **Ward Reservoir** (0-100, a stored charge of bindable light): +1/tick passively, +3 whenever an ally stands in one of her fields; placing and reinforcing fields draws from the Reservoir. Fields she maintains drain 1/tick each, so she can only hold so much ground at once.
- **Unique Identity:** The only Divine job that heals and protects the ground instead of the person; her power is measured in controlled square footage.
- **Strengths:** Best sustained area healing and zone denial in the family; strong preparation and chokepoint control; excellent in fixed-position fights.
- **Weaknesses:** Weak on the move (fields left behind are dead resource); low burst and single-target save; enemies who refuse her ground neutralize her.
- **Job Progression:** L1 Ward Reservoir + field-placement; L5 second field at once; L10 allies leaving a healing field keep a short Regen; L15 denial fields also apply Slow; L20 third field at once; L25 fields cost less to reinforce; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Consecrated Ground:** one field per fight becomes permanent (no per-tick drain) and gains +50% area.
- **Signature Ability - Sanctuary Line:** draw a line on the ground for 12s; allies crossing it gain a shield, enemies crossing it are Rooted for 1.5s. `[buff][cc][area]`

**Ten Active Abilities:**
1. `Healing Garden [20 MP / 12s]` - place a field that heals-over-time all allies inside for 10s. `[heal][area][prep]`
2. `Thornfield [18 MP / 10s]` - place a field that damages and applies Bleed to enemies inside. `[damage][area][debuff]`
3. `Wardstone [15 MP / 8s]` - drop a Totem that shields nearby allies while it stands. `[buff][area][prep]`
4. `Mireground [16 MP / 12s]` - field that applies Snare and Slow to enemies inside. `[cc][area][debuff]`
5. `Bulwark Line [25 Reservoir / 16s]` - raise a wall-line that blocks enemy movement for 6s. `[area][cc][position]`
6. `Cleansing Pool [18 MP / 14s]` - field that removes Burn/Chill/Shock from allies each tick. `[heal][area][support]`
7. `Radiant Stake [10 MP / 5s]` - Focus bolt that Marks where it lands, empowering your next field there. `[damage][prep][synergy]`
8. `Hallowed Circle [40 Reservoir / 30s]` - large zone granting allies inside Guard and Regen. `[heal][buff][area]`
9. `Sever Ground [20 Reservoir / 20s]` - collapse a field early to Stun every enemy standing in it. `[cc][area][interrupt]`
10. `Bastion Bloom [60 Reservoir / 90s]` - erect a fortified zone: allies inside take reduced damage and are healed, enemies inside are Weakened. `[heal][buff][debuff][area][synergy]`

**Five Passive Support Doctrines:**
- Attended Ground - fields with an ally standing in them drain Reservoir slower.
- Rooted Craft - your fields cannot be dispelled, only outlasted or destroyed.
- Layered Warding - overlapping two of your fields boosts both effects.
- Steady Keeper - you resist knockback and Root while standing in your own field.
- Efficient Binding - Wisdom lowers the Reservoir cost of reinforcing fields.

**Five Reaction Abilities:**
- `Snap Ward [an ally in your field drops below 30% HP; 14s]` - instant burst heal to everyone in that field. `[counter][heal][area]`
- `Ground Answer [an enemy enters your denial field; 8s]` - apply an extra stack of Slow. `[counter][cc]`
- `Collapse Guard [your field is about to be destroyed; 20s]` - it detonates, Rooting nearby enemies. `[counter][cc][area]`
- `Held Line [you are knocked back; 25s]` - anchor in place and drop a small Snare field. `[counter][area]`
- `Overgrowth [an ally leaves your healing field; 18s]` - extend their Regen for 4s. `[counter][heal]`

**Three Movement Techniques:**
- `Warded Step [10s]` - short blink that leaves a lingering Snare tile where you stood. `[mobility][area]`
- `Groundshift [16s]` - relocate one active field to your new position. `[mobility][prep]`
- `Rootwalk [12s]` - move without ending your maintained fields. `[mobility][support]`

**Secondary Job Synergies:**
- Templar: the Templar taunts enemies into the Warden's Thornfield and Mireground, pinning them in the damage.
- Cleric: Cleric shields on top of Hallowed Circle create an almost unkillable holding point.

**Example Builds:**
- *Chokepoint Keeper:* Warden / Templar, reaction Collapse Guard, movement Groundshift. Wall the lane with Bulwark Line, layer Thornfield and Mireground, heal from Healing Garden.
- *Field Medic Anchor:* Warden / Cleric, reaction Snap Ward, movement Warded Step. Hold Hallowed Circle on the team, reinforce with cheap fields, save Bastion Bloom for the crunch.
### Engineering family

The Engineering family turns the battlefield into a system to be operated, not just a foe to be
struck. Its jobs win through preparation, positioning, and control: they read the fight like a
diagnostic, place hardware where it matters, and convert foresight into hard mechanical advantage.
Where most families spend resources to deal damage, Engineers spend them to bend the field's rules.
The Engineer is the reference implementation for the whole system: it already ships in
`seeds/*/jobs.yaml`, and every field below matches its real data.

#### Engineer
- **Purpose:** The live battlefield operator: deploys devices, repairs allies, interrupts enemies, and controls space in real time.
- **Lore:** Forged in the maintenance bays of collapsing war-forts, the Engineer learned that a wrench swung in time saves a hundred blades. They walk into the Spiral carrying a Rig humming with Power Cells, reading the fight the way others read a torn schematic. Nothing on the field is beyond calibration, and nothing they deploy is ever truly idle.
- **Combat Role:** Support / Control. A sustained-presence class that shapes the fight through deployed hardware, timely interrupts, and repair, rather than burst damage.
- **Primary / Secondary Attributes:** Wisdom + Speed / Stamina. WIS powers tech/support scaling and resistances; SPD drives action rate and evasion.
- **Equipment Proficiencies:** Sidearm (favored), Fist, Thrown, Focus / Rig (favored), Brigandine, Leather / Kit (favored), Buckler, Trinket. Signature loadout: Sidearm + Rig + Kit.
- **Resource System:** HP (medium, STA-scaled). MP (low; the few arcane-flavored calibrations; WIS regen). **Power Cells** (starts at 6, +1/tick, soft cap 10, mastery 12): spent to deploy and sustain devices (1-4 Cells each). Cells are the true economy: no Cells, no hardware.
- **Unique Identity:** The only job whose power lives on the ground, not in its hands. An Engineer with three devices placed is stronger than one standing in an empty room, so the skill is where and when you spend Cells.
- **Strengths:** Unmatched zone control through stacked deployables; reliable ally sustain via repair that ignores healing-reduction on constructs; deep interrupt toolkit against casters.
- **Weaknesses:** Weak burst, device-gated and slow to ramp; Cell-starved early; punished by forced repositioning since devices do not follow.
- **Job Progression:** L1 Calibrated Strike, Diagnostic Scan, Power Cells; L5 Field Repair, Cell cap +1; L10 Deploy Barrier, devices gain Guard on deploy; L15 System Interrupt, interrupt cooldowns -15%; L20 second device active (cap 2 to 3); L25 Cell regen +1/tick while any device is deployed; L30 mastery + Forge Overdrive.
- **Job Mastery Bonus (Lvl 30) - Redundant Systems:** Power Cell cap becomes 12, and the first device destroyed each 30s auto-redeploys once at half duration.
- **Signature Ability - Forge Overdrive** [6 Cells / 90s]: for 10s, all deployed devices fire/pulse at double rate, deploy costs are halved, and Cell regen doubles. `[buff][synergy][resource]`
- **Resistances:** Lightning Weak; Earth, Poison, Wound Resist.

**Ten Active Abilities:**
1. `Diagnostic Scan [1 Cell / 6s]` - reveal target's resistances/statuses and apply Mark 8s; allies gain +10% damage vs the Marked. `[debuff][support][synergy]`
2. `Field Repair [2 Cells / 8s]` - restore HP to an ally or device (WIS-scaled), cleanse 1 debuff. `[heal][support]`
3. `Deploy Barrier [3 Cells / 14s]` - place a barrier device granting Guard to allies behind it; 12s. `[buff][area][position]`
4. `System Interrupt [2 Cells / 10s]` - ranged pulse: interrupt a cast and apply Silence 3s. `[interrupt][cc]`
5. `Deploy Turret [3 Cells / 16s]` - place a turret that auto-fires each tick (SPD-scaled) for 14s. `[damage][area][position]`
6. `Deploy Coil [2 Cells / 12s]` - place a coil that pulses Shock in an area each 2 ticks, applying Slow. `[damage][cc][area]`
7. `Overclock Device [1 Cell / 10s]` - target device gains Haste 8s (double output). `[buff][synergy]`
8. `Recall Kit [0 Cells / 8s]` - pull a deployed device back; refund half its Cell cost. `[resource][position]`
9. `Static Lance [2 Cells / 5s]` - Sidearm burst that channels 2s, applying Shock and Vulnerable. `[damage][debuff]`
10. `Reboot Grid [4 Cells / 45s]` - instantly refresh duration on all active devices and cleanse their Weaken. `[support][synergy][resource]`

**Five Passive Support Doctrines:**
- Systems Thinking - each active device grants +4% evasion and +1 WIS effectiveness (stacking).
- Preventive Maintenance - devices below 30% HP self-repair 5% per tick.
- Load Balancing - deploying a device refunds 1 Cell if two or more are already active.
- Grounded Rig - reduces incoming Shock and self-inflicted device backlash by 50%.
- Field Uptime - out of combat, Cell regen triples and devices persist between rooms for 6s.

**Five Reaction Abilities:**
- `Emergency Repair [ally drops below 25% HP; 20s]` - auto-cast a Field Repair on that ally for reduced value. `[counter][heal]`
- `Fault Trip [hit by an interrupt or Silence; 18s]` - cleanse it and gain Guard 4s. `[counter]`
- `Backup Power [Cells reach 0; 30s]` - instantly restore 3 Cells. `[resource][counter]`
- `Counter-Deploy [a device is destroyed; 15s]` - next deploy within 5s costs 1 less Cell. `[resource][counter]`
- `Surge Guard [take Lightning damage; 25s]` - convert 30% of it into 1 Cell and apply Guard 3s. `[counter][resource]`

**Three Movement Techniques:**
- `Field Deployment [14s]` - blink to a targeted spot and drop a barrier device on arrival. `[mobility][position]`
- `Cable Pull [10s]` - yank yourself to a deployed device's location. `[mobility][position][synergy]`
- `Kinetic Dash [8s]` - short dash granting Haste 2s and clearing Snare/Root. `[mobility]`

**Secondary Job Synergies:**
- Artificer: pre-charged relics cover the Engineer's slow early Cells, buying deploy time.
- Any Healer job: frees the Engineer to spend Cells on control instead of repair.
- A Ranged job: turret + coil zoning stacks with kited damage.

**Example Builds:**
- *Fortress Operator:* max Deploy Turret/Coil/Barrier uptime, Systems Thinking + Preventive Maintenance, Field Deployment; hold a chokepoint and out-attrit.
- *Interrupt Tech:* System Interrupt + Static Lance + Reboot Grid, Fault Trip reaction, Kinetic Dash; a mobile anti-caster shutting down enemy channels.

#### Artificer
- **Purpose:** The pre-combat craftsman: charges single-use relics and imbues allies' gear before the fight, then unleashes stored power at decisive moments.
- **Lore:** The Artificer never enters a fight unprepared, because for them the fight begins hours earlier at the workbench, folding Charge into brittle relics and etching augments into a comrade's blade. They carry a bandolier of glassy one-shot devices, each a promise made in advance. Their genius is not reaction but foresight: the battle is half-won before the first blow lands.
- **Combat Role:** Preparation / Burst-Enabler. A front-loaded support-control class whose strength is banked ahead of time and spent as sudden, high-impact single-use effects and ally augments.
- **Primary / Secondary Attributes:** Wisdom + Luck / Magic. WIS scales imbue potency and resistance; Luck raises relic charge tiers and proc chance.
- **Equipment Proficiencies:** Focus (favored), Thrown, Instrument, Sidearm / Cloth/Robe (favored), Leather, Rig / Kit (favored), Trinket, Totem. Signature loadout: Focus + Robe + Trinket.
- **Resource System:** HP (low-medium, STA-scaled). MP (medium; imbues and in-combat crafting; WIS regen). **Charge** (starts at 0, no passive regen, built by prep abilities, banks up to 8, mastery 10): stored in relics and augments and consumed when they trigger. Unspent Charge decays 1 per 6s once combat ends. You cannot regen your way out of poor preparation.
- **Unique Identity:** The only job that front-loads its power. An Artificer who spent the pre-fight window has a bandolier of loaded relics and imbued allies; one caught cold is nearly inert until they rebuild Charge under fire.
- **Strengths:** Enormous burst windows via released stored Charge; force-multiplies the whole party through gear imbues; front-loaded value ignores healing-reduction and rewards planning.
- **Weaknesses:** Terrible on the back foot with 0 Charge; relics are single-use and finite; Charge decays out of combat, so banked prep is perishable.
- **Job Progression:** L1 Precision Etch, Kindle, Charge pool; L5 Imbue Edge, Charge cap +1; L10 Craft Volatile Relic, relics gain a free charge tier; L15 Imbue Ward, imbues may target 2 allies; L20 second augment pre-slotted at combat start; L25 Charge decay slowed, Kindle +1; L30 mastery + Grand Detonation.
- **Job Mastery Bonus (Lvl 30) - Master Fabricator:** Charge cap becomes 10, and entering combat auto-grants 3 Charge (the "prepared" bonus).
- **Signature Ability - Grand Detonation** [6 Charge / 100s]: instantly trigger every relic and augment currently held/slotted at once, and apply their combined elemental statuses in an area. `[damage][area][synergy]`
- **Resistances:** Chill Weak; Burn, Shock, Silence Resist.

**Ten Active Abilities:**
1. `Kindle [0 Charge, 15 MP / 6s]` - channel 2s to bank +2 Charge (interruptible). `[prep][resource]`
2. `Craft Volatile Relic [2 Charge / 12s]` - store a single-use relic: on throw, area Burn + Vulnerable. `[prep][damage][area]`
3. `Imbue Edge [1 Charge, 20 MP / 10s]` - augment an ally's weapon 20s: +Magic damage and Shock on hit. `[buff][prep][support]`
4. `Imbue Ward [1 Charge, 20 MP / 10s]` - augment an ally's armor 20s: absorb shield + one-time Guard. `[buff][prep][support]`
5. `Throw Relic [trigger held relic / 4s]` - hurl a stored relic, releasing its stored effect and Charge. `[damage][synergy]`
6. `Etch Sigil [2 Charge / 14s]` - place a floor sigil that arms; first enemy to cross takes area Chill + Root 2s. `[cc][area][position]`
7. `Overcharge Augment [1 Charge / 12s]` - detonate an ally's active imbue early for a burst matching its element. `[damage][synergy]`
8. `Unstable Infusion [3 Charge / 18s]` - channel 1s: apply Burn + Shock + Chill to a target. `[damage][debuff]`
9. `Reclaim Matter [0 Charge / 20s]` - break an unused relic to refund 1 Charge and 15 MP. `[resource]`
10. `Prime Bandolier [4 Charge / 45s]` - instantly craft two basic relics and reduce all craft cooldowns 50% for 6s. `[prep][resource][synergy]`

**Five Passive Support Doctrines:**
- Foresight - Charge banked before combat starts does not decay for the first 20s of the fight.
- Lucky Etch - Luck grants a chance to craft a relic at +1 charge tier for no extra cost.
- Efficient Fabrication - every 3rd relic crafted costs 0 Charge.
- Resonant Augments - allies carrying your imbue gain +5% resistance to that imbue's element.
- Stable Storage - held relics reduce Charge decay by 1 per relic and cannot be destroyed by enemy area effects.

**Five Reaction Abilities:**
- `Reactive Augment [augmented ally drops below 30% HP; 20s]` - their imbue auto-detonates as a Ward shield. `[counter][support]`
- `Backlash Ward [interrupted mid-craft; 18s]` - refund the Charge and gain Guard 3s. `[counter][resource]`
- `Emergency Fabrication [Charge reaches 0 in combat; 30s]` - instantly bank 2 Charge. `[resource][counter]`
- `Sigil Snap [enemy enters melee; 15s]` - auto-arm a Chill sigil at your feet. `[cc][counter]`
- `Volatile Discharge [take a critical hit; 25s]` - release a held relic's effect on the attacker for free. `[counter][damage]`

**Three Movement Techniques:**
- `Blink Etch [12s]` - short teleport that leaves an armed sigil at your origin. `[mobility][position][synergy]`
- `Ferried Step [10s]` - swap positions with an augmented ally. `[mobility][position][support]`
- `Slipstream [8s]` - dash granting Haste 2s; next craft within 3s costs 1 less Charge. `[mobility][resource]`

**Secondary Job Synergies:**
- Engineer: Engineer devices cover the fight's early ticks while the Artificer's Charge is still low from an ambush.
- A frontline striker job: Imbue Edge + Overcharge Augment turns their auto-attacks into elemental burst.
- Any Buff/Bard job: stacks pre-combat setup, making the opening burst window overwhelming.

**Example Builds:**
- *Bandolier Bomber:* stack Craft Volatile Relic + Prime Bandolier + Grand Detonation, Efficient Fabrication + Stable Storage, Blink Etch; walk in loaded and delete a cluster.
- *Party Armorer:* Imbue Edge/Ward on two allies, Resonant Augments + Reactive Augment, Ferried Step; a pre-fight support that pre-arms the whole team then detonates on demand.
### Nature family

The Nature family channels living systems into war: the slow tide of growth, the patient economy of
stamina and wisdom, and the shared instinct of predator and pack. Nature jobs win through
adaptation and endurance rather than burst, re-tooling themselves mid-fight and controlling terrain
until the battlefield itself becomes an ally. They lean STA and WIS, trading raw ceiling for
resilience, flexibility, and relentless per-tick pressure.

#### Druid
- **Purpose:** A shapeshifting frontline-flex who swaps between combat Aspects, each one re-tooling the same ability slots into a different fighting stance (bruiser, caster, mender), so one job covers three roles by preparation and timing.
- **Lore:** The first Druids learned that the wild does not choose a single shape, it becomes whatever the season demands. They carry the Wildline, an inner current that thickens into fur, hardens into bark, or thins into pollen at the wearer's will. To fight a Druid is to fight three creatures wearing one name.
- **Combat Role:** Adaptive stance-dancer. Bridges melee sustain, ranged area magic, and group support by cycling Aspects to answer whatever the fight needs next.
- **Primary / Secondary Attributes:** STA (form durability, Wildline cadence), WIS (heal power, resistance, MP regen) / MAG (Bloom damage), Speed (shift cadence).
- **Equipment Proficiencies:** Natural, Focus, Instrument, Polearm / Leather, Cloth/Robe, Ward / Totem, Trinket, Kit.
- **Resource System:** HP (medium-high, STA-scaled; highest in Beast Aspect). MP (spent by Bloom and Grove; WIS regen). **Wildline** (0-100, the Aspect meter): +2/tick out of combat, +4/tick while any Aspect is held. Shifting into an Aspect costs 25 Wildline and locks it for a 6s minimum. A held Aspect's keystone ability drains 1/tick but pays back on-hit; at 0 Wildline the Druid snaps to baseline Human form. Three Aspects: **Beast** (STA/melee/sustain), **Bloom** (MAG/ranged area), **Grove** (WIS/support/heal).
- **Unique Identity:** The ability bar is fixed in slots but its contents are rewritten by the current Aspect: the same keybind is a maul in Beast, a spore-burst in Bloom, and a mending bract in Grove. Mastery is reading the fight and paying the shift tax at the right second.
- **Strengths:** Role-fluid, covers tank-lite, area caster, and healer without re-gearing; strong per-tick sustain and self-healing; hard to lock out (shifting clears the current Aspect's slotted debuff category).
- **Weaknesses:** Shift tax (25 Wildline + 6s lock) punishes panic-swapping; lower burst ceiling than a dedicated caster or striker; Wildline starvation forces a weak baseline form at the worst moment.
- **Job Progression:** L1 Beast Aspect; L4 Bloom; L7 Grove (three-way cycling); L10 Wildline cap +20, first Reaction; L13 Aspect keystones; L16 shift lock 6s to 4s, Movement slot; L19 cross-Aspect carry (one buff persists a shift); L22 +1 status resistance while any Aspect held; L25 signature; L28 Wildline generation +1/tick everywhere; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - Threefold Instinct:** the first shift every 20s is free (no cost, no lock), and holding an Aspect 10+ seconds grants a stacking +3% Aspect power (max 5 stacks, reset on shift).
- **Signature Ability - Seasonturn:** instantly cycle through all three Aspects over 3s, firing each Aspect's keystone once at the target area (Beast rend, Bloom spore-burst, Grove mend-wave), then settle into the chosen Aspect with Wildline refilled to 60. `[damage][heal][area][resource][synergy]`

**Ten Active Abilities:**
1. `Rendmaul [10 Wildline / 4s]` - Beast: heavy melee strike, applies Bleed; heals 30% of damage dealt. `[damage][heal]`
2. `Barkset [15 MP / 12s]` - Beast: gain Guard and +STA for 8s, taunting the nearest foe. `[buff][position]`
3. `Sporeburst [18 MP / 6s]` - Bloom: ranged area pod that bursts for MAG damage and applies Weaken. `[damage][area][debuff]`
4. `Pollenveil [14 MP / 10s]` - Bloom: cone that applies Blind and Slow to all caught. `[cc][debuff][area]`
5. `Mendbract [20 MP / 5s]` - Grove: heal an ally over 6s (Regen) and cleanse one Chill/Burn. `[heal][support]`
6. `Grovecall [25 MP / 18s]` - Grove: root a totem that pulses +WIS and MP regen to allies in area for 10s. `[support][area][buff]`
7. `Thornlash [8 Wildline / 3s]` - Beast: quick claw combo, builds +6 Wildline on hit. `[damage][resource]`
8. `Wildgraft [22 MP / 20s]` - any Aspect: bind a Regen to self that also grants status resistance for 8s. `[heal][buff]`
9. `Bramblesnare [16 MP / 14s]` - Bloom/Grove: area of living roots, applies Root then Snare in a 4s window. `[cc][area][position]`
10. `Aspectlock [12 Wildline / 25s]` - stabilize the current Aspect: no forced-baseline for 12s even at 0 Wildline. `[buff][resource][prep]`

**Five Passive Support Doctrines:**
- Second Skin - taking a new Aspect grants 4% damage reduction for 3s.
- Deeproot - MP regen +15% whenever a Grove totem is active.
- Feral Memory - Beast Aspect heals-on-hit gain +5% per Bleed on the target.
- Sunfed - Bloom area abilities cost 10% less MP in daylight rooms.
- Even Keel - Wildline never drops below 10 while an ally is below 30% HP.

**Five Reaction Abilities:**
- `Flinchfur [taking a melee hit; 12s]` - reflexively harden, negating 20% of that hit and gaining Guard 2s. `[counter]`
- `Spore Reflex [being Silenced; 20s]` - instantly shift to Beast (which ignores Silence) for free. `[counter][resource]`
- `Rootward [being Stunned; 25s]` - break the Stun and apply Root to the attacker. `[counter][cc]`
- `Bloomguard [ally dropping below 25% HP; 15s]` - auto-cast a small heal from Grove reserves. `[heal][support]`
- `Wildsurge [Wildline hitting 0; 18s]` - gain +20 Wildline instantly and Haste 3s. `[resource][counter]`

**Three Movement Techniques:**
- `Pounce [8s]` - Beast: leap to a target within range, closing distance and applying Snare on land. `[mobility][cc]`
- `Windseed [14s]` - Bloom: dissolve to pollen and drift a short distance, uninterruptible. `[mobility]`
- `Rootstep [10s]` - Grove: short blink to an allied totem or ally, granting them Regen 3s. `[mobility][support]`

**Secondary Job Synergies:**
- Beastmaster: Grove totems and companion positioning stack into a zone-control duo; the Druid heals the beast while the Beastmaster peels.
- A Focus/caster job: borrowing extra MAG actives deepens the Bloom Aspect's burst window between shifts.
- A Guard/tank job: Reaction and Movement slots let a Beast-Druid off-tank while the primary holds the line.

**Example Builds:**
- *Tideturner (flex frontline):* lead Beast for sustain, dip Grove for group saves, Seasonturn as an emergency reset. Prioritize STA then WIS.
- *Spore Warden (area control):* camp Bloom for Pollenveil/Bramblesnare zoning, shift Grove only to refill and heal. Prioritize MAG/WIS with high Speed for shift cadence.

#### Beastmaster
- **Purpose:** A companion-commander who fights as a two-body unit, issuing orders to a persistent beast and spending a shared Bond resource to trigger paired combos, so positioning and timing across the pair, not solo output, is the skill.
- **Lore:** A Beastmaster does not tame a creature so much as agree with one. The pact writes a living thread, the Tether, between two heartbeats, and each learns to move as the other's blind side. Kill the master and the beast still hunts; kill the beast and the master fights like something is missing, because it is.
- **Combat Role:** Duo bruiser-controller. The master directs and buffs from mid-range while the beast engages, peels, or holds ground; the pair trade positions to trap and combo.
- **Primary / Secondary Attributes:** STA (shared survivability, Bond cadence), WIS (order potency, beast regen, resistance) / Speed (repositioning), Strength (beast bite scaling).
- **Equipment Proficiencies:** Bow, Thrown, Fist, Natural / Leather, Brigandine, Rig / Totem, Kit, Trinket.
- **Resource System:** The master has a standard STA HP pool; the beast has its own separate HP bar (scales with the master's STA/WIS) and re-summons after 30s at 50% HP if it falls. MP (modest; Orders and utility; WIS regen). **Bond** (0-100, the shared combo currency): +3 whenever master and beast both damage the same target within 2s (a "linked strike"), +1/tick while both are within close range, +5 when an Order lands. Combo abilities spend it; at 75+ Bond the pair gains passive Haste; separated 5s, Bond decays 2/tick.
- **Unique Identity:** The Beastmaster commands a persistent, separately-health-barred companion. Most power lives in coordination: abilities read the beast's position and state, and the strongest tools are Combos that only fire when master and beast are linked. You pilot two units, not one.
- **Strengths:** Two bodies, two threat points, natural peel and flank; strong sustained pressure when the pair pincers a target; resilient, losing either half is a setback, not a death.
- **Weaknesses:** Split control wastes Bond and halves output if piloted badly; vulnerable when separated; beast AI can be baited or CC'd, stranding the master.
- **Job Progression:** L1 summon beast, basic Attack/Follow/Stay Orders; L4 Bond pool + first Combo; L7 Order: Guard-ally; L10 Bond cap +20, first Reaction; L13 beast second stance (Fang: damage / Hide: durability); L16 linked-strike Bond +1, Movement slot; L19 Recall 30s to 20s, re-summon at 60% HP; L22 Orders cost 15% less MP; L25 signature; L28 high-Bond Haste threshold lowered to 60; L30 mastery.
- **Job Mastery Bonus (Lvl 30) - One Pulse:** while Bond is 80+, master and beast share a portion of incoming damage (spreading spikes across two bars) and every linked strike heals both for 4% of damage dealt.
- **Signature Ability - Twin Fang Convergence:** order the beast to leap to the master's target while the master strikes it simultaneously; the linked hit deals heavy damage, applies Vulnerable, Roots the target 3s, and refills Bond to 80. `[damage][cc][synergy][resource]`

**Ten Active Abilities:**
1. `Order: Maul [12 MP / 4s]` - command the beast to bite for heavy damage and apply Bleed. `[damage][synergy]`
2. `Order: Hold [10 MP / 10s]` - beast taunts and gains Guard, anchoring a spot for 8s. `[position][buff][synergy]`
3. `Linked Volley [20 Bond / 8s]` - master and beast strike together for burst area damage and Mark. `[damage][area][debuff]`
4. `Hamstring Pack [14 MP / 12s]` - beast applies Snare, master applies Slow, pincering the target. `[cc][debuff]`
5. `Feed the Bond [16 MP / 6s]` - short channel where beast attacks generate double Bond for 4s. `[resource][prep]`
6. `Kindred Mend [22 MP / 9s]` - heal whichever of the pair is lower and grant it Regen 6s. `[heal][support]`
7. `Order: Flank [12 MP / 10s]` - beast repositions behind the target, granting the pair +Speed and a Vulnerable window. `[position][buff][debuff]`
8. `Snarl [10 MP / 14s]` - beast roars, applying Weaken and a brief interrupt to casters in area. `[interrupt][debuff][area]`
9. `Rend Convergence [30 Bond / 16s]` - both charge and cross through the target, heavy Bleed plus Root. `[damage][cc][synergy]`
10. `Pack Instinct [18 MP / 25s]` - both gain Haste and status resistance for 8s while within close range. `[buff][synergy]`

**Five Passive Support Doctrines:**
- Shared Nerve - the beast inherits 20% of the master's WIS-based resistances.
- Blind Side - hitting a target the beast is already attacking deals +8% damage (and vice versa).
- Tether Sense - Bond decays half as fast when either unit is below 30% HP.
- Steady Pack - +5% HP regen for both while both are within close range.
- Second Wind Pact - re-summoning the beast grants the master Haste 3s.

**Five Reaction Abilities:**
- `Interpose [master taking a hit above 15% HP; 15s]` - beast dashes in and absorbs 30% of the next hit. `[counter][support]`
- `Retaliate Pack [beast being Stunned; 20s]` - master's next Order fires free and breaks the Stun. `[counter][cc]`
- `Bond Reflex [Bond hitting 0; 18s]` - instantly restore 25 Bond and Mark the nearest foe. `[resource][counter]`
- `Cover Fire [ally dropping below 25% HP; 14s]` - beast leaps to peel, applying Snare to that ally's attacker. `[support][cc]`
- `Death Pact [beast falling; 30s]` - master gains +STA and lifesteal for 6s until the beast returns. `[counter][buff]`

**Three Movement Techniques:**
- `Slip Lead [8s]` - master rolls to the beast's position, swapping their places to reset spacing. `[mobility][position]`
- `Beast Vault [12s]` - vault off the beast to leap over an enemy, landing behind for a flank. `[mobility][position]`
- `Recall Step [16s]` - beast blinks to the master's side, ending its current Root/Snare. `[mobility][synergy]`

**Secondary Job Synergies:**
- Druid: Grove totems and Kindred Mend keep the beast alive through long fights; the pair becomes a durable zone-control trio.
- A Bow/ranged job: extra ranged actives let the master kite while the beast tanks, widening the pincer.
- A CC/control job: stacked Root/Snare from both the job and the beast makes escape near-impossible.

**Example Builds:**
- *Pincer (control duo):* open Hamstring Pack, hold with Order: Hold, spend Bond on Rend Convergence to lock a target between two bodies. Prioritize STA then WIS.
- *Bloodbond (sustained pressure):* stack linked strikes for constant Bond, keep Pack Instinct and One Pulse online, chain Twin Fang Convergence on cooldown. Prioritize WIS with Speed for repositioning.

---

## 9. Complete job matrix

All twenty launch jobs at a glance: family, combat role, primary attributes, custom resource, and
the one-line identity that makes it solve fights differently from every other job.

| Job | Family | Combat role | Primary attrs | Custom resource | Solves the fight by... |
|---|---|---|---|---|---|
| Vanguard | Martial | Control-tank | STA, STR | Bulwark (build, immobility) | escalating control the longer it holds an anchor |
| Duelist | Martial | Single-target duelist | SPD, LUCK | Tempo (reads on one target) | baiting and punishing one marked opponent |
| Sentinel | Martial | Guardian-protector | STA, WIS | Aegis (build on intercept) | taking allies' hits and reflecting them |
| Berserker | Martial | Risk-engine cannon | STR, STA | Fury (heat) | escalating damage with its own heat and wounds |
| Ranger | Precision | Ranged zone-controller | SPD, LUCK | Anchor (stationary) | denying a lane with fire and layered traps |
| Scout | Precision | Info/mobility support | SPD, WIS | Intel (motion, reads) | exposing weakness so the party aims true |
| Shadowblade | Precision | Burst assassin | LUCK, SPD | Shade (stealth charge) | banking darkness into one lethal opener |
| Saboteur | Precision | Trap/toxin engineer | LUCK, WIS | Doses (timed stock) | grinding foes down with layered attrition |
| Arcanist | Arcane | Ranged nuke controller | MAG, WIS | Resonance (cast bank) | hoarding cast economy into a burst window |
| Elementalist | Arcane | Area-denial controller | MAG, WIS | Attunement (4-way dial) | spending power into lingering terrain zones |
| Chronomancer | Arcane | Tempo support-controller | WIS, MAG | Echo Bank (scheduled) | playing the clock with delayed effects |
| Summoner | Arcane | Pet commander | MAG, WIS | Pact Reserve (upkeep) | fighting through funded, persistent summons |
| Cleric | Divine | Pre-emptive protector | WIS, STA | Devotion (spend on team) | acting before the hit, care fuels bigger care |
| Oracle | Divine | Predict-and-interrupt | WIS, LUCK | Omen (from enemy intent) | erasing enemy actions before they resolve |
| Templar | Divine | Protective bruiser | WIS, STR | Zeal (rises in danger) | scaling damage with punishment absorbed |
| Warden | Divine | Area-control sustainer | WIS, STA | Ward Reservoir (ground) | healing and denying the ground, not the person |
| Engineer | Engineering | Support/control operator | WIS, SPD | Power Cells (deploy) | shaping space with deployed hardware |
| Artificer | Engineering | Preparation burst-enabler | WIS, LUCK | Charge (pre-built) | front-loading power into relics and imbues |
| Druid | Nature | Adaptive stance-dancer | STA, WIS | Wildline (Aspect meter) | re-tooling its slots into three fighting forms |
| Beastmaster | Nature | Duo bruiser-controller | STA, WIS | Bond (shared, paired) | piloting two coordinated bodies as one |

## 10. Example character builds (cross-job)

Each per-job section lists builds within its own family. These builds cross families to show how
the slot system multiplies twenty jobs into a much larger space. Each names its Primary / Secondary
and the four freely-chosen slots (Reaction, Support, Movement, Signature) plus a gear line.

- **The Unbreakable Line** - Vanguard / Warden. Reaction *Braced Answer*, Support *Steadfast
  Frame*, Movement *Groundshift*, Signature *Tidebreak Wall*. Polearm + Heavy Plate + Shield. Plant
  an anchor inside a relocated Thornfield: the Vanguard clamps, the borrowed Warden actives make the
  ground itself hostile. A one-character chokepoint.
- **Read-and-Delete** - Shadowblade / Duelist. Reaction *Riposte Nick*, Support *Killer's
  Patience*, Movement *Smoke Fold*, Signature *Killing Moment*. Blade + Leather + Trinket. Mark with
  the Duelist's read package, bank Shade in stealth, open for a guaranteed crit that executes. The
  Tempo actives give it teeth if the first strike does not finish the job.
- **Anti-Caster Wall** - Oracle / Arcanist. Reaction *Snap Foretell*, Support *Quiet Mind*,
  Movement *Sidestep Fate*, Signature *Foreclosed Fate*. Focus + Ward + Trinket. Bank Omens off
  enemy casters and chain interrupts; the Arcanist's Silencing Verse and Counterspell tools stack a
  near-total lockout on any spellcaster.
- **The Prepared Fortress** - Engineer / Artificer. Reaction *Fault Trip*, Support *Systems
  Thinking*, Movement *Field Deployment*, Signature *Forge Overdrive*. Sidearm + Rig + Kit. Walk in
  with pre-crafted relics covering the Cell-starved opening ticks, then deploy a full device board
  and Overdrive it. Preparation buys the ramp the Engineer normally lacks.
- **Escalating Guardian** - Templar / Berserker. Reaction *Kept Vow*, Support *Wounded Beast*,
  Movement *Shieldrush*, Signature *Vow of the Kept Name*. Great Weapon + Heavy Plate + Totem. Bind
  a fragile ally, soak the focus-fire into Zeal, and let the borrowed low-HP escalation turn
  absorbed punishment into genuine kill pressure.
- **The Living Killbox** - Elementalist / Summoner. Reaction *Grounding*, Support *Fusion Sense*,
  Movement *Stone Anchor*, Signature *Fourfold Convergence*. Focus + Ward + Totem. Wall a lane with
  Stone, layer Frost and Ember for a Fusion, and park summoned Effigies inside so the terrain and
  the bodies both punish anything that enters.
- **Pack-Tempo Skirmisher** - Beastmaster / Chronomancer. Reaction *Bond Reflex*, Support *Blind
  Side*, Movement *Slip Lead*, Signature *Twin Fang Convergence*. Bow + Brigandine + Totem. Haste
  the beast and cut Order cooldowns with the borrowed tempo kit, keeping linked strikes constant so
  Bond never falls and the pincer never stops.
- **Front-Anchor Medic** - Cleric / Warden. Reaction *Reflex Ward*, Support *Kept Watch*, Movement
  *Processional*, Signature *Aegis Cascade*. Focus + Ward + Totem. Stand inside a Hallowed Circle,
  pre-shield the line, and let Devotion fund a cascading team shield. Prevention stacked on
  prevention.

The point of the slot system: none of these eight required a new job. They are Primary x Secondary
x four chosen slots x gear, and the roster of twenty produces this depth many times over.

---

## 11. Engineering: how a job plugs in (data-driven, plugin-friendly, future-proof)

The core promise: **the combat engine knows nothing about specific jobs.** A job is data plus a
set of ability *components*; adding one changes no core loop.

**A job is a data record.** It maps onto the shipped `Job` schema (`parts/world/seed.py`) exactly:

```yaml
myjob:
  name: My Job
  description: One line.
  stats: {strength: 8, speed: 12, magic: 8, stamina: 11, wisdom: 13, luck: 10}
  role_tags: [control, support]          # from the tag vocabulary
  automatic_attack: <ability label>
  abilities: [<active labels>]           # the ten actives
  counter: <reaction label>              # the equipped-by-default reaction
  movement: <movement label>
  inherent: <passive label>              # the equipped-by-default support doctrine
  signature: <signature label>
  resistances: {FIR: Resist, LGT: Weak}  # element/status affinities
  power_cells: 6                         # the custom resource pool size
  power_regen: 1                         # per-tick regeneration
  milestone_perks:                       # ordered passive unlocks (the doctrines)
    - {name: <doctrine>, target: DEF, amount: 4}
```

**An ability is an independent component.** Each active/passive/reaction/movement/signature is a
named unit with tags, a cost, a cooldown, a trigger (reactions), and an effect the engine applies
by name. Combat resolves *effects and tags*, never a job. This mirrors how the engine already
wires the Engineer's `Diagnostic Scan`, `Field Repair`, `Emergency Repair` (a reaction),
`Field Deployment` (a movement), `Systems Thinking` (a passive), and `Forge Overdrive`
(the signature).

**Resources are configurable.** A job declares its pool size, per-tick regen, and the generation
archetype its abilities read against (section 4). No new archetype requires a combat-loop change.

**To add a future job:**

1. Write its `seeds/<seed>/jobs.yaml` record against the schema above.
2. Register its new ability *components* (label -> effect + tags + cost + cooldown, plus a
   trigger for reactions). Reuse existing components wherever the effect already exists.
3. Declare its custom resource (name, pool, regen, archetype).
4. Add a test twin proving each new component is reachable through the tick.

No edit to the combat engine, the tick, or any other job. That is the whole point: the design is
a catalog of composable parts, and the engine is the loom, not the pattern.

---

*This design is the canonical intent for the CodeForge Job System. It is inspired by modular
tactical RPG design and is wholly original in lore, mechanics, terminology, progression, and
implementation. Balance numbers are starting points, meant to be tuned against play.*
