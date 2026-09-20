import json
import re
from pathlib import Path

import pandas as pd

from .common import flatten_ppi_scores, parse_dict, parse_jsonish, parse_pylist


def extract_isoform_label(hgvs_desc, gene):
    if not isinstance(hgvs_desc, str) or not hgvs_desc:
        return None
    first = hgvs_desc.split(",")[0]
    m = re.search(r"(isoform\s+[A-Za-z0-9\-]+)", first, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r"transcript variant\s+([A-Za-z0-9\-]+)", first, re.IGNORECASE)
    if m2:
        return "transcript variant " + m2.group(1)
    return None


def parse_diseases(row):
    """Map expanded OpenTargets associations into the public disease shape."""
    associations = parse_jsonish(row.get("opentargets_disease_associations")) or []
    out = []
    for association in associations:
        evidence = association.get("evidence_by_datatype") or []
        out.append({
            "disease_id": association.get("disease_id"),
            "score": round(float(association.get("max_datatype_score") or 0), 4),
            "evidence_count": int(association.get("evidence_count_total") or 0),
            "datatypes": sorted({item.get("datatype_id") for item in evidence if item.get("datatype_id")}),
        })
    out.sort(key=lambda x: -x["score"])
    return out


def build_summary(row):
    """Build the compact protein summary and its disease records from one row."""
    cond_names = parse_pylist(row["Condensate Name"])
    cond_types = parse_pylist(row["Condensate Type"])
    cond_conf = parse_pylist(row["Confidence Score"])
    ppi_dict = flatten_ppi_scores(
        parse_dict(row["PPI_UniProt_Partners_in_Dataframe"])
    )
    sat_list = parse_pylist(row["Saturation concentration [uM]"])
    dg_list = parse_pylist(row["Delta G [kT]"])

    idr_total = row["IDR_total_size"]
    fold_total = row["FOLD_total_size"]
    idr_total_num = 0 if pd.isna(idr_total) else idr_total
    fold_total_num = 0 if pd.isna(fold_total) else fold_total
    denom = idr_total_num + fold_total_num
    disorder_frac = round(idr_total_num / denom, 3) if denom else None

    seq = row["sequence"] if isinstance(row["sequence"], str) else ""
    idr_ranges = parse_pylist(row["IDR_range"])
    fold_ranges = parse_pylist(row["FOLD_range"])
    domain_names = parse_pylist(row["Domains"])
    domain_ranges_raw = parse_dict(row["Domains_range"])
    domains = []
    for dname in domain_names:
        for sp in domain_ranges_raw.get(dname, []):
            domains.append({"name": dname, "start": int(sp[0]), "end": int(sp[1])})

    rec = {
        "uniprot": row["uniprot_id"],
        "gene": row["Name"],
        "ensg": None if pd.isna(row["ID"]) else row["ID"],
        "dominant": bool(row["dominant_isoform"]) if not pd.isna(row["dominant_isoform"]) else None,
        "isoform_number": int(row["isoform_number"]) if not pd.isna(row["isoform_number"]) else None,
        "isoform_label": extract_isoform_label(row.get("HGVSDescription"), row["Name"]),
        "length": len(seq),
        "idr_count": int(row["IDR_count"]) if not pd.isna(row["IDR_count"]) else 0,
        "idr_total_size": int(idr_total) if not pd.isna(idr_total) else 0,
        "fold_total_size": int(fold_total) if not pd.isna(fold_total) else 0,
        "disorder_fraction": disorder_frac,
        "idr_ranges": [[int(a), int(b)] for a, b in idr_ranges] if idr_ranges else [],
        "fold_ranges": [[int(a), int(b)] for a, b in fold_ranges] if fold_ranges else [],
        "domains": domains,
        "condensates": cond_names,
        "condensate_types": cond_types,
        "condensate_confidence": cond_conf,
        "condensate_forming": len(cond_names) > 0,
        "ppi_partner_count": len(ppi_dict),
        "fcr": round(row["FCR"], 3) if not pd.isna(row["FCR"]) else None,
        "ncpr": round(row["NCPR"], 3) if not pd.isna(row["NCPR"]) else None,
        "kappa": round(row["kappa"], 3) if not pd.isna(row["kappa"]) else None,
        "mean_hydropathy": round(row["mean_hydropathy"], 3) if not pd.isna(row["mean_hydropathy"]) else None,
        "isoelectric_point": round(row["isoelectric_point"], 2) if not pd.isna(row["isoelectric_point"]) else None,
        "molecular_weight": round(row["molecular_weight"], 1) if not pd.isna(row["molecular_weight"]) else None,
        "saturation_conc_uM": round(sum(sat_list) / len(sat_list), 2) if sat_list else None,
        "delta_g_kt": round(sum(dg_list) / len(dg_list), 4) if dg_list else None,
    }
    return rec, parse_diseases(row)


def write_outputs(records, data_json: Path, diseases_json: Path):
    data_json.write_text(json.dumps([r.summary for r in records]))
    diseases_json.write_text(json.dumps({r.uniprot: r.diseases for r in records}))
