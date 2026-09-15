"""Explicit mappings for annotations introduced by the expanded RBP dataset."""
from __future__ import annotations

from typing import Any

import pandas as pd

from pipeline.steps.common import parse_jsonish


PARENT_ANNOTATION_FIELDS: dict[str, tuple[str, ...]] = {
    "gene": (
        "tax_id", "gene_symbol", "gene_synonyms", "gene_description",
        "ncbi_gene_id", "ncbi_gene_ids", "hgnc_ids", "ensembl_gene_ids",
    ),
    "open_targets": (
        "opentargets_tissue_expression", "opentargets_expression_tissue_count",
        "opentargets_disease_associations", "opentargets_disease_count",
        "opentargets_disease_names", "opentargets_therapeutic_areas",
        "opentargets_release", "opentargets_annotation_scope",
    ),
    "dataset_provenance": (
        "swissprot_release", "ncbi_annotation_release", "ensembl_release",
        "build_timestamp_utc",
    ),
}


ISOFORM_ANNOTATION_FIELDS: dict[str, tuple[str, ...]] = {
    "identifiers": (
        "protein_key", "ENSG", "ENST", "ENSP", "ncbi_gene_id",
        "uniprot_secondary_accessions", "uniprot_entry_name", "uniprot_parent_ids",
        "uniprot_isoform_ids", "swissprot_canonical_accessions", "is_swissprot_canonical",
        "refseq_protein_ids", "refseq_transcript_ids", "ncbi_isoform_names",
        "ensembl_gene_ids", "ensembl_transcript_ids", "ensembl_protein_ids",
        "identifier_mapping_methods", "identifier_ambiguity", "canonical_match_method",
    ),
    "rna_binding": (
        "rbp_census_unique", "eclip_join_symbol", "eclip_join_method", "eclip_annotation_scope",
        "encode_published_n_regions", "encode_published_frac_utr3", "encode_published_frac_utr5",
        "encode_published_frac_cds", "encode_published_frac_ncrna_exon",
        "encode_published_frac_intron", "encode_published_frac_intergenic",
        "encode_published_dominant", "encode_published_median_experiment_support",
        "encode_matched_n_regions", "encode_matched_frac_utr3", "encode_matched_frac_utr5",
        "encode_matched_frac_cds", "encode_matched_frac_ncrna_exon", "encode_matched_frac_intron",
        "encode_matched_frac_intergenic", "encode_matched_dominant",
        "encode_matched_median_experiment_support",
        "encori_published_n_regions", "encori_published_frac_utr3", "encori_published_frac_utr5",
        "encori_published_frac_cds", "encori_published_frac_ncrna_exon",
        "encori_published_frac_intron", "encori_published_frac_intergenic",
        "encori_published_dominant", "encori_published_median_support",
        "encori_matched_n_regions", "encori_matched_frac_utr3", "encori_matched_frac_utr5",
        "encori_matched_frac_cds", "encori_matched_frac_ncrna_exon", "encori_matched_frac_intron",
        "encori_matched_frac_intergenic", "encori_matched_dominant",
        "encori_matched_median_dataset_support",
        "postar_n_sites", "postar_frac_utr3", "postar_frac_utr5", "postar_frac_cds",
        "postar_frac_ncrna_exon", "postar_frac_intron", "postar_frac_intergenic", "postar_dominant",
        "skipper_n_windows", "skipper_frac_cds", "skipper_frac_intron",
        "skipper_frac_ncrna_exon", "skipper_frac_other", "skipper_frac_repeat",
        "skipper_frac_small_rna", "skipper_frac_splice_site", "skipper_frac_utr3",
        "skipper_frac_utr5", "skipper_enrich_cds", "skipper_enrich_intron",
        "skipper_enrich_ncrna_exon", "skipper_enrich_other", "skipper_enrich_repeat",
        "skipper_enrich_small_rna", "skipper_enrich_splice_site", "skipper_enrich_utr3",
        "skipper_enrich_utr5", "skipper_n_celllines", "skipper_dominant",
        "has_encode_published", "has_encode_matched", "has_encori_published",
        "has_encori_matched", "has_postar", "has_skipper", "n_eclip_sources",
        "has_union_published", "has_union_matched",
    ),
    "localization": (
        "deeploc_localizations", "deeploc_signals", "deeploc_membrane_types",
        "deeploc_probability_cytoplasm", "deeploc_probability_nucleus",
        "deeploc_probability_extracellular", "deeploc_probability_cell_membrane",
        "deeploc_probability_mitochondrion", "deeploc_probability_plastid",
        "deeploc_probability_endoplasmic_reticulum", "deeploc_probability_lysosome_vacuole",
        "deeploc_probability_golgi_apparatus", "deeploc_probability_peroxisome",
        "deeploc_probability_peripheral", "deeploc_probability_transmembrane",
        "deeploc_probability_lipid_anchor", "deeploc_probability_soluble",
        "deeploc_eligible", "deeploc_exclusion_reason", "deeploc_middle_truncated",
        "deeploc_source_id", "deeploc_version", "deeploc_model",
        "deeploc_embedding_model", "deeploc_annotation_scope",
    ),
    "interpro": (
        "InterPro_domains", "InterPro_count", "InterPro_range", "InterPro_accessions",
        "InterPro_databases", "InterPro_go_terms", "InterPro_n_hits",
        "interpro_source_refseq_protein", "interpro_version", "interpro_annotation_scope",
    ),
    "functional_roles": (
        "role_in_transcription", "role_in_translation", "role_in_mrna_stability",
        "role_in_translation_stability", "go_role_annotation_scope",
    ),
    "post_translational_modifications": (
        "ptm_acetylation", "ptm_acetylation_positions", "ptm_acetylation_residues",
        "ptm_n_glycosylation", "ptm_n_glycosylation_positions", "ptm_n_glycosylation_residues",
        "ptm_o_glycosylation", "ptm_o_glycosylation_positions", "ptm_o_glycosylation_residues",
        "ptm_c_glycosylation", "ptm_c_glycosylation_positions", "ptm_c_glycosylation_residues",
        "ptm_s_glycosylation", "ptm_s_glycosylation_positions", "ptm_s_glycosylation_residues",
        "ptm_methylation", "ptm_methylation_positions", "ptm_methylation_residues",
        "ptm_myristoylation", "ptm_myristoylation_positions", "ptm_myristoylation_residues",
        "ptm_phosphorylation", "ptm_phosphorylation_positions", "ptm_phosphorylation_residues",
        "ptm_sumoylation", "ptm_sumoylation_positions", "ptm_sumoylation_residues",
        "ptm_ubiquitination", "ptm_ubiquitination_positions", "ptm_ubiquitination_residues",
        "ptm_s_nitrosylation", "ptm_s_nitrosylation_positions", "ptm_s_nitrosylation_residues",
        "ptm_projection_source_uniprot_ids", "ptm_projection_methods",
        "ptm_projection_dropped_sites", "ptm_coordinate_system", "ptm_annotation_scope",
    ),
    "structure": (
        "RCSB_PDB_IDs", "RCSB_PDB_count", "RCSB_PDB_chains",
        "RCSB_PDB_entries_with_secondary_structure_count",
        "RCSB_PDB_entries_without_secondary_structure_count",
        "RCSB_secondary_structure_observation_count", "RCSB_helix_observation_count",
        "RCSB_beta_strand_observation_count", "RCSB_secondary_structure_complete_mapping_count",
        "RCSB_secondary_structure_partial_mapping_count", "rcsb_annotation_scope",
    ),
    "methods": (
        "idr_method", "uniprot_domain_annotation_scope", "go_annotation_scope",
        "go_source_uniprot_ids", "cdcode_annotation_scope", "string_query_ensp_ids",
        "string_partners_ensp_by_query", "string_partners_uniprot_by_query",
        "string_partners_ensp_in_catalog_by_query", "string_version",
        "cider_sequence_sanitization", "pslab_ncpr", "pslab_fcr", "pslab_annotation_scope",
    ),
}


PIPE_DELIMITED_FIELDS = {
    "deeploc_localizations", "deeploc_signals", "deeploc_membrane_types",
}


def clean_cell(value: Any, *, column: str | None = None) -> Any:
    """Convert a dataframe cell to a stable JSON-compatible value."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if column in PIPE_DELIMITED_FIELDS and isinstance(value, str):
        return [item for item in value.split("|") if item]
    value = parse_jsonish(value)
    return value.item() if hasattr(value, "item") else value


def _build_groups(row, groups: dict[str, tuple[str, ...]]) -> dict[str, dict[str, Any]]:
    return {
        group: {column: clean_cell(row.get(column), column=column) for column in columns}
        for group, columns in groups.items()
    }


def build_parent_annotations(row) -> dict[str, dict[str, Any]]:
    return _build_groups(row, PARENT_ANNOTATION_FIELDS)


def build_isoform_annotations(row) -> dict[str, dict[str, Any]]:
    return _build_groups(row, ISOFORM_ANNOTATION_FIELDS)
