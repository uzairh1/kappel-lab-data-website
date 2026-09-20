import json
from pathlib import Path

import pandas as pd

from pipeline.expanded_schema import ISOFORM_ANNOTATION_FIELDS, PARENT_ANNOTATION_FIELDS
from pipeline.field_families import CONDENSATE_FIELDS, domain_fields, idr_fields
from pipeline.steps.common import parse_dict
from pipeline.steps.structured import idr_alignment_lengths


REQUIRED_EXPANDED_COLUMNS = {
    "uniprot_id", "dataset_isoform_id", "dominant_isoform", "is_swissprot_canonical",
    "row_kind", "length_aa",
    "sequence", "Name", "ID", "isoform_number", "ProteinHGVS", "HGVSDescription",
    "ENSP", "ENSP_clean", "UNIQUE", "Description", "FCR", "NCPR", "kappa",
    "mean_hydropathy", "isoelectric_point", "molecular_weight", "amino_acid_fractions",
    "IDR_count", "IDR_total_size", "IDR_range", "IDR_discrete_seq", "IDR_concat_seq",
    "IDR_amino_acid_fractions", "FOLD_count", "FOLD_avg_size", "FOLD_total_size",
    "FOLD_range", "FOLD_discrete_seq", "FOLD_concat_seq", "Domains", "Domains_count",
    "Domains_range", "Domains_discrete_seq", "Domains_concat_seq",
    "Domains_amino_acid_fractions", "PPI_UniProt_Partners", "PPI_ENSP_Partners",
    "PPI_UniProt_Partners_in_Dataframe", "PPI_ENSP_Partners_in_Dataframe",
    "Condensate Name", "Condensate Type", "Confidence Score", "C_ids", "C_descriptions",
    "C_evidence", "P_ids", "P_descriptions", "P_evidence", "F_ids", "F_descriptions",
    "F_evidence", "mean_lambda", "faro", "shd", "scd", "ah_ij", "nu_svr",
    "Delta G [kT]", "Saturation concentration [mg/mL]", "Saturation concentration [uM]",
    "opentargets_tissue_expression", "opentargets_disease_associations",
} | {field.source for field in idr_fields()} | {
    field.source for field in domain_fields()
} | {field.source for field in CONDENSATE_FIELDS} | {
    column
    for groups in (PARENT_ANNOTATION_FIELDS, ISOFORM_ANNOTATION_FIELDS)
    for columns in groups.values()
    for column in columns
}


def validate_source(df):
    errors = []
    warnings = []
    missing_columns = sorted(REQUIRED_EXPANDED_COLUMNS - set(df.columns))
    if missing_columns:
        errors.append(f"Expanded dataset is missing required columns: {missing_columns}")
        return errors, warnings

    if df["uniprot_id"].isna().any():
        errors.append("Expanded dataset contains rows with no uniprot_id")
    if df["dataset_isoform_id"].isna().any():
        errors.append("Expanded dataset contains rows with no dataset_isoform_id")
    duplicate_isoforms = sorted(
        df.loc[df["dataset_isoform_id"].duplicated(keep=False), "dataset_isoform_id"].dropna().unique()
    )
    if duplicate_isoforms:
        errors.append(f"Duplicate dataset_isoform_id values: {duplicate_isoforms}")

    for uniprot, group in df.dropna(subset=["uniprot_id"]).groupby("uniprot_id", sort=False):
        dominant = group[group["dominant_isoform"] == 1]
        if len(dominant) != 1:
            errors.append(
                f"{uniprot}: expected exactly one dominant isoform; found {len(dominant)}"
            )
        elif not bool(dominant.iloc[0].get("is_swissprot_canonical")):
            warnings.append(f"{uniprot}: dominant isoform is not marked Swiss-Prot canonical")

    required_idr = ["IDR_FCR", "IDR_NCPR", "IDR_kappa", "IDR_delta", "IDR_deltaMax"]
    for index, row in df.iterrows():
        uniprot = row.get("uniprot_id") or f"row {index}"
        sequence = row.get("sequence")
        length = row.get("length_aa")
        if not isinstance(sequence, str):
            errors.append(f"{uniprot}/{row.get('dataset_isoform_id')}: sequence is missing")
        elif pd.isna(length) or len(sequence) != int(length):
            errors.append(
                f"{uniprot}/{row.get('dataset_isoform_id')}: sequence length {len(sequence)} "
                f"does not match length_aa={length}"
            )
        try:
            lengths = idr_alignment_lengths(row)
        except ValueError as exc:
            errors.append(f"Could not parse IDR fields for {uniprot}: {exc}")
            continue
        target = lengths["IDR_range"]
        mismatches = {k: v for k, v in lengths.items() if k != "IDR_range" and v not in (0, target)}
        if mismatches:
            errors.append(f"IDR field length mismatch for {uniprot}: IDR_range={target}; {mismatches}")
        idr_count = row.get("IDR_count")
        parsed_count = 0 if pd.isna(idr_count) else int(idr_count)
        if target and target != parsed_count:
            errors.append(f"IDR count/range mismatch for {uniprot}: IDR_count={row.get('IDR_count')}; ranges={target}")
        if target:
            for column in required_idr:
                if lengths.get(column, 0) == 0:
                    warnings.append(f"{uniprot}: {column} is empty despite {target} IDR(s)")

        # Registered domain fields are dictionaries keyed by the same domain
        # names as Domains_count.
        domain_names = set(parse_dict(row.get("Domains_count")).keys())
        for spec in domain_fields():
            values = parse_dict(row.get(spec.source))
            extra = set(values) - domain_names
            if extra:
                errors.append(
                    f"Domain field key mismatch for {uniprot}: {spec.source} has unknown domain keys {sorted(extra)}"
                )

    return errors, warnings


