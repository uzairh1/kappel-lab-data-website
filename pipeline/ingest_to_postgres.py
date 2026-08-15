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
import psycopg2
from psycopg2.extras import execute_values
 
try:
    from dotenv import load_dotenv
    load_dotenv()  # reads .env in the current directory automatically, if present
except ImportError:
    pass  # fine if not installed -- DATABASE_URL can still be set directly in the shell environment
 
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set.")
    print("Either: (1) put it in a .env file (pip install python-dotenv first), or")
    print('        (2) set it directly: export DATABASE_URL="postgresql://..."')
    sys.exit(1)
 
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
 
 
def ingest_proteins():
    proteins = json.load(open("data.json"))
    rows = [(
        p["uniprot"], p["gene"], p.get("ensg"), p.get("dominant"), p.get("isoform_number"),
        p.get("isoform_label"), p.get("length"), p.get("idr_count"), p.get("idr_total_size"),
        p.get("fold_total_size"), p.get("disorder_fraction"), json.dumps(p.get("idr_ranges")), json.dumps(p.get("fold_ranges")),
        json.dumps(p.get("domains")), p.get("condensates"), p.get("condensate_types"),
        p.get("condensate_confidence"), p.get("condensate_forming"), p.get("fcr"), p.get("ncpr"),
        p.get("kappa"), p.get("mean_hydropathy"), p.get("isoelectric_point"), p.get("molecular_weight"),
        p.get("saturation_conc_uM"), p.get("delta_g_kt"), p.get("ppi_partner_count"),
        p.get("disease_count"), json.dumps(p.get("variant_stats")),
    ) for p in proteins]
 
    execute_values(cur, """
        INSERT INTO proteins (
            uniprot, gene, ensg, dominant, isoform_number, isoform_label, length,
            idr_count, idr_total_size, fold_total_size, disorder_fraction, idr_ranges, fold_ranges, domains,
            condensates, condensate_types, condensate_confidence, condensate_forming,
            fcr, ncpr, kappa, mean_hydropathy, isoelectric_point, molecular_weight,
            saturation_conc_uM, delta_g_kt, ppi_partner_count, disease_count, variant_stats
        ) VALUES %s
        ON CONFLICT (uniprot) DO UPDATE SET
            gene=EXCLUDED.gene, ensg=EXCLUDED.ensg, dominant=EXCLUDED.dominant,
            isoform_number=EXCLUDED.isoform_number, isoform_label=EXCLUDED.isoform_label,
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
    """, rows, page_size=1000)
    conn.commit()
    print(f"Ingested {len(rows)} proteins.")
 
 
def ingest_diseases():
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
    """, rows, page_size=1000)
    conn.commit()
    print(f"Ingested {len(rows)} disease associations across {len(diseases)} proteins.")
 
 
def ingest_variants():
    mutations_dir = "mutations"
    if not os.path.isdir(mutations_dir):
        print("No mutations/ directory found -- skipping variant ingestion.")
        return
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
        """, rows, page_size=1000)
    conn.commit()
    print(f"Ingested {len(rows)} variants.")
    if skipped_proteins:
        print(f"Skipped {len(skipped_proteins)} protein(s) in mutations/ with no matching row in proteins table "
              f"(ingest_proteins() must run first, or these are stale/orphaned entries): {skipped_proteins}")
 
 
def ingest_protein_detail_tables():
    """Populates condensate_details, ppi_partners, idr_segments, go_terms
    from protein_details/*.json -- the data that used to only exist in
    lazy-loaded per-protein files, now queryable/filterable across all
    proteins at once."""
    details_dir = "protein_details"
    if not os.path.isdir(details_dir):
        print("No protein_details/ directory found -- skipping detail table ingestion.")
        return
 
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
        """, condensate_rows, page_size=1000)
    if ppi_rows:
        execute_values(cur, """
            INSERT INTO ppi_partners (uniprot, partner_uniprot, score, partner_in_pilot_set) VALUES %s
        """, ppi_rows, page_size=1000)
    if idr_rows:
        execute_values(cur, """
            INSERT INTO idr_segments (uniprot, segment_index, start_pos, end_pos, size,
                fcr, ncpr, kappa, delta, delta_max, isoelectric_point, molecular_weight,
                mean_net_charge, mean_hydropathy, uversky_hydropathy, ppii_propensity,
                fraction_negative, fraction_positive, fraction_expanding, fraction_disorder_promoting) VALUES %s
        """, idr_rows, page_size=1000)
    if go_rows:
        execute_values(cur, """
            INSERT INTO go_terms (uniprot, aspect, go_id, description, evidence) VALUES %s
        """, go_rows, page_size=1000)
    conn.commit()
 
    print(f"Ingested {len(condensate_rows)} condensate_details, {len(ppi_rows)} ppi_partners, "
          f"{len(idr_rows)} idr_segments, {len(go_rows)} go_terms rows.")
    if skipped:
        print(f"Skipped {len(skipped)} protein(s) in protein_details/ with no matching row in proteins table: {skipped}")
 
 
def ingest_tissue_expression():
    tissues_dir = "tissues"
    if not os.path.isdir(tissues_dir):
        print("No tissues/ directory found -- skipping tissue expression ingestion.")
        return
 
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
            rows.append((
                uniprot, t.get("label"), t.get("efo_code"), t.get("organs") or [],
                t.get("anatomical_systems") or [], t.get("rna_value"), t.get("rna_zscore"),
                t.get("rna_level"), t.get("protein_reliability"), t.get("protein_level"),
                t.get("protein_cell_types") or [],
            ))
 
    if rows:
        execute_values(cur, """
            INSERT INTO tissue_expression (
                uniprot, label, efo_code, organs, anatomical_systems,
                rna_value, rna_zscore, rna_level, protein_reliability, protein_level, protein_cell_types
            ) VALUES %s
        """, rows, page_size=1000)
    conn.commit()
    print(f"Ingested {len(rows)} tissue_expression rows.")
    if skipped:
        print(f"Skipped {len(skipped)} protein(s) in tissues/ with no matching row in proteins table: {skipped}")
 
 
if __name__ == "__main__":
    ingest_proteins()
    ingest_diseases()
    ingest_variants()
    ingest_protein_detail_tables()
    ingest_tissue_expression()
    cur.close()
    conn.close()
    print("\nDone. Note: R2 bulk-file upload was intentionally skipped this run (on hold) --")
    print("r2_details_key remains NULL for all proteins until that work resumes.")