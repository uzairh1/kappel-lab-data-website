"""Load the frozen legacy Variants & RBP values used by the website."""
import json
from pathlib import Path


def load_legacy_variant_stats(lookup_json: Path) -> dict[str, dict]:
    """Read the immutable per-UniProt lookup retained from the old pipeline."""
    values = json.loads(lookup_json.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError(f"Legacy variant lookup must be a JSON object: {lookup_json}")
    return values
