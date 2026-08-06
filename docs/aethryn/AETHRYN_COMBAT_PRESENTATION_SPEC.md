# Aethryn Combat Presentation Specification

CodeForge's current combat is continuous/tick-based with cooldowns, status effects, and menace
resolution; it is not a turn-based queue. Preserve that engine truth and present the event stream in
three modes.

## Event hierarchy

1. encounter lifecycle: started, target changed, defeated, escaped;
2. player decision result: accepted, refused, invalid, interrupted;
3. consequential effect: damage, heal, mitigation, status, resource, movement;
4. ambient effect: repeated DoT/HoT/regen and minor auto-attacks;
5. reward: XP, JP/TP, loot, quest progress.

Consequential events are named with actor and target. Ambient events are grouped over a beat. A
telegraphed enemy special gets one warning and one resolution; the warning is never buried.

## Modes

- Compact: `You strike Vermin for 8. HP 28/32. Vermin 12/20.` plus warnings/results.
- Standard: one block per command/tick, group repeated auto-attacks and minor effects.
- Detailed: each event, mitigation, element, and source, still grouped by actor.
- Linear: one event per line, no columns, prefixes `PLAYER`, `ALLY`, `FOE`, `SYSTEM`.
- Summary: start, decisive events, current resources, result, rewards.

Never hide an invalid command, a player action, a defeat, a status change, or a resource cost in
compact mode. Group only repeated events with the same actor, target, effect, and beat.

## Canonical block

```
COMBAT — Vermin
Target: Vermin   Range: near   Beat: 3

YOU > Brace: incoming physical damage reduced.
YOU > Strike Vermin for 8 physical damage. [Vermin: 12/20 HP]
FOE > Vermin's poison cloud is forming. [telegraph]
FOE > Poison cloud hits you for 2. [HP: 30/32]

STATUS: HP 30/32 | MP 7/7 | Target Vermin 12/20 | Poison 2 beats
NEXT: attack <target> | use <ability> | flee
```

The exact numbers above are illustrative only. Text and GMCP/structured events carry the same
identifiers and values. A summary may collapse ambient events but links to the detailed log in the
Master Client.

