"""Comprehensive test suite for the evaluation module (src/evaluation/).

Tests:
1. Metrics: BLEU, chrF, chrF++ mathematical correctness and SacreBLEU parity.
2. Error Analysis: Repetition, length anomaly, omission, untranslated copy, numerical consistency.
3. Human Evaluation: Sampling, blinding, unblinding key, CSV/JSONL export, Cohen's Kappa.
4. Evaluator: TranslationEvaluator benchmarking across E0, E1, E2, E1-M, A1, A2.
"""

import json
import math
import tempfile
import unittest
from pathlib import Path

from src.evaluation.error_analysis import (
    ErrorAnalyzer,
    ErrorCategory,
    Severity,
    TranslationError,
    batch_error_analysis,
    classify_translation_errors,
)
from src.evaluation.evaluator import (
    ComparativeEvaluationReport,
    ModelEvaluationScore,
    TranslationEvaluator,
)
from src.evaluation.human_eval import (
    BlindTranslationItem,
    HumanEvaluationBundle,
    HumanEvaluationSampler,
    calculate_cohens_kappa,
    export_guidelines_md,
    export_human_eval_sheet_csv,
    export_human_eval_sheet_jsonl,
    export_unblind_key,
    interpret_kappa,
    sample_blind_human_evaluation,
    unblind_evaluation_results,
)
from src.evaluation.metrics import (
    BLEUResult,
    CHRFResult,
    Tokenizer13a,
    compute_bleu,
    compute_chrf,
    compute_chrf_plus_plus,
    corpus_bleu,
    corpus_chrf,
    evaluate_metrics,
    sentence_bleu,
    sentence_chrf,
    tokenize_13a,
    tokenize_whitespace,
)
from src.models.config import Direction
from src.models.inference_adapter import TranslationInferenceAdapter


class TestMetrics(unittest.TestCase):
    """Test suite for metrics.py (BLEU, chrF, chrF++)."""

    def test_tokenizer_13a(self) -> None:
        """Verify 13a tokenizer punctuation splitting and entity handling."""
        line = 'Tháng giêng, sau tết (ngày 15) "bản làng" mở hội lượn &amp; hát!'
        tokens = tokenize_13a(line)
        self.assertIn("Tháng", tokens)
        self.assertIn(",", tokens)
        self.assertIn("(", tokens)
        self.assertIn("15", tokens)
        self.assertIn(")", tokens)
        self.assertIn("&", tokens)
        self.assertIn("!", tokens)

    def test_bleu_identical_strings(self) -> None:
        """Identical hypothesis and reference should yield 100.0 BLEU."""
        hyp = "Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn ."
        ref = "Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn ."
        res = compute_bleu([hyp], [ref])
        self.assertAlmostEqual(res.score, 100.0, places=4)
        self.assertAlmostEqual(res.bp, 1.0, places=4)
        self.assertEqual(res.sys_len, res.ref_len)

    def test_bleu_disjoint_strings(self) -> None:
        """Completely disjoint hypothesis and reference should yield 0.0 BLEU."""
        hyp = "Con trâu đang ăn cỏ trên đồi cao ."
        ref = "Thuyền buồm lướt sóng ra khơi đánh cá ."
        res = compute_bleu([hyp], [ref], smooth_method="none")
        self.assertAlmostEqual(res.score, 0.0, places=4)

    def test_bleu_brevity_penalty(self) -> None:
        """Hypothesis significantly shorter than reference must suffer brevity penalty."""
        hyp = "Bản làng mở hội ."
        ref = "Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn then ."
        res = compute_bleu([hyp], [ref])
        self.assertLess(res.bp, 1.0)
        self.assertGreater(res.bp, 0.0)

    def test_bleu_parity_with_sacrebleu(self) -> None:
        """Verify our pure-Python BLEU matches SacreBLEU library output to machine precision."""
        try:
            import sacrebleu
        except ImportError:
            self.skipTest("sacrebleu library not installed")

        hyps = [
            "Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn .",
            "Trai gái trong bản cùng nhau đi chợ xuân hát lượn nàng hai .",
            "Tiếng đàn tính then vang vọng khắp núi rừng cao bằng .",
        ]
        refs = [
            "Tháng giêng sau tết ngày mười lăm bản mường mở hội lượn .",
            "Trai gái chang bản cùng nhau đi chợ xuân lượn nàng hai .",
            "Tiếng đàn tính then vang vọng khắp núi non cao bằng .",
        ]

        my_res = compute_bleu(hyps, refs)
        sb_res = sacrebleu.corpus_bleu(hyps, [refs])

        self.assertAlmostEqual(my_res.score, sb_res.score, places=5)
        self.assertAlmostEqual(my_res.bp, sb_res.bp, places=5)
        self.assertEqual(my_res.sys_len, sb_res.sys_len)
        self.assertEqual(my_res.ref_len, sb_res.ref_len)

    def test_chrf_identical_strings(self) -> None:
        """chrF on identical strings must be 100.0."""
        hyp = "Bươn chiêng lăng tết slíp ngà bản mường khui hội lượn."
        ref = "Bươn chiêng lăng tết slíp ngà bản mường khui hội lượn."
        res = compute_chrf(hyp, ref)
        self.assertAlmostEqual(res.score, 100.0, places=4)

    def test_chrf_parity_with_sacrebleu(self) -> None:
        """Verify our chrF and chrF++ match SacreBLEU output to machine precision."""
        try:
            import sacrebleu
        except ImportError:
            self.skipTest("sacrebleu library not installed")

        hyps = [
            "Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn.",
            "Trai gái trong bản cùng nhau đi chợ xuân hát lượn nàng hai.",
        ]
        refs = [
            "Tháng giêng sau tết ngày mười lăm bản mường mở hội lượn.",
            "Trai gái chang bản cùng nhau đi chợ xuân lượn nàng hai.",
        ]

        my_chrf = compute_chrf(hyps, refs)
        sb_chrf = sacrebleu.corpus_chrf(hyps, [refs])
        self.assertAlmostEqual(my_chrf.score, sb_chrf.score, places=5)

        my_chrfpp = compute_chrf_plus_plus(hyps, refs)
        sb_chrfpp = sacrebleu.corpus_chrf(hyps, [refs], word_order=2)
        self.assertAlmostEqual(my_chrfpp.score, sb_chrfpp.score, places=5)

    def test_multi_reference_bleu(self) -> None:
        """BLEU with multiple references per hypothesis should pick closest length."""
        hyps = ["Bản làng mở hội mùa xuân ."]
        refs = [["Bản làng mở hội xuân .", "Trong bản làng mở hội mùa xuân năm nay ."]]
        res = compute_bleu(hyps, refs)
        self.assertGreater(res.score, 0.0)

    def test_evaluate_metrics_composite(self) -> None:
        """evaluate_metrics returns BLEU, chrF, and chrF++ simultaneously."""
        hyp = "Hôm nay trời rất đẹp ."
        ref = "Hôm nay trời đẹp lắm ."
        metrics = evaluate_metrics(hyp, ref)
        self.assertIsInstance(metrics.bleu, BLEUResult)
        self.assertIsInstance(metrics.chrf, CHRFResult)
        self.assertIsInstance(metrics.chrf_pp, CHRFResult)
        d = metrics.to_dict()
        self.assertIn("bleu", d)
        self.assertIn("chrf", d)
        self.assertIn("chrf_plus_plus", d)


