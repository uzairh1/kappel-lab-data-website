"""
ingest_to_postgres.py — loads data.json, diseases.json, and mutations/*
into the Supabase Postgres instance (schema.sql).
 
R2 upload is intentionally NOT included yet (on hold per instruction) --
the `r2_details_key` column stays NULL for now. Backfilling it later is a
separate, independent step that won't require touching this script's core
logic once R2 work resumes.
 
Reads the connection string from an environment variable, never hardcoded
-- this is what makes free -> paid (or provider -> provider) migration a
non-event: same script, just a different DATABASE_URL.
 
Setup:
    export DATABASE_URL="postgresql://user:password@host:port/dbname"
    # get the real value from Supabase dashboard -> Settings -> Database
    # -> Connection string. Put it in a .env file or your shell env,
    # never commit it to git.
 
Run:
    python3 pipeline/ingest_to_postgres.py
"""
import json, os, sys

# Support both `python pipeline/ingest_to_postgres.py` and module execution.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import psycopg2
from psycopg2.extras import execute_values

from pipeline.steps.tissues import normalize_protein_cell_types


STANDARD_BATCH_SIZE = 5_000
LARGE_JSON_BATCH_SIZE = 2_000
 
try:
    from dotenv import load_dotenv
    load_dotenv()  # reads .env in the current directory automatically, if present
except ImportError:
    pass  # fine if not installed -- DATABASE_URL can still be set directly in the shell environment


def preflight_generated_inputs():
    """Validate every locally adaptable detail/tissue value before connecting."""
    required = ["data.json", "diseases.json", "protein_details", "tissues", "mutations"]
    missing = [path for path in required if not os.path.exists(path)]
    if missing:
        raise ValueError(f"Required generated inputs are missing: {missing}")

    proteins = json.load(open("data.json"))
    protein_ids = {p["uniprot"] for p in proteins}
    diseases = json.load(open("diseases.json"))
    detail_ids = {name[:-5] for name in os.listdir("protein_details") if name.endswith(".json")}
    tissue_ids = {name[:-5] for name in os.listdir("tissues") if name.endswith(".json")}
    mutation_ids = {
        name for name in os.listdir("mutations")
        if os.path.isdir(os.path.join("mutations", name))
    }
    for label, ids in (
        ("diseases", set(diseases)),
        ("protein_details", detail_ids),
        ("tissues", tissue_ids),
    ):
        if ids != protein_ids:
            raise ValueError(
                f"{label} IDs differ from data.json: "
                f"missing={sorted(protein_ids - ids)}, extra={sorted(ids - protein_ids)}"
            )
    if not mutation_ids <= protein_ids:
        raise ValueError(f"mutations/ contains unknown proteins: {sorted(mutation_ids - protein_ids)}")

    ppi_count = tissue_count = 0
    for uniprot in sorted(detail_ids):
        detail = json.load(open(os.path.join("protein_details", f"{uniprot}.json")))
        for partner in detail.get("ppi", {}).get("all_partners", []):
            partner_id = partner.get("uniprot")
            score = partner.get("score")
            if not isinstance(partner_id, str) or not partner_id:
                raise ValueError(f"{uniprot}: invalid PPI partner ID: {partner_id!r}")
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                raise ValueError(
                    f"{uniprot}/{partner_id}: PPI score must be numeric, got {type(score).__name__}"
                )
            ppi_count += 1

    for uniprot in sorted(tissue_ids):
        tissue_doc = json.load(open(os.path.join("tissues", f"{uniprot}.json")))
        for tissue in tissue_doc.get("tissues", []):
            for key in ("organs", "anatomical_systems"):
                values = tissue.get(key) or []
                if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                    raise ValueError(f"{uniprot}/{tissue.get('label')}: {key} must be a string list")
            normalize_protein_cell_types(tissue.get("protein_cell_types"))
            for key in (
                "label", "efo_code", "rna_value", "rna_zscore", "rna_level",
                "protein_reliability", "protein_level",
            ):
                if isinstance(tissue.get(key), (dict, list)):
                    raise ValueError(
                        f"{uniprot}/{tissue.get('label')}: {key} must be scalar, "
                        f"got {type(tissue.get(key)).__name__}"
                    )
            tissue_count += 1

    print(
        "Preflight passed: "
        f"{len(protein_ids)} proteins, {ppi_count} PPI rows, "
        f"{tissue_count} tissue rows, {len(mutation_ids)} mutation proteins."
    )
 
