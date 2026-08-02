"""Benchmark: the telemetry spine (protobuf vs the JSON reference) on the real frames.

Evidence for the protocol-spine claim -- a typed binary contract is smaller on the wire and faster
to (de)serialise than ad-hoc JSON. Times encode + decode over the four telemetry frames the engine
actually emits, and reports the wire size of each. Frameless (perf_counter + statistics).
Run: `python benchmarks/bench_telemetry.py [iterations]`.

If the protobuf codec is not built (`make proto` not run) it reports the JSON numbers alone, so the
benchmark always runs.
"""

from __future__ import annotations

import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

# Run from anywhere: put the repo root on the path so `proto` (the generated binding) resolves the
# same way it does for the server and the tests, not just `parts` (found by the editable install).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel.telemetry import JSON_CODEC, PROTOBUF_CODEC  # noqa: E402

FRAMES: dict[str, dict[str, object]] = {
    "vitals": {
        "hp": 20,
        "maxhp": 40,
        "mp": 5,
        "maxmp": 10,
        "level": 3,
        "xp": 150,
        "nextlevel": 300,
    },
    "room": {
        "num": "forge",
        "name": "The Cold Forge",
        "exits": {"north": "courtyard", "east": "tunnel"},
    },
    "target": {
        "name": "A cinder wight",
        "hp": 30,
        "maxhp": 100,
        "element": "flame",
        "resists": {"stone": "Resist"},
    },
    "quest": {"name": "Relight the Beacons", "objective": "reach Emberreach"},
}


def _median_us(fn: Callable[[], object], iters: int) -> float:
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        for _ in range(iters):
            fn()
        samples.append((time.perf_counter() - start) / iters * 1_000_000)  # microseconds per op
    return statistics.median(samples)


def main() -> None:
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
    codecs = [("json", JSON_CODEC)]
    if PROTOBUF_CODEC is not None:
        codecs.append(("protobuf", PROTOBUF_CODEC))

    print(f"telemetry spine benchmark -- {iters:,} iterations per frame\n")
    print(f"  {'frame':>7}   {'codec':>9}   {'bytes':>6}   {'encode(us)':>11}   {'decode(us)':>11}")
    for kind, payload in FRAMES.items():
        for name, codec in codecs:
            blob = codec.encode(kind, payload)
            enc = _median_us(lambda c=codec, k=kind, p=payload: c.encode(k, p), iters)
            dec = _median_us(lambda c=codec, b=blob: c.decode(b), iters)
            print(f"  {kind:>7}   {name:>9}   {len(blob):>6}   {enc:>11.3f}   {dec:>11.3f}")
        print()

    if PROTOBUF_CODEC is None:
        print("(protobuf codec not built -- JSON reference numbers only; run `make proto`)")
    else:
        # a single-line honest summary of the size win on the whole frame set
        j = sum(len(JSON_CODEC.encode(k, p)) for k, p in FRAMES.items())
        pbf = sum(len(PROTOBUF_CODEC.encode(k, p)) for k, p in FRAMES.items())
        print(
            f"total wire size -- json: {j} bytes   protobuf: {pbf} bytes   ({j / pbf:.2f}x smaller)"
        )


if __name__ == "__main__":
    main()
