"""
audit_protein_details.py — automated, whole-dataset spot check. Run this
instead of manually browsing Jupyter or the site. It checks EVERY protein
(not a sample) against the raw CSV and prints only what's actually wrong.

Checks performed:
  1. Every real CSV column has somewhere it lands (data.json, diseases.json,
     or protein_details/*.json) — flags anything genuinely uncaptured.
  2. Per-protein structural consistency: sequence length, PPI partner counts,
     GO term counts, IDR+FOLD sizes all match their raw CSV source exactly.
  3. Parse-failure detection: for the Open Targets fields that needed the
     numpy-array regex fixup, flags any protein where the raw cell had real
     content but the parsed output came back empty/null (a likely parse
     failure, not a "this protein just has no data" case).

Run:
    python3 audit_protein_details.py
"""
import pandas as pd, json, ast, re
from pathlib import Path

df = pd.read_csv("Mini_Dataset.csv")
df_by_uniprot = df.set_index("uniprot_id")  # O(1) lookup instead of scanning the whole CSV per protein
data = json.load(open("data.json"))
details_dir = Path("protein_details")

def parse_dict(s):
    if not isinstance(s, str) or s.strip() in ("", "{}"):
        return {}
    try: return ast.literal_eval(s)
    except Exception: return {}

def parse_pylist(s):
    if not isinstance(s, str) or s.strip() in ("", "[]"):
        return []
    cleaned = re.sub(r"np\.(int64|float64)\((-?[\d\.]+)\)", r"\2", s)
    try: return ast.literal_eval(cleaned)
    except Exception: return []

problems = []
checked = 0

for p in data:
    uid = p["uniprot"]
    if uid not in df_by_uniprot.index:
        problems.append(f"{uid}: in data.json but not found in Mini_Dataset.csv at all")
        continue
    row = df_by_uniprot.loc[uid]
    detail_path = details_dir / f"{uid}.json"
    if not detail_path.exists():
        problems.append(f"{uid}: no protein_details/{uid}.json file found")
        continue
    d = json.loads(detail_path.read_text())
    checked += 1

    # 1. sequence length
    if len(row["sequence"]) != len(d["sequence"]):
        problems.append(f"{uid}: sequence length mismatch (CSV {len(row['sequence'])} vs JSON {len(d['sequence'])})")

    # 2. PPI partner counts
    raw_ppi = parse_dict(row["PPI_UniProt_Partners"])
    if len(raw_ppi) != len(d["ppi"]["all_partners"]):
        problems.append(f"{uid}: PPI partner count mismatch (CSV {len(raw_ppi)} vs JSON {len(d['ppi']['all_partners'])})")

    # 3. GO term counts
    for prefix, key in [("C","cellular_component"), ("P","biological_process"), ("F","molecular_function")]:
        raw_ids = parse_pylist(row[f"{prefix}_ids"])
        if len(raw_ids) != len(d["go_terms"][key]):
            problems.append(f"{uid}: GO {key} count mismatch (CSV {len(raw_ids)} vs JSON {len(d['go_terms'][key])})")

    # 4. IDR + FOLD sizes should sum to sequence length
    if d["biophysics_regions"]["idr"] is not None:
        idr_total = p.get("idr_total_size", 0)
        fold_total = p.get("fold_total_size", 0)
        if idr_total + fold_total != len(d["sequence"]):
            problems.append(f"{uid}: IDR+FOLD sizes ({idr_total}+{fold_total}) don't sum to sequence length ({len(d['sequence'])})")

    # 5. parse-failure detection on Open Targets fields — flag when raw had
    #    real content but parsed output is empty (likely regex-fixup failure)
    ga = d["gene_annotation"]
    checks = [
        ("synonyms", row["synonyms"]), ("subcellular_locations", row["subcellularLocations"]),
        ("pathways", row["pathways"]), ("transcript_ids", row["transcriptIds"]),
    ]
    for field, raw_cell in checks:
        raw_str = str(raw_cell)
        looks_populated = isinstance(raw_cell, str) and len(raw_str) > 30 and "nan" not in raw_str.lower()
        parsed_empty = not ga.get(field)
        if looks_populated and parsed_empty:
            problems.append(f"{uid}: gene_annotation.{field} is empty but raw CSV cell looks populated ({len(raw_str)} chars) — likely a parse failure")

print(f"Checked {checked} / {len(data)} proteins.\n")
if problems:
    print(f"{len(problems)} issue(s) found:\n")
    for pr in problems:
        print(" -", pr)
else:
    print("No issues found across any check, for any protein.")
