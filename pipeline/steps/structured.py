"""Structured transformations from expanded RBP dataset rows.

These builders turn the CSV's encoded complex fields into named canonical
objects. Output writers should consume these objects rather than re-parsing
raw CSV cells independently.
"""
import ast
import re
from typing import Any

import pandas as pd

from .common import avg_list, flatten_ppi_scores, parse_dict, parse_jsonish, parse_pylist
from pipeline.field_families import CONDENSATE_FIELDS, domain_fields, idr_fields


def _parse_list(value: Any) -> list:
    if not isinstance(value, str) or not value.strip() or value.strip() == "[]":
        return []
    cleaned = re.sub(r"np\.(int64|float64)\((-?[\d\.]+)\)", r"\2", value)
    try:
        parsed = ast.literal_eval(cleaned)
    except Exception as exc:
        raise ValueError(f"Could not parse list field: {value[:120]!r}") from exc
    return parsed if isinstance(parsed, list) else []


def build_idr_segments(row) -> list[dict[str, Any]]:
    """Build one canonical object per IDR from parallel source columns."""
    ranges = [(int(a), int(b)) for a, b in _parse_list(row.get("IDR_range"))]
    metric_specs = idr_fields()
    metric_values = {spec.output: _parse_list(row.get(spec.source)) for spec in metric_specs}
    amino_acid_fractions = _parse_list(row.get("IDR_amino_acid_fractions"))

    segments = []
    for index, (start, end) in enumerate(ranges):
        item = {"start": start, "end": end, "size": end - start}
        for key, values in metric_values.items():
            item[key] = values[index] if index < len(values) else None
        item["amino_acid_fractions"] = (
            amino_acid_fractions[index] if index < len(amino_acid_fractions) else None
        )
        segments.append(item)
    return segments


def idr_alignment_lengths(row) -> dict[str, int]:
    lengths = {"IDR_range": len(_parse_list(row.get("IDR_range")))}
    for spec in idr_fields():
        lengths[spec.source] = len(_parse_list(row.get(spec.source)))
    lengths["IDR_amino_acid_fractions"] = len(_parse_list(row.get("IDR_amino_acid_fractions")))
    return lengths


def region_biophysics(row, prefix: str) -> dict[str, Any]:
    """Build scalar whole-protein or FOLD biophysics."""
    def get(name: str):
        column = f"{prefix}{name}" if prefix else name
        value = row.get(column)
        if pd.isna(value):
            return None
        return value.item() if hasattr(value, "item") else value

    return {
        "fcr": get("FCR"), "ncpr": get("NCPR"), "kappa": get("kappa"),
        "delta": get("delta"), "delta_max": get("deltaMax"),
        "isoelectric_point": get("isoelectric_point"), "molecular_weight": get("molecular_weight"),
        "count_neg": get("countNeg"), "count_pos": get("countPos"), "count_neut": get("countNeut"),
        "fraction_negative": get("fraction_negative"), "fraction_positive": get("fraction_positive"),
        "fraction_expanding": get("fraction_expanding"), "fraction_disorder_promoting": get("fraction_disorder_promoting"),
        "mean_net_charge": get("mean_net_charge"), "mean_hydropathy": get("mean_hydropathy"),
        "uversky_hydropathy": get("uversky_hydropathy"), "ppii_propensity": get("PPII_propensity"),
    }


def build_region_sequences(row) -> dict[str, Any]:
    return {
        "idr_discrete": parse_pylist(row["IDR_discrete_seq"]),
        "idr_concat": row["IDR_concat_seq"] if isinstance(row["IDR_concat_seq"], str) else None,
        "fold_discrete": parse_pylist(row["FOLD_discrete_seq"]),
        "fold_concat": row["FOLD_concat_seq"] if isinstance(row["FOLD_concat_seq"], str) else None,
    }


def build_domain_types(row) -> list[dict[str, Any]]:
    """Build domain-type records from dictionaries keyed by domain name.

    Only columns registered in ``DOMAIN_FIELDS`` are attached. Unregistered
    source columns are ignored.
    """
    def d(column: str):
        return parse_dict(row.get(column))

    counts = d("Domains_count")
    fields = {spec.output: d(spec.source) for spec in domain_fields()}
    amino = d("Domains_amino_acid_fractions")
    discrete = d("Domains_discrete_seq")
    concat = d("Domains_concat_seq")

    output = []
    for name in counts:
        item = {"name": name, "count": counts.get(name)}
        for key, values in fields.items():
            value = values.get(name)
            item[key] = (
                avg_list(value) if isinstance(value, list) and value and isinstance(value[0], (int, float))
                else (value[0] if isinstance(value, list) and value else value)
            )
        aa_value = amino.get(name)
        item["amino_acid_fractions"] = aa_value[0] if isinstance(aa_value, list) and aa_value else None
        item["discrete_seq"] = discrete.get(name)
        item["concat_seq"] = concat.get(name)
        output.append(item)
    return output


