# ADR-0012: The protocol spine (a language-neutral typed contract)

Status: Accepted (2026-07-28)

## Context

ADR-0010 (in-process kernels) and ADR-0011 (out-of-process service organs) each admit a *single*
other-language component behind a Python fallback. As the polyglot organs multiply (Rust, C++, Go,
...), they need a way to **talk to each other** without every pair inventing its own wire format. The
telemetry the engine already projects to a client -- Char.Vitals, Room.Info, Char.Target, Char.Quest
-- is the natural first payload: it is emitted today as ad-hoc JSON dicts (`parts/gmcp.py`), untyped
and language-specific by convention only.

A **protocol spine** is the keystone: one schema, defined once, compiled to every language, so a frame
encoded by any organ decodes field-for-field in any other. It is what turns a pile of one-off organs
into services that share a contract.

## Decision

Adopt **Protocol Buffers** as the spine's contract language. One `.proto`
(`proto/telemetry.proto`) is the single source of truth, compiled to Python and Go (C++ later) from
that one file. The spine keeps the same guarantees as the accelerator ADRs, applied to a *contract*
rather than an implementation:

1. **Python-first with a fallback.** The capability ships as a pure-Python **JSON codec** first
   (`parts.telemetry.JsonCodec`), always available. The protobuf codec is *optional*: when the
   generated binding is not built, the spine still encodes/decodes via JSON and `make check` is green
   with no protobuf toolchain.
2. **A narrow, identical interface.** Both codecs expose the same `(kind, payload) <-> bytes`
   contract, so protobuf is a drop-in swap (`default_codec()` prefers it when built).
3. **A parity test.** When the binding is built, a test pins the protobuf codec to the JSON reference
   (same frame in, same frame out) AND -- the crown jewel -- proves **cross-language byte
   compatibility**: a frame encoded by the Go binding decodes in Python and vice versa
   (`tests/test_telemetry.py` driving `native/spine/xcheck`). One `.proto`, two languages, one wire.
4. **Committed benchmark evidence.** `benchmarks/bench_telemetry.py` records the measured benefit on
   the real frames. Measured 2026-07-28 (Pi): protobuf is **2.53x smaller on the wire** (420 -> 166
   bytes across the four frames; Char.Vitals 101 -> 18) and faster to encode; decode is a wash on the
   map-bearing frames. Honest label: **verified improvement** on wire size + encode.
5. **Governance.** Protocol Buffers, protoc, and protoc-gen-go are recorded in `intake_ledger.toml`
   and pass `make intake`; the protobuf runtime is confined to the optional spine path + its CI job,
   never added to the game's runtime dependency set.
6. **Isolation.** The `.proto` (source of truth) and `go.sum` are committed; the generated bindings
   (`proto/telemetry_pb2.py`, `native/spine/telemetrypb`) are git-ignored and rebuilt via `make proto`;
   a dedicated, **non-required** CI job (`spine`) generates, builds, and parity-tests both languages,
   so the main gate never blocks on the protobuf toolchain.

The live client's GMCP frames stay JSON: the spine is the typed transport for cross-language services,
proven to carry the exact frames `parts/gmcp.py` emits, not a rip-out of the client wire.

## Consequences

- **Positive:** the polyglot organs now share ONE typed contract instead of ad-hoc per-pair formats;
  the "cross-language" claim is proven end-to-end (a Go-encoded frame decodes in Python in CI), not
  asserted; the wire is smaller and the frames are typed; and the spine unlocks the organs after it
  (a Go telemetry channel, SQL analytics, a C kernel) with a schema already in place.
- **Costs / risks:** a codegen step (protoc + protoc-gen-go) and a protobuf runtime in the optional
  path; a schema to keep in step with `parts/gmcp.py`; generated code to rebuild on a schema change.
  All bounded by the JSON fallback: if the binding is absent or stale, the spine runs on JSON and the
  game is unaffected.
- **Exit:** delete `proto/`, `native/spine/`, and the protobuf branch of `parts.telemetry`; the JSON
  codec becomes the sole implementation with no other change.
