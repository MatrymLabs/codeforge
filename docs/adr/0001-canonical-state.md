# ADR-0001: State is canonical; text is a projection

**Status:** accepted (day one)

**Decision:** Only validated engine logic mutates world state. All player-visible
text -- scenes, sheets, broadcasts -- is derived from state and never authoritative.

**Consequences:** renderers are pure and trivially testable; multiple clients and
future locales are projections of one truth; the event bus can later carry typed
frames instead of strings without touching world logic.
