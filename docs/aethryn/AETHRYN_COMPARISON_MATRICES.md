# Aethryn Comparison Matrices

These are pattern comparisons, not endorsements of copied content. `ADOPT` means adopt the
interaction principle and implement original Aethryn content.

| Matrix | Example/system | Pattern | Strength | Weakness | Accessibility | Traditional | Structured | Complexity | Recommendation |
|---|---|---|---|---|---|---|---|---|---|
| room display | classic MUD | prose + exits | immersive | wall of text | weak if unlabelled | high | medium | low | ADAPT |
| room display | modern text game | labelled sections | scannable | can feel mechanical | strong | high | high | medium | ADOPT |
| combat | tick MUD | event stream | responsive | spam risk | medium | high | high | medium | ADAPT |
| combat | tactics RPG | decisive action summary | readable decisions | may hide ambient detail | strong | medium | high | medium | ADOPT |
| skills | command list | compact names | fast | missing requirements | weak | high | medium | low | REJECT alone |
| abilities | card/detail view | inspectable costs | learnable | panel dependency | strong | medium | high | medium | ADOPT with text |
| character sheet | current Aethryn | fixed paired report | dense and coherent | width-sensitive | medium | high | high | medium | PRESERVE_EXISTING |
| exits | cardinal MUD | n/e/s/w | spatial memory | poor for portals | strong | high | high | low | ADOPT |
| exits | named hub routes | landmark words | thematic | arbitrary movement verbs | medium | high | high | low | ADAPT as alias |
| command grammar | Evennia | key/aliases/locks/help category | registry-friendly | engine-specific | strong | high | medium | medium | ADAPT |
| command grammar | Mudlet | client regex aliases | efficient | client divergence | weak alone | medium | medium | medium | ADOPT only client-side |
| help | generated command help | syntax from registry | accurate | needs metadata | strong | high | high | medium | ADOPT |
| account flow | account + character | separate identity | supports multiple heroes | extra step | strong | high | high | medium | ADOPT |
| creation | wizard | backtracking preview | learnable | more state | strong | high | high | high | ADOPT |
| progression | layered jobs | prerequisite graph | long-tail goals | balance complexity | strong if linearized | high | high | high | BUILD_ORIGINAL |
| accessibility | linear text | one fact per line | screen-reader friendly | less visual density | strong | high | medium | low | ADOPT |
| client parity | GMCP side channel | typed state projection | rich panels | stale frames | strong when fallback exists | high | high | high | ADOPT |
| terminal styling | ANSI/Unicode | capability-aware decoration | attractive | unsupported glyphs | medium | high | high | low | ADAPT |

## Source-backed observations

- Evennia's command-set model demonstrates that command availability, aliases, and locks are
  separable concerns. This supports the Aethryn registry/permission split.
- Mudlet documents GMCP as a separate structured channel and aliases as client input transforms.
  This supports structured enhancement while warning against client authority.
- W3C guidance supports reflow, keyboard access, non-color cues, and programmatically discoverable
  status. Aethryn applies these as engineering requirements, not a claim of WCAG certification.

