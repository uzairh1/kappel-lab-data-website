import pandas as pd, re, json, ast, math

df = pd.read_csv('/mnt/user-data/uploads/Mini_Dataset.csv')

def parse_pylist(s):
    """Parse strings like "[np.int64(1300), np.int64(551)]" or "['Nucleolus', 'PML body']" or "[]" """
    if not isinstance(s, str) or s.strip() == '' or s.strip() == '[]':
        return []
    cleaned = re.sub(r'np\.int64\((\-?\d+)\)', r'\1', s)
    cleaned = re.sub(r'np\.float64\((\-?[\d\.]+)\)', r'\1', cleaned)
    try:
        return ast.literal_eval(cleaned)
    except Exception:
        return []

def parse_dict(s):
    if not isinstance(s, str) or s.strip() == '' or s.strip() == '{}':
        return {}
    try:
        return ast.literal_eval(s)
    except Exception:
        return {}

def extract_isoform_label(hgvs_desc, gene):
    if not isinstance(hgvs_desc, str) or not hgvs_desc:
        return None
    first = hgvs_desc.split(',')[0]
    m = re.search(r'(isoform\s+[A-Za-z0-9\-]+)', first, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r'transcript variant\s+([A-Za-z0-9\-]+)', first, re.IGNORECASE)
    if m2:
        return "transcript variant " + m2.group(1)
    return None

def parse_diseases(row, ensg):
    """
    diseaseId / datatypeId / score / evidenceCount are parallel Open Targets
    evidence-level arrays (one entry per evidence record, many records can
    point to the same disease). Aggregate to one row per unique disease:
    max score seen, total evidence count, and the distinct evidence types
    that contributed.
    """
    dis_list = parse_dict(row['diseaseId']).get(ensg, [])
    dt_list  = parse_dict(row['datatypeId']).get(ensg, [])
    sc_list  = parse_dict(row['score']).get(ensg, [])
    ec_list  = parse_dict(row['evidenceCount']).get(ensg, [])

    n = min(len(dis_list), len(dt_list), len(sc_list), len(ec_list))
    agg = {}
    for i in range(n):
        did = dis_list[i]
        entry = agg.setdefault(did, {"disease_id": did, "score": 0.0, "evidence_count": 0, "datatypes": set()})
        entry["score"] = max(entry["score"], float(sc_list[i]))
        entry["evidence_count"] += int(ec_list[i])
        entry["datatypes"].add(dt_list[i])

    out = []
    for e in agg.values():
        out.append({
            "disease_id": e["disease_id"],
            "score": round(e["score"], 4),
            "evidence_count": e["evidence_count"],
            "datatypes": sorted(e["datatypes"]),
        })
    out.sort(key=lambda x: -x["score"])
    return out

records = []
diseases_by_uniprot = {}
skipped = 0
for _, row in df.iterrows():
    try:
        cond_names = parse_pylist(row['Condensate Name'])
        cond_types = parse_pylist(row['Condensate Type'])
        cond_conf  = parse_pylist(row['Confidence Score'])
        ppi_dict = parse_dict(row['PPI_UniProt_Partners_in_Dataframe'])
        sat_list = parse_pylist(row['Saturation concentration [uM]'])
        dg_list  = parse_pylist(row['Delta G [kT]'])

        idr_total = row['IDR_total_size']
        fold_total = row['FOLD_total_size']
        denom = (idr_total or 0) + (fold_total or 0)
        disorder_frac = round(idr_total/denom, 3) if denom else None

        seq = row['sequence'] if isinstance(row['sequence'], str) else ""

        idr_ranges = parse_pylist(row['IDR_range'])
        fold_ranges = parse_pylist(row['FOLD_range'])
        domain_names = parse_pylist(row['Domains'])
        domain_ranges_raw = parse_dict(row['Domains_range']) if isinstance(row['Domains_range'], str) else {}
        domains = []
        for dname in domain_names:
            spans = domain_ranges_raw.get(dname, [])
            for sp in spans:
                domains.append({"name": dname, "start": int(sp[0]), "end": int(sp[1])})

        rec = {
            "uniprot": row['uniprot_id'],
            "gene": row['Name'],
            "ensg": row['ID'],
            "dominant": bool(row['Dominant_Isoform']) if not pd.isna(row['Dominant_Isoform']) else None,
            "isoform_number": int(row['isoform_number']) if not pd.isna(row['isoform_number']) else None,
            "isoform_label": extract_isoform_label(row.get('HGVSDescription'), row['Name']),
            "length": len(seq),
            "idr_count": int(row['IDR_count']) if not pd.isna(row['IDR_count']) else 0,
            "idr_total_size": int(idr_total) if not pd.isna(idr_total) else 0,
            "fold_total_size": int(fold_total) if not pd.isna(fold_total) else 0,
            "disorder_fraction": disorder_frac,
            "idr_ranges": [[int(a), int(b)] for a,b in idr_ranges] if idr_ranges else [],
            "fold_ranges": [[int(a), int(b)] for a,b in fold_ranges] if fold_ranges else [],
            "domains": domains,
            "condensates": cond_names,
            "condensate_types": cond_types,
            "condensate_confidence": cond_conf,
            "condensate_forming": len(cond_names) > 0,
            "ppi_partner_count": len(ppi_dict),
            "fcr": round(row['FCR'],3) if not pd.isna(row['FCR']) else None,
            "ncpr": round(row['NCPR'],3) if not pd.isna(row['NCPR']) else None,
            "kappa": round(row['kappa'],3) if not pd.isna(row['kappa']) else None,
            "mean_hydropathy": round(row['mean_hydropathy'],3) if not pd.isna(row['mean_hydropathy']) else None,
            "isoelectric_point": round(row['isoelectric_point'],2) if not pd.isna(row['isoelectric_point']) else None,
            "molecular_weight": round(row['molecular_weight'],1) if not pd.isna(row['molecular_weight']) else None,
            "saturation_conc_uM": round(sum(sat_list)/len(sat_list),2) if sat_list else None,
            "delta_g_kt": round(sum(dg_list)/len(dg_list),4) if dg_list else None,
        }

        diseases = parse_diseases(row, row['ID'])
        rec["disease_count"] = len(diseases)
        rec["top_diseases"] = diseases[:5]  # small preview embedded directly for quick display
        diseases_by_uniprot[rec["uniprot"]] = diseases

        records.append(rec)
    except Exception as e:
        skipped += 1

print("parsed:", len(records), "skipped:", skipped)
with open('/home/claude/proteins.json','w') as f:
    json.dump(records, f)
with open('/home/claude/diseases.json','w') as f:
    json.dump(diseases_by_uniprot, f)

total_disease_rows = sum(len(v) for v in diseases_by_uniprot.values())
print("total aggregated disease-association rows:", total_disease_rows)

# quick sanity print
for r in records[:5]:
    print(r['uniprot'], '| disease_count:', r['disease_count'], '| top:', r['top_diseases'][:2])
