import json
proteins = json.load(open('data.json'))
with open('uniprot_ids.txt', 'w') as f:
    for p in proteins:
        f.write(p['uniprot'] + '\n')
print(f"Wrote {len(proteins)} UniProt IDs to uniprot_ids.txt")
