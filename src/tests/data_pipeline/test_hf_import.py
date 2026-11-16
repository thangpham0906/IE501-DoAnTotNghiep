"""Offline tests: all text below is synthetic fixture, never corpus Tày."""
import json
import tempfile
import unittest
from pathlib import Path

from src.data_pipeline.import_hf_tay_vi import extract_pair, inspect_splits, save_import

REV = "a" * 40  # fixture, NOT a real upstream revision


class TestHfImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.train = [{"translation": {"tay": "source A", "viet": "target A"}},
                      {"translation": {"tay": "source B", "viet": "target B"}}]
        self.test = [{"translation": {"tay": "source C", "viet": "target C"}}]

    def test_extract_nested_original(self):
        self.assertEqual(extract_pair(self.train[0]), ("source A", "target A"))

    def test_extract_direct_columns(self):
        self.assertEqual(extract_pair({"tay": "A", "viet": "B"}), ("A", "B"))

    def test_missing_translation_rejected(self):
        with self.assertRaises(ValueError):
            extract_pair({"translation": {"tay": "source A"}})

    def test_audit_cross_split_exact_and_one_sided(self):
        result = inspect_splits(self.train, [self.train[0]])
        self.assertEqual(result["train_test_exact_pair_overlap"], 1)
        self.assertEqual(result["train_test_tay_overlap"], 1)

    def test_saves_unapproved_with_pinned_revision(self):
        p1 = self.root / "raw" / "train.jsonl"
        p2 = self.root / "quarantine" / "test.jsonl"
        m = self.root / "manifest.json"
        report = save_import(self.train, self.test, REV, p1, p2, m)
        rows = [json.loads(x) for x in p1.read_text().splitlines()]
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0]["training_approved"])
        self.assertEqual(rows[0]["source_revision"], REV)
        self.assertEqual(report["outputs"][1]["split"], "test_quarantine")

    def test_refuses_overwrite(self):
        p1 = self.root / "train.jsonl"
        p1.write_text("sentinel")
        with self.assertRaises(FileExistsError):
            save_import(self.train, self.test, REV, p1, self.root / "test.jsonl", self.root / "m.json")
        self.assertEqual(p1.read_text(), "sentinel")

    def test_revision_must_be_full_sha(self):
        with self.assertRaises(ValueError):
            save_import(self.train, self.test, "main", self.root / "train", self.root / "test", self.root / "m")


if __name__ == "__main__":
    unittest.main()
