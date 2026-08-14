"""Mutation-source filtering and JSON generation.

This module integrates the two historical Python mutation scripts into the
consolidated pipeline. It deliberately does *not* scan the 309 GB upstream
source; the HPC/awk prefilter remains a separate refresh step.

Normal inputs are either:

* ``variant_positions_prefiltered.csv`` -- run the filter + transform stages.
* ``variant_positions_filtered.csv`` -- skip directly to the transform stage.

The public ``mutations/`` JSON layout is preserved exactly: one ``index.json``
per protein plus one variant payload per isoform.
"""
from __future__ import annotations

import ast
import json
import math
import shutil
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


PREFILTER_COLUMNS = [
    "UniProtID",
    "VariationID",
    "MutatedFrom",
    "ProteinPosition",
    "MutatedTo",
    "MolecularConsequence",
    "VariantType",
    "MutationType",
    "Germline_Class",
    "SomaticClinicalImpact_Class",
    "Oncogenicity_Class",
    "GeneIsoform",
    "GeneIsoformWithDescription",
    "Dominant_Isoform",
    "UnmutatedSeq",
]

SEVERITY_RANK = {
    "Pathogenic": 5,
    "Likely pathogenic": 4,
    "Oncogenic": 5,
    "Likely oncogenic": 4,
    "Uncertain significance": 3,
    "Uncertain risk allele": 3,
    "Likely benign": 2,
    "Benign": 1,
}

CLASSIFICATION_COLUMNS = (
    ("germline", "Germline_Class"),
    ("somatic", "SomaticClinicalImpact_Class"),
    ("oncogenicity", "Oncogenicity_Class"),
)


@dataclass(frozen=True)
class MutationFilterStats:
    rows_scanned: int
    rows_matched: int
    proteins_matched: int
    classification_parse_failures: int
    position_parse_failures: int
    range_rows: int


@dataclass(frozen=True)
class MutationBuildStats:
    proteins_written: int
    variants_written: int
    rows_skipped_missing_position: int
    dominant_exact: int
    dominant_inferred: int
    dominant_missing: int


class MutationBuildError(RuntimeError):
    """Raised when mutation generation cannot safely replace the current tree."""


def severity(classification_label: Any) -> int:
    return SEVERITY_RANK.get(classification_label, 0)


