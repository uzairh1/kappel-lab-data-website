"""
merge_variant_stats.py — enrich data.json (the 101-protein pilot set) with
matched rows from per_protein_variant_stats_v2.csv (an 18.5k-gene reference
file: RNA-binding protein status, RBD domains, ClinVar-derived variant
classification counts, and human-readable disease names).

Only proteins already in data.json are touched. Matches are by UniProt ID.
Proteins with no match get variant_stats: null and are left otherwise
unchanged — no fabricated data for the ones that don't match.

Run:
    python3 merge_variant_stats.py
Reads:
    data.json                          (existing pilot dataset)
    per_protein_variant_stats_v2.csv   (the new reference file)
Writes:
    data.json                          (in place, enriched)
"""
import pandas as pd, json, ast, re
from pathlib import Path

DATA_JSON = Path("data.json")
VARIANT_CSV = Path("per_protein_variant_stats_v2.csv")

def parse_rbd_names(val):
    if not isinstance(val, str) or val.strip() in ("0", "[]", ""):
        return []
    try:
        return ast.literal_eval(val)
    except Exception:
        return []

def parse_diseases(val):
    if not isinstance(val, str) or not val.strip():
        return []
    return [d.strip() for d in val.split(";") if d.strip()]

def main():
    with open(DATA_JSON) as f:
        proteins = json.load(f)

    vdf = pd.read_csv(VARIANT_CSV)
    by_uniprot = {row["UniProtID"]: row for _, row in vdf.iterrows()}

    matched, unmatched = 0, 0
    for p in proteins:
        row = by_uniprot.get(p["uniprot"])
        if row is None:
            p["variant_stats"] = None
            unmatched += 1
            continue
        matched += 1
        p["variant_stats"] = {
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

    with open(DATA_JSON, "w") as f:
        json.dump(proteins, f)

    print(f"Matched: {matched} / {len(proteins)}")
    print(f"Unmatched (variant_stats = null): {unmatched}")
    if unmatched:
        missing = [p["uniprot"] for p in proteins if p["variant_stats"] is None]
        print("Unmatched UniProt IDs:", missing)

if __name__ == "__main__":
    main()
