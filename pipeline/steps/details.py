"""Serialize the canonical protein representation to existing detail JSON."""
import json
from pathlib import Path


def write_details(records, details_dir: Path):
    details_dir.mkdir(exist_ok=True)
    total_bytes = 0
    for record in records:
        text = json.dumps(record.details)
        (details_dir / f"{record.uniprot}.json").write_text(text)
        total_bytes += len(text)
    avg = total_bytes / max(len(records), 1) / 1024
    print(f"Wrote {len(records)} per-protein detail files to {details_dir}/ (avg {avg:.0f} KB each, {total_bytes/1024/1024:.1f} MB total)")
