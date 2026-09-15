from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelinePaths:
    root: Path
    expanded_dataset: Path
    legacy_variant_stats: Path
    legacy_gene_annotations: Path
    data_json: Path
    diseases_json: Path
    protein_details: Path
    tissues: Path
    mutations: Path
    variant_positions_prefiltered: Path
    variant_positions_filtered: Path


def default_paths(root: Path | None = None, dataset: Path | None = None) -> PipelinePaths:
    root = Path(root or Path(__file__).resolve().parents[1])
    dataset = Path(dataset or "RBP_Dataset.csv")
    if not dataset.is_absolute():
        dataset = root / dataset
    return PipelinePaths(
        root=root,
        expanded_dataset=dataset,
        legacy_variant_stats=root / "pipeline" / "legacy_variant_stats.json",
        legacy_gene_annotations=root / "pipeline" / "legacy_gene_annotations.json",
        data_json=root / "data.json",
        diseases_json=root / "diseases.json",
        protein_details=root / "protein_details",
        tissues=root / "tissues",
        mutations=root / "mutations",
        variant_positions_prefiltered=root / "variant_positions_prefiltered.csv",
        variant_positions_filtered=root / "variant_positions_filtered.csv",
    )
