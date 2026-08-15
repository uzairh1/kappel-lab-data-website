"""Canonical region builders for structured Mini_Dataset fields."""
import ast
from typing import Any


IDR_METRICS = {
    "fcr": "IDR_FCR",
    "ncpr": "IDR_NCPR",
    "kappa": "IDR_kappa",
    "delta": "IDR_delta",
    "delta_max": "IDR_deltaMax",
    "isoelectric_point": "IDR_isoelectric_point",
    "molecular_weight": "IDR_molecular_weight",
    "count_neg": "IDR_countNeg",
    "count_pos": "IDR_countPos",
    "count_neut": "IDR_countNeut",
    "fraction_negative": "IDR_fraction_negative",
    "fraction_positive": "IDR_fraction_positive",
    "fraction_expanding": "IDR_fraction_expanding",
    "fraction_disorder_promoting": "IDR_fraction_disorder_promoting",
    "mean_net_charge": "IDR_mean_net_charge",
    "mean_hydropathy": "IDR_mean_hydropathy",
    "uversky_hydropathy": "IDR_uversky_hydropathy",
    "ppii_propensity": "IDR_PPII_propensity",
}


def parse_list_field(value: Any) -> list:
    """Parse a Mini_Dataset cell that stores a Python-list string."""
    if not isinstance(value, str) or not value.strip() or value.strip() == "[]":
        return []
    try:
        parsed = ast.literal_eval(value)
    except Exception as exc:
        raise ValueError(f"Could not parse list field: {value[:120]!r}") from exc
    return parsed if isinstance(parsed, list) else []


def build_idr_segments(row) -> list[dict[str, Any]]:
    """Build one canonical object per IDR from parallel source columns.

    The source CSV stores IDR coordinates and IDR-level measurements in
    separate list-valued columns. All lists are aligned by position, so the
    canonical representation zips them onto the corresponding region.
    """
    raw_ranges = parse_list_field(row.get("IDR_range"))
    ranges = [(int(start), int(end)) for start, end in raw_ranges]

    parsed_metrics = {
        key: parse_list_field(row.get(column)) for key, column in IDR_METRICS.items()
    }
    aaf = parse_list_field(row.get("IDR_amino_acid_fractions"))

    segments: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(ranges):
        segment = {"start": start, "end": end, "size": end - start}
        for key, values in parsed_metrics.items():
            segment[key] = values[index] if index < len(values) else None
        segment["amino_acid_fractions"] = aaf[index] if index < len(aaf) else None
        segments.append(segment)

    return segments


def idr_alignment_lengths(row) -> dict[str, int]:
    """Return source list lengths for IDR consistency validation."""
    ranges = parse_list_field(row.get("IDR_range"))
    lengths = {"IDR_range": len(ranges)}
    for column in IDR_METRICS.values():
        lengths[column] = len(parse_list_field(row.get(column)))
    lengths["IDR_amino_acid_fractions"] = len(parse_list_field(row.get("IDR_amino_acid_fractions")))
    return lengths