def ingest_proteins(cur):
    proteins = json.load(open("data.json"))
    rows = [(
        p["uniprot"], p["gene"], p.get("ensg"), p.get("dominant"), p.get("isoform_number"),
        p.get("isoform_label"), p.get("isoform_count"), p.get("catalog_source"), p.get("length"), p.get("idr_count"), p.get("idr_total_size"),
        p.get("fold_total_size"), p.get("disorder_fraction"), json.dumps(p.get("idr_ranges")), json.dumps(p.get("fold_ranges")),
        json.dumps(p.get("domains")), p.get("condensates"), p.get("condensate_types"),
        p.get("condensate_confidence"), p.get("condensate_forming"), p.get("fcr"), p.get("ncpr"),
        p.get("kappa"), p.get("mean_hydropathy"), p.get("isoelectric_point"), p.get("molecular_weight"),
        p.get("saturation_conc_uM"), p.get("delta_g_kt"), p.get("ppi_partner_count"),
        p.get("disease_count"), json.dumps(p.get("variant_stats")),
    ) for p in proteins]
 
    execute_values(cur, """
        INSERT INTO proteins (
            uniprot, gene, ensg, dominant, isoform_number, isoform_label, isoform_count, catalog_source, length,
            idr_count, idr_total_size, fold_total_size, disorder_fraction, idr_ranges, fold_ranges, domains,
            condensates, condensate_types, condensate_confidence, condensate_forming,
            fcr, ncpr, kappa, mean_hydropathy, isoelectric_point, molecular_weight,
            saturation_conc_uM, delta_g_kt, ppi_partner_count, disease_count, variant_stats
        ) VALUES %s
        ON CONFLICT (uniprot) DO UPDATE SET
            gene=EXCLUDED.gene, ensg=EXCLUDED.ensg, dominant=EXCLUDED.dominant,
            isoform_number=EXCLUDED.isoform_number, isoform_label=EXCLUDED.isoform_label,
            isoform_count=EXCLUDED.isoform_count, catalog_source=EXCLUDED.catalog_source,
            length=EXCLUDED.length, idr_count=EXCLUDED.idr_count,
            idr_total_size=EXCLUDED.idr_total_size, fold_total_size=EXCLUDED.fold_total_size,
            disorder_fraction=EXCLUDED.disorder_fraction,
            idr_ranges=EXCLUDED.idr_ranges, fold_ranges=EXCLUDED.fold_ranges, domains=EXCLUDED.domains,
            condensates=EXCLUDED.condensates, condensate_types=EXCLUDED.condensate_types,
            condensate_confidence=EXCLUDED.condensate_confidence, condensate_forming=EXCLUDED.condensate_forming,
            fcr=EXCLUDED.fcr, ncpr=EXCLUDED.ncpr, kappa=EXCLUDED.kappa,
            mean_hydropathy=EXCLUDED.mean_hydropathy, isoelectric_point=EXCLUDED.isoelectric_point,
            molecular_weight=EXCLUDED.molecular_weight, saturation_conc_uM=EXCLUDED.saturation_conc_uM,
            delta_g_kt=EXCLUDED.delta_g_kt, ppi_partner_count=EXCLUDED.ppi_partner_count,
            disease_count=EXCLUDED.disease_count, variant_stats=EXCLUDED.variant_stats,
            updated_at=now()
    """, rows, page_size=STANDARD_BATCH_SIZE)
    protein_ids = [p["uniprot"] for p in proteins]
    cur.execute("DELETE FROM proteins WHERE NOT (uniprot = ANY(%s))", (protein_ids,))
    removed = cur.rowcount
    print(f"Ingested {len(rows)} proteins.")
    print(f"Removed {removed} proteins absent from the authoritative catalog.")


