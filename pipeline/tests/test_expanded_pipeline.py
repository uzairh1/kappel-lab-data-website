import json
import unittest

import pandas as pd

from pipeline.steps.canonical import build_canonical_records
from pipeline.expanded_schema import build_isoform_annotations
from pipeline.steps.proteins import parse_diseases
from pipeline.steps.tissues import build_tissue_entries
from pipeline.validation.checks import REQUIRED_EXPANDED_COLUMNS, validate_source


def expanded_row(uniprot="PTEST1", isoform="PTEST1-1", dominant=1):
    row = {column: None for column in REQUIRED_EXPANDED_COLUMNS}
    row.update({
        "uniprot_id": uniprot,
        "dataset_isoform_id": isoform,
        "dominant_isoform": dominant,
        "is_swissprot_canonical": dominant == 1,
        "row_kind": "swissprot_canonical" if dominant else "ncbi_isoform",
        "length_aa": 4,
        "sequence": "AAAA",
        "Name": "TEST",
        "ID": "ENSGTEST",
        "ENST": "ENSTTEST",
        "isoform_number": 1 if dominant else 2,
        "IDR_count": 0,
        "IDR_total_size": 0,
        "FOLD_count": 0,
        "FOLD_total_size": 0,
        "gene_synonyms": "[]",
        "ensembl_transcript_ids": "[]",
        "ensembl_protein_ids": "[]",
    })
    return row


class ExpandedPipelineTests(unittest.TestCase):
    def test_groups_isoforms_under_one_canonical_parent(self):
        frame = pd.DataFrame([
            expanded_row(),
            expanded_row(isoform="PTEST1-2", dominant=0),
        ])

        errors, warnings = validate_source(frame)
        records, skipped = build_canonical_records(frame)

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(skipped, [])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].summary["isoform_count"], 2)
        self.assertEqual(len(records[0].details["isoforms"]), 2)
        json.dumps(records[0].details, allow_nan=False)

    def test_rejects_multiple_dominant_isoforms(self):
        frame = pd.DataFrame([
            expanded_row(),
            expanded_row(isoform="PTEST1-2", dominant=1),
        ])

        errors, _ = validate_source(frame)

        self.assertTrue(any("expected exactly one dominant isoform" in error for error in errors))

    def test_uses_frozen_gene_annotation_when_available(self):
        frame = pd.DataFrame([expanded_row()])
        legacy = {"PTEST1": {"approved_name": "Frozen annotation"}}

        records, skipped = build_canonical_records(
            frame, legacy_gene_annotations=legacy
        )

        self.assertEqual(skipped, [])
        self.assertEqual(
            records[0].details["gene_annotation"],
            {"approved_name": "Frozen annotation"},
        )

    def test_expanded_annotations_do_not_auto_discover_columns(self):
        annotations = build_isoform_annotations(pd.Series({
            "deeploc_localizations": "Cytoplasm|Nucleus",
            "deeploc_future_field": "not registered",
        }))

        self.assertEqual(
            annotations["localization"]["deeploc_localizations"],
            ["Cytoplasm", "Nucleus"],
        )
        self.assertNotIn("deeploc_future_field", annotations["localization"])

    def test_maps_open_targets_diseases_and_tissues(self):
        disease = [{
            "disease_id": "EFO_TEST",
            "max_datatype_score": 0.75,
            "evidence_count_total": 3,
            "evidence_by_datatype": [{"datatype_id": "literature"}],
        }]
        tissue = [{
            "tissue_name": "brain",
            "tissue_id": "UBERON_TEST",
            "organs": ["brain"],
            "anatomical_systems": ["nervous system"],
            "rna_value": 12.5,
            "rna_zscore": 1.2,
            "rna_level": 2,
            "rna_unit": "TPM",
            "protein_reliability": True,
            "protein_level": 1,
            "protein_cell_types": [],
        }]

        diseases = parse_diseases(pd.Series({
            "opentargets_disease_associations": json.dumps(disease),
        }))
        tissues = build_tissue_entries(json.dumps(tissue))

        self.assertEqual(diseases[0]["disease_id"], "EFO_TEST")
        self.assertEqual(diseases[0]["datatypes"], ["literature"])
        self.assertEqual(tissues[0]["label"], "brain")
        self.assertEqual(tissues[0]["efo_code"], "UBERON_TEST")


if __name__ == "__main__":
    unittest.main()
