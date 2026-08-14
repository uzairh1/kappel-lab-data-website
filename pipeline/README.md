# Data Pipeline

Run from the repository root:

```bash
python -m pipeline.build
```

The pipeline reads `Mini_Dataset.csv` and `per_protein_variant_stats_v2.csv` and writes the existing website data products in place.

It does not currently regenerate `mutations/`; that directory is the downstream artifact of the external Tanya big SASA workflow.

For PostgreSQL ingestion, run:

```bash
python pipeline/ingest_to_postgres.py
```

from the repository root after setting `DATABASE_URL`.
