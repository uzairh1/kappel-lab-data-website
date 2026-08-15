"""Build one canonical in-memory protein object from one source row."""
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .common import parse_dict
from .proteins import build_summary, parse_diseases
from .structured import (
    build_condensate_details,
    build_domain_types,
    build_gene_annotation,
    build_go_terms,
    build_idr_segments,
    build_patterning,
    build_ppi,
    build_region_sequences,
    region_biophysics,
)
from .tissues import build_tissue_entries, top_tissues


@dataclass
class CanonicalProtein:
    """Normalized representation from which all public website products are built."""

    uniprot: str
    source_row: dict[str, Any]
    summary: dict[str, Any]
    diseases: list[dict[str, Any]]
    sequence: Any
    hgvs: dict[str, Any]
    biophysics_regions: dict[str, Any]
    region_sequences: dict[str, Any]
    domain_types: list[dict[str, Any]]
    patterning: dict[str, Any]
    ppi: dict[str, Any]
    go_terms: dict[str, list[dict[str, Any]]]
    condensate_details: list[dict[str, Any]]
    gene_annotation: dict[str, Any]
    tissues: dict[str, Any]
    variant_stats: dict[str, Any] | None

    @property
    def details(self) -> dict[str, Any]:
        """Return the existing protein_details JSON shape from canonical fields."""
        return {
            "sequence": self.sequence,
            "hgvs": self.hgvs,
            "biophysics_regions": self.biophysics_regions,
            "region_sequences": self.region_sequences,
            "domain_types": self.domain_types,
            "patterning": self.patterning,
            "ppi": self.ppi,
            "go_terms": self.go_terms,
            "condensate_details": self.condensate_details,
            "gene_annotation": self.gene_annotation,
        }

    def finalize(self) -> None:
        self.summary["disease_count"] = len(self.diseases)
        self.summary["top_diseases"] = self.diseases[:5]
        tissue_rows = self.tissues.get("tissues", [])
        self.summary["top_tissues"] = top_tissues(tissue_rows)
        self.summary["variant_stats"] = self.variant_stats


def _build_hgvs(row) -> dict[str, Any]:
    protein_hgvs = [x.strip() for x in str(row["ProteinHGVS"]).split(",")] if isinstance(row["ProteinHGVS"], str) else []
    description = [x.strip() for x in str(row["HGVSDescription"]).split(",")] if isinstance(row["HGVSDescription"], str) else []
    return {
        "protein_hgvs": protein_hgvs,
        "description": description,
        "ensp": row["ENSP"],
        "ensp_clean": row["ENSP_clean"],
        "unique_name": row["UNIQUE"],
        "description": row["Description"],
    }


def build_canonical_records(df: pd.DataFrame, *, variant_stats_map=None):
    records = []
    skipped = []
    for index, row in df.iterrows():
        try:
            summary, diseases = build_summary(row)
            uniprot = summary["uniprot"]
            idr_segments = build_idr_segments(row)
            whole = region_biophysics(row, "")
            fold = region_biophysics(row, "FOLD_")
            whole["amino_acid_fractions"] = parse_dict(row["amino_acid_fractions"])
            fold["avg_size"] = None if pd.isna(row["FOLD_avg_size"]) else row["FOLD_avg_size"]
            fold["count"] = None if pd.isna(row["FOLD_count"]) else int(row["FOLD_count"])

            cond_names = summary.get("condensates", [])
            protein = CanonicalProtein(
                uniprot=uniprot,
                source_row=row.to_dict(),
                summary=summary,
                diseases=diseases,
                sequence=row["sequence"],
                hgvs=_build_hgvs(row),
                biophysics_regions={"whole": whole, "idr_segments": idr_segments, "fold": fold},
                region_sequences=build_region_sequences(row),
                domain_types=build_domain_types(row),
                patterning=build_patterning(row),
                ppi=build_ppi(row),
                go_terms=build_go_terms(row),
                condensate_details=build_condensate_details(row, cond_names),
                gene_annotation=build_gene_annotation(row, row["ID"]),
                tissues={"tissues": build_tissue_entries(row.get("tissues"))},
                variant_stats=(variant_stats_map or {}).get(uniprot),
            )
            protein.finalize()
            records.append(protein)
        except Exception as exc:
            skipped.append({"row": int(index), "error": str(exc)})
    return records, skipped
