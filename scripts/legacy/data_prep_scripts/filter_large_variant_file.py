# Run this on Hoffman2 (as a batch job — see filter_variants_job.sh), next to
# the 309GB file and this project's data.json.
#
# Column choices and parsing logic here are based directly on
# variant_table_documentation.xlsx. Key gotchas handled:
#   - ProteinPosition is stored as float ("377.0") and can be a RANGE
#     ("377-380") for multi-residue variants — not a clean int.
#   - Germline_Class / SomaticClinicalImpact_Class / Oncogenicity_Class are
#     JSON arrays (one entry per ClinVar submitter), each with its own
#     condition/description/review_status — not a flat category.
#   - VariationID is the true unique-variant ID; the SAME variant can appear
#     as multiple rows (one per isoform) — that's intentional, not a
#     duplicate to collapse, since per-isoform position is what we need.
#   - Isoform length is derived from len(UnmutatedSeq) per row, then the
#     raw sequence is dropped before saving (keeps output small — we don't
#     need the full sequence text repeated on every variant row).
#
# Deliberately NOT pulled in this version (per explicit scope decision):
# GeneSymbol, GeneType, Accession, VariationName, ProteinChange, SASA_*,
# inDisorder, Domain_Annotation, Classical_RBD_At_Position, and the
# Unmutated_*/Mutated_* biophysics columns. Only UniProtID (join key),
# VariationID (unique key), UnmutatedSeq (isoform_length source), and the
# 12 explicitly-requested columns are pulled.

import pandas as pd, json, ast, re

our_proteins = json.load(open('data.json'))
our_uniprot_ids = set(p['uniprot'] for p in our_proteins)
our_lengths = {p['uniprot']: p['length'] for p in our_proteins}
print(f"Filtering for {len(our_uniprot_ids)} UniProt IDs")

cols_needed = [
    'UniProtID', 'VariationID',  # essential join key + unique variant ID — not optional
    'MutatedFrom', 'ProteinPosition', 'MutatedTo',
    'MolecularConsequence', 'VariantType', 'MutationType',
    'Germline_Class', 'SomaticClinicalImpact_Class', 'Oncogenicity_Class',
    'GeneIsoform', 'GeneIsoformWithDescription', 'Dominant_Isoform',
    'UnmutatedSeq',  # kept ONLY to derive isoform_length below, dropped after
]

def parse_protein_position(val):
    """Handles '377.0' (single, float-stringified) and '377-380' (range)."""
    if pd.isna(val):
        return None, None
    s = str(val).strip()
    if '-' in s and not s.startswith('-'):
        parts = s.split('-')
        try:
            return int(float(parts[0])), int(float(parts[1]))
        except (ValueError, IndexError):
            return None, None
    try:
        p = int(float(s))
        return p, p
    except ValueError:
        return None, None

def parse_classification_json(val):
    """Germline_Class etc — JSON array of submitter entries. Returns list of dicts."""
    if pd.isna(val) or not isinstance(val, str) or not val.strip():
        return []
    try:
        parsed = ast.literal_eval(val)
        return parsed if isinstance(parsed, list) else [parsed]
    except Exception:
        return []  # a handful may fail to parse — logged separately below

chunks = []
parse_failures = 0
total_rows = 0
chunk_num = 0
out_path = 'variant_positions_filtered.csv'
header_written = False

t_start = __import__('time').time()

