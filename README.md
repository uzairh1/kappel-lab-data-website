# Kappel Lab Protein Data Website

This repository builds and publishes a combined protein catalog consisting of
the frozen 101-protein legacy cohort and the current expanded annotation
dataset. The source layout uses descriptive internal names while the packaging
step preserves the website's established public filenames.

## Repository layout

- `frontend/` — browser interface source.
- `api/` — FastAPI/Postgres production API.
- `database/` — base schema and incremental migrations.
- `data/source/` — local expanded source dataset; ignored by Git.
- `data/mutation_inputs/` — local Tanya mutation intermediates; ignored by Git.
- `data/generated/` — reproducible JSON build products; ignored by Git.
- `pipeline/` — build, validation, packaging, ingestion, and tests.
- `pipeline/resources/legacy/` — checked-in frozen legacy catalog and lookups.
- `scripts/hpc/` — scripts for refreshing mutation source rows on HPC.
- `docs/` — detailed pipeline and schema-extension documentation.
- `build/site/` — deployable static website; ignored by Git.

## Setup

Install pipeline dependencies:

```bash
python -m pip install -r pipeline/requirements.txt
```

For API development, install the API dependencies as well:

```bash
python -m pip install -r api/requirements.txt
```

Copy `.env.example` to `.env` and provide a database URL only when migration,
ingestion, or local API work is needed. Never commit `.env`.

## Build and verify

Place the expanded dataset at:

```text
data/source/expanded_protein_annotations.csv
```

Then run:

```bash
python -m pipeline.build
python -m unittest discover pipeline/tests
python -m pipeline.package_site
```

The package command maps internal names to the stable public website contract:

- `protein_catalog.json` becomes `build/site/data.json`.
- `disease_associations.json` becomes `build/site/diseases.json`.
- `tissue_expression/` becomes `build/site/tissues/`.
- `frontend/application.js` becomes `build/site/app.js`.

## Publish to Postgres

After a successful build:

```bash
python pipeline/apply_database_migrations.py
python pipeline/ingest_postgres.py
```

Ingestion is an authoritative single-transaction refresh. See
`docs/DATA_PIPELINE.md` and `docs/MUTATION_PIPELINE.md` for the complete data
workflow.
