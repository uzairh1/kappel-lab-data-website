# Kappel Lab Data Website — file guide

This is the current, authoritative map of every file: what it is, whether
you need it, and whether it's live-site code, a one-time data-prep script,
or safe to ignore. Treat this file as the source of truth going forward,
not chat history — it gets out of date fast otherwise (two files were
found stale during the review that produced this doc).


---

## 1. Files the live site actually needs (must all be present together)

| File | What it is |
|---|---|
| `index.html` | Page structure — nav, hero, all tab markup |
| `styles.css` | All styling |
| `app.js` | All interactivity: search, filters, column toggles, tab rendering, lazy-loading |
| `data.json` | Core record for all 101 proteins — identity, IDR/domain positions, condensate summary, biophysics summary, disease/variant summary. Powers the main browse table. Small on purpose (~165KB). |
| `diseases.json` | Full per-disease association data (~26K rows across all proteins). Loaded lazily only when a protein's Diseases tab is opened. |
| `protein_details/*.json` | One file per protein (101 total, ~100KB avg) — sequence, full biophysics by region, PPI partners, GO terms, gene annotation. Loaded lazily only when that protein's page is opened. |

If any of these is missing, the site still loads but shows empty/fallback
states for whatever depends on the missing piece — it won't crash.

## 2. Source data (only needed to *regenerate* the files above)

| File | Role |
|---|---|
| `Mini_Dataset.csv` | Original 101-protein, 157-column dataset. Source for `data.json`'s core fields, `diseases.json`, and everything in `protein_details/`. |
| `per_protein_variant_stats_v2.csv` | 18.5k-gene reference file (RBP status, RNA-binding domains, ClinVar variant counts). Source for the `variant_stats` field in `data.json` (75/101 proteins matched). |

Not read by the live site at all — only by the scripts below, and only
when you're regenerating data after the source CSVs change.

## 3. Data-prep scripts (run only when source data changes — run in this order)

```bash
python3 parse_data.py                  # Mini_Dataset.csv -> data.json (core) + diseases.json
python3 merge_variant_stats.py         # + per_protein_variant_stats_v2.csv -> adds variant_stats into data.json
python3 enrich_full_mini_dataset.py    # Mini_Dataset.csv -> protein_details/*.json
```

Each is idempotent — safe to rerun any time the corresponding source CSV
is updated. None of them are called by the site itself at runtime.

## 4. How to check accuracy — now and going forward

Two audit scripts, run after any regeneration or whenever you want to
confirm the data is right. Both check **all 101 proteins automatically**
— no manual browsing needed.

```bash
python3 verify_data.py <gene_or_uniprot>   # spot-check one record against the raw CSV
python3 verify_data.py --all               # structural consistency check across all of data.json

python3 audit_protein_details.py           # structural consistency check across all of protein_details/
```

`audit_protein_details.py` checks: sequence lengths, PPI partner counts,
GO term counts, and IDR+FOLD size sums all match their raw CSV source
exactly, plus flags any Open Targets field that looks like it silently
failed to parse. It only prints what's actually wrong — a clean run says
so explicitly.

**As the dataset grows:** these scripts scale linearly (fixed an O(n×m)
lookup bug in `audit_protein_details.py` for exactly this reason) and
should keep working fine into the low thousands of proteins. 

`view_record.py` is a separate convenience tool for manually inspecting
one raw CSV row in Jupyter (nested fields decoded to readable JSON) — not
an accuracy check, just useful when you want to eyeball something.

```python
# view_record.py
from view_record import view, list_columns
import pandas as pd

df = pd.read_csv('Mini_Dataset.csv')

view(df, 'Q05682')            # every field for one protein, nested JSON decoded and pretty-printed
view(df, 'CALD1', by='Name')  # or look up by gene symbol
```

## 5. Complete column-by-column mapping (all 157 Mini_Dataset.csv columns)
 
Which file each column's data lives in. Generated directly from the
current parsing scripts and validated against the real CSV column list
(zero missing, zero typos) — not written from memory.
 
`{uid}` = the protein's UniProt ID (e.g. `Q05682.json`).
 
