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

## Previous names

The repository was reorganized without changing the meaning of these data
products. Use this table when translating older commands, documentation, or
Git history to the current layout.

| Previous path | Current path |
| --- | --- |
| `RBP_Dataset.csv` | `data/source/expanded_protein_annotations.csv` |
| `variant_positions_prefiltered.csv` | `data/mutation_inputs/tanya_catalog_variants.csv` |
| `variant_positions_filtered.csv` | `data/mutation_inputs/website_mutation_records.csv` |
| `Mini_Dataset.csv` | `data/archive/obsolete_legacy_inputs/legacy_mini_dataset.csv` |
| `per_protein_variant_stats_v2.csv` | `data/archive/obsolete_legacy_inputs/legacy_variant_statistics.csv` |
| `data.json` | `data/generated/protein_catalog.json` |
| `diseases.json` | `data/generated/disease_associations.json` |
| `protein_details/` | `data/generated/protein_details/` |
| `tissues/` | `data/generated/tissue_expression/` |
| `mutations/` | `data/generated/mutations/` |
| `uniprot_ids.txt` | `data/work/mutation_target_uniprot_ids.txt` |

The deployable package deliberately maps several descriptive internal names
back to their established public website paths. For example,
`protein_catalog.json` is published as `build/site/data.json`, and
`tissue_expression/` is published as `build/site/tissues/`.

## Previous legacy-resource names

| Previous path | Current path |
| --- | --- |
| `pipeline/legacy_catalog.tar.gz` | `pipeline/resources/legacy/protein_catalog_snapshot.tar.gz` |
| `pipeline/legacy_catalog_manifest.json` | `pipeline/resources/legacy/protein_catalog_manifest.json` |
| `pipeline/legacy_variant_stats.json` | `pipeline/resources/legacy/variant_rbp_lookup.json` |
| `pipeline/legacy_gene_annotations.json` | `pipeline/resources/legacy/gene_annotation_lookup.json` |
