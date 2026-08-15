"""Normalize the supplemental per-protein variant-statistics CSV."""
import ast
from pathlib import Path

import pandas as pd


def parse_rbd_names(value):
    if not isinstance(value, str) or value.strip() in ("0", "[]", ""):
        return []
    try:
        return ast.literal_eval(value)
    except Exception:
        return []


def parse_diseases(value):
    if not isinstance(value, str) or not value.strip():
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def build_variant_stats_map(variant_csv: Path):
    df = pd.read_csv(variant_csv)
    result = {}
    for _, row in df.iterrows():
        result[row["UniProtID"]] = {
            "gene_type": row["GeneType"],
            "is_rbp": row["isRBP"] == "Yes",
            "has_rbd": bool(row["Has_RBD"]),
            "rbd_names": parse_rbd_names(row["RBD_names"]),
            "benign_not_classical_rbd": int(row["Benign_Not_ClassicalRBD"]),
            "benign_in_classical_rbd": int(row["Benign_In_ClassicalRBD"]),
            "pathogenic_not_classical_rbd": int(row["Pathogenic_Not_ClassicalRBD"]),
            "pathogenic_in_classical_rbd": int(row["Pathogenic_In_ClassicalRBD"]),
            "vus_not_classical_rbd": int(row["VUS_Not_ClassicalRBD"]),
            "vus_in_classical_rbd": int(row["VUS_In_ClassicalRBD"]),
            "total_pathogenic": int(row["Total_Pathogenic"]),
            "total_vus": int(row["Total_VUS"]),
            "total_benign": int(row["Total_Benign"]),
            "disease_names": parse_diseases(row["Disease_Associations"]),
        }
    return result
