"""Synthetic fixture-only audit tests (not language samples)."""
import json
import tempfile
import unittest
from pathlib import Path

from src.data_pipeline.audit_external_corpus import audit_datasets, read_pairs

class TestExternalAudit(unittest.TestCase):
    def test_exact_overlap_and_approval_flag(self):
        row = {"tay":"alpha", "vi":"one", "doc":"d1", "approved":False, "synthetic":False}
        candidate = {**row, "approved":True}
        result = audit_datasets([candidate], [row], [row])
        self.assertEqual(result["overlap"]["train_holdout_exact_pair_overlap"], 1)
        self.assertEqual(result["candidate_flags"]["premature_approval"], 1)
        self.assertFalse(result["training_approved"])

    def test_read_pairs_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.jsonl"
            path.write_text(json.dumps({"translation":{"tay":"Alpha", "viet":" One"}}) + "\n")
            rows = read_pairs(path)
            self.assertEqual(rows[0]["tay"], "alpha")
            self.assertEqual(rows[0]["vi"], "one")

    def test_refuses_invalid_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.jsonl"
            path.write_text(json.dumps({"tay":"A"}) + "\n")
            with self.assertRaises(ValueError):
                read_pairs(path)

if __name__ == "__main__":
    unittest.main()