class TestErrorAnalysis(unittest.TestCase):
    """Test suite for error_analysis.py."""

    def setUp(self) -> None:
        self.analyzer = ErrorAnalyzer()

    def test_detect_consecutive_word_repetition(self) -> None:
        """Detect single word repeated >= 3 times."""
        rep = self.analyzer.analyze_sentence(
            src="Đi lên nương làm rẫy",
            hyp="Pây khửn rẩy rẩy rẩy hết việc",
        )
        self.assertTrue(rep.has_error)
        cat_names = [e.category.value for e in rep.errors]
        self.assertIn(ErrorCategory.REPETITION.value, cat_names)

    def test_detect_ngram_phrase_repetition(self) -> None:
        """Detect repeated bigrams or trigrams."""
        rep = self.analyzer.analyze_sentence(
            src="Trai gái trong bản đi chợ xuân",
            hyp="Báo sáo chang bản chang bản chang bản pây chơ xuân",
        )
        self.assertTrue(rep.has_error)
        cat_names = [e.category.value for e in rep.errors]
        self.assertIn(ErrorCategory.REPETITION.value, cat_names)

    def test_detect_length_anomalies(self) -> None:
        """Detect truncation and hallucinatory explosion."""
        # Truncation
        rep_trunc = self.analyzer.analyze_sentence(
            src="Tháng giêng sau tết ngày mười lăm bản làng mở hội lượn rất vui vẻ",
            hyp="Khui hội",
        )
        self.assertTrue(rep_trunc.has_error)
        self.assertTrue(
            any(e.category == ErrorCategory.LENGTH_ANOMALY for e in rep_trunc.errors)
        )

        # Explosion
        rep_exp = self.analyzer.analyze_sentence(
            src="Đi chợ",
            hyp="Pây chơ xuân lượn then nàng hai chang bản mường pưng vần phja thung lũng đồi núi rất nhiều lời dịch dài dòng thừa thãi",
        )
        self.assertTrue(rep_exp.has_error)
        self.assertTrue(
            any(e.category == ErrorCategory.LENGTH_ANOMALY for e in rep_exp.errors)
        )

    def test_detect_verbatim_source_copy(self) -> None:
        """Detect verbatim source copy without translation."""
        rep = self.analyzer.analyze_sentence(
            src="Bản làng mở hội lượn",
            hyp="Bản làng mở hội lượn",
        )
        self.assertTrue(rep.has_error)
        self.assertTrue(
            any(e.category == ErrorCategory.UNTRANSLATED_COPY for e in rep.errors)
        )

    def test_detect_missing_numerical_entities(self) -> None:
        """Detect when numbers present in source are dropped in hypothesis."""
        rep = self.analyzer.analyze_sentence(
            src="Ngày 15 tháng giêng mở hội",
            hyp="Văn nẩy bươn chiêng khui hội",
        )
        self.assertTrue(rep.has_error)
        self.assertTrue(
            any(e.category == ErrorCategory.MISSING_NUMERICAL for e in rep.errors)
        )

    def test_detect_corrupted_encoding_and_foreign_script(self) -> None:
        """Detect non-Latin Chinese/Cyrillic characters and replacement character."""
        rep_cjk = self.analyzer.analyze_sentence(
            src="Cần cù làm việc",
            hyp="Hết việc 勤劳",
        )
        self.assertTrue(rep_cjk.has_error)
        self.assertTrue(
            any(e.category == ErrorCategory.CORRUPTED_ENCODING for e in rep_cjk.errors)
        )

        rep_null = self.analyzer.analyze_sentence(
            src="Câu dịch lỗi",
            hyp="Pây � mường",
        )
        self.assertTrue(
            any(e.category == ErrorCategory.CORRUPTED_ENCODING for e in rep_null.errors)
        )

    def test_batch_error_analysis(self) -> None:
        """Verify aggregation across an entire batch of sentences."""
        sources = [
            "Tháng giêng mở hội",
            "Đi lên nương rẫy",
            "Ngày 15 có hội",
        ]
        hyps = [
            "Bươn chiêng khui hội",  # Clean
            "Pây pây pây khửn rẩy",  # Repetition
            "Khui hội",  # Missing number and short
        ]
        report = batch_error_analysis(sources, hyps)
        self.assertEqual(report.total_sentences, 3)
        self.assertGreaterEqual(report.sentences_with_errors, 2)
        self.assertGreater(report.error_rate, 0.0)
        self.assertIn(ErrorCategory.REPETITION.value, report.counts_by_category)


