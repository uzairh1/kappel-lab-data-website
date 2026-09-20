import ast
import json
import re
from typing import Any

import pandas as pd


def parse_pylist(value: Any):
    if not isinstance(value, str) or value.strip() in ("", "[]"):
        return []
    cleaned = re.sub(r"np\.int64\((-?\d+)\)", r"\1", value)
    cleaned = re.sub(r"np\.float64\((-?[\d\.]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"np\.(int64|float64)\((-?[\d\.]+)\)", r"\2", cleaned)
    try:
        return ast.literal_eval(cleaned)
    except Exception:
        return []


def parse_dict(value: Any):
    if not isinstance(value, str) or value.strip() in ("", "{}"):
        return {}
    try:
        return ast.literal_eval(value)
    except Exception:
        return {}


def parse_jsonish(value: Any):
    """Parse JSON or Python-literal collection cells without guessing scalars."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return None
    if not (stripped.startswith("[") or stripped.startswith("{")):
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(stripped)
        except (SyntaxError, ValueError):
            return value


def avg_list(values):
    return round(sum(values) / len(values), 4) if values else None


def flatten_ppi_scores(values: dict) -> dict[str, float | int]:
    """Normalize direct and ENSP-nested PPI maps to UniProt -> score."""
    flattened: dict[str, float | int] = {}
    for outer_id, value in (values or {}).items():
        candidates = value.items() if isinstance(value, dict) else [(outer_id, value)]
        for partner_id, score in candidates:
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                continue
            previous = flattened.get(str(partner_id))
            if previous is None or score > previous:
                flattened[str(partner_id)] = score
    return flattened


def is_missing(value) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
