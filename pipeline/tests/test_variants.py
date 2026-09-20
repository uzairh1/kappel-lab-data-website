import json
import tempfile
import unittest
from pathlib import Path

from pipeline.config import default_paths
from pipeline.steps.variants import load_legacy_gene_annotations, load_legacy_variant_stats


class LegacyVariantStatsTests(unittest.TestCase):
    def test_default_path_uses_checked_in_lookup(self):
        paths = default_paths(Path("repo"))

        self.assertEqual(
            paths.expanded_dataset,
            Path("repo/data/source/expanded_protein_annotations.csv"),
        )
        self.assertEqual(
            paths.legacy_variant_stats,
            Path("repo/pipeline/resources/legacy/variant_rbp_lookup.json"),
        )

    def test_loads_static_lookup(self):
        with tempfile.TemporaryDirectory() as temp_name:
            lookup = Path(temp_name) / "legacy.json"
            lookup.write_text(json.dumps({"PTEST1": {"is_rbp": True}}))

            self.assertEqual(
                load_legacy_variant_stats(lookup),
                {"PTEST1": {"is_rbp": True}},
            )

    def test_loads_static_gene_annotations(self):
        with tempfile.TemporaryDirectory() as temp_name:
            lookup = Path(temp_name) / "legacy.json"
            lookup.write_text(json.dumps({"PTEST1": {"approved_name": "Test"}}))

            self.assertEqual(
                load_legacy_gene_annotations(lookup),
                {"PTEST1": {"approved_name": "Test"}},
            )


if __name__ == "__main__":
    unittest.main()
