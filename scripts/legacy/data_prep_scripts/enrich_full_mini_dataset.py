"""
enrich_full_mini_dataset.py — builds protein_details.json, a SEPARATE
lazy-loaded file covering every remaining field from Mini_Dataset.csv that
data.json doesn't already carry (sequence, HGVS info, full region-by-region
biophysics, domain-type stats, phase-separation patterning params, full PPI
partner lists, GO terms, condensate metadata, and Open Targets gene
annotation). Kept separate — same pattern as diseases.json — so the main
table's data.json stays small and fast; this loads only when a protein's
detail page is opened.

Explicitly deferred: the `tissues` column (per-protein tissue expression
profile). It's ~50KB+ of nested data per protein — big enough to warrant
its own file if wanted later, not bundled here.

Run:
    python3 enrich_full_mini_dataset.py
Reads:
    data.json, Mini_Dataset.csv
Writes:
    protein_details.json   (does NOT modify data.json)
"""
import pandas as pd, json, ast, re
from pathlib import Path

DATA_JSON = Path("data.json")
CSV_PATH = Path("Mini_Dataset.csv")
DETAILS_DIR = Path("protein_details")  # one file per protein, not one giant file — see main()

# ---------------------------------------------------------------- parsing helpers

def parse_pylist(s):
    if not isinstance(s, str) or s.strip() in ("", "[]"):
        return []
    cleaned = re.sub(r"np\.(int64|float64)\((-?[\d\.]+)\)", r"\2", s)
    try:
        return ast.literal_eval(cleaned)
    except Exception:
        return []

def parse_dict(s):
    if not isinstance(s, str) or s.strip() in ("", "{}"):
        return {}
    try:
        return ast.literal_eval(s)
    except Exception:
        return {}

def parse_numpyish(s):
    """
    Handles the Open Targets columns' inner values, which are numpy-array
    str() dumps embedded as strings — space-separated instead of
    comma-separated, so plain ast.literal_eval fails on them. Fixes up
    the two shapes seen (array of quoted strings, array of dicts) by
    inserting commas at the right boundaries, then parses.
    """
    if not isinstance(s, str):
        return s
    s = s.strip()
    if s in ("", "nan", "None"):
        return None
    if not (s.startswith("[") or s.startswith("{")):
        return s  # plain scalar string
    fixed = re.sub(r"'\s+'", "', '", s)          # 'foo' 'bar' -> 'foo', 'bar'
    fixed = re.sub(r"\}\s+\{", "}, {", fixed)     # {...} {...} -> {...}, {...}
    fixed = re.sub(r"\]\s+\[", "], [", fixed)     # nested array boundaries, rare
    try:
        return ast.literal_eval(fixed)
    except Exception:
        return None  # a handful of edge cases may fail to parse; leave null rather than guess

def parse_ot_field(raw_val, ensg):
    """Open Targets columns are {ensg: <numpy-ish string>} — unwrap then parse."""
    outer = parse_dict(raw_val) if isinstance(raw_val, str) else {}
    inner = outer.get(ensg)
    return parse_numpyish(inner)

def avg_list(lst):
    return round(sum(lst) / len(lst), 4) if lst else None


def region_biophysics(row, prefix):
    """Shared metric set used for whole-protein and FOLD regions -- these
    ARE genuinely scalar (confirmed: only IDR has multiple segments)."""
    def g(name):
        col = f"{prefix}{name}" if prefix else name
        val = row.get(col)
        return None if pd.isna(val) else val
    return {
        "fcr": g("FCR"), "ncpr": g("NCPR"), "kappa": g("kappa"),
        "delta": g("delta"), "delta_max": g("deltaMax"),
        "isoelectric_point": g("isoelectric_point"), "molecular_weight": g("molecular_weight"),
        "count_neg": g("countNeg"), "count_pos": g("countPos"), "count_neut": g("countNeut"),
        "fraction_negative": g("fraction_negative"), "fraction_positive": g("fraction_positive"),
        "fraction_expanding": g("fraction_expanding"), "fraction_disorder_promoting": g("fraction_disorder_promoting"),
        "mean_net_charge": g("mean_net_charge"), "mean_hydropathy": g("mean_hydropathy"),
        "uversky_hydropathy": g("uversky_hydropathy"), "ppii_propensity": g("PPII_propensity"),
    }

