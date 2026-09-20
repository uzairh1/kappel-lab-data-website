# Data pipeline

## Current catalog

The website currently combines two cohorts into one 199-protein catalog:

- 101 original proteins from a frozen, checked-in legacy snapshot; and
- 98 proteins from the current expanded annotation CSV.

The two UniProt sets must not overlap. The build stops if a protein occurs in
both cohorts. When the expanded CSV is replaced in the future, its count may
change; the 101-protein legacy snapshot remains fixed unless an intentional
legacy migration is designed separately.

The original cohort retains its historical summaries, details, tissues, gene
annotations, and Variants & RBP lookup values. Expanded proteins use the new
CSV schema, including isoform-level RNA-binding, localization, InterPro,
functional-role, PTM, structure, and provenance annotations. Expanded values
are not invented for fields that are absent from the supplied dataset.

## Repository data layout

| Path | Role | Tracked by Git |
| --- | --- | --- |
| `data/source/expanded_protein_annotations.csv` | Primary expanded dataset and only external input required by a normal build | No |
| `pipeline/resources/legacy/protein_catalog_snapshot.tar.gz` | Frozen original 101-protein catalog | Yes |
| `pipeline/resources/legacy/protein_catalog_manifest.json` | Snapshot hashes, provenance, and expected counts | Yes |
| `pipeline/resources/legacy/variant_rbp_lookup.json` | Historical Variants & RBP values | Yes |
| `pipeline/resources/legacy/gene_annotation_lookup.json` | Historical gene-annotation values | Yes |
| `data/generated/` | Reproducible website JSON | No |
| `data/mutation_inputs/` | Large Tanya mutation intermediates | No |
| `build/site/` | Deployable static website | No |

The old mini dataset and per-protein variant-statistics CSV are retained only
under `data/archive/obsolete_legacy_inputs/`. They are not build inputs. See
`data/README.md` for the complete old-to-new filename mapping.

## Environment setup

Run commands from the repository root. Install the pipeline dependencies with:

```bash
python -m pip install -r pipeline/requirements.txt
```

Database operations additionally require a valid `DATABASE_URL` in the local
environment or ignored `.env` file. `.env.example` contains a safe placeholder.

## Normal build

Place the expanded CSV at its default location and run:

```bash
python -m pipeline.build
```

A different same-schema CSV can be tested without renaming it:

```bash
python -m pipeline.build --dataset path/to/expanded_protein_annotations.csv
```

The build performs these operations:

1. Loads and validates the expanded source schema.
2. Groups rows by `uniprot_id` and requires exactly one `dominant_isoform` row
   for each expanded protein.
3. Loads and verifies the frozen legacy archive against its manifest and
   SHA-256 checksum.
4. Rejects overlap between legacy and expanded UniProt IDs.
5. Writes the combined catalog, diseases, protein details, and tissues.
6. Validates the generated cross-file IDs and structured annotations.

Every expanded source row is retained in the parent protein's `isoforms`
array. The dominant row supplies backward-compatible parent-level fields.
Expanded annotation families are written into explicit
`expanded_annotations` namespaces; columns are not auto-discovered.

Source validation rejects, among other problems:

- missing required columns;
- missing or duplicate dataset isoform IDs;
- zero or multiple dominant rows for one protein;
- sequence-length mismatches;
- IDR value-count/alignment mismatches; and
- domain dictionaries whose keys do not match the declared domains.

## Generated outputs

| Internal output | Contents |
| --- | --- |
| `data/generated/protein_catalog.json` | Combined protein summaries used by the frontend |
| `data/generated/disease_associations.json` | Disease associations keyed by UniProt ID |
| `data/generated/protein_details/<UNIPROT>.json` | Deep annotations and expanded isoforms |
| `data/generated/tissue_expression/<UNIPROT>.json` | Tissue and cell-type expression |
| `data/generated/mutations/<UNIPROT>/` | Mutation-viewer index and isoform payloads |

A normal build deliberately leaves `data/generated/mutations/` unchanged.
Mutation refreshes are opt-in because their upstream source is much larger.
See `MUTATION_PIPELINE.md`.

## Tests and packaging

Run the test suite after pipeline changes:

```bash
python -m unittest discover pipeline/tests
```

Create a fresh deployable static site with:

```bash
python -m pipeline.package_site
```

Packaging writes `build/site/` from scratch, preventing stale files from a
previous catalog from surviving. Internal names are mapped to the established
public website contract:

| Internal source | Packaged public path |
| --- | --- |
| `frontend/application.js` | `build/site/app.js` |
| `data/generated/protein_catalog.json` | `build/site/data.json` |
| `data/generated/disease_associations.json` | `build/site/diseases.json` |
| `data/generated/protein_details/` | `build/site/protein_details/` |
| `data/generated/tissue_expression/` | `build/site/tissues/` |
| `data/generated/mutations/` | `build/site/mutations/` |

This compatibility mapping lets the source repository use descriptive names
without changing the existing website URLs.

## PostgreSQL publishing

The database definition is in `database/schema.sql`, with incremental changes
under `database/migrations/`. Apply the current migration and ingest the newly
generated catalog with:

```bash
python pipeline/apply_database_migrations.py
python pipeline/ingest_postgres.py
```

The migration runner uses Python and does not require the `psql` executable.
Ingestion first validates all local generated inputs, then performs an
authoritative refresh in one transaction under a PostgreSQL advisory lock. It
removes proteins absent from the current catalog, replaces dependent rows, and
rolls back the entire refresh if a stage fails.

## Replacing the expanded dataset

For a larger CSV with the same schema:

1. Back up the currently published CSV outside the repository.
2. Replace `data/source/expanded_protein_annotations.csv`.
3. Run `python -m pipeline.build` and review protein counts and all validation
   messages.
4. Run the tests.
5. If the UniProt set changed, refresh mutation targets and mutation data as
   described in `MUTATION_PIPELINE.md`. A normal build cannot create mutation
   rows for newly added proteins.
6. Run `python -m pipeline.package_site` and inspect `build/site/`.
7. Apply any new database migration, then run the authoritative ingestion.
8. Deploy the API and static package and verify representative legacy and
   expanded proteins in the UI.

If the replacement CSV changes column names or field structure, treat that as
a schema change rather than a simple data swap. Update the explicit mappings
using `FIELD_EXTENSIONS.md` and add tests before publishing.
