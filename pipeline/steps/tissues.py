"""Tissue parsing and output helpers."""
import ast
import json
import re
from pathlib import Path


def strip_numpy_array_wrappers(s):
    while "array(" in s:
        start = s.index("array(")
        depth = 0
        end = None
        for j in range(start + len("array"), len(s)):
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:
            break
        inner = s[start + len("array(") : end]
        inner = re.sub(r",\s*dtype=object\s*$", "", inner)
        s = s[:start] + inner + s[end + 1 :]
    return s


def parse_tissues(raw):
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        outer = ast.literal_eval(raw)
    except Exception:
        return []
    if not outer:
        return []
    inner_str = list(outer.values())[0]
    stripped = strip_numpy_array_wrappers(inner_str)
    fixed = re.sub(r"\}\s+\{", "}, {", stripped)
    fixed = re.sub(r"'\s+'", "', '", fixed)
    try:
        return ast.literal_eval(fixed)
    except Exception:
        return []


def build_tissue_entries(raw):
    entries = parse_tissues(raw)
    cleaned = []
    for e in entries:
        rna = e.get("rna") or {}
        protein = e.get("protein") or {}
        cleaned.append({
            "label": e.get("label"),
            "efo_code": e.get("efo_code"),
            "organs": e.get("organs") or [],
            "anatomical_systems": e.get("anatomical_systems") or [],
            "rna_value": rna.get("value"),
            "rna_zscore": rna.get("zscore"),
            "rna_level": rna.get("level"),
            "rna_unit": rna.get("unit"),
            "protein_reliability": protein.get("reliability"),
            "protein_level": protein.get("level"),
            "protein_cell_types": [c.get("name") for c in (protein.get("cell_type") or []) if isinstance(c, dict)],
        })
    return cleaned


def top_tissues(tissues):
    return [
        {"label": c["label"], "rna_value": c["rna_value"]}
        for c in sorted(
            [c for c in tissues if c["rna_value"] is not None],
            key=lambda c: c["rna_value"],
            reverse=True,
        )[:5]
    ]


def write_tissues(records, out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    written = 0
    failed = []
    for record in records:
        entries = record.tissues.get("tissues", [])
        if not entries:
            failed.append(record.uniprot)
            continue
        (out_dir / f"{record.uniprot}.json").write_text(json.dumps(record.tissues))
        written += 1
    print(f"Wrote {written} per-protein tissue files to {out_dir}/")
    if failed:
        print(f"Failed to parse tissue data for {len(failed)} protein(s): {failed}")