def parse_classification_json(value: Any) -> list:
    """Parse a classification cell into the submitter-entry list it contains."""
    if pd.isna(value) or not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = ast.literal_eval(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else [parsed]


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(float(value))
    except (ValueError, TypeError, OverflowError):
        return None


def _json_scalar(value: Any) -> Any:
    """Convert pandas/numpy missing scalars to JSON null while preserving values."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def parse_protein_position(value: Any) -> tuple[int | None, int | None]:
    """Parse single positions such as 377.0 and ranges such as 377-380."""
    if pd.isna(value):
        return None, None
    text = str(value).strip()
    if "-" in text and not text.startswith("-"):
        parts = text.split("-")
        try:
            return int(float(parts[0])), int(float(parts[1]))
        except (ValueError, IndexError):
            return None, None
    try:
        position = int(float(text))
        return position, position
    except ValueError:
        return None, None


def _known_proteins(records: Iterable[Any]) -> dict[str, int | None]:
    """Return UniProt -> known Mini Dataset length from canonical records."""
    known = {}
    for record in records:
        value = record.summary.get("length")
        known[record.uniprot] = safe_int(value)
    return known


def filter_prefiltered_variants(
    source_csv: Path,
    destination_csv: Path,
    records: Iterable[Any],
    *,
    chunksize: int = 500_000,
) -> MutationFilterStats:
    """Reduce a prefiltered variant CSV to the website proteins and derived fields.

    This is the pipeline version of ``filter_large_variant_file.py``. The output
    file is always created fresh; it is never appended to an older run.
    """
    source_csv = Path(source_csv)
    destination_csv = Path(destination_csv)
    if not source_csv.exists():
        raise MutationBuildError(f"Mutation source does not exist: {source_csv}")

    known = _known_proteins(records)
    known_ids = set(known)
    destination_csv.parent.mkdir(parents=True, exist_ok=True)
    if destination_csv.exists():
        destination_csv.unlink()

    rows_scanned = 0
    rows_matched = 0
    classification_parse_failures = 0
    position_parse_failures = 0
    range_rows = 0
    matched_proteins: set[str] = set()
    header_written = False

    try:
        reader = pd.read_csv(
            source_csv,
            usecols=PREFILTER_COLUMNS,
            chunksize=chunksize,
            low_memory=False,
        )
        for chunk in reader:
            rows_scanned += len(chunk)
            filtered = chunk[chunk["UniProtID"].isin(known_ids)].copy()
            if filtered.empty:
                continue

            rows_matched += len(filtered)
            matched_proteins.update(str(x) for x in filtered["UniProtID"].dropna().unique())

            parsed = filtered["ProteinPosition"].apply(parse_protein_position)
            filtered["position_start"] = parsed.apply(lambda x: x[0])
            filtered["position_end"] = parsed.apply(lambda x: x[1])
            position_parse_failures += int(filtered["position_start"].isna().sum())
            range_rows += int(
                (
                    filtered["position_start"].notna()
                    & filtered["position_end"].notna()
                    & (filtered["position_start"] != filtered["position_end"])
                ).sum()
            )

            filtered["isoform_length"] = filtered["UnmutatedSeq"].apply(
                lambda seq: len(seq) if isinstance(seq, str) else None
            )
            filtered = filtered.drop(columns=["UnmutatedSeq"])

            for _, column in CLASSIFICATION_COLUMNS:
                entries = filtered[column].apply(parse_classification_json)
                classification_parse_failures += int(
                    (filtered[column].notna() & (entries.apply(len) == 0)).sum()
                )

            filtered.to_csv(
                destination_csv,
                mode="a",
                header=not header_written,
                index=False,
            )
            header_written = True
    except ValueError as exc:
        raise MutationBuildError(
            f"Mutation prefiltered source is missing one or more required columns: {exc}"
        ) from exc

    if not header_written:
        # Preserve a valid, inspectable intermediate even when no rows match.
        pd.DataFrame(columns=[c for c in PREFILTER_COLUMNS if c != "UnmutatedSeq"] + [
            "position_start", "position_end", "isoform_length"
        ]).to_csv(destination_csv, index=False)

    return MutationFilterStats(
        rows_scanned=rows_scanned,
        rows_matched=rows_matched,
        proteins_matched=len(matched_proteins),
        classification_parse_failures=classification_parse_failures,
        position_parse_failures=position_parse_failures,
        range_rows=range_rows,
    )


def _classification_entries(rows: list[pd.Series]) -> list[dict[str, Any]]:
    all_entries: list[dict[str, Any]] = []
    for row in rows:
        for scheme, column in CLASSIFICATION_COLUMNS:
            for entry in parse_classification_json(row.get(column)):
                if not isinstance(entry, dict):
                    continue
                all_entries.append(
                    {
                        "scheme": scheme,
                        "condition": _json_scalar(entry.get("condition")),
                        "classification": _json_scalar(entry.get("description")),
                        "review_status": _json_scalar(entry.get("review_status")),
                        "submission_count": _json_scalar(entry.get("submission_count")),
                        "date_last_evaluated": _json_scalar(entry.get("date_last_evaluated")),
                    }
                )
    return all_entries


def generate_mutation_tree(
    filtered_csv: Path,
    output_dir: Path,
    records: Iterable[Any],
) -> MutationBuildStats:
    """Transform filtered variant rows into the existing per-isoform JSON tree."""
    filtered_csv = Path(filtered_csv)
    output_dir = Path(output_dir)
    if not filtered_csv.exists():
        raise MutationBuildError(f"Filtered mutation source does not exist: {filtered_csv}")

    known = _known_proteins(records)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(filtered_csv, low_memory=False)
    required = {
        "UniProtID", "VariationID", "GeneIsoform", "isoform_length",
        "position_start", "position_end", "Germline_Class",
        "SomaticClinicalImpact_Class", "Oncogenicity_Class",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise MutationBuildError(f"Filtered mutation source is missing required columns: {missing}")

    proteins_written = 0
    variants_written = 0
    skipped_no_position = 0
    dominant_exact = 0
    dominant_inferred = 0
    dominant_missing = 0

    for uniprot, protein_rows in df.groupby("UniProtID", sort=True):
        uniprot = str(uniprot)
        if uniprot not in known:
            continue

        isoforms: dict[Any, dict[str, Any]] = {}
        for _, row in protein_rows.drop_duplicates("GeneIsoform").iterrows():
            iso_id = row.get("GeneIsoform")
            if pd.isna(iso_id):
                continue
            iso_id = str(iso_id)
            length = safe_int(row.get("isoform_length"))
            label = _json_scalar(row.get("GeneIsoformWithDescription"))
            isoforms[iso_id] = {
                "id": iso_id,
                "label": label or iso_id,
                "length": length,
                "dominant": False,
                "isoform_length_mismatch": None,
                "our_known_length": known[uniprot],
                "dominant_source": None,
            }

        our_length = known[uniprot]
        exact_matches = [
            item for item in isoforms.values()
            if our_length is not None and item["length"] == our_length
        ]
        if exact_matches:
            chosen = exact_matches[0]
            chosen["dominant"] = True
            chosen["dominant_source"] = "exact_length_match"
            dominant_exact += 1
        elif isoforms:
            with_length = [item for item in isoforms.values() if item["length"] is not None]
            if with_length and our_length is not None:
                chosen = min(with_length, key=lambda item: abs(item["length"] - our_length))
                chosen["dominant"] = True
                chosen["dominant_source"] = "closest_length_inferred"
                chosen["isoform_length_mismatch"] = True
                dominant_inferred += 1
            else:
                dominant_missing += 1

        groups: dict[tuple[str, Any], list[pd.Series]] = defaultdict(list)
        for _, row in protein_rows.iterrows():
            iso_id = row.get("GeneIsoform")
            variation_id = row.get("VariationID")
            if pd.isna(iso_id) or pd.isna(variation_id):
                continue
            groups[(str(iso_id), _json_scalar(variation_id))].append(row)

        variants = []
        for (iso_id, variation_id), rows in groups.items():
            first = rows[0]
            position_start = safe_int(first.get("position_start"))
            position_end = safe_int(first.get("position_end"))
            if position_start is None:
                skipped_no_position += 1
                continue

            all_entries = _classification_entries(rows)
            if all_entries:
                worst = max(all_entries, key=lambda item: severity(item.get("classification")))
                primary_classification = worst.get("classification")
                primary_condition = worst.get("condition")
            else:
                primary_classification = None
                primary_condition = None

            variants.append(
                {
                    "variation_id": variation_id,
                    "isoform_id": iso_id,
                    "position_start": position_start,
                    "position_end": position_end if position_end is not None else position_start,
                    "is_range": position_end is not None and position_end != position_start,
                    "mutated_from": _json_scalar(first.get("MutatedFrom")),
                    "mutated_to": _json_scalar(first.get("MutatedTo")),
                    "molecular_consequence": _json_scalar(first.get("MolecularConsequence")),
                    "variant_type": _json_scalar(first.get("VariantType")),
                    "mutation_type": _json_scalar(first.get("MutationType")),
                    "primary_classification": primary_classification,
                    "primary_condition": primary_condition,
                    "all_classifications": all_entries,
                    "n_collapsed_rows": len(rows),
                }
            )

        if not variants:
            continue

        protein_dir = output_dir / uniprot
        protein_dir.mkdir(parents=True, exist_ok=True)
        variants_by_isoform: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for variant in variants:
            variants_by_isoform[variant["isoform_id"]].append(variant)

        index_isoforms = []
        for iso_id, iso_meta in isoforms.items():
            iso_variants = variants_by_isoform.get(iso_id, [])
            if not iso_variants:
                continue
            (protein_dir / f"{iso_id}.json").write_text(
                json.dumps({"variants": iso_variants}), encoding="utf-8"
            )
            index_isoforms.append({**iso_meta, "variant_count": len(iso_variants)})

        all_classes = sorted(
            {variant["primary_classification"] for variant in variants if variant["primary_classification"]}
        )
        all_conditions = sorted(
            {variant["primary_condition"] for variant in variants if variant["primary_condition"]}
        )
        (protein_dir / "index.json").write_text(
            json.dumps(
                {
                    "isoforms": index_isoforms,
                    "known_classifications": all_classes,
                    "known_conditions": all_conditions,
                    "total_variant_count": len(variants),
                }
            ),
            encoding="utf-8",
        )
        proteins_written += 1
        variants_written += len(variants)

    return MutationBuildStats(
        proteins_written=proteins_written,
        variants_written=variants_written,
        rows_skipped_missing_position=skipped_no_position,
        dominant_exact=dominant_exact,
        dominant_inferred=dominant_inferred,
        dominant_missing=dominant_missing,
    )


def validate_mutation_tree(output_dir: Path, records: Iterable[Any]) -> tuple[list[str], list[str]]:
    """Validate cross-file and per-variant invariants before publishing mutations/."""
    errors: list[str] = []
    warnings: list[str] = []
    known_ids = {record.uniprot for record in records}
    output_dir = Path(output_dir)

    if not output_dir.exists():
        errors.append(f"Mutation output directory does not exist: {output_dir}")
        return errors, warnings

    for protein_dir in sorted(path for path in output_dir.iterdir() if path.is_dir()):
        uniprot = protein_dir.name
        if uniprot not in known_ids:
            errors.append(f"Mutation tree contains unknown UniProt ID: {uniprot}")
            continue
        index_path = protein_dir / "index.json"
        if not index_path.exists():
            errors.append(f"Missing mutation index: {uniprot}/index.json")
            continue
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"Invalid mutation index JSON for {uniprot}: {exc}")
            continue

        isoforms = index.get("isoforms")
        if not isinstance(isoforms, list):
            errors.append(f"{uniprot}: index.isoforms is not a list")
            continue

        dominant = [item for item in isoforms if item.get("dominant") is True]
        if len(dominant) > 1:
            errors.append(f"{uniprot}: more than one dominant isoform in mutation index")
        if not dominant and isoforms:
            warnings.append(f"{uniprot}: no dominant mutation isoform selected")

        actual_total = 0
        indexed_files = set()
        for isoform in isoforms:
            iso_id = isoform.get("id")
            if not iso_id:
                errors.append(f"{uniprot}: mutation index contains isoform with no id")
                continue
            payload_path = protein_dir / f"{iso_id}.json"
            indexed_files.add(payload_path.name)
            if not payload_path.exists():
                errors.append(f"{uniprot}: missing payload for isoform {iso_id}")
                continue
            try:
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{uniprot}/{iso_id}: invalid JSON: {exc}")
                continue
            variants = payload.get("variants")
            if not isinstance(variants, list):
                errors.append(f"{uniprot}/{iso_id}: variants is not a list")
                continue
            if isoform.get("variant_count") != len(variants):
                errors.append(
                    f"{uniprot}/{iso_id}: index variant_count={isoform.get('variant_count')} but payload has {len(variants)}"
                )
            actual_total += len(variants)

            for variant in variants:
                variation_id = variant.get("variation_id")
                if variation_id is None:
                    errors.append(f"{uniprot}/{iso_id}: variant missing variation_id")
                if variant.get("isoform_id") != iso_id:
                    errors.append(
                        f"{uniprot}/{iso_id}: variation {variation_id} has isoform_id={variant.get('isoform_id')}"
                    )
                start = variant.get("position_start")
                end = variant.get("position_end")
                if not isinstance(start, int):
                    errors.append(f"{uniprot}/{iso_id}: variation {variation_id} has invalid start position")
                if not isinstance(end, int) or (isinstance(start, int) and end < start):
                    errors.append(f"{uniprot}/{iso_id}: variation {variation_id} has invalid end position")
                collapsed = variant.get("n_collapsed_rows")
                if not isinstance(collapsed, int) or collapsed < 1:
                    errors.append(f"{uniprot}/{iso_id}: variation {variation_id} has invalid n_collapsed_rows")
                entries = variant.get("all_classifications")
                if not isinstance(entries, list):
                    errors.append(f"{uniprot}/{iso_id}: variation {variation_id} all_classifications is not a list")
                    continue
                if entries:
                    worst_severity = max(severity(item.get("classification")) for item in entries)
                    primary = variant.get("primary_classification")
                    matching = [
                        item for item in entries
                        if item.get("classification") == primary
                        and item.get("condition") == variant.get("primary_condition")
                    ]
                    if not matching:
                        errors.append(
                            f"{uniprot}/{iso_id}: variation {variation_id} primary classification/condition is not present in all_classifications"
                        )
                    elif severity(primary) != worst_severity:
                        errors.append(
                            f"{uniprot}/{iso_id}: variation {variation_id} primary classification is not worst-severity"
                        )
                elif variant.get("primary_classification") is not None or variant.get("primary_condition") is not None:
                    errors.append(
                        f"{uniprot}/{iso_id}: variation {variation_id} has primary classification without classification entries"
                    )

        unexpected_payloads = {
            path.name for path in protein_dir.glob("*.json") if path.name != "index.json"
        } - indexed_files
        if unexpected_payloads:
            errors.append(f"{uniprot}: unindexed mutation payloads: {sorted(unexpected_payloads)}")

        if index.get("total_variant_count") != actual_total:
            errors.append(
                f"{uniprot}: total_variant_count={index.get('total_variant_count')} but payloads contain {actual_total}"
            )

    return errors, warnings


def _replace_directory_safely(staged: Path, destination: Path) -> None:
    destination = Path(destination)
    backup = destination.parent / f".{destination.name}.pipeline-backup-{uuid.uuid4().hex}"
    had_existing = destination.exists()
    try:
        if had_existing:
            destination.rename(backup)
        staged.rename(destination)
    except Exception:
        if destination.exists() and not had_existing:
            shutil.rmtree(destination, ignore_errors=True)
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)


def rebuild_mutations(
    records: Iterable[Any],
    *,
    output_dir: Path,
    prefiltered_csv: Path | None = None,
    filtered_csv: Path | None = None,
) -> tuple[MutationFilterStats | None, MutationBuildStats, list[str]]:
    """Build a fresh mutation tree and replace the old tree only after validation."""
    if (prefiltered_csv is None) == (filtered_csv is None):
        raise MutationBuildError("Provide exactly one of prefiltered_csv or filtered_csv")

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    records = list(records)

    with tempfile.TemporaryDirectory(prefix=".pipeline-mutations-", dir=output_dir.parent) as temp_name:
        temp_root = Path(temp_name)
        filter_stats = None
        if prefiltered_csv is not None:
            working_filtered = temp_root / "variant_positions_filtered.csv"
            filter_stats = filter_prefiltered_variants(
                Path(prefiltered_csv), working_filtered, records
            )
        else:
            working_filtered = Path(filtered_csv)

        staged = temp_root / "mutations"
        build_stats = generate_mutation_tree(working_filtered, staged, records)
        if build_stats.proteins_written == 0:
            raise MutationBuildError(
                "Mutation source produced zero protein folders; refusing to replace the existing mutations/ tree."
            )
        errors, warnings = validate_mutation_tree(staged, records)
        if errors:
            details = "\n".join(f"  - {message}" for message in errors[:20])
            if len(errors) > 20:
                details += f"\n  - ... and {len(errors) - 20} more"
            raise MutationBuildError(
                f"Generated mutation tree failed validation with {len(errors)} error(s):\n{details}"
            )

        _replace_directory_safely(staged, output_dir)
        return filter_stats, build_stats, warnings
