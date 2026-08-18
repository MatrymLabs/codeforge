"""CARD: currency -- the declared inventory of pinned tools, read from where they are pinned.

The inventory names WHERE each pin lives and how to recognise it, then reads the value off disk.
It never carries a copy of the version.

That is the whole design decision, and it is the one that keeps this honest. A hand-maintained
list of "what we pin" is a second source of truth, and a second source of truth about versions
drifts the moment somebody bumps a pin and forgets the list. Then the audit reports confidently
on numbers the repository no longer uses.

A pattern that stops matching is UNVERIFIABLE, never absent and never a pass. If a pin moves to a
new file or changes shape, the audit says so loudly instead of quietly auditing nine tools where
it used to audit ten. Silent shrinkage is how a gate stops covering things without ever failing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CI = ".github/workflows/ci.yml"
GRADLE_BUILD = "native/rider-retroforge/build.gradle.kts"
GRADLE_WRAPPER = "native/rider-retroforge/gradle/wrapper/gradle-wrapper.properties"

GO_PROXY = "https://proxy.golang.org/{module}/@latest"
GH_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
HASHICORP = "https://releases.hashicorp.com/{product}/index.json"


@dataclass(frozen=True)
class Tool:
    """One pinned tool, resolved against the working tree: where its pin lives, and what it says."""

    name: str
    pinned: str
    where: str
    ecosystem: str
    locator: str


@dataclass(frozen=True)
class PinSite:
    """One pin: the file it lives in, the pattern that finds it, and its source of truth."""

    name: str
    file: str
    pattern: str
    ecosystem: str
    locator: str


#: Every pinned tool the fleet installs. Adding a tool here is how it joins the audit.
#:
#: The ecosystem column is load-bearing, not decoration. `govulncheck` MUST resolve through the
#: Go module proxy: golang.org/x/vuln is developed at go.googlesource.com and its GitHub mirror
#: does not carry every release, so GitHub reports v1.1.4 as latest while the proxy correctly
#: reports v1.7.0. Ask the wrong source and a current pin reads as six versions ahead of upstream.
PIN_SITES: tuple[PinSite, ...] = (
    PinSite(
        "gitleaks",
        CI,
        r"GITLEAKS_VER=([\d.]+)",
        "github-release",
        GH_LATEST.format(repo="gitleaks/gitleaks"),
    ),
    PinSite(
        "trivy",
        CI,
        r"TRIVY_VER=([\d.]+)",
        "github-release",
        GH_LATEST.format(repo="aquasecurity/trivy"),
    ),
    PinSite(
        "terraform", CI, r"TF_VER=([\d.]+)", "hashicorp", HASHICORP.format(product="terraform")
    ),
    PinSite(
        "golangci-lint",
        CI,
        r"golangci-lint@v([\d.]+)",
        "github-release",
        GH_LATEST.format(repo="golangci/golangci-lint"),
    ),
    PinSite(
        "govulncheck",
        CI,
        r"govulncheck@v([\d.]+)",
        "go-proxy",
        GO_PROXY.format(module="golang.org/x/vuln"),
    ),
    PinSite(
        "protoc-gen-go",
        CI,
        r"protoc-gen-go@v([\d.]+)",
        "go-proxy",
        GO_PROXY.format(module="google.golang.org/protobuf"),
    ),
    PinSite(
        "kotlin",
        GRADLE_BUILD,
        r'kotlin\("jvm"\) version "([\d.]+)"',
        "github-release",
        GH_LATEST.format(repo="JetBrains/kotlin"),
    ),
    PinSite(
        "detekt",
        GRADLE_BUILD,
        r'detekt"\) version "([\d.]+)"',
        "github-release",
        GH_LATEST.format(repo="detekt/detekt"),
    ),
    PinSite(
        "ktlint-gradle",
        GRADLE_BUILD,
        r'ktlint"\) version "([\d.]+)"',
        "github-release",
        GH_LATEST.format(repo="JLLeitschuh/ktlint-gradle"),
    ),
    PinSite(
        "gradle",
        GRADLE_WRAPPER,
        r"gradle-([\d.]+)-bin",
        "github-release",
        GH_LATEST.format(repo="gradle/gradle"),
    ),
)


def find_pin(repo: Path, site: PinSite) -> str | None:
    """The pinned version as it is on disk right now, or None if the pattern no longer matches."""
    path = repo / site.file
    if not path.is_file():
        return None
    matches = re.findall(site.pattern, path.read_text(encoding="utf-8"))
    return str(matches[0]) if matches else None


def read_inventory(repo: Path) -> list[Tool]:
    """Every pin site, resolved against the working tree."""
    tools = []
    for site in PIN_SITES:
        found = find_pin(repo, site)
        tools.append(
            Tool(
                name=site.name,
                pinned=found or "NOT-FOUND",
                where=site.file,
                ecosystem=site.ecosystem if found else "unresolvable",
                locator=site.locator,
            )
        )
    return tools


def unmatched_pins(repo: Path) -> list[str]:
    """Pin sites whose pattern found nothing. Used by the test twin to fail loudly on drift."""
    return [site.name for site in PIN_SITES if find_pin(repo, site) is None]
