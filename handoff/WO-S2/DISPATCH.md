# DISPATCH WO-S2

**Status:** LANDED, codeforge #929, 2026-08-12. Merged after four tests were added on top: its dropped-field criterion was unprotected, and the schema can now no longer silently lose a field.

```yaml
packet_id:            WO-S2
title:                The wire protocol is a schema over a transport that already exists
stream:               engine-2d seam
owner:                Codex
reviewer:             Claude Code (re-runs every command independently)
merges:               founder
size:                 medium
flight:               M2 Engine Real
leg:                  2E
queue_position:       2. CX-009 first; take this when it is returned or blocked.

goal: >
  Define and enforce a VERSIONED JSON message contract between the CodeForge server and a future
  Godot client, carried over the WebSocket transport this engine already serves. The schema is the
  artifact both sides import; a server change that drops a field a client reads must fail a
  SERVER-side test, not the client at runtime in a language the server's suite cannot see.

named_consumers:
  - engine-2d client   the Godot spike (WO-S3), not yet written
  - codeforge server   adapters/web_gateway.py, the existing FastAPI app

prior_research: >
  ship reports/2026-08-12-demand-map-track-b.md and the Phase 2 demand map. The Twin Engine Sprint
  section 7 calls the wire schema "the one artifact both sides import; treat it as a shared
  contract... one agent changes it at a time, coordinated, both sides landed together". That asks
  for coordination by DISCIPLINE. This packet makes it mechanical.

preconditions: >
  CHECK: file adapters/web_gateway.py exists
  CHECK: file kernel/engine_seam.py contains class Engine2DStub

  THE ORIGINAL ORDER WAS WRONG AND THIS ONE CORRECTS IT. The sprint says "stand up a WebSocket
  endpoint on CodeForge". One exists: adapters/web_gateway.py, FastAPI, /ws mounted, seat cap and
  idle timeout already in place because it was built hostile to abuse for a public demo. Standing
  up a second driver would duplicate it, and the engine's law says handle_command is the only door.

  Confirm before starting:
    grep -n '@app.websocket' adapters/web_gateway.py     -> /ws exists
    grep -n 'kernel/shelf/contract.py' -r kernel/         -> Contract Jig exists

verification_command: |
  cd /home/josh/Projects/MatrymLabs/codeforge
  export PATH="$PWD/.venv/bin:$PATH"
  make check

definition_of_done: >
  a versioned message schema exists for hello / move_intent / entity_state / tick; every message
  carries its schema version; an unknown or mismatched version is REFUSED with a verdict rather
  than parsed hopefully; a consumer contract is registered via kernel/shelf/contract.py and a
  SERVER-side test fails when a declared field is dropped or retyped; make check green.

out_of_scope: >
  The Godot client. That is WO-S3 and does not exist yet.
  Rendering, interpolation, sprites, tiles. None of it.
  Modifying the demo gate's ritual, seat cap, or idle timeout. Those protect a PUBLIC demo from
  abuse and a game route is not a demo visitor; see the design note below.
  handle_command. It stays the only door. This packet frames messages, it does not add a door.

approval_gates: >
  Founder merges. No self-certification. If the schema cannot express something the seam needs
  without reaching below it into position representation, STOP and report it: that is a seam
  finding and it belongs to the founder, not to a workaround at the bench.

rollback: >
  git revert the merge commit. The route is additive; the demo gate is untouched.

boundary: >
  Computed by packet_gate: 7 first-party modules imported by the allowlisted files and not
  changeable here.

  adapters/gateway.py is the important exclusion. The wire protocol is a SCHEMA and a version, not
  a transport rewrite; the existing gateway already carries WebSocket traffic and the demand map
  recorded it as EXISTS, do not rebuild. If this order finds itself needing to edit the gateway, the
  schema has grown into a transport change and that is a block, not a widening.

  accounts, characters, events, jobs, seed, session are read by the protocol's payloads and define
  none of it. The schema describes what they already produce.

file_allowlist:
  - kernel/seam/wire.py                     # NEW. the schema, versions, and refusal
  - kernel/seam/__init__.py                 # NEW if needed
  - tests/test_wire_protocol.py             # NEW. contract tests, verbatim below
  - adapters/web_gateway.py                 # the sibling route ONLY. See the design note
  - registry/designations/modules.json      # the completeness gate will demand the new module
  - handoff/WO-S2/RETURN.md                 # NEW, explicitly authorised

contract_tests:       tests/test_wire_protocol.py
contract_test_policy: |
  ASSERTION-LOCKED. Create exactly. You may ADD. If an assertion is wrong, STOP and say so.

return_artifact:      handoff/WO-S2/RETURN.md
return_authorisation: |
  EXPLICITLY AUTHORISED. Required. Extraction block may not be blank.

store_search_result: |
  SEARCHED BOTH TIERS, logged in the demand map, and the result is IN this packet rather than left
  for you: Certified Tier has no wire/schema/envelope part. Working Shelf has `Contract Jig`
  (kernel/shelf/contract.py), `Typed API Contract` (adapters/api.py, Pydantic at the edge), and
  `Validated Loader` (schema gate at load). Re-run the search to confirm, and judge Typed API
  Contract and Validated Loader on their cards; I judged only Contract Jig.

parts_to_consume: |
  `Contract Jig`, CONSUMED WHERE IT SITS, not moved or extracted. Its card: "a CONSUMER declares a
  Contract: the fields and types it reads... the PROVIDER's own test verifies its actual response
  satisfies every registered consumer contract, so dropping or retyping a field a client needs
  fails a test on the provider side". That is exactly this packet's problem. Tolerant reader: extra
  server fields are fine, missing or retyped ones are not, which is the correct posture for a
  protocol that will version forward.

watch_for: |
  The Godot client is GDScript and cannot literally declare a Python Contract. The contract is
  therefore declared in Python ON BEHALF of the client, from the schema. Say in the RETURN whether
  that is honest or whether it merely moves the coordination problem, because a contract the
  consumer does not actually write is a weaker guarantee than Contract Jig's card describes.
```

