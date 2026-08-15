"""Single entry point for building website data products from source datasets."""
import argparse
from pathlib import Path

import pandas as pd

from pipeline.config import default_paths
from pipeline.field_families import extension_report
from pipeline.steps.canonical import build_canonical_records
from pipeline.steps.details import write_details
from pipeline.steps.mutations import MutationBuildError, rebuild_mutations
from pipeline.steps.proteins import write_outputs
from pipeline.steps.variants import build_variant_stats_map
from pipeline.steps.tissues import write_tissues


def _resolve_input(root: Path, path: Path | None) -> Path | None:
    if path is None or path.is_absolute():
        return path
    return root / path


def build(
    root: Path,
    *,
    validate_outputs: bool = True,
    run_variant_stats: bool = True,
    mutation_prefiltered: Path | None = None,
    mutation_filtered: Path | None = None,
):
    paths = default_paths(root)
    required = [paths.mini_dataset]
    if run_variant_stats:
        required.append(paths.variant_stats)
    missing = [path for path in required if not path.exists()]
    if missing:
        print("Cannot build: required source file(s) are missing:")
        for path in missing:
            print(f"  - {path}")
        return 2

    mutation_prefiltered = _resolve_input(paths.root, mutation_prefiltered)
    mutation_filtered = _resolve_input(paths.root, mutation_filtered)
    if mutation_prefiltered is not None and mutation_filtered is not None:
        print("Cannot build: choose either --mutations or --mutations-filtered, not both.")
        return 2

    print("[1/5] Loading source data")
    df = pd.read_csv(paths.mini_dataset)
    variant_map = build_variant_stats_map(paths.variant_stats) if run_variant_stats else {}
    extensions = extension_report(df.columns)
    for family, specs in extensions.items():
        for spec in specs:
            destination = (
                f"biophysics_regions.idr_segments[].{spec.output}"
                if family == "idr"
                else f"domain_types[].{spec.output}"
            )
            print(f"  auto-mapped new {family} field: {spec.source} -> {destination}")

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
    matched = sum(record.variant_stats is not None for record in records)
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

    if mutation_prefiltered is not None or mutation_filtered is not None:
        print("\n[MUTATIONS] Rebuilding mutation viewer data")
        source = mutation_prefiltered or mutation_filtered
        if source is None or not source.exists():
            print(f"Mutation build FAILED: source file does not exist: {source}")
            return 2
        try:
            filter_stats, mutation_stats, mutation_warnings = rebuild_mutations(
                records,
                output_dir=paths.mutations,
                prefiltered_csv=mutation_prefiltered,
                filtered_csv=mutation_filtered,
            )
        except MutationBuildError as exc:
            print(f"Mutation build FAILED: {exc}")
            print("Existing mutations/ was left unchanged.")
            return 1

        if filter_stats is not None:
            print(
                "  filter: "
                f"{filter_stats.rows_matched:,} matched rows / {filter_stats.rows_scanned:,} scanned; "
                f"{filter_stats.proteins_matched} proteins"
            )
            print(
                "  filter checks: "
                f"{filter_stats.position_parse_failures} position parse failures; "
                f"{filter_stats.classification_parse_failures} classification parse failures; "
                f"{filter_stats.range_rows} range rows"
            )
        print(
            "  output: "
            f"{mutation_stats.proteins_written} proteins; "
            f"{mutation_stats.variants_written:,} plotted variants; "
            f"{mutation_stats.rows_skipped_missing_position} rows skipped for missing position"
        )
        print(
            "  dominant isoforms: "
            f"{mutation_stats.dominant_exact} exact length matches; "
            f"{mutation_stats.dominant_inferred} inferred; "
            f"{mutation_stats.dominant_missing} missing"
        )
        print(f"  mutation validation: 0 errors; {len(mutation_warnings)} warnings")
        for warning in mutation_warnings:
            print(f"  WARNING: {warning}")

    print("\nBuild complete. PostgreSQL ingestion remains a separate publishing step.")
    return 0 if not skipped else 1


def main():
    parser = argparse.ArgumentParser(description="Build the Kappel Lab website data products.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root (default: auto-detected).")
    parser.add_argument("--no-validate", action="store_true", help="Skip core output validation.")
    parser.add_argument("--no-variant-stats", action="store_true", help="Skip supplemental variant-stat enrichment.")

    mutation_group = parser.add_mutually_exclusive_group()
    mutation_group.add_argument(
        "--mutations",
        type=Path,
        metavar="PREFILTERED_CSV",
        help=(
            "Also rebuild mutations/ from variant_positions_prefiltered.csv (or another CSV with the same schema). "
            "Runs both integrated Python mutation stages; the 309 GB awk prefilter remains separate."
        ),
    )
    mutation_group.add_argument(
        "--mutations-filtered",
        type=Path,
        metavar="FILTERED_CSV",
        help="Rebuild mutations/ from an already-created variant_positions_filtered.csv.",
    )

    parser.add_argument(
        "--compare-to",
        type=Path,
        default=None,
        help="After building, semantically compare generated JSON to a known-good repository root.",
    )
    args = parser.parse_args()
    root = args.root or default_paths().root
    code = build(
        root,
        validate_outputs=not args.no_validate,
        run_variant_stats=not args.no_variant_stats,
        mutation_prefiltered=args.mutations,
        mutation_filtered=args.mutations_filtered,
    )
    if code or args.compare_to is None:
        raise SystemExit(code)

    from pipeline.validation.compare import compare_trees

    missing, mismatches = compare_trees(args.compare_to, root)
    print(f"Comparison: {len(missing)} missing, {len(mismatches)} mismatched JSON files")
    raise SystemExit(1 if missing or mismatches else 0)


if __name__ == "__main__":
    main()
