# Data Pipeline

Run from the repository root:

```bash
python -m pipeline.build
```

The core pipeline reads `Mini_Dataset.csv` and writes the existing website
data products in place. The old Variants & RBP panel values are retained in
the checked-in `pipeline/legacy_variant_stats.json` lookup; the original
`per_protein_variant_stats.csv` / `per_protein_variant_stats_v2.csv` export is
not a build input and can be absent.

## Mutation viewer data

Mutation generation is opt-in because the upstream Tanya workflow is much
larger than the normal Mini Dataset build.

From an HPC-prefiltered variant file:

```bash
python -m pipeline.build --mutations variant_positions_prefiltered.csv
```

Or, if `variant_positions_filtered.csv` already exists:

```bash
python -m pipeline.build --mutations-filtered variant_positions_filtered.csv
```

See `pipeline/MUTATION_PIPELINE.md` for the complete lineage and validation
behavior. The 309 GB `awk_prefilter.sh` scan remains a separate HPC/raw-data
refresh operation.

For PostgreSQL ingestion, run:

```bash
python pipeline/ingest_to_postgres.py
```

from the repository root after setting `DATABASE_URL`.
