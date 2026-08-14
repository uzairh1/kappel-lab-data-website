# Adding complex Mini Dataset fields

The pipeline recognizes structured column **families** so new measurements do
not require another preprocessing script.

## Per-IDR measurements

Add a column named `IDR_<NAME>` whose cell contains one value per `IDR_range`.
For example:

```text
IDR_SASA
```

is automatically written as:

```text
protein_details/<UNIPROT>.json
  biophysics_regions.idr_segments[].sasa
```

The build validates that the number of values matches the number of IDRs. A
mismatch fails validation rather than silently dropping values.

## Per-domain measurements

Add a column named `Domains_<NAME>` whose cell is a dictionary keyed by the
same domain names used in `Domains_count`.

For example:

```text
Domains_SASA
```

is automatically written as:

```text
protein_details/<UNIPROT>.json
  domain_types[].sasa
```

Unknown domain keys fail validation.

## Condensate measurements

The current Mini Dataset uses irregular source names for condensate fields, so
these cannot be inferred safely from a prefix. Add one `FieldSpec` to
`CONDENSATE_FIELDS` in `pipeline/field_families.py`; no other transformation
code needs to change.

## What this does *not* do

Propagation into generated JSON is separate from deciding how a brand-new
measurement should be displayed in the browser. If a new field needs its own
label, table column, filter, plot, or tooltip, `app.js` still needs the
corresponding UI change.
