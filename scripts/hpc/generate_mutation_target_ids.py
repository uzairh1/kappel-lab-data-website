"""Generate the UniProt target list for the combined website catalog.

The legacy IDs come directly from the frozen catalog snapshot and the expanded
IDs come from ``expanded_protein_annotations.csv``. Only the resulting
newline-delimited ID file needs to be copied to the HPC system.
"""
from __future__ import annotations

import argparse
import csv
import json
import tarfile
from pathlib import Path


def legacy_ids(path: Path) -> set[str]:
    with tarfile.open(path, mode="r:gz") as archive:
        handle = archive.extractfile("data.json")
        if handle is None:
            raise ValueError(f"Frozen legacy catalog has no data.json: {path}")
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
        "--legacy-catalog",
        "--legacy-data",
        dest="legacy_catalog",
        type=Path,
        default=Path("pipeline/resources/legacy/protein_catalog_snapshot.tar.gz"),
        help="Frozen legacy catalog snapshot",
    )
    parser.add_argument(
        "--expanded-data",
        type=Path,
        default=Path("data/source/expanded_protein_annotations.csv"),
        help="Expanded dataset CSV (default: data/source/expanded_protein_annotations.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/work/mutation_target_uniprot_ids.txt"),
        help="Output ID list (default: data/work/mutation_target_uniprot_ids.txt)",
    )
    args = parser.parse_args()

    old = legacy_ids(args.legacy_catalog)
    expanded = expanded_ids(args.expanded_data)
    combined = old | expanded
    if not old or not expanded or not combined:
        raise SystemExit("Refusing to write an empty legacy, expanded, or combined ID set.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(f"{value}\n" for value in sorted(combined)), encoding="ascii")
    print(f"Legacy proteins:  {len(old)}")
    print(f"Expanded proteins: {len(expanded)}")
    print(f"Overlap:            {len(old & expanded)}")
    print(f"Combined targets:   {len(combined)}")
    print(f"Wrote: {args.output.resolve()}")


if __name__ == "__main__":
    main()