for chunk in pd.read_csv('variant_positions_prefiltered.csv', usecols=cols_needed, chunksize=500_000, low_memory=False):
    chunk_num += 1
    filtered = chunk[chunk['UniProtID'].isin(our_uniprot_ids)].copy()
    if not len(filtered):
        if chunk_num % 20 == 0:
            elapsed = __import__('time').time() - t_start
            print(f"[progress] chunk {chunk_num} ({chunk_num*500_000:,} rows scanned), "
                  f"{total_rows} matched so far, {elapsed/60:.1f} min elapsed", flush=True)
        continue
    total_rows += len(filtered)

    # position parsing
    pos_parsed = filtered['ProteinPosition'].apply(parse_protein_position)
    filtered['position_start'] = pos_parsed.apply(lambda x: x[0])
    filtered['position_end'] = pos_parsed.apply(lambda x: x[1])

    # isoform length from sequence, then drop the raw sequence (saves space)
    filtered['isoform_length'] = filtered['UnmutatedSeq'].apply(lambda s: len(s) if isinstance(s, str) else None)
    filtered = filtered.drop(columns=['UnmutatedSeq'])

    for col in ['Germline_Class', 'SomaticClinicalImpact_Class', 'Oncogenicity_Class']:
        entries = filtered[col].apply(parse_classification_json)
        parse_failures += (filtered[col].notna() & (entries.apply(len) == 0)).sum()

    # write incrementally — survives a timeout/crash partway through, and
    # lets you check progress in the output file before the job finishes
    filtered.to_csv(out_path, mode='a', header=not header_written, index=False)
    header_written = True
    chunks.append(filtered)  # kept in memory too, for the validation report below

    if chunk_num % 20 == 0:
        elapsed = __import__('time').time() - t_start
        print(f"[progress] chunk {chunk_num} ({chunk_num*500_000:,} rows scanned), "
              f"{total_rows} matched so far, {elapsed/60:.1f} min elapsed", flush=True)

result = pd.concat(chunks, ignore_index=True)
print(f"\nDone. Filtered down to {len(result)} rows (from {total_rows} matched pre-filter), "
      f"covering {result['UniProtID'].nunique()} of our proteins")
print(f"Classification JSON parse failures: {parse_failures}")
print(f"Output already written incrementally to {out_path} throughout the run.")

# ============================================================
# VALIDATION REPORT
# ============================================================
print("\n" + "="*60)
print("VARIATION ID — dedup check")
print("="*60)
print("Distinct VariationIDs:", result['VariationID'].nunique(), "/ total rows:", len(result))
print("(Same VariationID across multiple rows = same variant on different isoforms — expected, not a bug)")
dup_example = result[result.duplicated('VariationID', keep=False)].sort_values('VariationID')
if len(dup_example):
    print("\nExample — one variant across isoforms:")
    print(dup_example[['UniProtID','VariationID','GeneIsoform','Dominant_Isoform','position_start','isoform_length']].head(6).to_string())

print("\n" + "="*60)
print("POSITION PARSING")
print("="*60)
print("Rows with a range (position_start != position_end):", (result['position_start'] != result['position_end']).sum())
print("Rows where position parsing failed (both None):", result['position_start'].isna().sum())

print("\n" + "="*60)
print("ISOFORM LENGTH — real lengths, real variety?")
print("="*60)
print(result.groupby('UniProtID')['isoform_length'].nunique().sort_values(ascending=False).head(10))
print("\nDistinct isoform lengths per protein (top 10) — >1 means real multi-isoform data")

print("\n" + "="*60)
print("CRITICAL: position vs our known sequence length (dominant isoform only)")
print("="*60)
dom = result[result['Dominant_Isoform'] == 1.0].copy()
dom['our_known_length'] = dom['UniProtID'].map(our_lengths)
mismatch = dom[dom['position_start'] > dom['our_known_length']]
print(f"{len(mismatch)} / {len(dom)} dominant-isoform rows have position > our known sequence length")
if len(mismatch):
    print(mismatch[['UniProtID','VariationID','position_start','isoform_length','our_known_length']].head(10).to_string())

print("\n" + "="*60)
print("CLASSIFICATION SAMPLE (raw JSON — real parsing happens after this file is small)")
print("="*60)
print(result['Germline_Class'].dropna().iloc[0] if result['Germline_Class'].notna().any() else "no non-null values in sample")

print("\n" + "="*60)
print("ROW COUNT PER PROTEIN")
print("="*60)
print(result.groupby('UniProtID').size().describe())