| Mini_Dataset.csv column | File |
|---|---|
| `uniprot_id` | data.json |
| `Dominant_Isoform` | data.json |
| `sequence` | protein_details/{uid}.json |
| `UNIQUE` | protein_details/{uid}.json |
| `ProteinHGVS` | protein_details/{uid}.json |
| `HGVSDescription` | data.json, protein_details/{uid}.json |
| `ENSP` | protein_details/{uid}.json |
| `ID` | data.json |
| `Name` | data.json |
| `Description` | protein_details/{uid}.json |
| `FCR` | data.json, protein_details/{uid}.json |
| `NCPR` | data.json, protein_details/{uid}.json |
| `isoelectric_point` | data.json, protein_details/{uid}.json |
| `molecular_weight` | data.json, protein_details/{uid}.json |
| `countNeg` | protein_details/{uid}.json |
| `countPos` | protein_details/{uid}.json |
| `countNeut` | protein_details/{uid}.json |
| `fraction_negative` | protein_details/{uid}.json |
| `fraction_positive` | protein_details/{uid}.json |
| `fraction_expanding` | protein_details/{uid}.json |
| `amino_acid_fractions` | protein_details/{uid}.json |
| `fraction_disorder_promoting` | protein_details/{uid}.json |
| `mean_net_charge` | protein_details/{uid}.json |
| `mean_hydropathy` | data.json, protein_details/{uid}.json |
| `uversky_hydropathy` | protein_details/{uid}.json |
| `PPII_propensity` | protein_details/{uid}.json |
| `kappa` | data.json, protein_details/{uid}.json |
| `delta` | protein_details/{uid}.json |
| `deltaMax` | protein_details/{uid}.json |
| `IDR_count` | data.json |
| `IDR_avg_size` | protein_details/{uid}.json |
| `IDR_total_size` | data.json |
| `IDR_range` | data.json |
| `IDR_discrete_seq` | protein_details/{uid}.json |
| `IDR_concat_seq` | protein_details/{uid}.json |
| `FOLD_count` | protein_details/{uid}.json |
| `FOLD_avg_size` | protein_details/{uid}.json |
| `FOLD_total_size` | data.json |
| `FOLD_range` | data.json |
| `FOLD_discrete_seq` | protein_details/{uid}.json |
| `FOLD_concat_seq` | protein_details/{uid}.json |
| `IDR_FCR` | protein_details/{uid}.json |
| `IDR_NCPR` | protein_details/{uid}.json |
| `IDR_isoelectric_point` | protein_details/{uid}.json |
| `IDR_molecular_weight` | protein_details/{uid}.json |
| `IDR_countNeg` | protein_details/{uid}.json |
| `IDR_countPos` | protein_details/{uid}.json |
| `IDR_countNeut` | protein_details/{uid}.json |
| `IDR_fraction_negative` | protein_details/{uid}.json |
| `IDR_fraction_positive` | protein_details/{uid}.json |
| `IDR_fraction_expanding` | protein_details/{uid}.json |
| `IDR_amino_acid_fractions` | protein_details/{uid}.json |
| `IDR_fraction_disorder_promoting` | protein_details/{uid}.json |
| `IDR_kappa` | protein_details/{uid}.json |
| `IDR_mean_net_charge` | protein_details/{uid}.json |
| `IDR_mean_hydropathy` | protein_details/{uid}.json |
| `IDR_uversky_hydropathy` | protein_details/{uid}.json |
| `IDR_PPII_propensity` | protein_details/{uid}.json |
| `IDR_delta` | protein_details/{uid}.json |
| `IDR_deltaMax` | protein_details/{uid}.json |
| `Domains` | data.json |
| `Domains_count` | protein_details/{uid}.json |
| `Domains_avg_size` | protein_details/{uid}.json |
| `Domains_total_size` | protein_details/{uid}.json |
| `Domains_range` | data.json |
| `Domains_discrete_seq` | protein_details/{uid}.json |
| `Domains_concat_seq` | protein_details/{uid}.json |
| `Domains_FCR` | protein_details/{uid}.json |
| `Domains_NCPR` | protein_details/{uid}.json |
| `Domains_isoelectric_point` | protein_details/{uid}.json |
| `Domains_molecular_weight` | protein_details/{uid}.json |
| `Domains_countNeg` | protein_details/{uid}.json |
| `Domains_countPos` | protein_details/{uid}.json |
| `Domains_countNeut` | protein_details/{uid}.json |
| `Domains_fraction_negative` | protein_details/{uid}.json |
| `Domains_fraction_positive` | protein_details/{uid}.json |
| `Domains_fraction_expanding` | protein_details/{uid}.json |
| `Domains_amino_acid_fractions` | protein_details/{uid}.json |
| `Domains_fraction_disorder_promoting` | protein_details/{uid}.json |
| `Domains_kappa` | protein_details/{uid}.json |
| `Domains_Omega` | protein_details/{uid}.json |
| `Domains_mean_net_charge` | protein_details/{uid}.json |
| `Domains_mean_hydropathy` | protein_details/{uid}.json |
| `Domains_uversky_hydropathy` | protein_details/{uid}.json |
| `Domains_PPII_propensity` | protein_details/{uid}.json |
| `Domains_delta` | protein_details/{uid}.json |
| `Domains_deltaMax` | protein_details/{uid}.json |
| `ENSP_clean` | protein_details/{uid}.json |
| `PPI_ENSP_Partners` | protein_details/{uid}.json |
| `PPI_UniProt_Partners` | protein_details/{uid}.json |
| `PPI_ENSP_Partners_in_Dataframe` | protein_details/{uid}.json |
| `PPI_UniProt_Partners_in_Dataframe` | data.json, protein_details/{uid}.json |
| `Condensate Name` | data.json |
| `UID` | protein_details/{uid}.json |
| `Condensate Type` | data.json |
| `Species Tax Id` | protein_details/{uid}.json |
| `Proteins` | protein_details/{uid}.json |
| `DNA` | protein_details/{uid}.json |
| `RNA` | protein_details/{uid}.json |
| `C-mods` | protein_details/{uid}.json |
| `Condensatopathy` | protein_details/{uid}.json |
| `Confidence Score` | data.json |
| `C_ids` | protein_details/{uid}.json |
| `C_descriptions` | protein_details/{uid}.json |
| `C_evidence` | protein_details/{uid}.json |
| `P_ids` | protein_details/{uid}.json |
| `P_descriptions` | protein_details/{uid}.json |
| `P_evidence` | protein_details/{uid}.json |
| `F_ids` | protein_details/{uid}.json |
| `F_descriptions` | protein_details/{uid}.json |
| `F_evidence` | protein_details/{uid}.json |
| `isoform_number` | data.json |
| `ID_list` | protein_details/{uid}.json |
| `diseaseId` | diseases.json |
| `datatypeId` | diseases.json |
| `score` | data.json, diseases.json |
| `evidenceCount` | diseases.json |
| `tissues` | — (not captured) |
| `approvedSymbol` | — (not captured) |
| `biotype` | protein_details/{uid}.json |
| `transcriptIds` | protein_details/{uid}.json |
| `canonicalTranscript` | protein_details/{uid}.json |
| `canonicalExons` | protein_details/{uid}.json |
| `genomicLocation` | protein_details/{uid}.json |
| `alternativeGenes` | protein_details/{uid}.json |
| `approvedName` | protein_details/{uid}.json |
| `go` | — (not captured) |
| `hallmarks` | protein_details/{uid}.json |
| `synonyms` | protein_details/{uid}.json |
| `symbolSynonyms` | protein_details/{uid}.json |
| `nameSynonyms` | protein_details/{uid}.json |
| `functionDescriptions` | protein_details/{uid}.json |
| `subcellularLocations` | protein_details/{uid}.json |
| `targetClass` | protein_details/{uid}.json |
| `obsoleteSymbols` | protein_details/{uid}.json |
| `obsoleteNames` | protein_details/{uid}.json |
| `constraint` | protein_details/{uid}.json |
| `tep` | protein_details/{uid}.json |
| `proteinIds` | protein_details/{uid}.json |
| `dbXrefs` | protein_details/{uid}.json |
| `chemicalProbes` | protein_details/{uid}.json |
| `homologues` | protein_details/{uid}.json |
| `tractability` | protein_details/{uid}.json |
| `safetyLiabilities` | protein_details/{uid}.json |
| `pathways` | protein_details/{uid}.json |
| `tss` | protein_details/{uid}.json |
| `mean_lambda` | protein_details/{uid}.json |
| `faro` | protein_details/{uid}.json |
| `shd` | protein_details/{uid}.json |
| `ncpr` | — (not captured) |
| `fcr` | — (not captured) |
| `scd` | protein_details/{uid}.json |
| `ah_ij` | protein_details/{uid}.json |
| `nu_svr` | protein_details/{uid}.json |
| `Delta G [kT]` | data.json |
| `Saturation concentration [mg/mL]` | protein_details/{uid}.json |
| `Saturation concentration [uM]` | data.json |