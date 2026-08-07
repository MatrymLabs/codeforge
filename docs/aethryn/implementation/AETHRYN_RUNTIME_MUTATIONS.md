# Aethryn Runtime Mutations

The mutation adapter now proves two packet-declared local service actions.

## Reusable action contract

The three live slices use the same action boundary. The validator checks the state transition before
publication, and the adapter returns structured `ActionOutcome` evidence for future gateways while
the text client receives the declared message. Optional `consume_item: true` is supported for later
packets and is applied only after the state transition succeeds. Existing slices leave their tokens
and salves reusable, so their behavior is unchanged.

## Greenhold cistern repair

```text
Greenhold Undercroft
        -> take valve-key
        -> Cistern Court
        -> maintain cistern
        -> greenhold.cistern_status: low -> flowing
        -> persisted room projection and cleared shortage signal
```

The action uses the existing authored `greenhold_valve_key`. It does not create a new relic or
resolve the old works question. The packet declares the target, aliases, required prototype,
source state, destination state, and player-facing messages. The runtime refuses the action
without the key, refuses it outside Cistern Court, and returns an idempotent response after repair.

## Brightwater sluice service

```text
Brightwater Old Sluice
        -> take sluice-token
        -> maintain sluice
        -> brightwater.sluice_status: ticking -> quiet
        -> persisted room projection
```

The packet declares the command, target aliases, required item prototype, source state, destination
state, and player-facing messages. The engine does not hard-code the Brightwater transition.

The action refuses when:

- the Aethryn state package is not loaded;
- the target is not declared;
- the player is not in the declared room;
- the required token is not in the player's carrier;
- the state has already left the declared source value.

Successful transitions use `WorldStateStore.set`, so the state survives restart and the next room
render immediately projects the new value. The action does not consume the token, rewrite room
records, or resolve the unresolved question of who built the sluice.

## State-gated runtime signals

Greenhold's water-shortage pressure declares `greenhold.cistern_status` as its state gate and is
active only while the value is `low`. Once the cistern reaches `flowing`, the live room projection
stops reporting that resolved shortage. The compiler remains the source of the rule, and the
runtime only reads the persisted state while rendering.

The same rule applies to Duskwood's `duskwood.hollow_lantern` state. The Black Hollow lantern
shortage remains visible while the state is `dim` and disappears after `maintain lantern` changes it
to `lit`. The required salve is an ordinary shared item-registry record placed at the compiled
Ravenwatch, so the packet can use an existing item boundary without making the authored-town
loader own a generated room.

## Verification

```text
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_aethryn_actions.py tests/test_aethryn_runtime.py
```

These tests drive the real `handle_command` tick in isolated Aethryn processes, prove refusal
without the required tool, prove both transitions, prove idempotent repeat behavior, check live
projections, check state-gated pressure output, and check persisted state after process exit.