def build_patterning(row) -> dict[str, Any]:
    return {
        "mean_lambda": avg_list(parse_pylist(row["mean_lambda"])),
        "faro": avg_list(parse_pylist(row["faro"])),
        "shd": avg_list(parse_pylist(row["shd"])),
        "scd": avg_list(parse_pylist(row["scd"])),
        "ah_ij": avg_list(parse_pylist(row["ah_ij"])),
        "nu_svr": avg_list(parse_pylist(row["nu_svr"])),
        "saturation_conc_mgml": avg_list(parse_pylist(row["Saturation concentration [mg/mL]"])),
    }


def _ppi_dict_to_list(values: dict) -> list[dict[str, Any]]:
    return [
        {"uniprot": key, "score": value}
        for key, value in flatten_ppi_scores(values).items()
    ]


def build_ppi(row) -> dict[str, Any]:
    return {
        "all_partners": _ppi_dict_to_list(parse_dict(row["PPI_UniProt_Partners"])),
        "partners_in_pilot_set": _ppi_dict_to_list(parse_dict(row["PPI_UniProt_Partners_in_Dataframe"])),
        "ensp_all_partners": _ppi_dict_to_list(parse_dict(row["PPI_ENSP_Partners"])),
        "ensp_partners_in_pilot_set": _ppi_dict_to_list(parse_dict(row["PPI_ENSP_Partners_in_Dataframe"])),
    }


def build_go_terms(row) -> dict[str, list[dict[str, Any]]]:
    def one(prefix: str):
        ids = parse_pylist(row[f"{prefix}_ids"])
        desc = parse_pylist(row[f"{prefix}_descriptions"])
        evidence = parse_pylist(row[f"{prefix}_evidence"])
        return [
            {"id": ident, "description": desc[i] if i < len(desc) else None,
             "evidence": evidence[i] if i < len(evidence) else None}
            for i, ident in enumerate(ids)
        ]

    return {
        "cellular_component": one("C"),
        "biological_process": one("P"),
        "molecular_function": one("F"),
    }


def build_condensate_details(row, condensate_names: list[Any]) -> list[dict[str, Any]]:
    """Build condensate records using the central explicit field registry."""
    fields = {spec.output: parse_pylist(row.get(spec.source)) for spec in CONDENSATE_FIELDS}
    return [
        {key: values[i] if i < len(values) else None for key, values in fields.items()}
        for i in range(len(condensate_names))
    ]


def build_gene_annotation(row, legacy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Preserve frozen legacy annotations, with a minimal expanded-data fallback."""
    if legacy is not None:
        return legacy

    synonyms = parse_jsonish(row.get("gene_synonyms")) or []
    transcript_ids = parse_jsonish(row.get("ensembl_transcript_ids")) or []
    protein_ids = parse_jsonish(row.get("ensembl_protein_ids")) or []
    description = row.get("gene_description")
    if pd.isna(description):
        description = None
    return {
        "approved_name": description,
        "biotype": None,
        "id_list": parse_pylist(row.get("ID_list")),
        "transcript_ids": transcript_ids,
        "canonical_transcript": {"id": row.get("ENST")} if isinstance(row.get("ENST"), str) else None,
        "canonical_exons": [],
        "genomic_location": None,
        "synonyms": [{"label": value} for value in synonyms],
        "symbol_synonyms": synonyms,
        "name_synonyms": [],
        "function_descriptions": [description] if description else [],
        "subcellular_locations": [],
        "obsolete_symbols": [],
        "obsolete_names": [],
        "protein_ids": protein_ids,
        "db_xrefs": [],
        "pathways": [],
        "tss": None,
        "target_class": None,
        "hallmarks": None,
        "tep": None,
        "chemical_probes": None,
        "safety_liabilities": None,
        "alternative_genes": None,
        "constraint": [],
        "homologue_count": 0,
        "homologues_sample": [],
        "tractability_summary": [],
    }
