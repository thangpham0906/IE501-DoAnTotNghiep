"""Unit tests to verify strict isolation between train, validation, and test fixtures.

Zero Data Leakage (Q02):
- Train, validation, and test datasets must have zero overlap in document IDs (doc_id).
- Sentences in Vietnamese and Tay must not intersect across splits.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.data_pipeline.split_dataset import _text_signatures, is_near_duplicate


class TestFixturesIsolation(unittest.TestCase):
    """Test suite ensuring zero leakage between train, val, and test fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures_dir = Path(__file__).parent / "fixtures"
        cls.train_file = cls.fixtures_dir / "sample_train.jsonl"
        cls.val_file = cls.fixtures_dir / "sample_val.jsonl"
        cls.test_file = cls.fixtures_dir / "sample_test.jsonl"
        cls.mono_file = cls.fixtures_dir / "sample_monolingual.jsonl"
        cls.bi_file = cls.fixtures_dir / "sample_bilingual.jsonl"

    def test_fixtures_exist(self) -> None:
        """Verify all three split fixture files exist on disk."""
        self.assertTrue(self.train_file.exists(), f"Train file missing: {self.train_file}")
        self.assertTrue(self.val_file.exists(), f"Validation file missing: {self.val_file}")
        self.assertTrue(self.test_file.exists(), f"Test file missing: {self.test_file}")

    def _load_split(self, file_path: Path) -> list[dict]:
        records = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def test_record_counts(self) -> None:
        """Verify train, val, and test splits have expected sample sizes."""
        train_recs = self._load_split(self.train_file)
        val_recs = self._load_split(self.val_file)
        test_recs = self._load_split(self.test_file)

        self.assertEqual(len(train_recs), 20, f"Expected 20 train records, got {len(train_recs)}")
        self.assertEqual(len(val_recs), 4, f"Expected 4 validation records, got {len(val_recs)}")
        self.assertEqual(len(test_recs), 4, f"Expected 4 test records, got {len(test_recs)}")

    def test_doc_id_zero_overlap(self) -> None:
        """Verify 100% document ID isolation across train, val, and test splits."""
        train_recs = self._load_split(self.train_file)
        val_recs = self._load_split(self.val_file)
        test_recs = self._load_split(self.test_file)

        def get_doc_ids(records: list[dict]) -> set[str]:
            return {
                r.get("document_id") or r.get("source_doc_id")
                for r in records
                if r.get("document_id") or r.get("source_doc_id")
            }

        train_doc_ids = get_doc_ids(train_recs)
        val_doc_ids = get_doc_ids(val_recs)
        test_doc_ids = get_doc_ids(test_recs)

        self.assertTrue(train_doc_ids, "Train doc_ids must not be empty")
        self.assertTrue(val_doc_ids, "Val doc_ids must not be empty")
        self.assertTrue(test_doc_ids, "Test doc_ids must not be empty")

        train_val_overlap = train_doc_ids & val_doc_ids
        train_test_overlap = train_doc_ids & test_doc_ids
        val_test_overlap = val_doc_ids & test_doc_ids

        self.assertEqual(
            train_val_overlap,
            set(),
            f"Document ID leakage between train and val: {train_val_overlap}",
        )
        self.assertEqual(
            train_test_overlap,
            set(),
            f"Document ID leakage between train and test: {train_test_overlap}",
        )
        self.assertEqual(
            val_test_overlap,
            set(),
            f"Document ID leakage between val and test: {val_test_overlap}",
        )

    def test_sentence_text_zero_overlap(self) -> None:
        """Verify 100% sentence text isolation across train, val, and test splits."""
        train_recs = self._load_split(self.train_file)
        val_recs = self._load_split(self.val_file)
        test_recs = self._load_split(self.test_file)

        def extract_sentences(records: list[dict]) -> tuple[set[str], set[str]]:
            vi_sentences = set()
            tay_sentences = set()
            for r in records:
                vi = (r.get("vi") or r.get("vi_text") or "").strip().lower()
                tay = (r.get("tay") or r.get("tay_text") or r.get("ty") or "").strip().lower()
                if vi:
                    vi_sentences.add(vi)
                if tay:
                    tay_sentences.add(tay)
            return vi_sentences, tay_sentences

        train_vi, train_tay = extract_sentences(train_recs)
        val_vi, val_tay = extract_sentences(val_recs)
        test_vi, test_tay = extract_sentences(test_recs)

        # Check Vietnamese overlap
        self.assertEqual(
            train_vi & val_vi,
            set(),
            f"Vietnamese sentence leakage between train and val: {train_vi & val_vi}",
        )
        self.assertEqual(
            train_vi & test_vi,
            set(),
            f"Vietnamese sentence leakage between train and test: {train_vi & test_vi}",
        )
        self.assertEqual(
            val_vi & test_vi,
            set(),
            f"Vietnamese sentence leakage between val and test: {val_vi & test_vi}",
        )

        # Check Tay overlap
        self.assertEqual(
            train_tay & val_tay,
            set(),
            f"Tay sentence leakage between train and val: {train_tay & val_tay}",
        )
        self.assertEqual(
            train_tay & test_tay,
            set(),
            f"Tay sentence leakage between train and test: {train_tay & test_tay}",
        )
        self.assertEqual(
            val_tay & test_tay,
            set(),
            f"Tay sentence leakage between val and test: {val_tay & test_tay}",
        )

    def test_synthetic_fixture_markers(self) -> None:
        """Verify fixtures are clearly marked synthetic and never claim verified native review."""
        disallowed_fake_names = {"chuyên gia tày cao bằng", "người thẩm định bản ngữ"}

        for filepath in (self.train_file, self.val_file, self.test_file, self.bi_file, self.mono_file):
            records = self._load_split(filepath)
            for r in records:
                self.assertTrue(
                    r.get("synthetic_fixture") is True or r.get("is_test_fixture") is True,
                    f"Record in {filepath.name} must be clearly marked synthetic fixture",
                )
                reviewer = str(r.get("reviewed_by") or "").strip().lower()
                self.assertNotIn(
                    reviewer,
                    disallowed_fake_names,
                    f"Record in {filepath.name} must not claim fake reviewer '{reviewer}'",
                )

    def test_zero_near_duplicate_overlap(self) -> None:
        """Verify zero near-duplicate overlap between train, val, and test splits."""
        train_recs = self._load_split(self.train_file)
        val_recs = self._load_split(self.val_file)
        test_recs = self._load_split(self.test_file)

        def get_sigs(recs: list[dict], key: str) -> list[tuple[str, set[str], set[str]]]:
            sigs = []
            for r in recs:
                t = r.get(key) or r.get(f"{key}_text") or ""
                if t:
                    sigs.append(_text_signatures(t))
            return sigs

        for side in ("vi", "tay"):
            train_sigs = get_sigs(train_recs, side)
            val_sigs = get_sigs(val_recs, side)
            test_sigs = get_sigs(test_recs, side)

            for s_train in train_sigs:
                for s_val in val_sigs:
                    self.assertFalse(
                        is_near_duplicate(s_train, s_val, threshold=0.85),
                        f"Near duplicate leakage on {side} between train and val: '{s_train[0]}' vs '{s_val[0]}'",
                    )
                for s_test in test_sigs:
                    self.assertFalse(
                        is_near_duplicate(s_train, s_test, threshold=0.85),
                        f"Near duplicate leakage on {side} between train and test: '{s_train[0]}' vs '{s_test[0]}'",
                    )

            for s_val in val_sigs:
                for s_test in test_sigs:
                    self.assertFalse(
                        is_near_duplicate(s_val, s_test, threshold=0.85),
                        f"Near duplicate leakage on {side} between val and test: '{s_val[0]}' vs '{s_test[0]}'",
                    )

    def test_monolingual_isolation(self) -> None:
        """Verify sample_monolingual.jsonl has zero overlap with val and test splits."""
        mono_recs = self._load_split(self.mono_file)
        val_recs = self._load_split(self.val_file)
        test_recs = self._load_split(self.test_file)

        eval_texts = set()
        eval_sigs = []
        for r in val_recs + test_recs:
            for key in ("vi", "vi_text", "tay", "tay_text", "text", "ty"):
                val = r.get(key)
                if val:
                    sig = _text_signatures(val)
                    eval_texts.add(sig[0])
                    eval_sigs.append(sig)

        for m in mono_recs:
            text = m.get("text") or m.get("tay_text") or m.get("vi_text") or ""
            sig_m = _text_signatures(text)
            self.assertNotIn(
                sig_m[0],
                eval_texts,
                f"Monolingual sentence '{text}' leaks into eval set (exact match)",
            )
            for s_eval in eval_sigs:
                self.assertFalse(
                    is_near_duplicate(sig_m, s_eval, threshold=0.85),
                    f"Monolingual sentence '{text}' leaks into eval set (near duplicate of '{s_eval[0]}')",
                )


if __name__ == "__main__":
    unittest.main()
