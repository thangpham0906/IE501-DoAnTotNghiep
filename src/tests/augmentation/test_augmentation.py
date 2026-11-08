"""Unit and integration tests for src/augmentation module.

Covers:
- QualityControlFilter: Individual rules (R1 to R5), ablation disabling, and filtering statistics.
- BackTranslator: Monolingual back-translation, directional mapping, and zero data leakage protection.
- AugmentationSampler: Deterministic sampling, seed control, E2, E1-M, A1, A2 generation.
- AugmentationPipeline: End-to-end orchestration, file outputs, and manifest verification.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.augmentation.back_translation import BackTranslator
from src.augmentation.pipeline import AugmentationPipeline, run_augmentation_pipeline
from src.augmentation.qc_filters import QCFilter, QCFilterConfig, QualityControlFilter
from src.augmentation.sampler import AugmentationSampler, sample_without_replacement
from src.data_pipeline.common import read_jsonl, write_jsonl
from src.models.config import Direction
from src.models.inference_adapter import TranslationInferenceAdapter, TranslationResult

ROOT = Path(__file__).resolve().parents[3]


class TestQualityControlFilter(unittest.TestCase):
    """Test individual rules and ablation capabilities of QualityControlFilter."""

    def setUp(self) -> None:
        self.qc = QualityControlFilter()

    def test_r1_length_ratio(self) -> None:
        """R1: Test length ratio rule (character and word ratios)."""
        src = "Đây là một câu nguồn bình thường có độ dài vừa phải."
        # Good ratio (~1.0)
        tgt_good = "Nẩy là nả câu nguồn bình thường mi độ dòi đo đầy."
        accepted, reasons = self.qc.evaluate_pair(src, tgt_good)
        self.assertTrue(accepted)
        self.assertEqual(len(reasons), 0)

        # Abnormally short target (ratio << 0.4)
        tgt_short = "Nẩy."
        accepted, reasons = self.qc.evaluate_pair(src, tgt_short)
        self.assertFalse(accepted)
        self.assertTrue(any("R1" in r for r in reasons))

        # Abnormally long target (ratio >> 2.5)
        tgt_long = tgt_good * 4
        accepted, reasons = self.qc.evaluate_pair(src, tgt_long)
        self.assertFalse(accepted)
        self.assertTrue(any("R1" in r for r in reasons))

    def test_r2_repetition(self) -> None:
        """R2: Test word and n-gram repetition detection."""
        src = "Mặt trời mọc đỏ rực trên đỉnh núi đá vôi."

        # Consecutive word repetition: "núi núi núi"
        tgt_word_rep = "Bươn đét khửn phja phja phja sang chang bản."
        accepted, reasons = self.qc.evaluate_pair(src, tgt_word_rep)
        self.assertFalse(accepted)
        self.assertTrue(any("R2_consecutive_word_repeat" in r for r in reasons))

        # Consecutive bigram repetition: "chang bản chang bản"
        tgt_ngram_rep = "Bươn đét khửn chang bản chang bản chang bản hôm nay."
        accepted, reasons = self.qc.evaluate_pair(src, tgt_ngram_rep)
        self.assertFalse(accepted)
        self.assertTrue(any("R2_consecutive" in r for r in reasons))

        # Low lexical diversity (TTR)
        tgt_low_ttr = "nẩy nẩy pây pây nẩy nẩy pây pây nẩy pây"
        accepted, reasons = self.qc.evaluate_pair(src, tgt_low_ttr)
        self.assertFalse(accepted)
        self.assertTrue(any("R2" in r for r in reasons))

    def test_r3_source_copy(self) -> None:
        """R3: Test verbatim source copy rejection."""
        src = "Bà con nông dân vui mừng khi lúa trúng mùa to."

        # Exact match copy
        tgt_exact = src
        accepted, reasons = self.qc.evaluate_pair(src, tgt_exact)
        self.assertFalse(accepted)
        self.assertIn("R3_exact_source_copy", reasons)

        # High Jaccard word overlap
        tgt_near_copy = "Bà con nông dân vui mừng khi lúa trúng mùa to nhé."
        accepted, reasons = self.qc.evaluate_pair(src, tgt_near_copy)
        self.assertFalse(accepted)
        self.assertTrue(any("R3" in r for r in reasons))

    def test_r4_length_bounds(self) -> None:
        """R4: Test minimum and maximum length bounds."""
        # Too short (< 2 words)
        accepted, reasons = self.qc.evaluate_pair("Chào", "Tỏn")
        self.assertFalse(accepted)
        self.assertTrue(any("R4_min_words" in r for r in reasons))

        # Too long (> 200 words)
        long_src = "từ " * 210
        long_tgt = "từ " * 210
        accepted, reasons = self.qc.evaluate_pair(long_src, long_tgt)
        self.assertFalse(accepted)
        self.assertTrue(any("R4_max_words" in r for r in reasons))

    def test_r5_target_heuristics(self) -> None:
        """R5: Test target script heuristics and corrupted characters."""
        src = "Tiếng suối reo hòa cùng tiếng gió xào xạc trong rừng."

        # Target containing Chinese characters
        tgt_cjk = "Tiếng suối reo cùng 森林 tiếng gió."
        accepted, reasons = self.qc.evaluate_pair(src, tgt_cjk)
        self.assertFalse(accepted)
        self.assertTrue(any("R5_disallowed_foreign_script" in r for r in reasons))

        # Target containing replacement character �
        tgt_corrupt = "Tiếng suối reo hòa cùng � trong rừng."
        accepted, reasons = self.qc.evaluate_pair(src, tgt_corrupt)
        self.assertFalse(accepted)
        self.assertTrue(any("R5_corrupted_symbol" in r for r in reasons))

        # Target containing HTML tags
        tgt_html = "Tiếng suối reo <b>trong rừng</b>."
        accepted, reasons = self.qc.evaluate_pair(src, tgt_html)
        self.assertFalse(accepted)
        self.assertTrue(any("R5_html_or_xml_tags" in r for r in reasons))

        # Target with low alphabetic ratio (mostly punctuation / digits)
        tgt_punct = "...... 123456789 !!!!! ????"
        accepted, reasons = self.qc.evaluate_pair(src, tgt_punct)
        self.assertFalse(accepted)
        self.assertTrue(any("R5_low_alpha_ratio" in r for r in reasons))

    def test_ablation_disabled_rule_r1(self) -> None:
        """Ablation A1: Disabling R1 allows length ratio violations to pass if other rules pass."""
        src = "Câu nguồn này có độ dài bình thường tương đối."
        # Abnormally short target that violates R1 and R4 min length if single word,
        # so make it 2 words to pass R4 but fail R1 length ratio
        tgt_short_ratio = "Hết việc."  # 2 words (passes R4), but 9 chars vs 49 chars (ratio=0.18 < 0.4)

        # With all rules active -> rejected by R1
        accepted, reasons = self.qc.evaluate_pair(src, tgt_short_ratio)
        self.assertFalse(accepted)
        self.assertTrue(any(r.startswith("R1") for r in reasons))

        # With R1 disabled -> passes!
        accepted_abl, reasons_abl = self.qc.evaluate_pair(
            src, tgt_short_ratio, disabled_rule="R1"
        )
        self.assertTrue(accepted_abl)
        self.assertEqual(len(reasons_abl), 0)

    def test_ablation_disabled_rule_r2(self) -> None:
        """Ablation A2: Disabling R2 allows repetition to pass if other rules pass."""
        src = "Mặt trời mọc đỏ rực trên đỉnh núi đá vôi."
        tgt_rep = "Bươn đét khửn phja phja phja sang chang bản mường pây."

        # With all rules active -> rejected by R2
        accepted, reasons = self.qc.evaluate_pair(src, tgt_rep)
        self.assertFalse(accepted)
        self.assertTrue(any(r.startswith("R2") for r in reasons))

        # With R2 disabled -> passes!
        accepted_abl, reasons_abl = self.qc.evaluate_pair(
            src, tgt_rep, disabled_rule="R2"
        )
        self.assertTrue(accepted_abl)
        self.assertEqual(len(reasons_abl), 0)

    def test_filter_records_statistics(self) -> None:
        """Test batch record filtering and statistics reporting."""
        records = [
            {"source_text": "Người Tày dệt vải thổ cẩm rất đẹp.", "target_text": "Cần Tày dệt thổ cẩm đây lai."},  # Good
            {"source_text": "Bản làng mở hội lượn.", "target_text": "Bản làng mở hội lượn."},  # R3 copy
            {"source_text": "Đàn chim bay về tổ.", "target_text": "Tua chim pây pây pây pây pây pây."},  # R2 repeat
        ]
        kept, rejected, stats = self.qc.filter_records(records)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(rejected), 2)
        self.assertEqual(stats["total_evaluated"], 3)
        self.assertEqual(stats["total_kept"], 1)
        self.assertEqual(stats["total_rejected"], 2)
        self.assertGreater(stats["rejections_by_rule"]["R2"], 0)
        self.assertGreater(stats["rejections_by_rule"]["R3"], 0)


class TestBackTranslator(unittest.TestCase):
    """Test BackTranslator functionality, direction routing, and anti-leakage."""

    def setUp(self) -> None:
        self.adapter = TranslationInferenceAdapter(mock_mode=True)
        self.translator = BackTranslator(adapter=self.adapter)
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_u_dataset_tay_to_vi(self) -> None:
        """Test back-translation for Tay monolingual -> synthetic Vietnamese."""
        mono_records = [
            {"text": "Bươn chiêng slíp ngà bản mường khui hội lượn.", "document_id": "m1"},
            {"text": "Báo sáo chang bản păn pây chơ xuân lượn nàng hai.", "document_id": "m2"},
        ]
        u_records, manifest = self.translator.generate_u_dataset(
            monolingual_records=mono_records,
            generation_direction=Direction.TAY_TO_VI,
        )
        self.assertEqual(len(u_records), 2)
        self.assertEqual(manifest["generation_direction"], "tyz-vi")
        self.assertEqual(manifest["target_model_direction"], "vi-tyz")

        # In TAY_TO_VI generation:
        # tay is gold mono, vi is synthetic
        r0 = u_records[0]
        self.assertEqual(r0["tay"], "Bươn chiêng slíp ngà bản mường khui hội lượn.")
        self.assertTrue(r0["synthetic"])
        self.assertEqual(r0["synthetic_side"], "vi")
        self.assertEqual(r0["source_monolingual_lang"], "ty")
        self.assertIn("u_", r0["u_id"])
        self.assertIn("hash", r0)

    def test_generate_u_dataset_vi_to_tay(self) -> None:
        """Test back-translation for Vietnamese monolingual -> synthetic Tay."""
        mono_records = [
            {"text": "Tháng giêng sau tết bản làng mở hội.", "document_id": "m_vi_1"},
        ]
        u_records, manifest = self.translator.generate_u_dataset(
            monolingual_records=mono_records,
            generation_direction=Direction.VI_TO_TAY,
        )
        self.assertEqual(len(u_records), 1)
        r0 = u_records[0]
        self.assertEqual(r0["vi"], "Tháng giêng sau tết bản làng mở hội.")
        self.assertEqual(r0["synthetic_side"], "ty")
        self.assertEqual(r0["source_monolingual_lang"], "vi")

    def test_zero_data_leakage_protection(self) -> None:
        """Q02: Monolingual sentence matching validation or test set must be isolated."""
        val_records = [
            {"tay": "Nặm huổi chảy mát chang đông sâu.", "vi": "Nước suối chảy mát trong rừng sâu."}
        ]
        test_records = [
            {"tay": "Tua vài chang nà lăm nặm mùa hạ.", "vi": "Con trâu trên ruộng đầm nước mùa hạ."}
        ]

        mono_records = [
            {"text": "Nặm huổi chảy mát chang đông sâu.", "document_id": "leaked_val"},  # Leaks val
            {"text": "Tua vài chang nà lăm nặm mùa hạ.", "document_id": "leaked_test"},  # Leaks test
            {"text": "Cần Tày chăm chỉ cày bừa chang nà ruộng.", "document_id": "clean_mono"},  # Clean
        ]

        u_records, manifest = self.translator.generate_u_dataset(
            monolingual_records=mono_records,
            generation_direction=Direction.TAY_TO_VI,
            val_records=val_records,
            test_records=test_records,
        )

        # Only 1 clean record should pass; 2 leaked records must be filtered out
        self.assertEqual(len(u_records), 1)
        self.assertEqual(u_records[0]["tay"], "Cần Tày chăm chỉ cày bừa chang nà ruộng.")
        self.assertEqual(manifest["anti_leakage"]["leakage_count"], 2)


class TestAugmentationSampler(unittest.TestCase):
    """Test deterministic sampling, reproducible seeds, and variant generators."""

    def setUp(self) -> None:
        self.sampler = AugmentationSampler()
        # Create 10 dummy U records
        self.dummy_u = [
            {
                "u_id": f"u_{i:03d}",
                "hash": f"hash_{i:03d}",
                "vi_text": f"Câu tiếng Việt số {i} với nội dung có ý nghĩa đầy đủ.",
                "tay_text": f"Nả câu tiếng Tày slố {i} mi ý nghĩa đài.",
                "source_text": f"Câu tiếng Việt số {i} với nội dung có ý nghĩa đầy đủ.",
                "target_text": f"Nả câu tiếng Tày slố {i} mi ý nghĩa đài.",
            }
            for i in range(10)
        ]

    def test_sample_without_replacement_reproducibility(self) -> None:
        """Q03: Same seed must yield identical sample IDs across multiple invocations."""
        samples1, info1 = sample_without_replacement(self.dummy_u, n_samples=4, seed=42)
        samples2, info2 = sample_without_replacement(self.dummy_u, n_samples=4, seed=42)

        self.assertEqual(len(samples1), 4)
        self.assertEqual(info1["sampled_ids"], info2["sampled_ids"])
        self.assertEqual([s["u_id"] for s in samples1], [s["u_id"] for s in samples2])

        # Different seed yields different sequence
        samples3, info3 = sample_without_replacement(self.dummy_u, n_samples=4, seed=99)
        self.assertNotEqual(info1["sampled_ids"], info3["sampled_ids"])

    def test_create_e2_and_e1_m(self) -> None:
        """Verify E2 filtering and E1-M control of identical size N."""
        e2_samples, e2_manifest = self.sampler.create_e2(self.dummy_u, n_samples=5, seed=42)
        self.assertEqual(len(e2_samples), 5)
        self.assertEqual(e2_manifest["variant"], "E2")

        # E1-M must take exactly 5 samples with same seed
        e1_m_samples, e1_m_manifest = self.sampler.create_e1_m(
            self.dummy_u, n_samples=5, seed=42
        )
        self.assertEqual(len(e1_m_samples), 5)
        self.assertEqual(e1_m_manifest["variant"], "E1-M")
        self.assertEqual(e1_m_manifest["seed"], e2_manifest["seed"])

    def test_create_a1_and_a2_ablations(self) -> None:
        """Verify A1 (disabled R1) and A2 (disabled R2) creation."""
        a1_samples, a1_manifest = self.sampler.create_a1(self.dummy_u, n_samples=5, seed=42)
        self.assertEqual(len(a1_samples), 5)
        self.assertEqual(a1_manifest["variant"], "A1")
        self.assertEqual(a1_manifest["disabled_rule"], "R1")

        a2_samples, a2_manifest = self.sampler.create_a2(self.dummy_u, n_samples=5, seed=42)
        self.assertEqual(len(a2_samples), 5)
        self.assertEqual(a2_manifest["variant"], "A2")
        self.assertEqual(a2_manifest["disabled_rule"], "R2")


class TestAugmentationPipelineEndToEnd(unittest.TestCase):
    """End-to-End integration test using fixture files."""

    def setUp(self) -> None:
        self.test_dir = Path(tempfile.mkdtemp())
        self.fixture_mono = ROOT / "src/tests/fixtures/sample_monolingual.jsonl"
        self.fixture_bi = ROOT / "src/tests/fixtures/sample_bilingual.jsonl"

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_pipeline_run(self) -> None:
        """Execute full pipeline from monolingual source to E1, E2, E1-M, A1, A2."""
        pipeline = AugmentationPipeline(mock_mode=True)
        manifest = pipeline.run(
            output_dir=self.test_dir,
            train_e0_source=self.fixture_bi,
            monolingual_source=self.fixture_mono,
            direction=Direction.VI_TO_TAY,
            n_samples=5,
            seed=42,
        )

        self.assertEqual(manifest["pipeline"], "AugmentationPipeline")
        self.assertEqual(manifest["target_direction"], "vi-tyz")
        self.assertEqual(manifest["n_effective"], 5)

        # Check that files were created
        expected_files = [
            "train_e1.jsonl",
            "train_e2.jsonl",
            "train_e1_m.jsonl",
            "train_a1.jsonl",
            "train_a2.jsonl",
            "u_synthetic.jsonl",
            "augmentation_manifest.json",
        ]
        for fname in expected_files:
            p = self.test_dir / fname
            self.assertTrue(p.is_file(), f"Expected file missing: {fname}")

        # Check dataset sizes
        e0_count = len(read_jsonl(self.fixture_bi))
        train_e2 = read_jsonl(self.test_dir / "train_e2.jsonl")
        train_e1_m = read_jsonl(self.test_dir / "train_e1_m.jsonl")
        train_a1 = read_jsonl(self.test_dir / "train_a1.jsonl")
        train_a2 = read_jsonl(self.test_dir / "train_a2.jsonl")

        self.assertEqual(len(train_e2), e0_count + 5)
        self.assertEqual(len(train_e1_m), e0_count + 5)
        self.assertEqual(len(train_a1), e0_count + 5)
        self.assertEqual(len(train_a2), e0_count + 5)

        # Verify provenance tags
        synthetic_e2 = [r for r in train_e2 if r.get("synthetic") is True]
        gold_e2 = [r for r in train_e2 if r.get("synthetic") is False]
        self.assertEqual(len(synthetic_e2), 5)
        self.assertEqual(len(gold_e2), e0_count)

    def test_convenience_function_run_augmentation_pipeline(self) -> None:
        """Test top-level run_augmentation_pipeline helper."""
        manifest = run_augmentation_pipeline(
            output_dir=self.test_dir / "run_helper",
            train_e0_source=self.fixture_bi,
            monolingual_source=self.fixture_mono,
            n_samples=3,
            seed=123,
            mock_mode=True,
        )
        self.assertEqual(manifest["n_effective"], 3)
        self.assertTrue((self.test_dir / "run_helper/train_e2.jsonl").is_file())


class TestAugmentationEdgeCasesAndLeakage(unittest.TestCase):
    """Test edge cases, boundary thresholds, anti-leakage robustness, and sampling invariants."""

    def setUp(self) -> None:
        self.qc = QualityControlFilter()
        self.sampler = AugmentationSampler()

    def test_qc_boundary_conditions(self) -> None:
        """Verify QC filter behavior at exact boundary conditions."""
        # 1 word -> fails R4 min_words (min 2 words)
        acc, reasons = self.qc.evaluate_pair("Chào", "Tỏn")
        self.assertFalse(acc)
        self.assertTrue(any("R4_min_words" in r for r in reasons))

        # 2 words -> passes R4 min_words
        acc, reasons = self.qc.evaluate_pair("Chào bạn", "Tỏn mạy")
        self.assertTrue(acc)

    def test_qc_custom_config(self) -> None:
        """Verify QC filter uses customized thresholds properly."""
        custom_cfg = QCFilterConfig(
            min_length_ratio=0.8,
            max_length_ratio=1.2,
        )
        strict_qc = QualityControlFilter(config=custom_cfg)

        src = "Câu tiếng Việt này dùng để thử nghiệm bộ lọc tỷ lệ."
        tgt = "Nả câu tiếng Tày dùng để thử nghiệm."  # Ratio ~ 0.70, passes default 0.4 but fails strict 0.8
        acc_default, _ = self.qc.evaluate_pair(src, tgt)
        self.assertTrue(acc_default)

        acc_strict, reasons_strict = strict_qc.evaluate_pair(src, tgt)
        self.assertFalse(acc_strict)
        self.assertTrue(any("R1" in r for r in reasons_strict))

    def test_qc_empty_and_whitespace_inputs(self) -> None:
        """Verify QC handles empty and whitespace strings gracefully."""
        acc, reasons = self.qc.evaluate_pair("", "")
        self.assertFalse(acc)
        self.assertTrue(any("R1_empty_text" in r for r in reasons))

        acc_ws, reasons_ws = self.qc.evaluate_pair("   \t\n", "   ")
        self.assertFalse(acc_ws)

    def test_sampler_n_samples_greater_than_candidates(self) -> None:
        """Verify sampling when n_samples exceeds candidate pool."""
        records = [{"u_id": f"u_{i}", "hash": f"h_{i}"} for i in range(3)]

        # Non-strict mode clamps to available candidate count
        sampled, info = sample_without_replacement(records, n_samples=10, strict=False)
        self.assertEqual(len(sampled), 3)
        self.assertTrue(info["insufficient_candidates"])

        # Strict mode raises ValueError
        with self.assertRaises(ValueError):
            sample_without_replacement(records, n_samples=10, strict=True)

    def test_sampler_zero_and_negative_n_samples(self) -> None:
        """Verify sampling with zero or negative n_samples."""
        records = [{"u_id": "u_1", "hash": "h_1"}]
        sampled, info = sample_without_replacement(records, n_samples=0)
        self.assertEqual(len(sampled), 0)
        self.assertEqual(info["actual_n"], 0)

        with self.assertRaises(ValueError):
            sample_without_replacement(records, n_samples=-5)

    def test_back_translation_empty_monolingual(self) -> None:
        """Verify back-translation with empty monolingual inputs."""
        adapter = TranslationInferenceAdapter(mock_mode=True)
        translator = BackTranslator(adapter=adapter)
        u_records, manifest = translator.generate_u_dataset(
            monolingual_records=[],
            generation_direction=Direction.TAY_TO_VI,
        )
        self.assertEqual(len(u_records), 0)
        self.assertEqual(manifest["u_records_generated"], 0)

    def test_anti_leakage_whitespace_and_punctuation_insensitivity(self) -> None:
        """Verify anti-leakage detects leakage despite whitespace, punctuation, or case variations."""
        val_records = [
            {"tay": "Bươn chiêng khui hội lượn.", "vi": "Tháng giêng mở hội lượn."}
        ]
        # Variations of the val sentence
        variations = [
            {"text": "  bươn chiêng khui hội lượn.  ", "document_id": "v1"},
            {"text": "BƯƠN CHIÊNG KHUI HỘI LƯỢN.", "document_id": "v2"},
            {"text": "Bươn   chiêng  khui   hội   lượn.", "document_id": "v3"},
        ]
        adapter = TranslationInferenceAdapter(mock_mode=True)
        translator = BackTranslator(adapter=adapter)
        u_records, manifest = translator.generate_u_dataset(
            monolingual_records=variations,
            generation_direction=Direction.TAY_TO_VI,
            val_records=val_records,
        )
        # All 3 variations must be caught and excluded
        self.assertEqual(len(u_records), 0)
        self.assertEqual(manifest["anti_leakage"]["leakage_count"], 3)

    def test_sampler_strict_mode_when_insufficient_samples(self) -> None:
        """Verify sampler strictly raises ValueError when QC fails to yield required N samples."""
        records = [
            {"u_id": f"u_{i}", "hash": f"h_{i}", "source_text": "A", "target_text": "B"}
            for i in range(3)
        ]
        # E2, E1-M, A1, A2 with strict=True must fail if N > len(records)
        with self.assertRaisesRegex(ValueError, "QC không đủ mẫu cho E2"):
            self.sampler.create_e2(records, n_samples=10, strict=True)

        with self.assertRaisesRegex(ValueError, "Không đủ mẫu cho E1-M"):
            self.sampler.create_e1_m(records, n_samples=10, strict=True)

        with self.assertRaisesRegex(ValueError, "QC không đủ mẫu cho A1"):
            self.sampler.create_a1(records, n_samples=10, strict=True)

        with self.assertRaisesRegex(ValueError, "QC không đủ mẫu cho A2"):
            self.sampler.create_a2(records, n_samples=10, strict=True)

    def test_back_translation_monolingual_language_filtering(self) -> None:
        """Verify monolingual records of mismatched language are filtered for direction."""
        mismatched_mono = [
            {"text": "Câu này là tiếng Việt nhưng đưa vào TAY_TO_VI", "lang": "vi", "document_id": "m_vi"},
            {"text": "Bươn chiêng slíp ngà bản mường khui hội lượn.", "lang": "ty", "document_id": "m_ty"},
        ]
        adapter = TranslationInferenceAdapter(mock_mode=True)
        translator = BackTranslator(adapter=adapter)
        u_records, manifest = translator.generate_u_dataset(
            monolingual_records=mismatched_mono,
            generation_direction=Direction.TAY_TO_VI,
        )
        # Vietnamese record must be skipped; only Tay record is processed
        self.assertEqual(len(u_records), 1)
        self.assertEqual(u_records[0]["tay"], "Bươn chiêng slíp ngà bản mường khui hội lượn.")
        self.assertEqual(manifest["language_mismatched_skipped"], 1)

    def test_anti_leakage_synthetic_output_leakage_caught(self) -> None:
        """Verify synthetic translation output matching evaluation set is caught and excluded."""
        class MockLeakingAdapter:
            def translate(self, text: str, direction: Direction):
                # Always returns the exact validation sentence as translation
                return TranslationResult(
                    src_text=text,
                    tgt_text="Tháng giêng mở hội lượn.",
                    direction=direction.value if hasattr(direction, "value") else str(direction),
                    model_version="mock_leaker",
                    latency_ms=1.0,
                    status="success",
                )

        val_records = [
            {"tay": "Bươn chiêng khui hội.", "vi": "Tháng giêng mở hội lượn."}
        ]
        clean_mono = [
            {"text": "Bản mường chăm chỉ cày bừa nà ruộng.", "document_id": "clean_1"}
        ]
        translator = BackTranslator(adapter=MockLeakingAdapter())
        u_records, manifest = translator.generate_u_dataset(
            monolingual_records=clean_mono,
            generation_direction=Direction.TAY_TO_VI,
            val_records=val_records,
        )
        # Input was clean, but synthesized output leaked into validation -> must be rejected!
        self.assertEqual(len(u_records), 0)
        self.assertEqual(manifest["anti_leakage"]["synth_leakage_count"], 1)


if __name__ == "__main__":
    unittest.main()
