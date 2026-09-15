"""Generate the UniProt target list for the combined website catalog.

The legacy catalog is represented by the already-published ``data.json`` and
the expanded catalog by ``RBP_Dataset.csv``.  Only the resulting newline-
delimited ID file needs to be copied to the HPC system.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def legacy_ids(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig") as handle:
        records = json.load(handle)
    if not isinstance(records, list):
        raise ValueError(f"Legacy data must be a JSON list: {path}")
    ids = {
        str(record.get("uniprot", "")).strip()
        for record in records
        if isinstance(record, dict)
    }
    ids.discard("")
    return ids


def expanded_ids(path: Path, column: str = "uniprot_id") -> set[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or column not in reader.fieldnames:
            raise ValueError(
                f"Expanded dataset is missing required column {column!r}: {path}"
            )
        ids = {str(row.get(column, "")).strip() for row in reader}
    ids.discard("")
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the combined legacy + expanded mutation target list."
    )
    parser.add_argument(
        "--legacy-data",
        type=Path,
        default=Path("dist/data.json"),
        help="Published legacy data.json (default: dist/data.json)",
    )
    parser.add_argument(
        "--expanded-data",
        type=Path,
        default=Path("RBP_Dataset.csv"),
        help="Expanded dataset CSV (default: RBP_Dataset.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("uniprot_ids.txt"),
        help="Output ID list (default: uniprot_ids.txt)",
    )
    args = parser.parse_args()

    old = legacy_ids(args.legacy_data)
    expanded = expanded_ids(args.expanded_data)
    combined = old | expanded
    if not old or not expanded or not combined:
        raise SystemExit("Refusing to write an empty legacy, expanded, or combined ID set.")

    args.output.write_text("".join(f"{value}\n" for value in sorted(combined)), encoding="ascii")
    print(f"Legacy proteins:  {len(old)}")
    print(f"Expanded proteins: {len(expanded)}")
    print(f"Overlap:            {len(old & expanded)}")
    print(f"Combined targets:   {len(combined)}")
    print(f"Wrote: {args.output.resolve()}")


if __name__ == "__main__":
    main()