def idr_segment_biophysics(row, idr_ranges):
    """
    IDR_* biophysics columns are NOT scalar aggregates -- confirmed by
    direct inspection (CHD3/Q12873: IDR_FCR is a 9-element list, exactly
    matching its 9 IDR_range segments). Each column is a per-segment list,
    indexed the same way as idr_ranges. This returns one dict PER SEGMENT,
    each paired with its [start,end] position, instead of collapsing
    everything into one misleading aggregate value.
    """
    def parse_list_col(name):
        val = row.get(f"IDR_{name}")
        if not isinstance(val, str) or not val.strip():
            return []
        try:
            return ast.literal_eval(val)
        except Exception:
            return []

    aaf_list = parse_list_col("amino_acid_fractions")
    cols = {
        "fcr": parse_list_col("FCR"), "ncpr": parse_list_col("NCPR"), "kappa": parse_list_col("kappa"),
        "delta": parse_list_col("delta"), "delta_max": parse_list_col("deltaMax"),
        "isoelectric_point": parse_list_col("isoelectric_point"), "molecular_weight": parse_list_col("molecular_weight"),
        "count_neg": parse_list_col("countNeg"), "count_pos": parse_list_col("countPos"), "count_neut": parse_list_col("countNeut"),
        "fraction_negative": parse_list_col("fraction_negative"), "fraction_positive": parse_list_col("fraction_positive"),
        "fraction_expanding": parse_list_col("fraction_expanding"), "fraction_disorder_promoting": parse_list_col("fraction_disorder_promoting"),
        "mean_net_charge": parse_list_col("mean_net_charge"), "mean_hydropathy": parse_list_col("mean_hydropathy"),
        "uversky_hydropathy": parse_list_col("uversky_hydropathy"), "ppii_propensity": parse_list_col("PPII_propensity"),
    }

    segments = []
    for i, (start, end) in enumerate(idr_ranges):
        seg = {"start": start, "end": end, "size": end - start}
        for key, values in cols.items():
            seg[key] = values[i] if i < len(values) else None
        seg["amino_acid_fractions"] = aaf_list[i] if i < len(aaf_list) else None
        segments.append(seg)
    return segments

def domain_type_biophysics(row):
    """Domains_* columns are dicts keyed by domain NAME (not occurrence), unlike IDR/FOLD."""
    def dd(col):
        return parse_dict(row[col])
    counts = dd("Domains_count")
    fields = {
        "avg_size": dd("Domains_avg_size"), "total_size": dd("Domains_total_size"),
        "fcr": dd("Domains_FCR"), "ncpr": dd("Domains_NCPR"), "kappa": dd("Domains_kappa"), "omega": dd("Domains_Omega"),
        "isoelectric_point": dd("Domains_isoelectric_point"), "molecular_weight": dd("Domains_molecular_weight"),
        "count_neg": dd("Domains_countNeg"), "count_pos": dd("Domains_countPos"), "count_neut": dd("Domains_countNeut"),
        "fraction_negative": dd("Domains_fraction_negative"), "fraction_positive": dd("Domains_fraction_positive"),
        "fraction_expanding": dd("Domains_fraction_expanding"), "fraction_disorder_promoting": dd("Domains_fraction_disorder_promoting"),
        "mean_net_charge": dd("Domains_mean_net_charge"), "mean_hydropathy": dd("Domains_mean_hydropathy"),
        "uversky_hydropathy": dd("Domains_uversky_hydropathy"), "ppii_propensity": dd("Domains_PPII_propensity"),
        "delta": dd("Domains_delta"), "delta_max": dd("Domains_deltaMax"),
    }
    aaf = dd("Domains_amino_acid_fractions")
    out = []
    for name in counts:
        entry = {"name": name, "count": counts.get(name)}
        for key, valdict in fields.items():
            v = valdict.get(name)
            entry[key] = avg_list(v) if isinstance(v, list) and v and isinstance(v[0], (int, float)) else (v[0] if isinstance(v, list) and v else v)
        aaf_v = aaf.get(name)
        entry["amino_acid_fractions"] = aaf_v[0] if isinstance(aaf_v, list) and aaf_v else None
        entry["discrete_seq"] = dd("Domains_discrete_seq").get(name)
        entry["concat_seq"] = dd("Domains_concat_seq").get(name)
        out.append(entry)
    return out

