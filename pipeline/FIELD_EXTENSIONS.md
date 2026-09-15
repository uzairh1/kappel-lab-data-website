# Registering complex Mini Dataset fields

The pipeline uses explicit field registries. A new source column is ignored
until its source and output names are added to `pipeline/field_families.py`.

## Per-IDR measurements

Add a `FieldSpec` to `IDR_FIELDS`. The source cell must contain one value per
`IDR_range`. For example:

```python
FieldSpec("IDR_SASA", "sasa")
```

This writes the registered value to:

```text
protein_details/<UNIPROT>.json
  biophysics_regions.idr_segments[].sasa
```

The build validates that the number of values matches the number of IDRs. A
mismatch fails validation rather than silently dropping values.

## Per-domain measurements

Add a `FieldSpec` to `DOMAIN_FIELDS`. Its source cell must be a dictionary
keyed by the same domain names used in `Domains_count`. For example:

```python
FieldSpec("Domains_SASA", "sasa")
```

This writes the registered value to:

```text
protein_details/<UNIPROT>.json
  domain_types[].sasa
```

Unknown domain keys fail validation.

## Condensate measurements

Add one `FieldSpec` to `CONDENSATE_FIELDS` in
`pipeline/field_families.py`.

## What this does *not* do

Propagation into generated JSON is separate from deciding how a brand-new
measurement should be displayed in the browser. If a new field needs its own
label, table column, filter, plot, or tooltip, `app.js` still needs the
corresponding UI change.