def ingest_protein_isoforms(cur):
    """Load nested expanded-dataset isoform metadata from protein detail files."""
    details_dir = "protein_details"
    if not os.path.isdir(details_dir):
        raise FileNotFoundError("protein_details/ is required for authoritative ingestion")

    cur.execute("SELECT uniprot FROM proteins")
    known_proteins = {row[0] for row in cur.fetchall()}
    cur.execute("DELETE FROM protein_isoforms")
    rows = []
    for fname in os.listdir(details_dir):
        if not fname.endswith(".json"):
            continue
        uniprot = fname[:-5]
        if uniprot not in known_proteins:
            continue
        detail = json.load(open(os.path.join(details_dir, fname)))
        for isoform in detail.get("isoforms", []):
            annotations = isoform.get("expanded_annotations") or {}
            rows.append((
                isoform["dataset_isoform_id"], uniprot, isoform.get("dominant", False),
                isoform.get("row_kind"), isoform.get("length"), isoform.get("sequence_sha256"),
                isoform.get("sequence_source"), json.dumps(annotations.get("identifiers") or {}),
                json.dumps(annotations),
            ))

    if rows:
        execute_values(cur, """
            INSERT INTO protein_isoforms (
                dataset_isoform_id, uniprot, dominant, row_kind, length, sequence_sha256,
                sequence_source, identifiers, expanded_annotations
            ) VALUES %s
        """, rows, page_size=STANDARD_BATCH_SIZE)
    print(f"Ingested {len(rows)} protein isoforms.")
 
 
def ingest_diseases(cur):
    diseases = json.load(open("diseases.json"))
    cur.execute("DELETE FROM diseases")  # full refresh -- diseases has no natural unique key to upsert on
    rows = [
        (uniprot, d["disease_id"], d.get("score"), d.get("evidence_count"), d.get("datatypes"))
        for uniprot, entries in diseases.items() for d in entries
    ]
    # one round-trip per BATCH, not per row -- this is what actually matters
    # once the DB isn't on localhost. 26K individual round-trips to a remote
    # DB (each with real network latency) is minutes; batched, it's seconds.
    execute_values(cur, """
        INSERT INTO diseases (uniprot, disease_id, score, evidence_count, datatypes) VALUES %s
    """, rows, page_size=STANDARD_BATCH_SIZE)
    print(f"Ingested {len(rows)} disease associations across {len(diseases)} proteins.")
 
 
def ingest_variants(cur):
    mutations_dir = "mutations"
    if not os.path.isdir(mutations_dir):
        raise FileNotFoundError("mutations/ is required for authoritative ingestion")
    cur.execute("SELECT uniprot FROM proteins")
    known_proteins = {row[0] for row in cur.fetchall()}
 
    cur.execute("DELETE FROM variants")  # full refresh, same reasoning as diseases
    rows, skipped_proteins = [], []
    for uniprot in os.listdir(mutations_dir):
        protein_dir = os.path.join(mutations_dir, uniprot)
        if not os.path.isdir(protein_dir):
            continue
        if uniprot not in known_proteins:
            skipped_proteins.append(uniprot)  # in mutations/ but not in proteins table -- don't crash the whole run over one bad record
            continue
        index_path = os.path.join(protein_dir, "index.json")
        if not os.path.exists(index_path):
            continue
        index = json.load(open(index_path))
        iso_meta = {i["id"]: i for i in index["isoforms"]}
 
        for fname in os.listdir(protein_dir):
            if fname == "index.json" or not fname.endswith(".json"):
                continue
            iso_id = fname[:-5]
            data = json.load(open(os.path.join(protein_dir, fname)))
            meta = iso_meta.get(iso_id, {})
            for v in data["variants"]:
                rows.append((
                    uniprot, v["isoform_id"], v["variation_id"], meta.get("dominant"), meta.get("length"),
                    meta.get("isoform_length_mismatch"), v.get("position_start"), v.get("position_end"),
                    v.get("is_range"), v.get("mutated_from"), v.get("mutated_to"),
                    v.get("molecular_consequence"), v.get("variant_type"), v.get("mutation_type"),
                    v.get("primary_classification"), v.get("primary_condition"),
                    json.dumps(v.get("all_classifications")), v.get("n_collapsed_rows"),
                ))
 
    if rows:
        execute_values(cur, """
            INSERT INTO variants (
                uniprot, isoform_id, variation_id, isoform_dominant, isoform_length,
                isoform_length_mismatch, position_start, position_end, is_range,
                mutated_from, mutated_to, molecular_consequence, variant_type, mutation_type,
                primary_classification, primary_condition, all_classifications, n_collapsed_rows
            ) VALUES %s
        """, rows, page_size=LARGE_JSON_BATCH_SIZE)
    print(f"Ingested {len(rows)} variants.")
    if skipped_proteins:
        print(f"Skipped {len(skipped_proteins)} protein(s) in mutations/ with no matching row in proteins table "
              f"(ingest_proteins() must run first, or these are stale/orphaned entries): {skipped_proteins}")
 
 