def go_terms(row, prefix):
    ids = parse_pylist(row[f"{prefix}_ids"])
    descs = parse_pylist(row[f"{prefix}_descriptions"])
    evid = parse_pylist(row[f"{prefix}_evidence"])
    n = min(len(ids), len(descs), len(evid)) if evid else min(len(ids), len(descs))
    out = []
    for i in range(len(ids)):
        out.append({
            "id": ids[i],
            "description": descs[i] if i < len(descs) else None,
            "evidence": evid[i] if i < len(evid) else None,
        })
    return out

def ppi_dict_to_list(d):
    return [{"uniprot": k, "score": v} for k, v in d.items()]


def main():
    with open(DATA_JSON) as f:
        proteins = json.load(f)

    df = pd.read_csv(CSV_PATH)
    by_uniprot = {row["uniprot_id"]: row for _, row in df.iterrows()}

    details = {}
    for p in proteins:
        row = by_uniprot.get(p["uniprot"])
        if row is None:
            continue
        ensg = row["ID"]
        d = {}

        d["sequence"] = row["sequence"]

        d["hgvs"] = {
            "protein_hgvs": [x.strip() for x in str(row["ProteinHGVS"]).split(",")] if isinstance(row["ProteinHGVS"], str) else [],
            "description": [x.strip() for x in str(row["HGVSDescription"]).split(",")] if isinstance(row["HGVSDescription"], str) else [],
            "ensp": row["ENSP"], "ensp_clean": row["ENSP_clean"],
            "unique_name": row["UNIQUE"], "description": row["Description"],
        }

        idr_ranges_raw = parse_pylist(row["IDR_range"])
        idr_ranges = [(int(a), int(b)) for a, b in idr_ranges_raw] if idr_ranges_raw else []

        d["biophysics_regions"] = {
            "whole": region_biophysics(row, ""),
            "idr_segments": idr_segment_biophysics(row, idr_ranges),  # one entry per real IDR segment, not one aggregate
            "fold": region_biophysics(row, "FOLD_"),
        }
        d["biophysics_regions"]["whole"]["amino_acid_fractions"] = parse_dict(row["amino_acid_fractions"])
        d["biophysics_regions"]["fold"]["avg_size"] = None if pd.isna(row["FOLD_avg_size"]) else row["FOLD_avg_size"]
        d["biophysics_regions"]["fold"]["count"] = None if pd.isna(row["FOLD_count"]) else int(row["FOLD_count"])
        d["region_sequences"] = {
            "idr_discrete": parse_pylist(row["IDR_discrete_seq"]),
            "idr_concat": row["IDR_concat_seq"] if isinstance(row["IDR_concat_seq"], str) else None,
            "fold_discrete": parse_pylist(row["FOLD_discrete_seq"]),
            "fold_concat": row["FOLD_concat_seq"] if isinstance(row["FOLD_concat_seq"], str) else None,
        }
        d["domain_types"] = domain_type_biophysics(row)

        d["patterning"] = {
            "mean_lambda": avg_list(parse_pylist(row["mean_lambda"])),
            "faro": avg_list(parse_pylist(row["faro"])),
            "shd": avg_list(parse_pylist(row["shd"])),
            "scd": avg_list(parse_pylist(row["scd"])),
            "ah_ij": avg_list(parse_pylist(row["ah_ij"])),
            "nu_svr": avg_list(parse_pylist(row["nu_svr"])),
            "saturation_conc_mgml": avg_list(parse_pylist(row["Saturation concentration [mg/mL]"])),
        }

        uniprot_partners = parse_dict(row["PPI_UniProt_Partners"])
        uniprot_partners_in_ds = parse_dict(row["PPI_UniProt_Partners_in_Dataframe"])
        ensp_partners = parse_dict(row["PPI_ENSP_Partners"])
        ensp_partners_in_ds = parse_dict(row["PPI_ENSP_Partners_in_Dataframe"])
        d["ppi"] = {
            "all_partners": ppi_dict_to_list(uniprot_partners),
            "partners_in_pilot_set": ppi_dict_to_list(uniprot_partners_in_ds),
            "ensp_all_partners": ppi_dict_to_list(ensp_partners),
            "ensp_partners_in_pilot_set": ppi_dict_to_list(ensp_partners_in_ds),
        }

        d["go_terms"] = {
            "cellular_component": go_terms(row, "C"),
            "biological_process": go_terms(row, "P"),
            "molecular_function": go_terms(row, "F"),
        }

        cond_species = parse_pylist(row["Species Tax Id"])
        cond_dna = parse_pylist(row["DNA"])
        cond_rna = parse_pylist(row["RNA"])
        cond_cmods = parse_pylist(row["C-mods"])
        cond_pathy = parse_pylist(row["Condensatopathy"])
        cond_uid = parse_pylist(row["UID"])
        cond_protein_count = parse_pylist(row["Proteins"])
        cond_details = []
        for i in range(len(p.get("condensates", []))):
            cond_details.append({
                "species_tax_id": cond_species[i] if i < len(cond_species) else None,
                "dna_associated": cond_dna[i] if i < len(cond_dna) else None,
                "rna_associated": cond_rna[i] if i < len(cond_rna) else None,
                "chemical_mods": cond_cmods[i] if i < len(cond_cmods) else None,
                "condensatopathy": cond_pathy[i] if i < len(cond_pathy) else None,
                "condensate_db_uid": cond_uid[i] if i < len(cond_uid) else None,
                "reported_protein_count": cond_protein_count[i] if i < len(cond_protein_count) else None,
            })
        d["condensate_details"] = cond_details

        homologues = parse_ot_field(row["homologues"], ensg) or []
        tractability = parse_ot_field(row["tractability"], ensg) or []
        d["gene_annotation"] = {
            "approved_name": parse_ot_field(row["approvedName"], ensg),
            "biotype": parse_ot_field(row["biotype"], ensg),
            "id_list": parse_pylist(row["ID_list"]),
            "transcript_ids": parse_ot_field(row["transcriptIds"], ensg) or [],
            "canonical_transcript": parse_ot_field(row["canonicalTranscript"], ensg),
            "canonical_exons": parse_ot_field(row["canonicalExons"], ensg) or [],
            "genomic_location": parse_ot_field(row["genomicLocation"], ensg),
            "synonyms": parse_ot_field(row["synonyms"], ensg) or [],
            "symbol_synonyms": parse_ot_field(row["symbolSynonyms"], ensg) or [],
            "name_synonyms": parse_ot_field(row["nameSynonyms"], ensg) or [],
            "function_descriptions": parse_ot_field(row["functionDescriptions"], ensg) or [],
            "subcellular_locations": parse_ot_field(row["subcellularLocations"], ensg) or [],
            "obsolete_symbols": parse_ot_field(row["obsoleteSymbols"], ensg) or [],
            "obsolete_names": parse_ot_field(row["obsoleteNames"], ensg) or [],
            "protein_ids": parse_ot_field(row["proteinIds"], ensg) or [],
            "db_xrefs": parse_ot_field(row["dbXrefs"], ensg) or [],
            "pathways": parse_ot_field(row["pathways"], ensg) or [],
            "tss": parse_ot_field(row["tss"], ensg),
            "target_class": parse_ot_field(row["targetClass"], ensg),
            "hallmarks": parse_ot_field(row["hallmarks"], ensg),
            "tep": parse_ot_field(row["tep"], ensg),
            "chemical_probes": parse_ot_field(row["chemicalProbes"], ensg),
            "safety_liabilities": parse_ot_field(row["safetyLiabilities"], ensg),
            "alternative_genes": parse_ot_field(row["alternativeGenes"], ensg),
            "constraint": parse_ot_field(row["constraint"], ensg) or [],
            "homologue_count": len(homologues),
            "homologues_sample": homologues[:15],
            "tractability_summary": [t for t in tractability if isinstance(t, dict) and t.get("value") is True],
        }
        # NOTE: `tissues` intentionally not included — see module docstring.

        details[p["uniprot"]] = d

    DETAILS_DIR.mkdir(exist_ok=True)
    total_bytes = 0
    for uniprot, d in details.items():
        out_path = DETAILS_DIR / f"{uniprot}.json"
        text = json.dumps(d)
        out_path.write_text(text)
        total_bytes += len(text)

    print(f"Wrote {len(details)} per-protein detail files to {DETAILS_DIR}/ "
          f"(avg {total_bytes//max(len(details),1)/1024:.0f} KB each, {total_bytes/1024/1024:.1f} MB total)")

if __name__ == "__main__":
    main()