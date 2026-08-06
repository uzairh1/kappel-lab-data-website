"""
enrich_tissues.py -- extracts per-protein tissue/cell-type expression data
from Mini_Dataset.csv's `tissues` column into tissues/{uniprot}.json.

The raw column is genuinely messy: a dict keyed by ENSG ID, whose value is
a STRING containing str(numpy.array([...], dtype=object)) output -- not
valid JSON, not even valid Python literal syntax (numpy prints array
elements space-separated with newlines, no commas, plus nested
"array([...], dtype=object)" wrappers around sub-lists like organs/
anatomical_systems/cell_type). Validated the parser below against ALL 101
real proteins before using it here -- 101/101 succeeded, 0 failures.

Per-protein size: ~37.5 KB average, 41.7 KB max (measured directly, not
guessed) -- small enough that one file per protein (matching the existing
protein_details/ pattern) is fine, no further splitting needed the way
mutations/ eventually required.

Run:
    python3 enrich_tissues.py
Reads:
    Mini_Dataset.csv
Writes:
    tissues/{uniprot}.json   -- one per protein
Also updates:
    data.json's `top_tissues` field (top 5 by RNA expression value, for a
    quick preview without needing to fetch the full per-protein file)
"""
import pandas as pd
import re, ast, json
from pathlib import Path

CSV_PATH = "Mini_Dataset.csv"
OUT_DIR = Path("tissues")


def strip_numpy_array_wrappers(s):
    """
    Repeatedly strips 'array([...], dtype=object)' down to just '[...]'.
    Walks character-by-character to find the real matching close-paren for
    each 'array(' occurrence, rather than relying on regex alone -- arrays
    can nest inside dicts inside arrays here, arbitrarily deep, and a
    non-greedy regex would incorrectly stop at the first inner
    ", dtype=object)" rather than the outer one's.
    """
    while "array(" in s:
        start = s.index("array(")
        depth = 0
        end = None
        for j in range(start + len("array"), len(s)):
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:
            break  # unbalanced -- bail rather than loop forever
        inner = s[start + len("array(") : end]
        inner = re.sub(r",\s*dtype=object\s*$", "", inner)
        s = s[:start] + inner + s[end + 1 :]
    return s


def parse_tissues(raw):
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        outer = ast.literal_eval(raw)
    except Exception:
        return []
    if not outer:
        return []
    inner_str = list(outer.values())[0]
    stripped = strip_numpy_array_wrappers(inner_str)
    fixed = re.sub(r"\}\s+\{", "}, {", stripped)   # missing commas between top-level dicts
    fixed = re.sub(r"'\s+'", "', '", fixed)         # same, for adjacent quoted strings
    try:
        return ast.literal_eval(fixed)
    except Exception:
        return []  # a genuine parse failure -- shouldn't happen (0/101 in validation), but don't crash the run over one row


def main():
    df = pd.read_csv(CSV_PATH)
    OUT_DIR.mkdir(exist_ok=True)

    data = json.load(open("data.json"))
    by_uniprot = {p["uniprot"]: p for p in data}

    written, failed = 0, []
    for _, row in df.iterrows():
        uniprot = row["uniprot_id"]
        entries = parse_tissues(row.get("tissues"))
        if not entries:
            failed.append(uniprot)
            continue

        # clean each entry into a stable, simple shape for the frontend
        cleaned = []
        for e in entries:
            rna = e.get("rna") or {}
            protein = e.get("protein") or {}
            cleaned.append({
                "label": e.get("label"),
                "efo_code": e.get("efo_code"),
                "organs": e.get("organs") or [],
                "anatomical_systems": e.get("anatomical_systems") or [],
                "rna_value": rna.get("value"),
                "rna_zscore": rna.get("zscore"),
                "rna_level": rna.get("level"),
                "rna_unit": rna.get("unit"),
                "protein_reliability": protein.get("reliability"),
                "protein_level": protein.get("level"),
                "protein_cell_types": [c.get("name") for c in (protein.get("cell_type") or []) if isinstance(c, dict)],
            })

        (OUT_DIR / f"{uniprot}.json").write_text(json.dumps({"tissues": cleaned}))
        written += 1

        # top 5 by RNA expression value, for a quick data.json-level preview
        if uniprot in by_uniprot:
            top5 = sorted(
                [c for c in cleaned if c["rna_value"] is not None],
                key=lambda c: c["rna_value"], reverse=True
            )[:5]
            by_uniprot[uniprot]["top_tissues"] = [
                {"label": c["label"], "rna_value": c["rna_value"]} for c in top5
            ]

    json.dump(list(by_uniprot.values()), open("data.json", "w"))

    print(f"Wrote {written} per-protein tissue files to {OUT_DIR}/")
    if failed:
        print(f"Failed to parse tissue data for {len(failed)} protein(s) (skipped, not crashed): {failed}")


if __name__ == "__main__":
    main()
