import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from pipeline.legacy_catalog import LegacyCatalogError, load_legacy_catalog


class LegacyCatalogTests(unittest.TestCase):
    def make_snapshot(self, root: Path):
        archive_path = root / "legacy.tar.gz"
        payloads = {
            "data.json": [{"uniprot": "PLEGACY", "variant_stats": {"is_rbp": True}}],
            "diseases.json": {"PLEGACY": []},
            "protein_details/PLEGACY.json": {"sequence": "AAAA"},
            "tissues/PLEGACY.json": {"tissues": []},
        }
        with tarfile.open(archive_path, "w:gz") as archive:
            for name, payload in payloads.items():
                content = json.dumps(payload).encode()
                info = tarfile.TarInfo(name)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
        archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        ids_hash = hashlib.sha256(b"PLEGACY\n").hexdigest()
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps({
            "archive_sha256": archive_hash,
            "uniprot_ids_sha256": ids_hash,
            "counts": {"proteins": 1},
        }))
        return archive_path, manifest_path

    def test_loads_and_normalizes_verified_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_name:
            archive, manifest = self.make_snapshot(Path(temp_name))
            records = load_legacy_catalog(archive, manifest)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].summary["catalog_source"], "legacy_snapshot")
        self.assertEqual(records[0].summary["isoform_count"], 0)
        self.assertEqual(records[0].details["isoforms"], [])
        self.assertEqual(records[0].details["expanded_annotations"], {})

    def test_rejects_archive_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_name:
            archive, manifest = self.make_snapshot(Path(temp_name))
            archive.write_bytes(archive.read_bytes() + b"changed")
            with self.assertRaises(LegacyCatalogError):
                load_legacy_catalog(archive, manifest)


if __name__ == "__main__":
    unittest.main()
