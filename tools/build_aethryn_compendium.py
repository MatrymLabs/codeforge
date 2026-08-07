#!/usr/bin/env python3
"""Build one source-labeled Markdown compendium for Aethryn design work."""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "aethryn" / "AETHRYN_MASTER_COMPENDIUM.md"
MAP_POSTER = Path(
    "/home/josh/Downloads/Matrym_Labs_Research_Archive_2026-08-02/"
    "a_highly_detailed_fantasy_world_map_poster_layout.png"
)
LONG_DASHES = str.maketrans({"\u2013": " - ", "\u2014": " - "})
FENCE_RE = re.compile(r"`+")


@dataclass(frozen=True)
class Source:
    """One text source included in the compendium."""

    path: Path
    status: str
    role: str


def _normalize(text: str) -> str:
    """Apply the repository's plain-dash rule without changing source meaning."""
    return text.translate(LONG_DASHES)


def _fence(text: str) -> str:
    longest = max((len(match.group()) for match in FENCE_RE.finditer(text)), default=0)
    return "`" * max(3, longest + 1)


def _repo_files(pattern: str) -> list[Path]:
    return sorted(REPO_ROOT.glob(pattern))


def _external_files() -> list[Path]:
    downloads = Path("/home/josh/Downloads")
    if not downloads.is_dir():
        return []
    allowed = {".md", ".txt", ".yaml", ".yml", ".json", ".csv"}
    return sorted(
        path
        for path in downloads.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed and "aethryn" in path.name.casefold()
    )


def collect_sources(include_external: bool = True) -> list[Source]:
    """Collect current, legacy, and external text sources in stable order."""
    groups: list[tuple[str, str, list[Path]]] = [
        (
            "Current canon",
            "Locked or readable current canon",
            [
                REPO_ROOT / "docs/aethryn_lore_bible.md",
                REPO_ROOT / "docs/aethryn_seed_reconciliation.md",
                REPO_ROOT / "content/seeds/aethryn/canon.yaml",
                REPO_ROOT / "content/seeds/aethryn/world.yaml",
            ],
        ),
        (
            "Current Aethryn design records",
            "Design contract, decisions, research, and presentation record",
            [
                path
                for path in _repo_files("docs/aethryn/*")
                if path.name
                not in {
                    "AETHRYN_MASTER_COMPENDIUM.md",
                    "AETHRYN_MASTER_LORE_INDEX.md",
                }
            ],
        ),
        (
            "Current Seed data",
            "Runtime, authored, generated, and room-batch content",
            sorted(
                path
                for pattern in ("content/seeds/aethryn/**/*.yaml", "content/seeds/aethryn/**/*.txt")
                for path in _repo_files(pattern)
            ),
        ),
        (
            "Legacy world library",
            "Superseded fiction or still-live mechanical reference",
            [REPO_ROOT / "docs/world_bible.md", *_repo_files("docs/world/*")],
        ),
    ]
    if include_external:
        groups.append(
            (
                "External Aethryn source material",
                "Unvendored manuscripts and research inputs",
                _external_files(),
            )
        )

    seen: set[Path] = set()
    sources: list[Source] = []
    for status, role, paths in groups:
        for path in paths:
            resolved = path.resolve()
            if (
                resolved in seen
                or not path.is_file()
                or path.suffix.lower()
                not in {
                    ".md",
                    ".txt",
                    ".yaml",
                    ".yml",
                    ".json",
                    ".csv",
                }
            ):
                continue
            seen.add(resolved)
            sources.append(Source(path=path, status=status, role=role))
    return sources


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _source_block(source: Source) -> str:
    raw = source.path.read_text(encoding="utf-8")
    normalized = _normalize(raw)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    fence = _fence(normalized)
    return "\n".join(
        [
            f"### `{_display_path(source.path)}`",
            f"Status: {source.status}",
            f"Role: {source.role}",
            f"SHA-256: `{digest}`",
            f"Lines: {len(raw.splitlines())}",
            "",
            fence + "text",
            normalized.rstrip("\n"),
            fence,
            "",
        ]
    )


def build_compendium(output: Path, *, include_external: bool = True) -> tuple[int, int]:
    sources = collect_sources(include_external=include_external)
    output.parent.mkdir(parents=True, exist_ok=True)
    sections: list[str] = [
        "# Aethryn Master World Compendium",
        "",
        f"Generated: {date.today().isoformat()}",
        "",
        "This is a source-preserving design compendium generated from the current CodeForge Seed, "
        "Aethryn design records, legacy references, and available external manuscripts.",
        "",
        "The compendium is an indexable snapshot, not a replacement for the source files. "
        "Each source is labeled by status and includes its original SHA-256 hash. Long dash "
        "characters are normalized to plain spaced hyphens for repository style.",
        "",
        "## Authority warning",
        "",
        "Current canon is the Netharion and divine-strike design in `canon.yaml` and "
        "`docs/aethryn_lore_bible.md`. The Forge, Ember, and Unforging fiction under "
        "`docs/world_bible.md` and parts of `docs/world/` are legacy alternate lore. They are "
        "included for brainstorming and provenance, not as current canon.",
        "",
        "The supplied fantasy map poster is a visual source. Its machine-readable topology is "
        "`content/seeds/aethryn/world_graph.yaml`. Binary images are referenced in the manifest "
        "but are not embedded in this Markdown file.",
        "",
        "## Source manifest",
        "",
        "| # | Status | Path | SHA-256 | Lines |",
        "| ---: | --- | --- | --- | ---: |",
    ]
    for index, source in enumerate(sources, start=1):
        raw = source.path.read_text(encoding="utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        sections.append(
            f"| {index} | {source.status} | `{_display_path(source.path)}` | "
            f"`{digest[:16]}...` | {len(raw.splitlines())} |"
        )
    if MAP_POSTER.is_file():
        digest = hashlib.sha256(MAP_POSTER.read_bytes()).hexdigest()
        sections.extend(
            [
                "",
                "### Visual source",
                "",
                f"`{MAP_POSTER}`",
                "",
                f"SHA-256: `{digest}`",
            ]
        )
    sections.extend(["", "## Complete source snapshots", ""])
    current_status = ""
    for source in sources:
        if source.status != current_status:
            current_status = source.status
            sections.extend([f"## {current_status}", "", f"{source.role}.", ""])
        sections.append(_source_block(source))
    output.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return len(sources), sum(
        len(source.path.read_text(encoding="utf-8").splitlines()) for source in sources
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-external", action="store_true")
    args = parser.parse_args()
    count, lines = build_compendium(args.output, include_external=not args.no_external)
    print(f"built {args.output}: {count} sources, {lines} source lines")


if __name__ == "__main__":
    main()
