#!/bin/bash
# Fast first-pass filter using awk — matches ONLY the UniProtID column
# (not the whole line), so it's safe against the JSON-with-commas fields
# elsewhere in each row (Germline_Class etc). Run make_id_list.py first.
#
# IMPORTANT: confirm UNIPROT_COL below is correct before running:
#   head -1 YOUR_309GB_FILE.csv | tr ',' '\n' | cat -n | grep -i uniprot
# Change the number if UniProtID isn't actually column 1.

UNIPROT_COL=1

awk -F',' -v col="$UNIPROT_COL" '
BEGIN {
  while ((getline id < "uniprot_ids.txt") > 0) ids[id] = 1
}
NR==1 { print; next }               # always keep the header row
($col in ids) { print }
' YOUR_309GB_FILE.csv > variant_positions_prefiltered.csv

echo "Done. Row count in prefiltered file:"
wc -l variant_positions_prefiltered.csv
