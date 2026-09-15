import unittest

import pandas as pd

from pipeline.steps.structured import build_domain_types, build_idr_segments


class ExplicitFieldRegistryTests(unittest.TestCase):
    def test_unregistered_idr_column_is_ignored(self):
        row = pd.Series({
            "IDR_range": "[(1, 5)]",
            "IDR_SASA": "[12.5]",
        })

        segments = build_idr_segments(row)

        self.assertEqual(len(segments), 1)
        self.assertNotIn("sasa", segments[0])

    def test_unregistered_domain_column_is_ignored(self):
        row = pd.Series({
            "Domains_count": "{'RRM': 1}",
            "Domains_SASA": "{'RRM': [12.5]}",
        })

        domains = build_domain_types(row)

        self.assertEqual(len(domains), 1)
        self.assertNotIn("sasa", domains[0])


if __name__ == "__main__":
    unittest.main()
