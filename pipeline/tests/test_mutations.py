import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pipeline.steps.mutations import (
    filter_prefiltered_variants,
    rebuild_mutations,
    validate_mutation_tree,
)


class MutationPipelineTests(unittest.TestCase):
    def record(self, uniprot="PTEST1", length=100):
        return SimpleNamespace(uniprot=uniprot, summary={"length": length})

    def write_prefiltered(self, path: Path):
        fields = [
            "UniProtID", "VariationID", "MutatedFrom", "ProteinPosition", "MutatedTo",
            "MolecularConsequence", "VariantType", "MutationType", "Germline_Class",
            "SomaticClinicalImpact_Class", "Oncogenicity_Class", "GeneIsoform",
            "GeneIsoformWithDescription", "Dominant_Isoform", "UnmutatedSeq",
        ]
        germline_a = str([{
            "condition": "Condition A", "description": "Benign",
            "review_status": "reviewed", "submission_count": "1",
            "date_last_evaluated": "2024-01-01",
        }])
        germline_b = str([{
            "condition": "Condition B", "description": "Pathogenic",
            "review_status": "reviewed", "submission_count": "2",
            "date_last_evaluated": "2024-02-01",
        }])
        rows = [
            ["PTEST1", 123.0, "Ala", "10.0", "Val", "missense", "SNV", "missense", germline_a, "", "", "ISO1", "ISO1 description", 1, "A" * 100],
            ["PTEST1", 123.0, "Ala", "10.0", "Val", "missense", "SNV", "missense", germline_b, "", "", "ISO1", "ISO1 description", 1, "A" * 100],
            ["PTEST1", 456.0, "Gly", "20-22", "del", "inframe deletion", "Deletion", "deletion", "", "", "", "ISO2", "ISO2 description", 0, "A" * 105],
            ["NOTOURS", 999.0, "Ala", "5", "Val", "missense", "SNV", "missense", germline_a, "", "", "OTHER", "other", 1, "A" * 50],
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            writer.writerows(rows)

    def test_filter_transform_and_collapse(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "prefiltered.csv"
            filtered = root / "filtered.csv"
            self.write_prefiltered(source)
            records = [self.record()]

            filter_stats = filter_prefiltered_variants(source, filtered, records, chunksize=2)
            self.assertEqual(filter_stats.rows_scanned, 4)
            self.assertEqual(filter_stats.rows_matched, 3)
            self.assertEqual(filter_stats.proteins_matched, 1)
            self.assertEqual(filter_stats.range_rows, 1)

            output = root / "mutations"
            _, stats, warnings = rebuild_mutations(
                records, output_dir=output, filtered_csv=filtered
            )
            self.assertEqual(warnings, [])
            self.assertEqual(stats.proteins_written, 1)
            index = json.loads((output / "PTEST1" / "index.json").read_text())
            self.assertEqual(index["total_variant_count"], 2)
            self.assertEqual(len([x for x in index["isoforms"] if x["dominant"]]), 1)

            payload = json.loads((output / "PTEST1" / "ISO1.json").read_text())
            variant = payload["variants"][0]
            self.assertEqual(variant["variation_id"], 123.0)
            self.assertEqual(variant["n_collapsed_rows"], 2)
            self.assertEqual(len(variant["all_classifications"]), 2)
            self.assertEqual(variant["primary_classification"], "Pathogenic")
            self.assertEqual(variant["primary_condition"], "Condition B")

            errors, warnings = validate_mutation_tree(output, records)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])

    def test_successful_rebuild_removes_stale_files(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "prefiltered.csv"
            self.write_prefiltered(source)
            output = root / "mutations"
            stale = output / "STALE"
            stale.mkdir(parents=True)
            (stale / "index.json").write_text("{}")

            rebuild_mutations([self.record()], output_dir=output, prefiltered_csv=source)
            self.assertFalse((output / "STALE").exists())
            self.assertTrue((output / "PTEST1" / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
