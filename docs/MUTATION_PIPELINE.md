# Mutation pipeline

## Current context

Mutation data is independent of the normal protein-catalog build. The current
catalog contains 101 frozen legacy proteins and 98 expanded proteins. Mutation
targets must cover the union of those UniProt IDs, but the generated mutation
tree contains folders only for proteins with retained source rows. At the time
of this reorganization, 79 of the 199 proteins have generated mutation data.

The raw Tanya variant-position export is approximately 309 GB and remains on
HPC storage. It must not be copied into this repository.

## Data flow

```text
Tanya raw variant-position CSV (~309 GB, HPC)
        |
        | scripts/hpc/extract_catalog_variants.sh
        v
data/mutation_inputs/tanya_catalog_variants.csv
        |
        | integrated Python filtering
        v
website_mutation_records.csv (normally temporary)
        |
        | integrated JSON transformation and validation
        v
data/generated/mutations/<UNIPROT>/index.json
data/generated/mutations/<UNIPROT>/<ISOFORM>.json
```

## The two mutation CSVs

`data/mutation_inputs/tanya_catalog_variants.csv` is the broader HPC result.
It contains complete Tanya rows for the UniProt IDs supplied to the scan,
including the full `UnmutatedSeq` and columns the website does not currently
use. Keep it when filtering rules or required Tanya columns may change.

`data/mutation_inputs/website_mutation_records.csv` is the compact,
website-ready intermediate. The filtering stage:

- rechecks UniProt IDs against the catalog being built;
- retains only the mutation columns required by the website;
- parses `ProteinPosition` into `position_start` and `position_end`;
- derives `isoform_length` from `UnmutatedSeq`;
- records parse failures and range rows; and
- removes the full sequence column.

The compact file is sufficient to reproduce the current mutation JSON, but it
cannot recover source columns that were discarded. Neither CSV can supply
mutations for a newly added protein unless that protein was included in the
HPC target list used to create the file.

## Generate the target list

Run this locally from the repository root:

```bash
python scripts/hpc/generate_mutation_target_ids.py
```

The defaults read:

- legacy IDs from
  `pipeline/resources/legacy/protein_catalog_snapshot.tar.gz`;
- expanded IDs from `data/source/expanded_protein_annotations.csv`; and
- write `data/work/mutation_target_uniprot_ids.txt`.

For the current dataset, the command should report 101 legacy proteins, 98
expanded proteins, zero overlap, and 199 combined targets. Future expanded
datasets may produce different expanded and combined counts.

The explicit equivalent is:

```bash
python scripts/hpc/generate_mutation_target_ids.py \
  --legacy-catalog pipeline/resources/legacy/protein_catalog_snapshot.tar.gz \
  --expanded-data data/source/expanded_protein_annotations.csv \
  --output data/work/mutation_target_uniprot_ids.txt
```

## Run the HPC extraction

Copy these two small files to the HPC system:

- `data/work/mutation_target_uniprot_ids.txt`
- `scripts/hpc/extract_catalog_variants.sh`

Submit the scan through the cluster scheduler. The command executed by the job
is:

```bash
bash extract_catalog_variants.sh \
  /absolute/path/to/TANYA_309GB.csv \
  mutation_target_uniprot_ids.txt \
  tanya_catalog_variants.csv
```

The script requires `UniProtID` to be the first CSV column. It writes to a
temporary partial file and renames the result only after a complete scan, so an
interrupted job cannot look like a finished extraction. Its AWK implementation
also assumes one CSV record per physical line; reconfirm that property if the
raw export format changes.

Copy the completed result back to:

```text
data/mutation_inputs/tanya_catalog_variants.csv
```

## Rebuild mutation JSON

From the broader HPC extraction, run both local stages:

```bash
python -m pipeline.build \
  --mutations data/mutation_inputs/tanya_catalog_variants.csv
```

This creates the compact filtered CSV in a temporary directory and deletes it
after a successful build.

If a retained compact intermediate is available, skip directly to JSON
generation:

```bash
python -m pipeline.build \
  --mutations-filtered data/mutation_inputs/website_mutation_records.csv
```

The ordinary command below rebuilds the protein catalog but intentionally
leaves existing mutation JSON untouched:

```bash
python -m pipeline.build
```

## Output and viewer semantics

Each protein directory contains a small `index.json` describing its mutation
isoforms. Each isoform JSON contains the plotted variants. When a RefSeq
protein identifier uniquely matches an expanded-dataset isoform, the index
records its `dataset_isoform_id`; otherwise dominant-isoform selection falls
back to the existing length-based logic.

Source rows are collapsed by `(GeneIsoform, VariationID)`. Consequently, one
displayed marker may represent multiple source rows or classification entries:

- `variation_id` comes from `VariationID`;
- `n_collapsed_rows` records how many filtered source rows were combined;
- `all_classifications` retains parsed germline, somatic-impact, and
  oncogenicity classifications; and
- `primary_classification` and `primary_condition` use the highest-severity
  retained entry.

`n_collapsed_rows` remains in the generated data for provenance, but the
current UI deliberately does not display the former “X from Y source rows”
parenthetical. Missing condition values are presented in a collapsed,
human-readable form rather than as separate “not specified” variants.

## Safety and publishing

Mutation generation writes a complete candidate tree in a temporary directory
and validates it before replacing `data/generated/mutations/`. This prevents:

- partial failures from damaging the last valid mutation tree;
- an old filtered CSV from being appended to accidentally; and
- stale protein or isoform JSON from surviving a successful refresh.

After a successful mutation refresh:

1. Run `python -m unittest discover pipeline/tests`.
2. Run `python -m pipeline.package_site` to update `build/site/mutations/`.
3. Run `python pipeline/ingest_postgres.py` to refresh database variants along
   with the rest of the authoritative catalog.
4. Verify at least one legacy protein and one expanded protein in the mutation
   viewer.
