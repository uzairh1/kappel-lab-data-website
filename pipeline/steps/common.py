import ast
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


def parse_numpyish(value: Any):
    if not isinstance(value, str):
        return value
    s = value.strip()
    if s in ("", "nan", "None"):
        return None
    if not (s.startswith("[") or s.startswith("{")):
        return s
    fixed = re.sub(r"'\s+'", "', '", s)
    fixed = re.sub(r"\}\s+\{", "}, {", fixed)
    fixed = re.sub(r"\]\s+\[", "], [", fixed)
    try:
        return ast.literal_eval(fixed)
    except Exception:
        return None


def parse_ot_field(raw_value: Any, ensg: str):
    outer = parse_dict(raw_value) if isinstance(raw_value, str) else {}
    return parse_numpyish(outer.get(ensg))


def avg_list(values):
    return round(sum(values) / len(values), 4) if values else None


def is_missing(value) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