class TestHumanEvaluation(unittest.TestCase):
    """Test suite for human_eval.py (blinding, sampling, Cohen's Kappa)."""

    def setUp(self) -> None:
        self.fixture_path = (
            Path(__file__).parent.parent / "fixtures" / "sample_bilingual.jsonl"
        )
        self.records = []
        if self.fixture_path.exists():
            with open(self.fixture_path, encoding="utf-8") as f:
                for line in f:
                    self.records.append(json.loads(line))

    def test_cohens_kappa_perfect_agreement(self) -> None:
        """When two raters agree 100%, unweighted and weighted kappa must be 1.0."""
        r1 = [1, 2, 3, 4, 5, 3, 4, 5, 2, 1]
        r2 = [1, 2, 3, 4, 5, 3, 4, 5, 2, 1]
        res = calculate_cohens_kappa(r1, r2, weights="quadratic")
        self.assertAlmostEqual(res.kappa, 1.0, places=4)
        self.assertAlmostEqual(res.weighted_kappa, 1.0, places=4)
        self.assertAlmostEqual(res.observed_agreement, 1.0, places=4)
        self.assertAlmostEqual(res.adjacent_agreement, 1.0, places=4)

    def test_cohens_kappa_weighted_ordinal(self) -> None:
        """Adjacent discrepancies (1-point diff) should produce higher weighted kappa than unweighted."""
        r1 = [1, 2, 3, 4, 5, 2, 3, 4, 5, 1]
        r2 = [1, 2, 3, 4, 4, 2, 4, 4, 5, 1]  # minor differences of 1 point
        res = calculate_cohens_kappa(r1, r2, weights="quadratic")
        self.assertIsNotNone(res.weighted_kappa)
        self.assertGreater(res.weighted_kappa, res.kappa)
        self.assertEqual(res.adjacent_agreement, 1.0)

    def test_sampling_and_blinding_bundle(self) -> None:
        """Verify blind bundle creation, randomization, and unblinding integrity."""
        if not self.records:
            self.skipTest("Sample bilingual fixture not found")

        translators = {
            "E0": lambda t, d: f"E0:{t[:10]}",
            "E1": lambda t, d: f"E1:{t[:10]}",
            "E2": lambda t, d: f"E2:{t[:10]}",
            "E1-M": lambda t, d: f"E1M:{t[:10]}",
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle = sample_blind_human_evaluation(
                test_records=self.records,
                system_translators=translators,
                output_dir=tmp_dir,
                sample_size_per_direction=5,
                seed=42,
            )

            # 5 samples * 4 systems * 2 directions = 40 items
            self.assertEqual(len(bundle.items), 40)
            self.assertTrue((Path(tmp_dir) / "human_eval_sheet.csv").exists())
            self.assertTrue((Path(tmp_dir) / "human_eval_sheet.jsonl").exists())
            self.assertTrue((Path(tmp_dir) / "unblind_key.json").exists())
            self.assertTrue((Path(tmp_dir) / "HUMAN_EVAL_GUIDELINES.md").exists())

            # Check that each item in CSV has blind label only
            for item in bundle.items:
                self.assertIn(item.blind_system_id, ["SYS_A", "SYS_B", "SYS_C", "SYS_D"])

            # Test unblinding aggregation
            mock_scored_items = []
            for item in bundle.items:
                item_dict = item.to_dict()
                item_dict["semantic_accuracy_1_5"] = 4
                item_dict["fluency_1_5"] = 5
                mock_scored_items.append(item_dict)

            summary = unblind_evaluation_results(mock_scored_items, bundle.unblind_key)
            self.assertIn("E0", summary)
            self.assertIn("E2", summary)
            self.assertEqual(summary["E0"]["semantic_all"]["mean"], 4.0)
            self.assertEqual(summary["E2"]["fluency_all"]["mean"], 5.0)


class TestTranslationEvaluator(unittest.TestCase):
    """Test suite for evaluator.py (TranslationEvaluator)."""

    def setUp(self) -> None:
        self.fixture_path = (
            Path(__file__).parent.parent / "fixtures" / "sample_bilingual.jsonl"
        )
        self.records = []
        if self.fixture_path.exists():
            with open(self.fixture_path, encoding="utf-8") as f:
                for line in f:
                    self.records.append(json.loads(line))

    def test_evaluator_with_mock_adapter(self) -> None:
        """Run evaluator on mock translation adapter across test fixture."""
        if not self.records:
            self.skipTest("Sample bilingual fixture not found")

        evaluator = TranslationEvaluator()
        adapter = TranslationInferenceAdapter(mock_mode=True)

        report, preds = evaluator.evaluate_test_set(
            test_records=self.records[:5],
            models={"E0": adapter, "E2": adapter},
            directions=[Direction.VI_TO_TAY, Direction.TAY_TO_VI],
        )

        self.assertIsInstance(report, ComparativeEvaluationReport)
        self.assertEqual(len(report.scores), 4)  # 2 models * 2 directions
        self.assertGreater(len(preds), 0)

        # Verify markdown table generation
        md_table = report.generate_markdown_table()
        self.assertIn("| **E0** |", md_table)
        self.assertIn("| **E2** |", md_table)
        self.assertIn("BLEU", md_table)
        self.assertIn("chrF", md_table)

    def test_evaluator_all_six_variants_benchmark(self) -> None:
        """Simulate comparative evaluation across all 6 research variants (E0, E1, E2, E1-M, A1, A2)."""
        evaluator = TranslationEvaluator()

        # Mock translators with slight lexical variations
        models = {
            "E0": lambda t, d: f"E0 translation of {t[:12]}",
            "E1": lambda t, d: f"E1 raw translation of {t[:12]}",
            "E2": lambda t, d: f"E2 clean translation of {t[:12]}",
            "E1-M": lambda t, d: f"E1-M random control of {t[:12]}",
            "A1": lambda t, d: f"A1 no-R1 ablation of {t[:12]}",
            "A2": lambda t, d: f"A2 no-R2 ablation of {t[:12]}",
        }

        test_records = [
            {"vi": "Tháng giêng mở hội lượn", "ty": "Bươn chiêng khui hội lượn"},
            {"vi": "Trai gái đi chợ xuân", "ty": "Báo sáo pây chơ xuân"},
        ]

        report, preds = evaluator.evaluate_test_set(
            test_records=test_records,
            models=models,
            directions=[Direction.VI_TO_TAY],
        )

        self.assertEqual(len(report.scores), 6)
        model_names = [s.model_name for s in report.scores]
        for v in ["E0", "E1", "E2", "E1-M", "A1", "A2"]:
            self.assertIn(v, model_names)

        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = report.save_json(Path(tmp_dir) / "eval_report.json")
            md_path = report.save_markdown(Path(tmp_dir) / "eval_report.md")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())


