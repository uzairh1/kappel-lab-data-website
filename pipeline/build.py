"""Single entry point for building website data products from source datasets."""
import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import default_paths
from pipeline.steps.canonical import build_canonical_records
from pipeline.steps.details import write_details
from pipeline.steps.proteins import write_outputs
from pipeline.steps.variants import build_variant_stats_map
from pipeline.steps.tissues import write_tissues
from pipeline.validation.validate import run as validate


def build(root: Path, *, validate_outputs: bool = True, run_variant_stats: bool = True):
    paths = default_paths(root)
    missing = [p for p in (paths.mini_dataset, paths.variant_stats) if not p.exists()]
    if missing:
        print("Cannot build: required source file(s) are missing:")
        for path in missing:
            print(f"  - {path}")
        return 2

    print(f"[1/5] Loading source data")
    df = pd.read_csv(paths.mini_dataset)
    variant_map = build_variant_stats_map(paths.variant_stats) if run_variant_stats else {}

    print("[2/5] Building canonical protein records")
    records, skipped = build_canonical_records(df, variant_stats_map=variant_map)
    print(f"  proteins: {len(records)}; skipped rows: {len(skipped)}")
    if skipped:
        for item in skipped[:10]:
            print(f"  SKIPPED row {item['row']}: {item['error']}")
        if len(skipped) > 10:
            print(f"  ... and {len(skipped) - 10} more")

    print("[3/5] Writing website JSON products")
    write_outputs(records, paths.data_json, paths.diseases_json)
    write_details(records, paths.protein_details)
    write_tissues(records, paths.tissues)

    print("[4/5] Reporting supplemental variant statistics")
    matched = sum(r.variant_stats is not None for r in records)
    unmatched = len(records) - matched
    print(f"  matched: {matched} / {len(records)}")
    print(f"  unmatched: {unmatched}")

    print("[5/5] Validating generated outputs")
    if validate_outputs:
        from pipeline.validation.validate import run as validate_run
        code = validate_run(paths, source_df=df)
        if code:
            return code
    else:
        print("  skipped by option")

    print("\nBuild complete. PostgreSQL ingestion remains a separate publishing step.")
    return 0 if not skipped else 1


def main():
    parser = argparse.ArgumentParser(description="Build the Kappel Lab website data products.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root (default: auto-detected).")
    parser.add_argument("--no-validate", action="store_true", help="Skip output validation.")
    parser.add_argument("--no-variant-stats", action="store_true", help="Skip supplemental variant-stat enrichment.")
    parser.add_argument("--compare-to", type=Path, default=None, help="After building, semantically compare generated JSON to a known-good repository root.")
    args = parser.parse_args()
    root = args.root or default_paths().root
    code = build(root, validate_outputs=not args.no_validate, run_variant_stats=not args.no_variant_stats)
    if code or args.compare_to is None:
        raise SystemExit(code)
    from pipeline.validation.compare import compare_trees
    missing, mismatches = compare_trees(args.compare_to, root)
    print(f"Comparison: {len(missing)} missing, {len(mismatches)} mismatched JSON files")
    raise SystemExit(1 if missing or mismatches else 0)


if __name__ == "__main__":
    main()
