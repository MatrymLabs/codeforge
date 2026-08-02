"""CARD: probabilistic -- space-efficient probabilistic data structures with provable error bounds.

The first rung of the R&D **Algorithms Lab**, opened by the "CodeForge Knowledge
Assimilation Corpus" master survey (2026-08-01). That corpus ranks probabilistic
structures #3 of its top-25 highest-value items to ingest, and a fleet search confirmed
they are genuinely absent (the only "bloom" in codeforge is a spring flower). These are
the canonical members-and-counts sketches:

- **BloomFilter** - space-efficient set membership. NO false negatives (a definite "no"
  is always true); a tunable, MEASURED false-positive rate is the price of the space win.
- **HyperLogLog** - cardinality (distinct-count) estimation in a fixed tiny footprint,
  with standard error 1.04/sqrt(m) (Flajolet, Fusy, Gandouet & Meunier 2007).
- **CountMinSketch** - frequency (heavy-hitter) estimation that OVER-estimates only, never
  under (Cormode & Muthukrishnan 2005).

Honesty contract (the load-bearing property): these are APPROXIMATE by design, and the
error is *provable, not guesswork*. Each structure states its one-sided guarantee and its
error bound in the open. No estimate is presented as an exact count. Clean-room, stdlib
only (`hashlib`, `math`): the hash functions are the seam, the formulas are textbook.

Items are hashed as BYTES (str encodes UTF-8, int stringifies); hashing is
case-preserving, so "Pass" and "pass" are distinct members - no case-mangling, in keeping
with the fleet's secrets-are-never-case-mangled law.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

__all__ = [
    "BloomFilter",
    "CountMinSketch",
    "HyperLogLog",
    "ProbabilisticError",
]


class ProbabilisticError(ValueError):
    """Raised on out-of-range parameters or unhashable items. Fails loud and early."""


Item = str | bytes | int


def _to_bytes(item: Item) -> bytes:
    """Normalize a supported item to bytes. Anything else fails loud."""
    if isinstance(item, bytes):
        return item
    if isinstance(item, str):
        return item.encode("utf-8")
    if isinstance(item, bool):  # bool is an int subclass; reject it explicitly as ambiguous
        raise ProbabilisticError("bool is not a supported item (did you mean 0/1?)")
    if isinstance(item, int):
        return str(item).encode("ascii")
    raise ProbabilisticError(
        f"unsupported item type: {type(item).__name__} (use str, bytes, or int)"
    )


def _digest64(data: bytes, seed: int = 0) -> int:
    """A fast 64-bit hash of data under a seed, via BLAKE2b's native salt/person channels."""
    h = hashlib.blake2b(data, digest_size=8, person=seed.to_bytes(8, "little"))
    return int.from_bytes(h.digest(), "little")


# --------------------------------------------------------------------------------------
# BloomFilter -- membership, no false negatives
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BloomParams:
    """The sizing a (capacity, target-fpr) request resolves to. Exposed for defensibility."""

    capacity: int
    target_fpr: float
    num_bits: int
    num_hashes: int


