# Data Pipeline

Run from the repository root:

```bash
python -m pipeline.build
```

The only external dataset required by the core build is
`data/source/expanded_protein_annotations.csv`. A different path, including an absolute path to a sample,
can be supplied explicitly:

```bash
python -m pipeline.build --dataset path/to/expanded_protein_annotations.csv
```

Rows are grouped by `uniprot_id`. Exactly one `dominant_isoform` row becomes
the backward-compatible parent protein, while every row is retained under
`data/generated/protein_details/<UNIPROT>.json` in the `isoforms` array. New annotation
families are stored in explicit `expanded_annotations` namespaces.

The old Variants & RBP and gene-annotation panel values are retained in the
checked-in `pipeline/resources/legacy/variant_rbp_lookup.json` and
`pipeline/resources/legacy/gene_annotation_lookup.json` lookups. Neither the legacy mini dataset
nor `per_protein_variant_stats*.csv` is a build input.

The original 101-protein website catalog is retained as the verified,
compressed `pipeline/resources/legacy/protein_catalog_snapshot.tar.gz` snapshot. The build checks its
hash and manifest, rejects any UniProt collision with the expanded dataset,
and emits one combined catalog. The archive excludes mutation payloads and is
about 2.3 MB; it is read directly without unpacking loose legacy JSON into the
working tree.

Before writing any output, the build rejects missing or duplicate isoform IDs,
proteins without exactly one dominant row, sequence-length mismatches, IDR
alignment errors, and domain-key mismatches.

## Mutation viewer data

Mutation generation is opt-in because the upstream Tanya workflow is much
larger than the normal Mini Dataset build.

From an HPC-prefiltered variant file:

```bash
python -m pipeline.build --mutations data/mutation_inputs/tanya_catalog_variants.csv
```

Or, if `website_mutation_records.csv` already exists:

```bash
python -m pipeline.build --mutations-filtered data/mutation_inputs/website_mutation_records.csv
```

See `docs/MUTATION_PIPELINE.md` for the complete lineage and validation
behavior. The 309 GB `awk_prefilter.sh` scan remains a separate HPC/raw-data
refresh operation.

When RefSeq protein identifiers uniquely match an expanded-dataset isoform,
the mutation index records its `dataset_isoform_id`. Otherwise the existing
length-based dominant selection remains the fallback.

For PostgreSQL ingestion, run:

```bash
python pipeline/apply_database_migrations.py
python pipeline/ingest_postgres.py
```

from the repository root after setting `DATABASE_URL`. The migration is
idempotent and the Python runner does not require the `psql` command-line
client. Ingestion is an authoritative, single-transaction refresh: it
removes proteins absent from the generated catalog, replaces all dependent
table contents, and rolls back the entire refresh if any stage fails. Tissue
cell-type names remain queryable as `TEXT[]`, while their full level and
reliability objects are retained in `protein_cell_type_details` JSONB.
