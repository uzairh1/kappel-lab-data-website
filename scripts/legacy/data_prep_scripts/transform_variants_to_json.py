"""
transform_variants_to_json.py — turns variant_positions_filtered.csv into
mutations/{uniprot}/index.json + mutations/{uniprot}/{isoform_id}.json,
split per isoform (not one big per-protein file — see the split rationale
inline below), ready for the Mutant view tab to load directly.

Handles, per the locked design decisions:
  - Classification: a variant can have entries in Germline_Class,
    SomaticClinicalImpact_Class, and/or Oncogenicity_Class, each itself a
    JSON array of per-submitter entries. The WORST-CASE entry across all
    of them (by severity rank) drives the marker's color AND shape (shape
    = that same entry's condition) — keeps color/shape visually paired to
    one coherent assessment. ALL entries are kept in full for the
    click-detail panel, nothing is discarded.
  - Dedup: rows sharing the same (UniProtID, GeneIsoform, VariationID) are
    collapsed into one marker, with classification entries merged from all
    collapsed rows (this is where most of CTNNA1-style duplication comes
    from — same variant, same isoform, multiple submission records).
  - Range positions: position_start/position_end kept distinct (already
    parsed by filter_large_variant_file.py) — rendered as a span, not
    forced into a single point.
  - Isoform length: taken from THIS file's own isoform_length (derived
    from UnmutatedSeq), not from data.json — they can legitimately
    disagree (confirmed for O95319: 539 here vs 508 in data.json). When
    they disagree for the dominant isoform, isoform_length_mismatch=true
    is set so the frontend can show a flag, per the locked decision to
    surface it rather than silently pick one.
  - No default filtering happens here — ALL variants are written out.
    "Max visibility by default" is a frontend display decision, not a
    data-pipeline one.

Run (works fine on a login node now, file is small enough):
    python3 transform_variants_to_json.py
Reads:
    variant_positions_filtered.csv, data.json
Writes:
    mutations/{uniprot}/index.json         (isoform metadata list)
    mutations/{uniprot}/{isoform_id}.json  (that isoform's variants only)
    Proteins with no variant data (~26/101) simply get no folder.
"""
import pandas as pd, json, ast, math
from pathlib import Path
from collections import defaultdict

CSV_PATH = Path("variant_positions_filtered.csv")
DATA_JSON = Path("data.json")
OUT_DIR = Path("mutations")

SEVERITY_RANK = {
    "Pathogenic": 5, "Likely pathogenic": 4, "Oncogenic": 5, "Likely oncogenic": 4,
    "Uncertain significance": 3, "Uncertain risk allele": 3,
    "Likely benign": 2, "Benign": 1,
}
def severity(classification_label):
    return SEVERITY_RANK.get(classification_label, 0)  # unranked/unknown labels sort lowest

def parse_classification_json(val):
    if pd.isna(val) or not isinstance(val, str) or not val.strip():
        return []
    try:
        parsed = ast.literal_eval(val)
        return parsed if isinstance(parsed, list) else [parsed]
    except Exception:
        return []

def safe_int(val):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None

