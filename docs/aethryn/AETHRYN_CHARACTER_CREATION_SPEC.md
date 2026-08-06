# Character Creation Specification

Creation is a resumable, backtracking wizard. The initial slice is intentionally small:

1. character name;
2. presentation options (including skin color, pronouns, and description where supported);
3. origin/background;
4. one of the three current starting callings;
5. mechanical preview;
6. confirmation;
7. entry at the canonical starting room.

Do not expose all 30 callings at creation. Job unlocks are learned in play and presented later.
Skin color is a first-class persisted appearance field with a neutral fallback and a test that the
choice is rendered in `details`/appearance; it must not be silently dropped by the client.

```
CHARACTER CREATION — 2/5 CALLING
Name: Matrym
Origin: [unset]
Calling: > Vanguard — front-line control; high stamina and strength
         Pathfinder — mobile precision; speed and skill
         Emberwright — maker and ember; magic and craft

back | next | help creation
```

Confirmation prints every persisted choice and the first location. Creation writes atomically only
after confirmation; cancellation leaves no partial character unless resumable drafts are explicitly
enabled.