def ingest_protein_detail_tables(cur):
    """Populates condensate_details, ppi_partners, idr_segments, go_terms
    from protein_details/*.json -- the data that used to only exist in
    lazy-loaded per-protein files, now queryable/filterable across all
    proteins at once."""
    details_dir = "protein_details"
    if not os.path.isdir(details_dir):
        raise FileNotFoundError("protein_details/ is required for authoritative ingestion")
 
    cur.execute("SELECT uniprot FROM proteins")
    known_proteins = {row[0] for row in cur.fetchall()}
 
    # condensate NAME/type/confidence live in data.json's parallel arrays
    # (aligned by index to condensate_details), not in protein_details
    # itself -- confirmed by direct inspection, not assumed
    proteins_raw = {p["uniprot"]: p for p in json.load(open("data.json"))}
 
    for table in ["condensate_details", "ppi_partners", "idr_segments", "go_terms"]:
        cur.execute(f"DELETE FROM {table}")  # full refresh, same reasoning as diseases/variants
 
    condensate_rows, ppi_rows, idr_rows, go_rows = [], [], [], []
    skipped = []
 
    for fname in os.listdir(details_dir):
        if not fname.endswith(".json"):
            continue
        uniprot = fname[:-5]
        if uniprot not in known_proteins:
            skipped.append(uniprot)
            continue
        d = json.load(open(os.path.join(details_dir, fname)))
        raw_p = proteins_raw.get(uniprot, {})
        cond_names = raw_p.get("condensates", [])
        cond_types = raw_p.get("condensate_types", [])
        cond_confidence = raw_p.get("condensate_confidence", [])
 
        for i, cd in enumerate(d.get("condensate_details", [])):
            condensate_rows.append((
                uniprot,
                cond_names[i] if i < len(cond_names) else None,
                cond_types[i] if i < len(cond_types) else None,
                cond_confidence[i] if i < len(cond_confidence) else None,
                cd.get("species_tax_id"), cd.get("dna_associated"), cd.get("rna_associated"),
                cd.get("chemical_mods"), cd.get("condensatopathy"),
            ))
 
        for p in d.get("ppi", {}).get("all_partners", []):
            partner_id = p.get("uniprot")
            ppi_rows.append((uniprot, partner_id, p.get("score"), partner_id in known_proteins))
 
        for i, seg in enumerate(d.get("biophysics_regions", {}).get("idr_segments", [])):
            idr_rows.append((
                uniprot, i + 1, seg.get("start"), seg.get("end"), seg.get("size"),
                seg.get("fcr"), seg.get("ncpr"), seg.get("kappa"), seg.get("delta"), seg.get("delta_max"),
                seg.get("isoelectric_point"), seg.get("molecular_weight"), seg.get("mean_net_charge"),
                seg.get("mean_hydropathy"), seg.get("uversky_hydropathy"), seg.get("ppii_propensity"),
                seg.get("fraction_negative"), seg.get("fraction_positive"),
                seg.get("fraction_expanding"), seg.get("fraction_disorder_promoting"),
            ))
 
        for aspect, terms in d.get("go_terms", {}).items():
            for t in terms:
                go_rows.append((uniprot, aspect, t.get("id"), t.get("description"), t.get("evidence")))
 
    if condensate_rows:
        execute_values(cur, """
            INSERT INTO condensate_details (uniprot, condensate_name, condensate_type, confidence,
                species_tax_id, dna_associated, rna_associated, chemical_mods, condensatopathy) VALUES %s
        """, condensate_rows, page_size=STANDARD_BATCH_SIZE)
    if ppi_rows:
        execute_values(cur, """
            INSERT INTO ppi_partners (uniprot, partner_uniprot, score, partner_in_pilot_set) VALUES %s
        """, ppi_rows, page_size=STANDARD_BATCH_SIZE)
    if idr_rows:
        execute_values(cur, """
            INSERT INTO idr_segments (uniprot, segment_index, start_pos, end_pos, size,
                fcr, ncpr, kappa, delta, delta_max, isoelectric_point, molecular_weight,
                mean_net_charge, mean_hydropathy, uversky_hydropathy, ppii_propensity,
                fraction_negative, fraction_positive, fraction_expanding, fraction_disorder_promoting) VALUES %s
        """, idr_rows, page_size=STANDARD_BATCH_SIZE)
    if go_rows:
        execute_values(cur, """
            INSERT INTO go_terms (uniprot, aspect, go_id, description, evidence) VALUES %s
        """, go_rows, page_size=STANDARD_BATCH_SIZE)
    print(f"Ingested {len(condensate_rows)} condensate_details, {len(ppi_rows)} ppi_partners, "
          f"{len(idr_rows)} idr_segments, {len(go_rows)} go_terms rows.")
    if skipped:
        print(f"Skipped {len(skipped)} protein(s) in protein_details/ with no matching row in proteins table: {skipped}")
 
 
