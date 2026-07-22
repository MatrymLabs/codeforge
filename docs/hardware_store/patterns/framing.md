# Pattern family: Stream Framing

*Tenth family doc for the Hardware Store's pattern shelf. Harvested from the sibling repo
`codeforge-client` (CodeForge_Client_mk1), where a line framer was proven first while building the
MUD client's protocol spine. This is the gap-analysis loop working as designed: a pattern the client
exposed graduates back into the CodeForge Hardware Store as a reusable part.*

## Provenance

- **Origin:** `harvested_pattern`. The client needed to turn arbitrary byte chunks from a Telnet
  socket into whole lines; that framer proved the behavior. This part reimplements the same standard
  framing idea as a general, delimiter-configurable component. **No code was copied.**
- **Why it exists:** the naive `chunk.endswith(delimiter)` splits or drops messages, and
  `endswith(b"")` is always True (a documented CodeForge scar). Framing needs its own buffer.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `stream-framer`

`parts/shelf/stream_framer.py` -- a `StreamFramer`: `feed(chunk)` returns every complete,
delimiter-terminated message the chunk finished (delimiter removed, decoded), holding a partial tail;
`flush()` returns any buffered partial (e.g. a prompt with no trailing delimiter). Delimiter,
encoding, and CR-strip are configurable; an empty delimiter fails loud.

**Invariants (tested):** a message split across two chunks reappears whole; multiple messages in one
chunk all emit; a custom delimiter frames records; flush returns and then clears the tail; invalid
bytes are replaced, never fatal; an empty delimiter is refused.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** a bursty `telegraph` (`parts/telegraph.py`).
- **Core behavior:** reassemble a byte stream into complete messages regardless of chunk boundaries.
- **Game-specific presentation:** "A telegraph arrives, burst by burst:" with clean reframed lines.
- **Reusable domain logic:** the whole `StreamFramer` (game-free).
- **Practical applications:** log tailers, protocol clients, delimited-record ingest.
- **Security implications:** bound the buffer for untrusted streams (a delimiter that never arrives).
- **Testing implications:** split-across-chunks, custom delimiter, partial flush.
- **Hardware Store candidate:** YES (stocked as `stream-framer`).

## Adapters (one core, two lives)

- **Game:** `parts/telegraph.py` -- the `telegraph` verb frames a dispatch delivered in awkward
  bursts into whole lines. Tick-reachable.
- **Practical:** `parts/record_stream.py` -- a `RecordStream` reads delimited records off a byte
  stream fed chunk by chunk, flushing a trailing partial on close.

## Evidence

- Tests: `tests/test_stream_framer.py` (core), `tests/test_telegraph.py` (game + tick),
  `tests/test_record_stream.py` (practical + a one-core proof).
- Manifest: `docs/hardware/stream-framer.yaml`. Trace it: `make loop PART=stream-framer`.
- **Maturity: `beta`** -- proven in two contexts and tested; not `stable` (no max-buffer guard or
  length-prefixed framing yet).

## Deferred (needs Josh's approval)

A bounded-buffer guard and a length-prefixed framing mode are later slices.
