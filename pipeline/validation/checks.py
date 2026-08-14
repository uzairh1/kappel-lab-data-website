import json
from pathlib import Path

from pipeline.steps.structured import idr_alignment_lengths


def validate_source(df):
    errors = []
    warnings = []
    required_idr = ["IDR_FCR", "IDR_NCPR", "IDR_kappa", "IDR_delta", "IDR_deltaMax"]
    for index, row in df.iterrows():
        uniprot = row.get("uniprot_id") or f"row {index}"
        lengths = idr_alignment_lengths(row)
        target = lengths["IDR_range"]
        mismatches = {k: v for k, v in lengths.items() if k != "IDR_range" and v not in (0, target)}
        if mismatches:
            errors.append(f"IDR field length mismatch for {uniprot}: IDR_range={target}; {mismatches}")
        if target and target != int(row.get("IDR_count") or 0):
            errors.append(f"IDR count/range mismatch for {uniprot}: IDR_count={row.get('IDR_count')}; ranges={target}")
        if target:
            for column in required_idr:
                if lengths.get(column, 0) == 0:
                    warnings.append(f"{uniprot}: {column} is empty despite {target} IDR(s)")

    return errors, warnings


def validate_outputs(data_json: Path, diseases_json: Path, protein_details: Path, tissues: Path):
    errors = []
    warnings = []
    proteins = json.loads(data_json.read_text())
    diseases = json.loads(diseases_json.read_text())

    uniprots = [p.get("uniprot") for p in proteins]
    if len(uniprots) != len(set(uniprots)):
        errors.append("Duplicate UniProt IDs in data.json")
    if any(not u for u in uniprots):
        errors.append("At least one protein is missing a UniProt ID")

    detail_ids = {p.stem for p in protein_details.glob("*.json")}
    missing_details = set(uniprots) - detail_ids
    if missing_details:
        errors.append(f"Missing protein detail files: {sorted(missing_details)}")

    tissue_ids = {p.stem for p in tissues.glob("*.json")}
    missing_tissues = set(uniprots) - tissue_ids
    if missing_tissues:
        warnings.append(f"Missing tissue files: {sorted(missing_tissues)}")

    for p in proteins:
        u = p["uniprot"]
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

    return errors, warnings
