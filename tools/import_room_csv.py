#!/usr/bin/env python3
"""Compile a structured CSV room drop into a validated Aethryn room batch."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import yaml

from tools.import_mud_batch import compile_batches

_REQUIRED_COLUMNS = {
    "id",
    "zone",
    "subzone",
    "min_level",
    "max_level",
    "title",
    "room_type",
    "description_one",
    "description_two",
    "visible_one",
    "visible_two",
    "visible_three",
    "exits",
}


def parse_csv(source: Path) -> list[dict[str, Any]]:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        missing = sorted(_REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            label = (row["id"] or "").strip()
            if not label:
                raise ValueError(f"row {row_number} has an empty id")
            if label in seen:
                raise ValueError(f"row {row_number} repeats room id {label!r}")
            seen.add(label)

            exits = [value.strip() for value in (row["exits"] or "").split("|") if value.strip()]
            if not exits:
                raise ValueError(f"row {row_number} has no exits")
            try:
                min_level = int(row["min_level"])
                max_level = int(row["max_level"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"row {row_number} has invalid level bounds") from exc
            if min_level > max_level:
                raise ValueError(f"row {row_number} has reversed level bounds")

            prose = "\n\n".join(
                value.strip()
                for value in (row["description_one"], row["description_two"])
                if value and value.strip()
            )
            if not prose:
                raise ValueError(f"row {row_number} has no room prose")

            records.append(
                {
                    "label": label,
                    "name": row["title"].strip(),
                    "room_type": row["room_type"].strip(),
                    "desc": prose,
                    "source_exits": exits,
                    "occupants": [],
                    "objects": [
                        row["visible_one"].strip().rstrip("."),
                        row["visible_two"].strip().rstrip("."),
                        row["visible_three"].strip().rstrip("."),
                    ],
                    "notes": (
                        f"{row['zone'].strip()} / {row['subzone'].strip()} / "
                        f"levels {min_level}-{max_level}"
                    ),
                }
            )
    if not records:
        raise ValueError("CSV contains no room records")
    return records


def compile_csv(records: list[dict[str, Any]], sequence: int) -> dict[str, Any]:
    batch = compile_batches(records, sequence)[0]
    batch["batch"]["id"] = f"aethryn_voidscar_csv_{sequence:04d}"
    for room in batch["rooms"].values():
        room["tags"] = ["voidscar", "imported_csv_drop"]
    for record in records:
        batch["rooms"][record["label"]]["notes"] = record["notes"]
    return batch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--sequence", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.sequence < 1:
        parser.error("--sequence must be positive")

    records = parse_csv(args.source)
    batch = compile_csv(records, args.sequence)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / f"voidscar_content_batch_{args.sequence:04d}.yaml"
    path.write_text(yaml.safe_dump(batch, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"compiled {path}: {batch['batch']['size']} rooms")


if __name__ == "__main__":
    main()
