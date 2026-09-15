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


def is_missing(value) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
