# Mutation pipeline

The mutation viewer has one expensive upstream/HPC step and two normal Python
stages.

```text
Tanya big SASA file (~309 GB)
        |
        |  awk_prefilter.sh (HPC / refresh only)
        v
variant_positions_prefiltered.csv
        |
        |  integrated filtering stage
        v
variant_positions_filtered.csv  (temporary by default)
        |
        |  integrated transformation stage
        v
mutations/{uniprot}/index.json
mutations/{uniprot}/{isoform}.json
```

## Normal core build

```bash
python -m pipeline.build
```

This does **not** touch `mutations/`.

## Rebuild mutations from the prefiltered Tanya data

```bash
python -m pipeline.build --mutations variant_positions_prefiltered.csv
```

This runs both Python mutation stages. The intermediate filtered CSV is created
in a temporary directory and deleted after a successful build.

## Rebuild from an existing filtered intermediate

```bash
python -m pipeline.build --mutations-filtered variant_positions_filtered.csv
```

This skips the filtering stage and regenerates `mutations/` directly.

## Safety behavior

Mutation generation is staged in a temporary directory. The existing
`mutations/` tree is replaced only after the newly generated tree passes
validation. This prevents both historical rerun hazards:

* a previous `variant_positions_filtered.csv` cannot accidentally be appended
  to by the integrated pipeline; and
* stale mutation JSON for proteins/isoforms that disappear from a new dataset
  cannot survive a successful rebuild.

The mutation stage uses the canonical proteins already built from
`Mini_Dataset.csv` for the target UniProt set and known protein lengths. It no
longer reopens `data.json` as an input dependency.

## What the viewer fields mean

Rows are collapsed by `(GeneIsoform, VariationID)`. One displayed variant can
therefore represent multiple source rows.

* `variation_id` comes from source `VariationID`.
* `n_collapsed_rows` is the number of filtered source rows represented by the
  displayed marker.
* `all_classifications` contains every parsed germline, somatic-impact, and
  oncogenicity classification entry across those collapsed rows.
* `primary_classification` and `primary_condition` come from the worst-severity
  entry in `all_classifications`.

Thus a viewer label such as `6 from 3 source rows` means there are six retained
classification entries across three collapsed source rows.
