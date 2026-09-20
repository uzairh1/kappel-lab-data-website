from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelinePaths:
    root: Path
    expanded_dataset: Path
    legacy_variant_stats: Path
    legacy_gene_annotations: Path
    legacy_catalog: Path
    legacy_catalog_manifest: Path
    protein_catalog: Path
    disease_associations: Path
    protein_details: Path
    tissue_expression: Path
    mutations: Path
    tanya_catalog_variants: Path
    website_mutation_records: Path


def default_paths(root: Path | None = None, dataset: Path | None = None) -> PipelinePaths:
    root = Path(root or Path(__file__).resolve().parents[1])
    dataset = Path(dataset or "data/source/expanded_protein_annotations.csv")
    if not dataset.is_absolute():
        dataset = root / dataset
    return PipelinePaths(
        root=root,
        expanded_dataset=dataset,
        legacy_variant_stats=root / "pipeline" / "resources" / "legacy" / "variant_rbp_lookup.json",
        legacy_gene_annotations=root / "pipeline" / "resources" / "legacy" / "gene_annotation_lookup.json",
        legacy_catalog=root / "pipeline" / "resources" / "legacy" / "protein_catalog_snapshot.tar.gz",
        legacy_catalog_manifest=root / "pipeline" / "resources" / "legacy" / "protein_catalog_manifest.json",
        protein_catalog=root / "data" / "generated" / "protein_catalog.json",
        disease_associations=root / "data" / "generated" / "disease_associations.json",
        protein_details=root / "data" / "generated" / "protein_details",
        tissue_expression=root / "data" / "generated" / "tissue_expression",
        mutations=root / "data" / "generated" / "mutations",
        tanya_catalog_variants=root / "data" / "mutation_inputs" / "tanya_catalog_variants.csv",
        website_mutation_records=root / "data" / "mutation_inputs" / "website_mutation_records.csv",
    )