## The design decision, made here so you do not have to guess

**Mount a SIBLING route on the existing FastAPI app. Do not build a second driver, and do not
change the demo gate.**

`web_gateway.py` runs the front-desk-then-tick ritual over WS TEXT frames for a browser terminal.
The Engine-2D client speaks structured JSON. Same transport, different protocol, so they are
sibling routes on one app rather than one route serving two grammars.

The demo gate's seat cap, idle timeout, and ephemeral database exist because a link on a resume
must not be farmable. A game client is not an anonymous demo visitor and should not inherit that
policy by accident, nor should the demo lose it because a game route was added beside it. **Two
routes, two policies, one app, one door.**

## Invariant

**Every message carries its schema version, and a version the server does not know is refused
rather than parsed hopefully.**

A protocol that guesses at an unknown message is a protocol that will one day act on a message from
a client three versions ahead of it.

## The contract tests, verbatim

Create `tests/test_wire_protocol.py` with exactly this content.

```python
"""The wire protocol: versioned messages, refused when unknown, pinned by a consumer contract.

The sprint calls the schema "the one artifact both sides import" and asks for coordination by
discipline. This makes it mechanical: the client's declared reads are registered as a Contract, and
the SERVER's own test fails when a field it promised disappears. Without that, a protocol change
breaks the client at runtime, in a language the server's suite cannot see, across a process and a
machine boundary. That is the worst available place to discover a contract break.
"""

from __future__ import annotations

import pytest

from kernel.seam.wire import (
    WIRE_VERSION,
    WireRefused,
    decode,
    encode,
    hello,
)


def test_every_message_carries_its_version() -> None:
    assert encode(hello(session="s1"))["v"] == WIRE_VERSION


def test_a_message_from_an_unknown_version_is_REFUSED_not_parsed() -> None:
    """A protocol that guesses will one day act on a message three versions ahead of it."""
    with pytest.raises(WireRefused):
        decode({"v": WIRE_VERSION + 999, "type": "hello", "session": "s1"})


def test_a_message_with_NO_version_is_refused() -> None:
    """Absent is not 'probably current'."""
    with pytest.raises(WireRefused):
        decode({"type": "hello", "session": "s1"})


def test_an_unknown_message_type_is_refused() -> None:
    with pytest.raises(WireRefused):
        decode({"v": WIRE_VERSION, "type": "not_a_real_message"})


def test_encode_decode_round_trips() -> None:
    original = hello(session="s1")
    assert decode(encode(original)) == original


@pytest.mark.parametrize("hostile", [None, [], "hello", 0, {"v": "one", "type": "hello"}])
def test_a_hostile_payload_is_refused_rather_than_crashing(hostile) -> None:
    """The transport is a network. Everything arriving on it is hostile until parsed."""
    with pytest.raises(WireRefused):
        decode(hostile)


def test_the_client_contract_is_satisfied_by_the_server_message() -> None:
    """Contract Jig, consumed where it sits. The consumer declares what it reads; this test is the
    PROVIDER-side check that the server still sends it."""
    from kernel.seam.wire import CLIENT_CONTRACTS
    from kernel.shelf.contract import verify

    assert CLIENT_CONTRACTS, "a registry with no contracts pins nothing"
    for contract in CLIENT_CONTRACTS:
        sample = encode(hello(session="s1"))
        if contract.name == "hello":
            assert verify(contract, sample) == [], f"the server no longer satisfies {contract.name}"


def test_dropping_a_field_the_client_reads_fails_HERE_not_in_the_client() -> None:
    """The whole point of the packet. A server-side test must catch it."""
    from kernel.seam.wire import CLIENT_CONTRACTS
    from kernel.shelf.contract import verify

    hello_contract = next((c for c in CLIENT_CONTRACTS if c.name == "hello"), None)
    assert hello_contract is not None
    broken = {k: v for k, v in encode(hello(session="s1")).items() if k != "v"}
    assert verify(hello_contract, broken) != [], (
        "a dropped field passed the provider-side contract check, so it would have surfaced in "
        "the Godot client at runtime instead"
    )
```

## Definition of done

```bash
cd /home/josh/Projects/MatrymLabs/codeforge
export PATH="$PWD/.venv/bin:$PATH"
make check
```

Drive the route once and paste the transcript: a client connects, sends `hello`, receives a
versioned reply. A schema demonstrated only by unit test has not been shown to survive the
transport it was written for.
