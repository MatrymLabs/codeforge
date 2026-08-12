# CODEFORGE ARCHITECTURAL LAWS

**Moved here 2026-08-12 from `WORKSHOP_DOCTRINE.md` section 6.** These govern CodeForge, one
product. The Workshop's constitution governs the Workshop, and a law about the engine tick does not
bind the Hardware Store.

**Workshop-wide security law stays in the doctrine** and is not repeated here: secrets never enter
git, passwords are never stored or logged in plaintext, secrets are never case-mangled. Those bind
every product and live at `WORKSHOP_DOCTRINE.md` section 6. Laws 7 and 8 below are the CodeForge
statement of the same rules, kept because they name the mechanism this engine uses.

1. **State is canonical; text is a projection.** Renderers never mutate state.
2. **The world is data.** Content lives in seed files behind loader gates, never hard-coded.
3. **Derive, do not store.** A parity test pins restore-math to play-math.
4. **The engine tick is the only door.** All drivers are thin callers.
5. **Authorization before capability.** Rank is checked before any privileged code runs.
6. **Server authority is absolute.** Clients and agents request; the runtime decides.
7. **Passwords are never stored or logged in plaintext.** Salted pbkdf2, constant-time comparison.
   Refuse any request to store or display plaintext at rest.
8. **Secrets are never case-mangled.** Password arguments are parsed from the ORIGINAL input.
9. **Grammar before worlds.** The kernel knows nothing of games; domains are modules.
10. **One core, two transmissions.** Everything that never asks "where exactly are you" is core;
    position granularity is the only variable.

**Secrets never enter git.** Only `.env.example` is tracked.
