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
    python3 ingest_to_postgres.py
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
        p.get("fold_total_size"), json.dumps(p.get("idr_ranges")), json.dumps(p.get("fold_ranges")),
        json.dumps(p.get("domains")), p.get("condensates"), p.get("condensate_types"),
        p.get("condensate_confidence"), p.get("condensate_forming"), p.get("fcr"), p.get("ncpr"),
        p.get("kappa"), p.get("mean_hydropathy"), p.get("isoelectric_point"), p.get("molecular_weight"),
        p.get("saturation_conc_uM"), p.get("delta_g_kt"), p.get("ppi_partner_count"),
        p.get("disease_count"), json.dumps(p.get("variant_stats")),
    ) for p in proteins]

    execute_values(cur, """
        INSERT INTO proteins (
            uniprot, gene, ensg, dominant, isoform_number, isoform_label, length,
            idr_count, idr_total_size, fold_total_size, idr_ranges, fold_ranges, domains,
            condensates, condensate_types, condensate_confidence, condensate_forming,
            fcr, ncpr, kappa, mean_hydropathy, isoelectric_point, molecular_weight,
            saturation_conc_uM, delta_g_kt, ppi_partner_count, disease_count, variant_stats
        ) VALUES %s
        ON CONFLICT (uniprot) DO UPDATE SET
            gene=EXCLUDED.gene, ensg=EXCLUDED.ensg, dominant=EXCLUDED.dominant,
            isoform_number=EXCLUDED.isoform_number, isoform_label=EXCLUDED.isoform_label,
            length=EXCLUDED.length, idr_count=EXCLUDED.idr_count,
            idr_total_size=EXCLUDED.idr_total_size, fold_total_size=EXCLUDED.fold_total_size,
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


if __name__ == "__main__":
    ingest_proteins()
    ingest_diseases()
    ingest_variants()
    cur.close()
    conn.close()
    print("\nDone. Note: R2 bulk-file upload was intentionally skipped this run (on hold) --")
    print("r2_details_key remains NULL for all proteins until that work resumes.")