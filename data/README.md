# Local and generated data

The contents of this directory are intentionally separated by lifecycle:

- `source/expanded_protein_annotations.csv` is the current expanded dataset.
- `mutation_inputs/tanya_catalog_variants.csv` is the broad HPC extraction.
- `mutation_inputs/website_mutation_records.csv` is the compact, directly
  rebuildable mutation input.
- `generated/` contains reproducible website JSON produced by the pipeline.
- `work/` contains disposable handoff files such as mutation target IDs.
- `archive/` is for obsolete local inputs retained temporarily during cleanup.

CSV sources, intermediates, generated data, work products, and archives are
ignored by Git. The frozen legacy cohort required by the build is tracked in
`pipeline/resources/legacy/`.
