"""
Spot-check data.json against the original Mini_Dataset.csv.

Usage:
    python3 verify_data.py Q9BRJ6 Q05682 CACTIN     # by UniProt ID or gene symbol
    python3 verify_data.py --all                    # just run the automated invariant checks
"""
import pandas as pd, json, re, ast, sys, os

CSV_PATH = "Mini_Dataset.csv"          # put next to this script, or edit the path
JSON_PATH = "data.json"

def parse_pylist(s):
    if not isinstance(s, str) or s.strip() in ('', '[]'):
        return []
    cleaned = re.sub(r'np\.(int64|float64)\((\-?[\d\.]+)\)', r'\2', s)
    try: return ast.literal_eval(cleaned)
    except Exception: return f"PARSE_FAIL: {s[:80]}"

def load():
    df = pd.read_csv(CSV_PATH)
    data = json.load(open(JSON_PATH))
    return df, data

def spot_check(df, data, query):
    by_uid = {r['uniprot']: r for r in data}
    by_gene = {r['gene']: r for r in data}
    parsed = by_uid.get(query) or by_gene.get(query)
    if not parsed:
        print(f"'{query}' not found in data.json"); return
    raw = df[df['uniprot_id']==parsed['uniprot']].iloc[0]

    print("="*80)
    print(f"UniProt: {parsed['uniprot']}   Gene: {parsed['gene']}")
    print("-"*80)
    rows = [
        ("dominant",        raw['Dominant_Isoform'],            parsed['dominant']),
        ("isoform_number",  raw['isoform_number'],              parsed['isoform_number']),
        ("sequence length", len(raw['sequence']),                parsed['length']),
        ("IDR_count",       raw['IDR_count'],                    parsed['idr_count']),
        ("IDR_total_size",  raw['IDR_total_size'],               parsed['idr_total_size']),
        ("FOLD_total_size", raw['FOLD_total_size'],              parsed['fold_total_size']),
        ("Condensate Name", parse_pylist(raw['Condensate Name']),parsed['condensates']),
        ("Confidence Score",parse_pylist(raw['Confidence Score']),parsed['condensate_confidence']),
        ("FCR",             raw['FCR'],                          parsed['fcr']),
        ("kappa",           raw['kappa'],                        parsed['kappa']),
    ]
    for label, r, p in rows:
        print(f"{label:20} RAW: {str(r):40} JSON: {p}")

def run_all_checks(df, data):
    fails = 0
    for r in data:
        raw = df[df['uniprot_id']==r['uniprot']].iloc[0]
        problems = []
        if len(raw['sequence']) != r['length']:
            problems.append("length mismatch")
        if r['idr_total_size'] + r['fold_total_size'] != r['length']:
            problems.append("IDR+FOLD != length")
        if len(r['condensates']) != len(r['condensate_types']) or len(r['condensates']) != len(r['condensate_confidence']):
            problems.append("condensate list length mismatch")
        if bool(raw['Dominant_Isoform']) != r['dominant']:
            problems.append("dominant flag mismatch")
        if problems:
            fails += 1
            print(r['uniprot'], problems)
    print(f"\n{fails} / {len(data)} rows failed consistency checks.")

if __name__ == "__main__":
    if not os.path.exists(CSV_PATH):
        print(f"Can't find {CSV_PATH} — edit CSV_PATH at the top of this script."); sys.exit(1)
    df, data = load()
    args = sys.argv[1:]
    if not args or args == ['--all']:
        run_all_checks(df, data)
    else:
        for q in args:
            spot_check(df, data, q)
