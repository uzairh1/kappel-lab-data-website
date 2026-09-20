# Extending the expanded dataset schema

## Why fields are explicit

The pipeline does not auto-discover new CSV columns. Every supported field is
registered or transformed intentionally so that a misspelled, temporary, or
unexpected source column cannot silently become part of the website contract.

A same-schema replacement of
`data/source/expanded_protein_annotations.csv` requires no mapping changes. A
new or renamed column is a schema change and must follow the appropriate path
below.

There are two main registries:

- `pipeline/expanded_schema.py` maps ordinary parent- and isoform-level
  annotations into named `expanded_annotations` groups.
- `pipeline/field_families.py` maps parallel per-IDR, per-domain, and
  per-condensate columns into structured objects.

Core summary fields that affect canonical protein construction may also
require an explicit transformation in `pipeline/steps/canonical.py`,
`pipeline/steps/proteins.py`, or `pipeline/steps/structured.py`.

## Ordinary parent-level annotations

Parent annotations describe the protein or gene rather than one isoform. Add
the source column to the appropriate tuple in `PARENT_ANNOTATION_FIELDS` in
`pipeline/expanded_schema.py`, or create a clearly named group there.

Current parent groups include:

- `gene`;
- `open_targets`; and
- `dataset_provenance`.

The value will be written under:

```text
data/generated/protein_details/<UNIPROT>.json
  expanded_annotations.<group>.<source_column>
```

Parent annotations are built from the selected dominant source row.

## Ordinary isoform-level annotations

Add an isoform-specific source column to the appropriate tuple in
`ISOFORM_ANNOTATION_FIELDS` in `pipeline/expanded_schema.py`.

Current groups include identifiers, RNA binding, localization, InterPro,
functional roles, post-translational modifications, structure, and method or
provenance metadata.

The value will be written for every retained source row under:

```text
data/generated/protein_details/<UNIPROT>.json
  isoforms[].expanded_annotations.<group>.<source_column>
```

Most cells are normalized through `clean_cell()`, which converts missing
values to JSON `null` and parses supported JSON-like source values. Fields that
need special delimiter handling must be explicitly added to the relevant
normalization set rather than relying on prefix discovery.

## Per-IDR measurements

Add a `FieldSpec` to `IDR_FIELDS` in `pipeline/field_families.py`. For example:

```python
FieldSpec("IDR_SASA", "sasa")
```

The source cell must contain one value per declared `IDR_range`. The output is:

```text
data/generated/protein_details/<UNIPROT>.json
  biophysics_regions.idr_segments[].sasa
```

The build compares the number of registered values with the number of IDR
segments. A mismatch is a validation error, not a silent truncation.

## Per-domain measurements

Add a `FieldSpec` to `DOMAIN_FIELDS`. For example:

```python
FieldSpec("Domains_SASA", "sasa")
```

The source cell must be a dictionary keyed by the same domain names declared
in `Domains_count`. The output is:

```text
data/generated/protein_details/<UNIPROT>.json
  domain_types[].sasa
```

Unknown domain keys fail validation. `Domains_count` remains the anchor set;
domain ranges remain part of the architecture summary rather than being
folded into `domain_types` automatically.

## Per-condensate measurements

Add a `FieldSpec` to `CONDENSATE_FIELDS`. These source columns do not share a
reliable prefix, which is why each one must be named explicitly. For example:

```python
FieldSpec("New condensate column", "new_output_name")
```

Parallel condensate values must remain aligned with the condensate records
created by `pipeline/steps/structured.py`.

## Required source columns

If the new column is mandatory for every future build, add it to the source
validation contract in `pipeline/validation/checks.py`. Use this sparingly:
optional annotations should normally remain nullable rather than making an
otherwise usable dataset fail.

If a field changes an existing output invariant, update the relevant
validation check as part of the same change.

## UI, API, and database exposure

Adding a field to generated JSON does not automatically display or query it.
Depending on its intended use, also update:

- `frontend/application.js` for labels, cards, tables, filters, plots, or
  tooltips;
- `api/main.py` if the API needs a dedicated query or response field;
- `database/schema.sql` and a new file under `database/migrations/` if it needs
  a queryable database column or table; and
- `pipeline/ingest_postgres.py` if it must be ingested outside the existing
  JSONB annotation payloads.

Prefer retaining richly structured, infrequently queried annotations inside
the existing JSON/JSONB payloads. Add relational columns only when the website
needs cross-protein filtering, sorting, indexing, or aggregation.

## Tests and release checklist

For every schema extension:

1. Add a focused fixture and assertion under `pipeline/tests/`.
2. Run `python -m unittest discover pipeline/tests`.
3. Run `python -m pipeline.build` and require zero validation errors.
4. Inspect one generated protein-detail JSON containing the new value and one
   missing-value case.
5. If the UI changed, package with `python -m pipeline.package_site` and test
   the relevant legacy and expanded protein views.
6. If the database changed, apply the new migration before authoritative
   ingestion.
