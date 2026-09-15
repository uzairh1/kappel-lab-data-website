"""Explicit registry for structured expanded-dataset column families.

The expanded RBP source CSV stores several logical objects across parallel columns.
This module is the one place that defines how those columns map into canonical
objects. Fields must be registered here; similarly prefixed source columns are
intentionally ignored.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    source: str
    output: str


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


def idr_fields() -> tuple[FieldSpec, ...]:
    """Return the explicitly supported per-IDR fields."""
    return IDR_FIELDS


def domain_fields() -> tuple[FieldSpec, ...]:
    """Return the explicitly supported per-domain fields."""
    return DOMAIN_FIELDS