class TestEvaluationEdgeCases(unittest.TestCase):
    """Test edge cases for metrics, error analysis, and human evaluation."""

    def test_bleu_smoothing_methods(self) -> None:
        """Verify BLEU computation across different smoothing techniques."""
        hyp = "Tháng giêng mở hội"
        ref = "Tháng giêng mở hội lượn then nàng hai trên núi"

        for method in ["floor", "add-k", "exp", "none"]:
            res = compute_bleu([hyp], [ref], smooth_method=method)
            self.assertGreaterEqual(res.score, 0.0)
            self.assertLessEqual(res.score, 100.0)

    def test_chrf_empty_and_single_char(self) -> None:
        """Verify chrF handles empty strings and single character inputs."""
        res_empty = compute_chrf("", "")
        self.assertEqual(res_empty.score, 0.0)

        res_char = compute_chrf("a", "a")
        self.assertEqual(res_char.score, 100.0)

    def test_error_analysis_clean_sentence(self) -> None:
        """Verify error analyzer reports no errors for clean translations."""
        analyzer = ErrorAnalyzer()
        res = analyzer.analyze_sentence(
            src="Tháng giêng mở hội lượn.",
            hyp="Bươn chiêng khui hội lượn.",
        )
        self.assertFalse(res.has_error)
        self.assertEqual(len(res.errors), 0)

    def test_error_analysis_multiple_errors(self) -> None:
        """Verify sentence with multiple distinct errors detects all error categories."""
        analyzer = ErrorAnalyzer()
        # Source has number 15, hyp has word repetition and non-Latin CJK character
        res = analyzer.analyze_sentence(
            src="Ngày 15 mở hội lượn.",
            hyp="Bươn bươn bươn khui 快乐.",
        )
        self.assertTrue(res.has_error)
        cats = {e.category for e in res.errors}
        self.assertIn(ErrorCategory.REPETITION, cats)
        self.assertIn(ErrorCategory.MISSING_NUMERICAL, cats)
        self.assertIn(ErrorCategory.CORRUPTED_ENCODING, cats)

    def test_cohens_kappa_mismatched_lengths(self) -> None:
        """Verify calculate_cohens_kappa raises ValueError when rater lists differ in length."""
        with self.assertRaises(ValueError):
            calculate_cohens_kappa([1, 2, 3], [1, 2])

    def test_cohens_kappa_zero_variance(self) -> None:
        """Verify calculate_cohens_kappa handles constant rating vectors without ZeroDivisionError and marks kappa undefined."""
        r1 = [5, 5, 5, 5, 5]
        r2 = [5, 5, 5, 5, 5]
        res = calculate_cohens_kappa(r1, r2)
        self.assertAlmostEqual(res.observed_agreement, 1.0)
        self.assertAlmostEqual(res.chance_agreement, 1.0)
        self.assertTrue(math.isnan(res.kappa))
        self.assertIn("Undefined", res.interpretation)
        self.assertIn("Undefined", res.format_summary())
        self.assertIsNone(res.to_dict()["kappa"])

    def test_cohens_kappa_likert_fixed_categories(self) -> None:
        """Verify Likert ratings preserve fixed 1..5 category scale without distance compression."""
        # Only ratings 4 and 5 are observed, but the scale is 1..5
        r1 = [4, 5, 5, 4]
        r2 = [5, 5, 4, 4]
        res = calculate_cohens_kappa(r1, r2, weights="quadratic")
        # Ensure categories span 1..5
        self.assertEqual(res.categories, [1, 2, 3, 4, 5])
        # On 1..5 scale, adjacent diff of 1 has weight 1 - (1/16) = 0.9375
        self.assertIsNotNone(res.weighted_kappa)
        self.assertFalse(math.isnan(res.weighted_kappa))

    def test_cohens_kappa_complete_disagreement(self) -> None:
        """Verify calculate_cohens_kappa with maximal disagreement yields non-positive kappa."""
        r1 = [1, 1, 1, 1, 1, 1, 1, 1]
        r2 = [5, 5, 5, 5, 5, 5, 5, 5]
        res = calculate_cohens_kappa(r1, r2)
        self.assertLessEqual(res.kappa, 0.0)

    def test_bleu_unicode_nfc_nfd_normalization_parity(self) -> None:
        """Verify decomposed NFD and composed NFC Vietnamese text achieve 100% BLEU and chrF."""
        import unicodedata
        s_nfc = "Tháng giêng mở hội lượn then nàng hai trên núi cao ."
        s_nfd = unicodedata.normalize("NFD", s_nfc)
        self.assertNotEqual(s_nfc, s_nfd, "NFD and NFC binary strings must differ")

        # Due to automatic NFC normalization, score must be 100.0
        bleu = compute_bleu([s_nfd], [s_nfc])
        self.assertAlmostEqual(bleu.score, 100.0, places=4)

        chrf = compute_chrf([s_nfd], [s_nfc])
        self.assertAlmostEqual(chrf.score, 100.0, places=4)

    def test_metric_signature_generation(self) -> None:
        """Verify SacreBLEU signature formats for BLEU, chrF, and chrF++."""
        hyps = ["Đây là một câu thử nghiệm ."]
        refs = ["Đây là một câu thử nghiệm ."]

        bleu = compute_bleu(hyps, refs)
        self.assertTrue(len(bleu.signature) > 0)
        self.assertIn("tok:13a", bleu.signature)
        self.assertIn("version:", bleu.signature)

        chrf = compute_chrf(hyps, refs, word_order=0)
        self.assertTrue(len(chrf.signature) > 0)
        self.assertIn("nw:0", chrf.signature)

        chrf_pp = compute_chrf_plus_plus(hyps, refs)
        self.assertTrue(len(chrf_pp.signature) > 0)
        self.assertIn("nw:2", chrf_pp.signature)

    def test_human_eval_three_criteria_and_honest_counts(self) -> None:
        """Verify three evaluation criteria (adequacy, completeness, fluency) and honest count reporting."""
        records = [
            {"id": "doc1_s1", "vi": "Câu một", "tay": "Côm nưng"},
            {"id": "doc1_s2", "vi": "Câu hai dài hơn một chút để phân tầng độ dài", "tay": "Côm sloong"},
        ]
        translators = {
            "E0": lambda t, d: t,
            "E1": lambda t, d: t,
            "E2": lambda t, d: t,
            "E1-M": lambda t, d: t,
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle = sample_blind_human_evaluation(
                test_records=records,
                system_translators=translators,
                output_dir=tmp_dir,
                sample_size_per_direction=50,  # Request 50, but only 2 available
                seed=42,
            )

            # 2 samples * 4 systems * 2 directions = 16 items
            self.assertEqual(len(bundle.items), 16)
            self.assertEqual(bundle.manifest["actual_samples_vi_to_tay"], 2)
            self.assertEqual(bundle.manifest["actual_samples_tay_to_vi"], 2)
            self.assertEqual(bundle.manifest["total_evaluated_translations"], 16)
            self.assertTrue(bundle.manifest["is_truncated"])

            # Test scoring all 3 criteria
            scored_items = []
            for item in bundle.items:
                item_dict = item.to_dict()
                item_dict["adequacy_1_5"] = 4
                item_dict["completeness_1_5"] = 5
                item_dict["fluency_1_5"] = 4
                scored_items.append(item_dict)

            summary = unblind_evaluation_results(scored_items, bundle.unblind_key)
            self.assertEqual(summary["E0"]["adequacy_all"]["mean"], 4.0)
            self.assertEqual(summary["E0"]["completeness_all"]["mean"], 5.0)
            self.assertEqual(summary["E0"]["fluency_all"]["mean"], 4.0)

    def test_evaluator_metadata_and_mock_flag(self) -> None:
        """Verify TranslationEvaluator flags mock adapters and preserves provenance."""
        evaluator = TranslationEvaluator()
        adapter = TranslationInferenceAdapter(mock_mode=True)
        test_records = [
            {"id": "rec_001", "source_doc_id": "doc_vov_01", "vi": "Bản làng mở hội", "tay": "Bản mường khui hội"}
        ]
        report, preds = evaluator.evaluate_test_set(
            test_records=test_records,
            models={"E0": adapter},
            directions=[Direction.VI_TO_TAY],
        )
        self.assertTrue(report.scores[0].is_mock)
        self.assertEqual(preds[0]["sample_id"], "rec_001")
        self.assertEqual(preds[0]["provenance"]["source_doc_id"], "doc_vov_01")
        self.assertTrue(preds[0]["is_mock"])
        self.assertTrue(report.metadata["has_mock_models"])

    def test_human_eval_sampler_reproducibility(self) -> None:
        """Verify calling sample_blind_evaluation multiple times on the same sampler produces identical items."""
        records = [
            {"id": f"rec_{i:02d}", "source": "vov4", "vi": f"Câu tiếng Việt số {i}", "tay": f"Côm Tày slíp {i}"}
            for i in range(10)
        ]
        translators = {"E0": lambda t, d: t, "E1": lambda t, d: t, "E2": lambda t, d: t, "E1-M": lambda t, d: t}
        sampler = HumanEvaluationSampler(seed=42)

        bundle1 = sampler.sample_blind_evaluation(records, translators, sample_size_per_direction=5)
        bundle2 = sampler.sample_blind_evaluation(records, translators, sample_size_per_direction=5)

        self.assertEqual(len(bundle1.items), len(bundle2.items))
        for item1, item2 in zip(bundle1.items, bundle2.items):
            self.assertEqual(item1.item_id, item2.item_id)
            self.assertEqual(item1.sample_id, item2.sample_id)
            self.assertEqual(item1.blind_system_id, item2.blind_system_id)
            self.assertEqual(item1.source_text, item2.source_text)
            self.assertEqual(item1.hypothesis_text, item2.hypothesis_text)
        self.assertEqual(bundle1.unblind_key, bundle2.unblind_key)

    def test_human_eval_provenance_and_unblind_key(self) -> None:
        """Verify unblind key maps original IDs and provenance while rater items remain blinded."""
        records = [
            {
                "id": "rec_corpus_001",
                "source": "vov4_tay",
                "source_doc_id": "doc_106",
                "topic": "culture",
                "vi": "Hôm nay bản làng mở hội lượn rất vui.",
                "tay": "Văn nẩy bản mường khui hội lượn đây lai.",
            }
        ]
        translators = {"E0": lambda t, d: "hyp_e0", "E1": lambda t, d: "hyp_e1", "E2": lambda t, d: "hyp_e2", "E1-M": lambda t, d: "hyp_e1_m"}
        sampler = HumanEvaluationSampler(seed=42)
        bundle = sampler.sample_blind_evaluation(records, translators, sample_size_per_direction=1)

        # Ensure rater items do not leak original IDs or system names
        for item in bundle.items:
            self.assertNotIn("rec_corpus_001", item.item_id)
            self.assertNotIn("vov4_tay", item.item_id)
            self.assertNotIn("E0", item.blind_system_id)
            self.assertNotIn("E1", item.blind_system_id)

        # Check that unblind key contains original_id and provenance
        for sample_id, key_entry in bundle.unblind_key.items():
            self.assertEqual(key_entry["original_id"], "rec_corpus_001")
            self.assertEqual(key_entry["provenance"]["source"], "vov4_tay")
            self.assertEqual(key_entry["provenance"]["source_doc_id"], "doc_106")
            self.assertIn("systems", key_entry)

    def test_stratification_by_source_and_length(self) -> None:
        """Verify stratification selects from multiple sources and length buckets."""
        records = [
            {"id": "s1_short", "source": "src_a", "vi": "Đi chợ", "tay": "Pây chơ"},
            {"id": "s1_med", "source": "src_a", "vi": "Bản làng mở hội lượn mừng xuân mới rất vui", "tay": "Bản mường khui hội"},
            {"id": "s2_short", "source": "src_b", "vi": "Ăn cơm", "tay": "Kin khẩu"},
            {"id": "s2_med", "source": "src_b", "vi": "Mặt trời mọc đỏ rực trên ngọn núi cao phía đông", "tay": "Bươn đét khửn phja"},
        ]
        sampler = HumanEvaluationSampler(seed=42)
        stratified = sampler._stratify_by_source_and_length(records, text_key="vi", n_samples=3)
        self.assertEqual(len(stratified), 3)
        sources = {r["source"] for r in stratified}
        self.assertGreaterEqual(len(sources), 2, "Should sample across multiple sources")

    def test_evaluator_mismatched_length_validation(self) -> None:
        """Verify TranslationEvaluator raises ValueError on length mismatches before execution."""
        evaluator = TranslationEvaluator()
        sources = ["câu 1", "câu 2"]
        references = ["ref 1"]  # Mismatched length

        with self.assertRaises(ValueError):
            evaluator.evaluate_model(
                model_name="test_model",
                translator=lambda t, d: t,
                sources=sources,
                references=references,
            )

        with self.assertRaises(ValueError):
            evaluator.evaluate_model(
                model_name="test_model",
                translator=lambda t, d: t,
                sources=sources,
                references=["ref 1", "ref 2"],
                sample_ids=["id 1"],  # Mismatched IDs
            )

    def test_evaluator_unknown_translator_is_mock(self) -> None:
        """Verify anonymous callables, dicts, or unverified stubs default to is_mock=True."""
        evaluator = TranslationEvaluator()
        sources = ["Xin chào"]
        references = ["Tỏn chào"]

        # Anonymous lambda
        score1, _ = evaluator.evaluate_model(
            model_name="lambda_model",
            translator=lambda t, d: t,
            sources=sources,
            references=references,
        )
        self.assertTrue(score1.is_mock, "Anonymous lambda must fail-closed to is_mock=True")

        # Plain dictionary lookup
        score2, _ = evaluator.evaluate_model(
            model_name="dict_model",
            translator={"Xin chào": "Tỏn chào"},
            sources=sources,
            references=references,
        )
        self.assertTrue(score2.is_mock, "Dictionary translator must fail-closed to is_mock=True")

    def test_sampler_n_less_than_strata_no_lexical_bias(self) -> None:
        """Verify sampling when N < number of strata does not systematically bias toward alphabetical first strata."""
        records = [
            {"id": x, "source": x, "vi": f"Câu ngắn {x}", "tay": f"Côm {x}"}
            for x in ["a", "b", "c", "d", "e", "f"]
        ]
        translators = {"E0": lambda t, d: t, "E1": lambda t, d: t, "E2": lambda t, d: t, "E1-M": lambda t, d: t}

        selected_per_seed: dict[int, list[str]] = {}
        all_selected_ids: set[str] = set()

        for seed in [1, 2, 3, 99]:
            sampler = HumanEvaluationSampler(seed=seed)
            bundle = sampler.sample_blind_evaluation(records, translators, sample_size_per_direction=2)
            # Vi->ty samples
            vi_items = [item for item in bundle.items if item.direction == "vi-tyz"]
            sample_ids = sorted(list(set(item.sample_id for item in vi_items)))
            self.assertEqual(len(sample_ids), 2)

            original_ids = sorted([bundle.unblind_key[s_id]["original_id"] for s_id in sample_ids])
            selected_per_seed[seed] = original_ids
            all_selected_ids.update(original_ids)

            # Ensure without replacement and uniqueness
            self.assertEqual(len(set(original_ids)), 2)

        # Seeds 1, 2, 3, 99 must NOT all produce ['a', 'b']
        identical_to_ab = all(selected_per_seed[s] == ["a", "b"] for s in [1, 2, 3, 99])
        self.assertFalse(identical_to_ab, "Sampler must not bias selection to lexical 'a', 'b' across different seeds")
        # Strata beyond 'a' and 'b' must have non-zero probability of being chosen
        self.assertTrue(len(all_selected_ids) > 2, f"Selection across seeds must cover diverse strata, got: {all_selected_ids}")

    def test_sampler_imbalanced_sources_proportionality(self) -> None:
        """Verify Largest Remainder sampling preserves proportionality when sources are severely imbalanced."""
        records = []
        for i in range(20):
            records.append({"id": f"src_large_{i:02d}", "source": "large_corpus", "vi": f"Câu {i}", "tay": f"Côm {i}"})
        for i in range(4):
            records.append({"id": f"src_med_{i:02d}", "source": "medium_corpus", "vi": f"Câu {i}", "tay": f"Côm {i}"})
        for i in range(1):
            records.append({"id": f"src_small_{i:02d}", "source": "small_corpus", "vi": f"Câu {i}", "tay": f"Côm {i}"})

        sampler = HumanEvaluationSampler(seed=42)
        sampled = sampler._stratify_by_source_and_length(records, text_key="vi", n_samples=5)

        self.assertEqual(len(sampled), 5)
        # All sampled records must be unique without replacement
        sampled_ids = [r["id"] for r in sampled]
        self.assertEqual(len(set(sampled_ids)), 5)

        # Proportional allocation check: large_corpus has 20/25 = 80% of data, must get majority
        large_count = sum(1 for r in sampled if r["source"] == "large_corpus")
        self.assertGreaterEqual(large_count, 3, "Large corpus must receive proportional majority quota")

    def test_bleu_invalid_tokenizer_and_config_raises(self) -> None:
        """Verify invalid tokenizer or smoothing config raises ValueError and does not silently fallback."""
        hyps = ["a b c d"]
        refs = ["a b c d"]

        # 1. Invalid tokenizer with auto/official engine must raise ValueError
        with self.assertRaises(ValueError):
            compute_bleu(hyps, refs, tokenize="INVALID_REVIEW_TOKENIZER")

        # 2. Invalid tokenizer with explicit standalone engine must raise ValueError
        with self.assertRaises(ValueError):
            compute_bleu(hyps, refs, tokenize="INVALID_REVIEW_TOKENIZER", engine="standalone")

        # 3. Invalid smoothing method with standalone engine must raise ValueError
        with self.assertRaises(ValueError):
            compute_bleu(hyps, refs, smooth_method="unsupported_smoothing", engine="standalone")

        # 4. Invalid ngram order
        with self.assertRaises(ValueError):
            compute_bleu(hyps, refs, max_ngram_order=0)

        # 5. Invalid engine option
        with self.assertRaises(ValueError):
            compute_bleu(hyps, refs, engine="invalid_engine_name")

    def test_chrf_invalid_config_raises(self) -> None:
        """Verify invalid parameters in compute_chrf raise ValueError."""
        hyps = ["a b c"]
        refs = ["a b c"]

        with self.assertRaises(ValueError):
            compute_chrf(hyps, refs, char_order=-1)

        with self.assertRaises(ValueError):
            compute_chrf(hyps, refs, word_order=-1)

        with self.assertRaises(ValueError):
            compute_chrf(hyps, refs, beta=0.0)

        with self.assertRaises(ValueError):
            compute_chrf(hyps, refs, char_order=-1, engine="standalone")

    def test_metric_standalone_explicit_signature(self) -> None:
        """Verify explicit standalone engine marks version as 2.6.0-standalone."""
        hyps = ["Tháng giêng mở hội lượn ."]
        refs = ["Tháng giêng mở hội lượn ."]

        bleu_res = compute_bleu(hyps, refs, engine="standalone")
        self.assertIn("version:2.6.0-standalone", bleu_res.signature)
        self.assertNotIn("standalone-fallback", bleu_res.signature)

        chrf_res = compute_chrf(hyps, refs, engine="standalone")
        self.assertIn("version:2.6.0-standalone", chrf_res.signature)
        self.assertNotIn("standalone-fallback", chrf_res.signature)

    def test_dependency_runtime_failure_on_missing_sacrebleu(self) -> None:
        """Verify requesting engine='sacrebleu' raises RuntimeError when library is unavailable."""
        import src.evaluation.metrics as metrics_mod
        orig_has = metrics_mod._HAS_SACREBLEU
        try:
            metrics_mod._HAS_SACREBLEU = False
            with self.assertRaises(RuntimeError):
                compute_bleu(["a"], ["a"], engine="sacrebleu")
            with self.assertRaises(RuntimeError):
                compute_chrf(["a"], ["a"], engine="sacrebleu")
        finally:
            metrics_mod._HAS_SACREBLEU = orig_has

    def test_evaluator_tiers_and_fixture_separation(self) -> None:
        """Verify evaluator distinguishes mock_simulation, smoke_fixture, and research_corpus tiers."""
        evaluator = TranslationEvaluator()

        # 1. Mock adapter
        mock_adapter = TranslationInferenceAdapter(mock_mode=True)
        score_mock, _ = evaluator.evaluate_model(
            model_name="mock_test",
            translator=mock_adapter,
            sources=["Bản làng mở hội"],
            references=["Bản mường khui hội"],
            sample_ids=["sample_0001"],
            provenance_list=[{"source": "fixture"}],
        )
        self.assertTrue(score_mock.is_mock)
        self.assertEqual(score_mock.evaluation_tier, "mock_simulation")
        self.assertFalse(score_mock.to_dict()["is_research_verified"])

        # 2. Pseudo-neural adapter evaluated on fixture test data
        class DummyNeuralAdapter:
            def __init__(self):
                self.mock_mode = False
                self.status = "ready"
                self.checkpoint_dir = Path("/tmp/mock_ckpt")
                self.model_version = "neural-fixture-v1"
            def translate(self, text, direction):
                return "Bản mường khui hội"

        neural_adapter = DummyNeuralAdapter()
        score_smoke, _ = evaluator.evaluate_model(
            model_name="neural_smoke_test",
            translator=neural_adapter,
            sources=["Bản làng mở hội"],
            references=["Bản mường khui hội"],
            sample_ids=["sample_0001"],
            provenance_list=[{"source": "fixture"}],
        )
        # mock_mode is False, but it is on fixture -> must be smoke_fixture tier!
        self.assertEqual(score_smoke.evaluation_tier, "smoke_fixture")
        self.assertFalse(score_smoke.to_dict()["is_research_verified"])

        # Markdown report check
        report = ComparativeEvaluationReport(scores=[score_mock, score_smoke])
        md = report.generate_markdown_table()
        self.assertIn("AUDIT DISCLAIMER", md)
        self.assertIn("SMOKE (Neural/Fixture)", md)
        self.assertIn("MOCK", md)


if __name__ == "__main__":
    unittest.main()