def validate_outputs(
    protein_catalog: Path,
    disease_associations: Path,
    protein_details: Path,
    tissue_expression: Path,
):
    errors = []
    warnings = []
    proteins = json.loads(protein_catalog.read_text())
    diseases = json.loads(disease_associations.read_text())

    uniprots = [p.get("uniprot") for p in proteins]
    if len(uniprots) != len(set(uniprots)):
        errors.append("Duplicate UniProt IDs in data.json")
    if any(not u for u in uniprots):
        errors.append("At least one protein is missing a UniProt ID")

    detail_ids = {p.stem for p in protein_details.glob("*.json")}
    missing_details = set(uniprots) - detail_ids
    if missing_details:
        errors.append(f"Missing protein detail files: {sorted(missing_details)}")

    tissue_ids = {p.stem for p in tissue_expression.glob("*.json")}
    missing_tissues = set(uniprots) - tissue_ids
    if missing_tissues:
        warnings.append(f"Missing tissue files: {sorted(missing_tissues)}")

    for p in proteins:
        u = p["uniprot"]
        source = p.get("catalog_source")
        if source not in {"legacy_snapshot", "expanded_dataset"}:
            errors.append(f"Unknown or missing catalog_source for {u}: {source}")
        if u not in diseases:
            warnings.append(f"No disease entry for {u}")
        detail_path = protein_details / f"{u}.json"
        if detail_path.exists():
            detail = json.loads(detail_path.read_text())
            idr_count = len(detail.get("biophysics_regions", {}).get("idr_segments", []))
            range_count = len(p.get("idr_ranges", []))
            if idr_count != range_count:
                errors.append(f"Generated IDR mismatch for {u}: summary={range_count}; detail={idr_count}")
            for key in ("domain_types", "go_terms", "ppi", "condensate_details", "gene_annotation", "patterning"):
                if key not in detail:
                    errors.append(f"Missing detail section for {u}: {key}")
            isoforms = detail.get("isoforms")
            if not isinstance(isoforms, list):
                errors.append(f"Missing nested isoforms for {u}")
            else:
                ids = [isoform.get("dataset_isoform_id") for isoform in isoforms]
                if len(ids) != len(set(ids)):
                    errors.append(f"Duplicate nested isoform IDs for {u}")
                dominant_count = sum(isoform.get("dominant") is True for isoform in isoforms)
                if source == "expanded_dataset" and dominant_count != 1:
                    errors.append(
                        f"Generated dominant isoform mismatch for {u}: found {dominant_count}"
                    )
                if len(isoforms) != p.get("isoform_count"):
                    errors.append(
                        f"Generated isoform count mismatch for {u}: "
                        f"summary={p.get('isoform_count')}; detail={len(isoforms)}"
                    )
                if source == "legacy_snapshot" and isoforms:
                    errors.append(f"Legacy snapshot unexpectedly contains expanded isoforms for {u}")
            if "expanded_annotations" not in detail:
                errors.append(f"Missing expanded annotations for {u}")
            if detail.get("catalog_source") != source:
                errors.append(f"Catalog source mismatch between summary and details for {u}")

    return errors, warnings