def ingest_tissue_expression(cur):
    tissues_dir = "tissues"
    if not os.path.isdir(tissues_dir):
        raise FileNotFoundError("tissues/ is required for authoritative ingestion")
 
    cur.execute("SELECT uniprot FROM proteins")
    known_proteins = {row[0] for row in cur.fetchall()}
    cur.execute("DELETE FROM tissue_expression")
 
    rows, skipped = [], []
    for fname in os.listdir(tissues_dir):
        if not fname.endswith(".json"):
            continue
        uniprot = fname[:-5]
        if uniprot not in known_proteins:
            skipped.append(uniprot)
            continue
        d = json.load(open(os.path.join(tissues_dir, fname)))
        for t in d.get("tissues", []):
            cell_type_names, cell_type_details = normalize_protein_cell_types(
                t.get("protein_cell_types")
            )
            rows.append((
                uniprot, t.get("label"), t.get("efo_code"), t.get("organs") or [],
                t.get("anatomical_systems") or [], t.get("rna_value"), t.get("rna_zscore"),
                t.get("rna_level"), t.get("protein_reliability"), t.get("protein_level"),
                cell_type_names, json.dumps(cell_type_details),
            ))
 
    if rows:
        execute_values(cur, """
            INSERT INTO tissue_expression (
                uniprot, label, efo_code, organs, anatomical_systems,
                rna_value, rna_zscore, rna_level, protein_reliability, protein_level,
                protein_cell_types, protein_cell_type_details
            ) VALUES %s
        """, rows, page_size=STANDARD_BATCH_SIZE)
    print(f"Ingested {len(rows)} tissue_expression rows.")
    if skipped:
        print(f"Skipped {len(skipped)} protein(s) in tissues/ with no matching row in proteins table: {skipped}")
 
 
def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set.")
        print("Either put it in .env or export DATABASE_URL before ingestion.")
        return 1

    try:
        preflight_generated_inputs()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: Local ingestion preflight failed: {exc}")
        return 1

    # One transaction gives readers either the complete old catalog or the
    # complete new catalog. The advisory lock prevents concurrent publishers.
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('kappel_catalog_ingestion'))")
            ingest_proteins(cur)
            ingest_protein_isoforms(cur)
            ingest_diseases(cur)
            ingest_protein_detail_tables(cur)
            ingest_tissue_expression(cur)
            ingest_variants(cur)
    print("\nDone. Note: R2 bulk-file upload was intentionally skipped this run (on hold) --")
    print("r2_details_key remains NULL for all proteins until that work resumes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
