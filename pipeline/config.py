from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelinePaths:
    root: Path
    mini_dataset: Path
    variant_stats: Path
    data_json: Path
    diseases_json: Path
    protein_details: Path
    tissues: Path
    mutations: Path
    variant_positions_prefiltered: Path
    variant_positions_filtered: Path


def default_paths(root: Path | None = None) -> PipelinePaths:
    root = Path(root or Path(__file__).resolve().parents[1])
    return PipelinePaths(
        root=root,
        mini_dataset=root / "Mini_Dataset.csv",
        variant_stats=root / "per_protein_variant_stats_v2.csv",
        data_json=root / "data.json",
        diseases_json=root / "diseases.json",
        protein_details=root / "protein_details",
        tissues=root / "tissues",
        mutations=root / "mutations",
        variant_positions_prefiltered=root / "variant_positions_prefiltered.csv",
        variant_positions_filtered=root / "variant_positions_filtered.csv",
    )
