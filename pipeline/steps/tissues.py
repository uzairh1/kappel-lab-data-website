"""Expanded OpenTargets tissue parsing and output helpers."""
import json
from pathlib import Path

from .common import parse_jsonish


def normalize_protein_cell_types(values):
    """Return searchable names plus lossless structured cell-type details."""
    names = []
    details = []
    for value in values or []:
        if isinstance(value, str):
            name = value.strip()
            if not name:
                continue
            names.append(name)
            details.append({"name": name, "level": None, "reliability": None})
        elif isinstance(value, dict):
            name = value.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            names.append(name.strip())
            details.append(dict(value))
    # Preserve first-seen order while avoiding duplicate names in TEXT[].
    names = list(dict.fromkeys(names))
    return names, details

def build_tissue_entries(raw):
    entries = parse_jsonish(raw) or []
    cleaned = []
    for e in entries:
        cleaned.append({
            "label": e.get("tissue_name"),
            "efo_code": e.get("tissue_id"),
            "organs": e.get("organs") or [],
            "anatomical_systems": e.get("anatomical_systems") or [],
            "rna_value": e.get("rna_value"),
            "rna_zscore": e.get("rna_zscore"),
            "rna_level": e.get("rna_level"),
            "rna_unit": e.get("rna_unit"),
            "protein_reliability": e.get("protein_reliability"),
            "protein_level": e.get("protein_level"),
            "protein_cell_types": e.get("protein_cell_types") or [],
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
    expected = {
        f"{record.uniprot}.json"
        for record in records
    }
    for path in out_dir.glob("*.json"):
        if path.name not in expected:
            path.unlink()
    written = 0
    for record in records:
        (out_dir / f"{record.uniprot}.json").write_text(json.dumps(record.tissues))
        written += 1
    print(f"Wrote {written} per-protein tissue files to {out_dir}/")
