# The Architect's brain (an API key away from live)

The Architect NPC (`parts/architect.py`) answers Workshop questions through a **seam** - the
`Advisor` protocol (`advise(prompt) -> str`). Two brains implement it behind the *same*
interface, so callers (`consult`, the `ai` verb) never change:

- **`LocalArchitect`** - a rule-based guide. No network, no key, no dependency. **The
  default**, and the only brain CI and offline play ever use.
- **`ClaudeAdvisor`** - backed by the Anthropic Messages API (model `claude-opus-4-8`). The
  architecture is **complete and tested**; it is dormant until a key is present.

## Waking the Claude brain (the small change, later)

Three switches, no code edit:

```bash
pip install "codeforge[ai]"          # the optional 'ai' extra (anthropic)
export ANTHROPIC_API_KEY=sk-...      # your key; read from the env only
export CODEFORGE_ARCHITECT=claude    # opt in; default is the local guide
```

With `CODEFORGE_ARCHITECT` unset (or not `claude`), the Architect stays local. If Claude is
requested but the key or package is missing, `consult` falls back to the local guide **and
says so** in a one-line note - the gap is surfaced, never hidden (VeritasGate).

## Why it is safe by construction

- **The SDK is touched in exactly one place** (`build_claude_advisor` / `ClaudeAdvisor`),
  behind the `Advisor` protocol. codeforge core never imports `anthropic`; it is an optional
  extra, so the engine runs without it. The dependency ledger justifies it, and `make deps`
  folds the `ai` extra into the gate so it still earns its place.
- **Tests never touch the network.** `ClaudeAdvisor` takes an **injected** client, so the
  suite drives it with a fake that mirrors the SDK shape. CI runs with no `ANTHROPIC_API_KEY`.
- **Secrets never leave the machine.** The prompt is passed through `_redact` before any call,
  scrubbing anything that looks like a password/token/key. Only redacted, public project
  context is ever sent (`docs/proving_ground/SAFETY.md`).
- **Advisory only.** The Architect explains, suggests commands, and points at parts. It never
  edits files or runs anything - that stays with you and the FailsafeRunner. No autonomous-
  coding claim is made.

## What is still `planned`

A live LLM brain inside codeforge is `research_more` in the framework decision
(`docs/full_stack_forge_decision.md`): the seam is here and proven, but running it against a
real key in a shipped surface (rate limits, cost, prompt-injection hardening, evidence
capture) is deliberately deferred. The real, exercised LLM pipeline lives in the sibling
`ai-log-triage` repo (schema-enforced `messages.parse`, mockable boundary, high coverage).