def main():
    our_proteins = {p["uniprot"]: p for p in json.load(open(DATA_JSON))}
    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"Loaded {len(df)} rows covering {df['UniProtID'].nunique()} proteins")

    OUT_DIR.mkdir(exist_ok=True)
    written, skipped_no_position = 0, 0

    for uniprot, protein_rows in df.groupby("UniProtID"):
        if uniprot not in our_proteins:
            continue  # shouldn't happen post-awk-filter, but guard anyway

        # ---- isoforms for this protein ----
        # NOTE: Dominant_Isoform in THIS file does NOT reliably identify a
        # single isoform per protein — diagnosed 71/75 proteins have MULTIPLE
        # distinct GeneIsoform values all marked Dominant_Isoform==1. Cannot
        # trust that column for "the" dominant isoform (see
        # diagnose_dominant_isoform.py). Fallback: pick whichever isoform's
        # length matches our already-verified data.json length (sourced from
        # Mini_Dataset.csv, extensively audited earlier in this project).
        # This is a heuristic standing in for an unresolved data-semantics
        # question — flagged in the output, not silently presented as fact.
        isoforms = {}
        for _, row in protein_rows.drop_duplicates("GeneIsoform").iterrows():
            iso_id = row["GeneIsoform"]
            if pd.isna(iso_id):
                continue
            length = safe_int(row.get("isoform_length"))
            isoforms[iso_id] = {
                "id": iso_id,
                "label": row.get("GeneIsoformWithDescription") or iso_id,
                "length": length,
                "dominant": False,  # decided below, not from the unreliable column
                "isoform_length_mismatch": None,
                "our_known_length": our_proteins[uniprot]["length"],
                "dominant_source": None,
            }

        our_length = our_proteins[uniprot]["length"]
        exact_matches = [i for i in isoforms.values() if i["length"] == our_length]
        if exact_matches:
            chosen = exact_matches[0]
            chosen["dominant"] = True
            chosen["dominant_source"] = "exact_length_match"
        elif isoforms:
            # no exact match — pick closest, flag as inferred not confirmed
            with_length = [i for i in isoforms.values() if i["length"] is not None]
            if with_length:
                chosen = min(with_length, key=lambda i: abs(i["length"] - our_length))
                chosen["dominant"] = True
                chosen["dominant_source"] = "closest_length_inferred"
                chosen["isoform_length_mismatch"] = True

        # ---- dedup: group rows by (GeneIsoform, VariationID), merge classifications ----
        groups = defaultdict(list)
        for _, row in protein_rows.iterrows():
            if pd.isna(row.get("GeneIsoform")) or pd.isna(row.get("VariationID")):
                continue
            groups[(row["GeneIsoform"], row["VariationID"])].append(row)

        variants = []
        for (iso_id, variation_id), rows in groups.items():
            first = rows[0]
            pos_start = safe_int(first.get("position_start"))
            pos_end = safe_int(first.get("position_end"))
            if pos_start is None:
                skipped_no_position += 1
                continue  # can't plot without a position — still counted, not silently lost

            # merge classification entries across ALL collapsed rows and ALL 3 schemes
            all_entries = []
            for r in rows:
                for scheme, col in [("germline","Germline_Class"),
                                     ("somatic","SomaticClinicalImpact_Class"),
                                     ("oncogenicity","Oncogenicity_Class")]:
                    for e in parse_classification_json(r.get(col)):
                        if isinstance(e, dict):
                            all_entries.append({
                                "scheme": scheme,
                                "condition": e.get("condition"),
                                "classification": e.get("description"),
                                "review_status": e.get("review_status"),
                                "submission_count": e.get("submission_count"),
                                "date_last_evaluated": e.get("date_last_evaluated"),
                            })

            if all_entries:
                worst = max(all_entries, key=lambda e: severity(e["classification"]))
                primary_classification = worst["classification"]
                primary_condition = worst["condition"]
            else:
                primary_classification, primary_condition = None, None

            variants.append({
                "variation_id": variation_id,
                "isoform_id": iso_id,
                "position_start": pos_start,
                "position_end": pos_end if pos_end is not None else pos_start,
                "is_range": pos_end is not None and pos_end != pos_start,
                "mutated_from": first.get("MutatedFrom"),
                "mutated_to": first.get("MutatedTo"),
                "molecular_consequence": first.get("MolecularConsequence"),
                "variant_type": first.get("VariantType"),
                "mutation_type": first.get("MutationType"),
                "primary_classification": primary_classification,
                "primary_condition": primary_condition,
                "all_classifications": all_entries,
                "n_collapsed_rows": len(rows),  # transparency: how many raw rows this represents
            })

        if not variants:
            continue

        # Split per-isoform, not one big per-protein file — the UI only
        # shows the dominant isoform expanded by default, so shipping every
        # alternate isoform's full variant payload upfront is pure waste.
        # Real-world case that forced this: CTNNA1 (38 isoforms) produced a
        # 131MB single file, well past GitHub's 100MB limit and far too
        # much to download just to view one protein's dominant track.
        protein_dir = OUT_DIR / uniprot
        protein_dir.mkdir(exist_ok=True)

        variants_by_isoform = defaultdict(list)
        for v in variants:
            variants_by_isoform[v["isoform_id"]].append(v)

        index_isoforms = []
        for iso_id, iso_meta in isoforms.items():
            iso_variants = variants_by_isoform.get(iso_id, [])
            if not iso_variants:
                continue
            (protein_dir / f"{iso_id}.json").write_text(json.dumps({"variants": iso_variants}))
            index_isoforms.append({**iso_meta, "variant_count": len(iso_variants)})

        # lightweight aggregate so filter dropdowns can populate fully
        # without needing to eager-fetch every isoform's full variant file
        all_classes = sorted({v["primary_classification"] for v in variants if v["primary_classification"]})
        all_conditions = sorted({v["primary_condition"] for v in variants if v["primary_condition"]})

        (protein_dir / "index.json").write_text(json.dumps({
            "isoforms": index_isoforms,
            "known_classifications": all_classes,
            "known_conditions": all_conditions,
            "total_variant_count": len(variants),
        }))
        written += 1

    print(f"\nWrote {written} per-protein mutation files to {OUT_DIR}/")
    print(f"Rows skipped for missing position (not silently dropped, just uncounted for plotting): {skipped_no_position}")

    exact, inferred, no_dominant = [], [], []
    for f in OUT_DIR.glob("*/index.json"):
        uid = f.parent.name
        d = json.loads(f.read_text())
        dominant_iso = next((i for i in d["isoforms"] if i["dominant"]), None)
        if dominant_iso is None:
            no_dominant.append(uid)
        elif dominant_iso["dominant_source"] == "exact_length_match":
            exact.append(uid)
        else:
            inferred.append((uid, dominant_iso["length"], dominant_iso["our_known_length"]))

    print(f"\n{'='*60}")
    print(f"DOMINANT ISOFORM SELECTION (Dominant_Isoform column not trusted —")
    print(f"see diagnose_dominant_isoform.py: 71/75 proteins had multiple")
    print(f"isoforms marked dominant in the source file)")
    print(f"{'='*60}")
    print(f"Exact length match to our verified data.json (confident): {len(exact)} / {written}")
    print(f"No exact match — closest length used as INFERRED, not confirmed: {len(inferred)} / {written}")
    for uid, real_len, our_len in inferred:
        print(f"  {uid}: closest available is {real_len} aa, our record says {our_len} aa")
    print(f"No isoform with any usable length at all — no dominant track chosen: {len(no_dominant)} / {written}")
    for uid in no_dominant:
        print(f"  {uid}")


if __name__ == "__main__":
    main()
