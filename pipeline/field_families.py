"""Central registry for structured Mini_Dataset column families.

The website source CSV stores several logical objects across parallel columns.
This module is the one place that defines how those column families map into
canonical objects.

Two families support convention-based extensions:

* ``IDR_<NAME>`` -> ``biophysics_regions.idr_segments[].<name>``
* ``Domains_<NAME>`` -> ``domain_types[].<name>``

Known historical columns keep explicit output names for backwards
compatibility. New columns with those prefixes are discovered automatically,
validated for alignment, and propagated without changing the transformation
code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FieldSpec:
    source: str
    output: str


def _snake(name: str) -> str:
    """Convert a source-field suffix to a stable snake_case JSON key."""
    name = name.strip().replace("-", "_").replace(" ", "_")
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_").lower()


# Historical IDR fields. Explicit names preserve the existing public JSON.
IDR_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("IDR_FCR", "fcr"),
    FieldSpec("IDR_NCPR", "ncpr"),
    FieldSpec("IDR_kappa", "kappa"),
    FieldSpec("IDR_delta", "delta"),
    FieldSpec("IDR_deltaMax", "delta_max"),
    FieldSpec("IDR_isoelectric_point", "isoelectric_point"),
    FieldSpec("IDR_molecular_weight", "molecular_weight"),
    FieldSpec("IDR_countNeg", "count_neg"),
    FieldSpec("IDR_countPos", "count_pos"),
    FieldSpec("IDR_countNeut", "count_neut"),
    FieldSpec("IDR_fraction_negative", "fraction_negative"),
    FieldSpec("IDR_fraction_positive", "fraction_positive"),
    FieldSpec("IDR_fraction_expanding", "fraction_expanding"),
    FieldSpec("IDR_fraction_disorder_promoting", "fraction_disorder_promoting"),
    FieldSpec("IDR_mean_net_charge", "mean_net_charge"),
    FieldSpec("IDR_mean_hydropathy", "mean_hydropathy"),
    FieldSpec("IDR_uversky_hydropathy", "uversky_hydropathy"),
    FieldSpec("IDR_PPII_propensity", "ppii_propensity"),
)

IDR_STRUCTURAL_COLUMNS = {
    "IDR_count",
    "IDR_avg_size",
    "IDR_total_size",
    "IDR_range",
    "IDR_discrete_seq",
    "IDR_concat_seq",
    "IDR_amino_acid_fractions",
}


# Historical domain fields. Domains_count is the anchor/key set and is handled
# separately; range data belongs to the architecture summary and is not folded
# into domain_types here in order to preserve the current output contract.
DOMAIN_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("Domains_avg_size", "avg_size"),
    FieldSpec("Domains_total_size", "total_size"),
    FieldSpec("Domains_FCR", "fcr"),
    FieldSpec("Domains_NCPR", "ncpr"),
    FieldSpec("Domains_kappa", "kappa"),
    FieldSpec("Domains_Omega", "omega"),
    FieldSpec("Domains_isoelectric_point", "isoelectric_point"),
    FieldSpec("Domains_molecular_weight", "molecular_weight"),
    FieldSpec("Domains_countNeg", "count_neg"),
    FieldSpec("Domains_countPos", "count_pos"),
    FieldSpec("Domains_countNeut", "count_neut"),
    FieldSpec("Domains_fraction_negative", "fraction_negative"),
    FieldSpec("Domains_fraction_positive", "fraction_positive"),
    FieldSpec("Domains_fraction_expanding", "fraction_expanding"),
    FieldSpec("Domains_fraction_disorder_promoting", "fraction_disorder_promoting"),
    FieldSpec("Domains_mean_net_charge", "mean_net_charge"),
    FieldSpec("Domains_mean_hydropathy", "mean_hydropathy"),
    FieldSpec("Domains_uversky_hydropathy", "uversky_hydropathy"),
    FieldSpec("Domains_PPII_propensity", "ppii_propensity"),
    FieldSpec("Domains_delta", "delta"),
    FieldSpec("Domains_deltaMax", "delta_max"),
)

DOMAIN_STRUCTURAL_COLUMNS = {
    "Domains",
    "Domains_count",
    "Domains_range",
    "Domains_discrete_seq",
    "Domains_concat_seq",
    "Domains_amino_acid_fractions",
}


# Condensate fields do not have a consistent source prefix, so this explicit
# registry is the intended extension point. Adding a new parallel condensate
# column requires one FieldSpec here rather than edits throughout the pipeline.
CONDENSATE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("Species Tax Id", "species_tax_id"),
    FieldSpec("DNA", "dna_associated"),
    FieldSpec("RNA", "rna_associated"),
    FieldSpec("C-mods", "chemical_mods"),
    FieldSpec("Condensatopathy", "condensatopathy"),
    FieldSpec("UID", "condensate_db_uid"),
    FieldSpec("Proteins", "reported_protein_count"),
)


def _extensions(columns: Iterable[str], *, prefix: str, known: tuple[FieldSpec, ...], reserved: set[str]) -> list[FieldSpec]:
    known_sources = {field.source for field in known}
    output_names = {field.output for field in known}
    discovered: list[FieldSpec] = []
    for column in columns:
        if not column.startswith(prefix) or column in known_sources or column in reserved:
            continue
        suffix = column[len(prefix):]
        if not suffix:
            continue
        output = _snake(suffix)
        if not output or output in output_names:
            continue
        discovered.append(FieldSpec(column, output))
        output_names.add(output)
    return discovered


def idr_fields(columns: Iterable[str]) -> list[FieldSpec]:
    return list(IDR_FIELDS) + _extensions(
        columns, prefix="IDR_", known=IDR_FIELDS, reserved=IDR_STRUCTURAL_COLUMNS
    )


def domain_fields(columns: Iterable[str]) -> list[FieldSpec]:
    return list(DOMAIN_FIELDS) + _extensions(
        columns, prefix="Domains_", known=DOMAIN_FIELDS, reserved=DOMAIN_STRUCTURAL_COLUMNS
    )


def extension_report(columns: Iterable[str]) -> dict[str, list[FieldSpec]]:
    columns = list(columns)
    known_idr = {f.source for f in IDR_FIELDS}
    known_domain = {f.source for f in DOMAIN_FIELDS}
    return {
        "idr": [f for f in idr_fields(columns) if f.source not in known_idr],
        "domains": [f for f in domain_fields(columns) if f.source not in known_domain],
    }
