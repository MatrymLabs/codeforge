"""CARD: currency_audit -- is every pinned tool still the current one, and can we prove it.

The fleet pins its toolchain hard, which is correct: an unpinned tool makes a build
irreproducible and hands a supply-chain attacker a moving target. But a pin has a second life
nobody schedules. It stops being "the version we chose" and becomes "the version we happened to
stop looking at", and nothing in the repository can tell those two apart. A pin does not rot
loudly. It just quietly ages while every gate stays green.

So this reports drift, and REFUSES TO GUESS. Three verdicts, never a boolean:

    CURRENT       the pin equals what upstream publishes today
    BEHIND        upstream is ahead; the gap is named, the decision is a human's
    UNVERIFIABLE  we could not reach or parse the source. NOT current, NOT behind, and
                  deliberately not silent, because "I could not check" reported as "fine" is
                  the exact failure this file exists to prevent

THE AUTHORITATIVE SOURCE DIFFERS PER ECOSYSTEM, and getting that wrong invents defects. Written
against a real near-miss: `govulncheck` is pinned at v1.7.0, and GitHub's releases API reports
golang/vuln's latest as v1.1.4, which reads as a pin six minor versions AHEAD of upstream. Both
numbers are true. golang.org/x/vuln is developed at go.googlesource.com and its GitHub mirror
simply does not carry every release. The Go module proxy says v1.7.0 is latest, and the proxy is
canonical for Go modules. A naive one-source checker would have filed a confident, wrong finding.

Consume-first (ADR-0005), logged: the Certified Tier's `source-monitor` (PRT-0003) was searched
first and read. It is the right Part for "watch a locator and classify what changed against a
snapshot", and this audit deliberately borrows its central discipline -- the injected `fetch`
seam, so the logic is testable with no network. It is NOT consumed wholesale, because it answers
"did this source change since last time" and the question here is "is our pin behind the current
release", which is a comparison it does not model. Half a fit, taken as half.

Network-bound, so this is NOT part of `make check`. `make currency` runs it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kernel.currency import Tool, read_inventory  # noqa: E402  (after the sys.path bootstrap)

#: The injected seam. Same shape source-monitor uses, and for the same reason: a checker that can
#: only be exercised against the live internet is a checker nobody runs in a test.
Fetch = Callable[[str], bytes]

CURRENT = "CURRENT"
BEHIND = "BEHIND"
UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class Verdict:
    tool: str
    pinned: str
    latest: str | None
    status: str
    detail: str

    def render(self) -> str:
        latest = self.latest or "-"
        return (
            f"  [{self.status:12}] {self.tool:16} pinned {self.pinned:12} "
            f"latest {latest:12} {self.detail}"
        )


def _normalise(version: str) -> tuple[int, ...]:
    """`v1.34.2` and `1.34.2` compare equal. Trailing junk is dropped, never guessed at."""
    digits = re.findall(r"\d+", version)
    return tuple(int(part) for part in digits[:4])


def http_fetch(locator: str) -> bytes:
    """The real seam. Every caller in this module goes through the injected one instead.

    HTTPS ONLY, checked rather than assumed. `urlopen` honours whatever scheme it is handed,
    including `file:` and `ftp:`, so a locator that reached this function from anywhere less
    trustworthy than the declared inventory could read the local disk and have its contents
    parsed as a version. bandit flags exactly this (B310) and it is a real finding, not noise:
    the fix is to constrain the scheme, not to silence the check.
    """
    if not locator.startswith("https://"):
        raise ValueError(f"refusing a non-HTTPS locator: {locator!r}")
    request = urllib.request.Request(locator, headers={"User-Agent": "matrym-currency-audit"})  # noqa: S310
    # nosec B310 -- the scheme is validated immediately above, which is the risk B310 names.
    # bandit blacklists the urlopen CALL and cannot see the guard, so the suppression is here
    # rather than the check being weakened. Reason recorded per the no-silent-suppression rule.
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310  # nosec B310
        return response.read()


def latest_from_go_proxy(payload: bytes) -> str:
    """The Go module proxy. Canonical for Go modules; GitHub releases are a mirror and lag."""
    return str(json.loads(payload)["Version"])


def latest_from_github_release(payload: bytes) -> str:
    return str(json.loads(payload)["tag_name"])


def latest_from_hashicorp(payload: bytes) -> str:
    """HashiCorp's release index. Pre-releases are excluded; a beta is not a version we pin to."""
    versions = [v for v in json.loads(payload)["versions"] if re.fullmatch(r"[\d.]+", v)]
    if not versions:
        raise ValueError("no stable versions in the HashiCorp index")
    return max(versions, key=_normalise)


RESOLVERS: dict[str, Callable[[bytes], str]] = {
    "go-proxy": latest_from_go_proxy,
    "github-release": latest_from_github_release,
    "hashicorp": latest_from_hashicorp,
}


def audit(tools: list[Tool], fetch: Fetch) -> list[Verdict]:
    """Classify every tool. A fetch or parse failure is a VALUE, never an exception."""
    verdicts = []
    for tool in tools:
        resolver = RESOLVERS.get(tool.ecosystem)
        if resolver is None:
            verdicts.append(
                Verdict(
                    tool.name, tool.pinned, None, UNVERIFIABLE, f"no resolver for {tool.ecosystem}"
                )
            )
            continue
        try:
            latest = resolver(fetch(tool.locator))
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as exc:
            verdicts.append(
                Verdict(tool.name, tool.pinned, None, UNVERIFIABLE, f"{type(exc).__name__}: {exc}")
            )
            continue

        if _normalise(latest) == _normalise(tool.pinned):
            verdicts.append(Verdict(tool.name, tool.pinned, latest, CURRENT, tool.where))
        else:
            verdicts.append(Verdict(tool.name, tool.pinned, latest, BEHIND, tool.where))
    return verdicts


def render(verdicts: list[Verdict]) -> str:
    behind = [v for v in verdicts if v.status == BEHIND]
    unknown = [v for v in verdicts if v.status == UNVERIFIABLE]
    lines = ["Toolchain currency :: every pin, against the source that is canonical for it", ""]
    lines += [v.render() for v in verdicts]
    current = len(verdicts) - len(behind) - len(unknown)
    summary = f"VERDICT: {current} current, {len(behind)} behind, {len(unknown)} UNVERIFIABLE"
    lines += ["", summary]
    if unknown:
        lines.append(
            "  UNVERIFIABLE is not a pass. A pin nobody could check is a pin nobody checked."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when anything is BEHIND (default: only UNVERIFIABLE fails)",
    )
    args = parser.parse_args(argv)

    verdicts = audit(read_inventory(REPO), http_fetch)
    print(render(verdicts))

    if any(v.status == UNVERIFIABLE for v in verdicts):
        return 2
    if args.strict and any(v.status == BEHIND for v in verdicts):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
