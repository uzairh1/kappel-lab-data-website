import json
import tempfile
import unittest
from pathlib import Path

from pipeline.config import default_paths
from pipeline.steps.variants import load_legacy_variant_stats


class LegacyVariantStatsTests(unittest.TestCase):
    def test_default_path_uses_checked_in_lookup(self):
        paths = default_paths(Path("repo"))

        self.assertEqual(
            paths.legacy_variant_stats,
            Path("repo/pipeline/legacy_variant_stats.json"),
        )

    def test_loads_static_lookup(self):
        with tempfile.TemporaryDirectory() as temp_name:
            lookup = Path(temp_name) / "legacy.json"
            lookup.write_text(json.dumps({"PTEST1": {"is_rbp": True}}))

            self.assertEqual(
                load_legacy_variant_stats(lookup),
                {"PTEST1": {"is_rbp": True}},
            )


if __name__ == "__main__":
    unittest.main()
