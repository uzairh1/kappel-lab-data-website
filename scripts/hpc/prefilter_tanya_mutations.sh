#!/usr/bin/env bash
# Stream the large Tanya CSV once and retain rows for the requested UniProt IDs.
# This is intentionally line-oriented and requires UniProtID to be column 1.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 RAW_TANYA.csv uniprot_ids.txt variant_positions_prefiltered.csv" >&2
  exit 2
fi

raw_file=$1
id_file=$2
output_file=$3

[[ -f "$raw_file" ]] || { echo "Raw Tanya CSV not found: $raw_file" >&2; exit 2; }
[[ -s "$id_file" ]] || { echo "UniProt ID file is missing or empty: $id_file" >&2; exit 2; }
[[ "$raw_file" != "$output_file" ]] || { echo "Input and output paths must differ." >&2; exit 2; }

header=$(head -n 1 "$raw_file")
first_column=${header%%,*}
first_column=${first_column//$'\r'/}
first_column=${first_column#\"}
first_column=${first_column%\"}
first_column=${first_column#$'\xef\xbb\xbf'}
if [[ "$first_column" != "UniProtID" ]]; then
  echo "Expected UniProtID in column 1, found: $first_column" >&2
  echo "Do not run the AWK filter until the raw file's join column is confirmed." >&2
  exit 2
fi

output_dir=$(dirname "$output_file")
mkdir -p "$output_dir"
partial_file="${output_file}.partial.$$"
trap 'rm -f "$partial_file"' EXIT HUP INT TERM

echo "Scanning $raw_file"
echo "Target IDs: $(awk 'NF {count++} END {print count+0}' "$id_file")"
LC_ALL=C awk -F',' -v ids_path="$id_file" '
BEGIN {
  while ((getline id < ids_path) > 0) {
    sub(/\r$/, "", id)
    if (id != "") ids[id] = 1
  }
  close(ids_path)
}
NR == 1 { print; next }
{
  id = $1
  sub(/^"/, "", id)
  sub(/"$/, "", id)
  if (id in ids) print
}
' "$raw_file" > "$partial_file"

mv "$partial_file" "$output_file"
trap - EXIT HUP INT TERM
echo "Completed: $output_file"
echo "Rows including header: $(wc -l < "$output_file")"