class BloomFilter:
    """Space-efficient set membership with NO false negatives.

    Size from the capacity you expect and the false-positive rate you will tolerate;
    the optimal bit count m and hash count k are computed from the textbook formulas
    (m = -n*ln(p)/(ln 2)^2, k = round(m/n * ln 2)). Two independent hashes are combined
    by double hashing (Kirsch & Mitzenmacher 2006) so k probes cost one digest.
    """

    def __init__(self, capacity: int, false_positive_rate: float = 0.01) -> None:
        if capacity <= 0:
            raise ProbabilisticError(f"capacity must be >= 1, got {capacity}")
        if not (0.0 < false_positive_rate < 1.0):
            raise ProbabilisticError(
                f"false_positive_rate must be in (0, 1), got {false_positive_rate}"
            )
        num_bits = math.ceil(-capacity * math.log(false_positive_rate) / (math.log(2) ** 2))
        num_bits = max(num_bits, 1)
        num_hashes = max(1, round((num_bits / capacity) * math.log(2)))
        self.params = BloomParams(capacity, false_positive_rate, num_bits, num_hashes)
        self._bits = bytearray((num_bits + 7) // 8)
        self._count = 0

    def _positions(self, item: Item) -> list[int]:
        data = _to_bytes(item)
        h1 = _digest64(data, seed=0)
        h2 = _digest64(data, seed=1) | 1  # odd, so the step never collapses the cycle
        m = self.params.num_bits
        return [(h1 + i * h2) % m for i in range(self.params.num_hashes)]

    def add(self, item: Item) -> None:
        """Record an item. Idempotent by set semantics."""
        for pos in self._positions(item):
            self._bits[pos >> 3] |= 1 << (pos & 7)
        self._count += 1

    def __contains__(self, item: Item) -> bool:
        """True = 'probably present' (may be a false positive); False = 'definitely absent'."""
        return all(self._bits[pos >> 3] & (1 << (pos & 7)) for pos in self._positions(item))

    def __len__(self) -> int:
        """Number of add() calls (insertions), not distinct items."""
        return self._count

    def estimated_fpr(self) -> float:
        """The current false-positive probability, (1 - e^(-k*n/m))^k, given what's inserted."""
        k, n, m = self.params.num_hashes, self._count, self.params.num_bits
        return (1.0 - math.exp(-k * n / m)) ** k


# --------------------------------------------------------------------------------------
# HyperLogLog -- cardinality estimation
# --------------------------------------------------------------------------------------


class HyperLogLog:
    """Distinct-count estimation in a fixed tiny footprint.

    Precision p in [4, 16] gives m = 2^p one-byte registers and a standard error of
    1.04/sqrt(m) (e.g. p=14 -> 16384 registers, ~0.8% error, ~16 KB). Uses 64-bit hashes
    with linear-counting correction in the small-cardinality range (Flajolet et al. 2007).
    """

    def __init__(self, precision: int = 14) -> None:
        if not (4 <= precision <= 16):
            raise ProbabilisticError(f"precision must be in [4, 16], got {precision}")
        self.precision = precision
        self.num_registers = 1 << precision
        self._registers = bytearray(self.num_registers)

    @property
    def standard_error(self) -> float:
        """The relative standard error of the estimate: 1.04 / sqrt(m)."""
        return 1.04 / math.sqrt(self.num_registers)

    def _alpha(self) -> float:
        m = self.num_registers
        if m == 16:
            return 0.673
        if m == 32:
            return 0.697
        if m == 64:
            return 0.709
        return 0.7213 / (1.0 + 1.079 / m)

    def add(self, item: Item) -> None:
        x = _digest64(_to_bytes(item))
        index = x >> (64 - self.precision)
        suffix_bits = 64 - self.precision
        w = x & ((1 << suffix_bits) - 1)
        # rho = position of the leftmost 1-bit in the suffix (1-indexed), or suffix+1 if all zero.
        rho = suffix_bits + 1 if w == 0 else suffix_bits - w.bit_length() + 1
        self._registers[index] = max(self._registers[index], rho)

    def cardinality(self) -> int:
        m = self.num_registers
        raw = self._alpha() * m * m / sum(2.0**-r for r in self._registers)
        if raw <= 2.5 * m:  # small-range: switch to linear counting if any register is empty
            zeros = self._registers.count(0)
            if zeros:
                return round(m * math.log(m / zeros))
        return round(raw)

    def __len__(self) -> int:
        return self.cardinality()


# --------------------------------------------------------------------------------------
# CountMinSketch -- frequency estimation, over-estimates only
# --------------------------------------------------------------------------------------


class CountMinSketch:
    """Frequency (heavy-hitter) estimation that never UNDER-counts.

    Size from an error factor epsilon and a failure probability delta: width
    w = ceil(e/epsilon), depth d = ceil(ln(1/delta)). The estimate for any key is at most
    the true count + epsilon*N with probability 1 - delta (Cormode & Muthukrishnan 2005),
    so it over-estimates on hash collisions but is guaranteed never to miss.
    """

    def __init__(self, epsilon: float = 0.001, delta: float = 0.001) -> None:
        if not (0.0 < epsilon < 1.0):
            raise ProbabilisticError(f"epsilon must be in (0, 1), got {epsilon}")
        if not (0.0 < delta < 1.0):
            raise ProbabilisticError(f"delta must be in (0, 1), got {delta}")
        self.epsilon = epsilon
        self.delta = delta
        self.width = math.ceil(math.e / epsilon)
        self.depth = math.ceil(math.log(1.0 / delta))
        self._rows = [[0] * self.width for _ in range(self.depth)]
        self._total = 0

    def _columns(self, data: bytes) -> list[int]:
        return [_digest64(data, seed=row) % self.width for row in range(self.depth)]

    def add(self, item: Item, count: int = 1) -> None:
        """Add `count` occurrences of an item. A negative count is refused (it would break
        the never-under-count guarantee)."""
        if count < 0:
            raise ProbabilisticError(f"count must be >= 0, got {count}")
        data = _to_bytes(item)
        for row, col in enumerate(self._columns(data)):
            self._rows[row][col] += count
        self._total += count

    def estimate(self, item: Item) -> int:
        """The estimated frequency: the minimum across rows (>= the true count, never less)."""
        data = _to_bytes(item)
        return min(self._rows[row][col] for row, col in enumerate(self._columns(data)))

    @property
    def total(self) -> int:
        """The total mass added (sum of all counts). N in the epsilon*N error term."""
        return self._total
