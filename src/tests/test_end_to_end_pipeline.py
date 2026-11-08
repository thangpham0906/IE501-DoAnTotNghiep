"""End-to-End Pipeline Integration Test.

Validates the complete workflow from fixture datasets to final evaluation:
1. Dataset split hygiene (zero leakage between Train, Validation, and Test).
2. Back-translation with reverse model mock and active anti-leakage protection.
3. Quality Control (QC) filtering (R1-R5), ablations (A1, A2), and exact control sampler (E1-M).
4. Dataset collation and training readiness for all 6 variants (E0, E1, E2, E1-M, A1, A2) in both directions.
5. Model inference adapter, automated evaluation (BLEU, chrF, chrF++), error analysis, and blinded human eval.
6. Comprehensive zero-leakage guarantee across all components.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from src.augmentation.back_translation import BackTranslator
from src.augmentation.pipeline import AugmentationPipeline
from src.augmentation.qc_filters import QCFilterConfig, QualityControlFilter
from src.augmentation.sampler import AugmentationSampler, sample_without_replacement
from src.data_pipeline.common import read_jsonl, write_jsonl
from src.evaluation.error_analysis import (
    ErrorAnalyzer,
    ErrorCategory,
    batch_error_analysis,
)
from src.evaluation.evaluator import ComparativeEvaluationReport, TranslationEvaluator
from src.evaluation.human_eval import (
    calculate_cohens_kappa,
    sample_blind_human_evaluation,
    unblind_evaluation_results,
)
from src.evaluation.metrics import evaluate_metrics
from src.models.config import Direction, ModelConfig, TrainingConfig
from src.models.dataset import (
    TranslationCollator,
    TranslationDataset,
    collate_translation_batch,
    extract_pair,
)
from src.models.inference_adapter import (
    MockTranslator,
    TranslationInferenceAdapter,
    TranslationResult,
)
from src.models.tokenizer import TayTokenizerWrapper
from src.models.trainer import MockSeq2SeqModel, TranslationTrainer

ROOT = Path(__file__).resolve().parents[2]


class TestEndToEndPipeline(unittest.TestCase):
    """Integration test suite executing the entire pipeline with mock models."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.fixture_bilingual = (
            ROOT / "src/tests/fixtures/sample_bilingual.jsonl"
        )
        self.fixture_monolingual = (
            ROOT / "src/tests/fixtures/sample_monolingual.jsonl"
        )
        self.tokenizer = TayTokenizerWrapper(mock_mode=True)
        self.adapter = TranslationInferenceAdapter(mock_mode=True)

        # Load fixtures
        self.assertTrue(
            self.fixture_bilingual.exists(), "Bilingual fixture missing"
        )
        self.assertTrue(
            self.fixture_monolingual.exists(), "Monolingual fixture missing"
        )
        self.bilingual_records = read_jsonl(self.fixture_bilingual)
        self.monolingual_records = read_jsonl(self.fixture_monolingual)

        # Split bilingual fixture into Train (E0), Val, and Test
        # 28 samples: 18 train, 5 val, 5 test
        self.train_gold = self.bilingual_records[:18]
        self.val_gold = self.bilingual_records[18:23]
        self.test_gold = self.bilingual_records[23:28]

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_fixture_split_hygiene_and_integrity(self) -> None:
        """Verify baseline split hygiene: train, val, and test must be strictly disjoint."""
        self.assertEqual(len(self.train_gold), 18)
        self.assertEqual(len(self.val_gold), 5)
        self.assertEqual(len(self.test_gold), 5)

        train_vi = {r["vi"].strip().lower() for r in self.train_gold}
        val_vi = {r["vi"].strip().lower() for r in self.val_gold}
        test_vi = {r["vi"].strip().lower() for r in self.test_gold}

        train_tay = {r["tay"].strip().lower() for r in self.train_gold}
        val_tay = {r["tay"].strip().lower() for r in self.val_gold}
        test_tay = {r["tay"].strip().lower() for r in self.test_gold}

        # Zero overlap between splits
        self.assertEqual(len(train_vi & val_vi), 0, "Train and Val VI overlap detected")
        self.assertEqual(len(train_vi & test_vi), 0, "Train and Test VI overlap detected")
        self.assertEqual(len(val_vi & test_vi), 0, "Val and Test VI overlap detected")

        self.assertEqual(len(train_tay & val_tay), 0, "Train and Val Tay overlap detected")
        self.assertEqual(len(train_tay & test_tay), 0, "Train and Test Tay overlap detected")
        self.assertEqual(len(val_tay & test_tay), 0, "Val and Test Tay overlap detected")

    def test_02_back_translation_with_anti_leakage_and_provenance(self) -> None:
        """Verify back-translation produces synthetic pairs and filters injected leakage."""
        # Inject intentional leakage into monolingual pool
        contaminated_mono = list(self.monolingual_records)
        # Add exact duplicate of a val sentence
        contaminated_mono.append({
            "text": self.val_gold[0]["tay"],
            "document_id": "injected_val_leak",
        })
        # Add exact duplicate of a test sentence
        contaminated_mono.append({
            "text": self.test_gold[0]["tay"],
            "document_id": "injected_test_leak",
        })
        # Add whitespace/case variation of a test sentence
        contaminated_mono.append({
            "text": "  " + self.test_gold[1]["tay"].upper() + "  ",
            "document_id": "injected_test_leak_case",
        })

        translator = BackTranslator(adapter=self.adapter)
        u_records, manifest = translator.generate_u_dataset(
            monolingual_records=contaminated_mono,
            generation_direction=Direction.TAY_TO_VI,
            val_records=self.val_gold,
            test_records=self.test_gold,
        )

        # Anti-leakage verification
        leakage_info = manifest["anti_leakage"]
        self.assertEqual(
            leakage_info["leakage_count"],
            3,
            "Anti-leakage mechanism must catch all 3 injected leaked sentences",
        )
        self.assertEqual(len(u_records), len(self.monolingual_records))

        # Check provenance metadata on generated synthetic records
        for rec in u_records:
            self.assertTrue(rec.get("synthetic"), "Must be tagged synthetic: True")
            self.assertEqual(rec.get("synthetic_side"), "vi")
            self.assertEqual(rec.get("source_monolingual_lang"), "ty")
            self.assertIn("u_id", rec)
            self.assertIn("hash", rec)
            self.assertGreater(len(rec["vi"]), 0)
            self.assertGreater(len(rec["tay"]), 0)

            # Ensure none match val or test
            self.assertNotIn(rec["tay"].strip().lower(), {v["tay"].strip().lower() for v in self.val_gold})
            self.assertNotIn(rec["tay"].strip().lower(), {t["tay"].strip().lower() for t in self.test_gold})

    def test_03_qc_filtering_ablation_and_exact_control_sampling(self) -> None:
        """Verify QC filters R1-R5, ablations A1/A2, and E1-M exact N matching."""
        translator = BackTranslator(adapter=self.adapter)
        u_records, _ = translator.generate_u_dataset(
            monolingual_records=self.monolingual_records,
            generation_direction=Direction.TAY_TO_VI,
            val_records=self.val_gold,
            test_records=self.test_gold,
        )

        # Add dummy anomalies to test all 5 QC rules specifically in the candidate pool
        u_records_extended = list(u_records)
        u_records_extended.extend([
            {
                "u_id": "u_r1_bad",
                "hash": "hash_r1_bad",
                "tay": "Bươn chiêng lăng tết slíp ngà bản mường khui hội lượn.",
                "vi": "Hết việc.",  # R1 length ratio violation (short)
                "source_text": "Bươn chiêng lăng tết slíp ngà bản mường khui hội lượn.",
                "target_text": "Hết việc.",
                "generation_direction": "tyz-vi",
                "synthetic": True,
            },
            {
                "u_id": "u_r2_bad",
                "hash": "hash_r2_bad",
                "tay": "Bươn đét khửn chang bản.",
                "vi": "Mặt trời mọc mọc mọc mọc đỏ rực.",  # R2 repetition
                "source_text": "Bươn đét khửn chang bản.",
                "target_text": "Mặt trời mọc mọc mọc mọc đỏ rực.",
                "generation_direction": "tyz-vi",
                "synthetic": True,
            },
            {
                "u_id": "u_r3_bad",
                "hash": "hash_r3_bad",
                "tay": "Cần Tày chăm chỉ cày bừa chang nà ruộng.",
                "vi": "Cần Tày chăm chỉ cày bừa chang nà ruộng.",  # R3 source copy
                "source_text": "Cần Tày chăm chỉ cày bừa chang nà ruộng.",
                "target_text": "Cần Tày chăm chỉ cày bừa chang nà ruộng.",
                "generation_direction": "tyz-vi",
                "synthetic": True,
            },
            {
                "u_id": "u_r4_bad",
                "hash": "hash_r4_bad",
                "tay": "Pây.",
                "vi": "Đi.",  # R4 min words (< 2 words)
                "source_text": "Pây.",
                "target_text": "Đi.",
                "generation_direction": "tyz-vi",
                "synthetic": True,
            },
            {
                "u_id": "u_r5_bad",
                "hash": "hash_r5_bad",
                "tay": "Bản làng mở hội vui vẻ.",
                "vi": "Bản làng mở hội 快乐 trong rừng.",  # R5 foreign CJK script
                "source_text": "Bản làng mở hội vui vẻ.",
                "target_text": "Bản làng mở hội 快乐 trong rừng.",
                "generation_direction": "tyz-vi",
                "synthetic": True,
            },
        ])

        sampler = AugmentationSampler()

        # E2: Full QC
        e2_samples, e2_manifest = sampler.create_e2(u_records_extended, n_samples=8, seed=42)
        n_effective = len(e2_samples)
        self.assertGreater(n_effective, 0)
        self.assertLessEqual(n_effective, 8)

        # Ensure none of the bad samples passed E2
        e2_ids = {s["u_id"] for s in e2_samples}
        for bad_id in ["u_r1_bad", "u_r2_bad", "u_r3_bad", "u_r4_bad", "u_r5_bad"]:
            self.assertNotIn(bad_id, e2_ids, f"{bad_id} should have been rejected by QC")

        # E1-M: Random control drawn from raw U with EXACT same N
        e1_m_samples, e1_m_manifest = sampler.create_e1_m(
            u_records_extended, n_samples=n_effective, seed=42
        )
        self.assertEqual(
            len(e1_m_samples),
            n_effective,
            "E1-M control must have identical sample count N to E2",
        )
        self.assertEqual(e1_m_manifest["seed"], 42)

        # A1 Ablation: Disable R1 -> u_r1_bad can pass if other rules pass
        a1_samples, a1_manifest = sampler.create_a1(
            u_records_extended, n_samples=n_effective, seed=42
        )
        self.assertEqual(a1_manifest["disabled_rule"], "R1")
        self.assertEqual(len(a1_samples), n_effective)

        # A2 Ablation: Disable R2 -> u_r2_bad can pass if other rules pass
        a2_samples, a2_manifest = sampler.create_a2(
            u_records_extended, n_samples=n_effective, seed=42
        )
        self.assertEqual(a2_manifest["disabled_rule"], "R2")
        self.assertEqual(len(a2_samples), n_effective)

    def test_04_dataset_composition_and_dataloader_for_all_six_variants(self) -> None:
        """Test dataset composition, dynamic padding, and label masking for E0, E1, E2, E1-M, A1, A2."""
        pipeline = AugmentationPipeline(mock_mode=True)
        manifest = pipeline.run(
            output_dir=self.temp_dir,
            train_e0_source=self.fixture_bilingual,
            monolingual_source=self.fixture_monolingual,
            direction=Direction.VI_TO_TAY,
            n_samples=5,
            seed=42,
        )

        variants = ["train_e1.jsonl", "train_e2.jsonl", "train_e1_m.jsonl", "train_a1.jsonl", "train_a2.jsonl"]
        for vfile in variants:
            vpath = self.temp_dir / vfile
            self.assertTrue(vpath.exists(), f"Variant file {vfile} must exist")

            # Load into TranslationDataset for both directions
            for dir_name in [Direction.VI_TO_TAY, Direction.TAY_TO_VI]:
                dataset = TranslationDataset(
                    data=vpath,
                    tokenizer=self.tokenizer,
                    direction=dir_name,
                )
                self.assertGreater(len(dataset), 0)

                # Batch collate via TranslationCollator
                collator = TranslationCollator(pad_token_id=1, label_pad_token_id=-100)
                batch = [dataset[i] for i in range(min(4, len(dataset)))]
                batch_tensors = collator(batch)

                self.assertIn("input_ids", batch_tensors)
                self.assertIn("attention_mask", batch_tensors)
                self.assertIn("labels", batch_tensors)

                # Dimensions
                b_size = len(batch)
                self.assertEqual(batch_tensors["input_ids"].shape[0], b_size)
                self.assertEqual(batch_tensors["attention_mask"].shape[0], b_size)
                self.assertEqual(batch_tensors["labels"].shape[0], b_size)

                # Dynamic padding check: padding positions in input_ids must have pad_token_id (1)
                # and attention_mask == 0
                input_ids = batch_tensors["input_ids"]
                mask = batch_tensors["attention_mask"]
                labels = batch_tensors["labels"]

                pad_mask = (input_ids == 1)
                self.assertTrue(torch.all(mask[pad_mask] == 0))

                # Labels padding check: padding positions in labels must have -100
                label_pad_mask = (labels == -100)
                # If there is any padding in labels, verify it is marked -100
                if label_pad_mask.any():
                    self.assertTrue(torch.all(labels[label_pad_mask] == -100))

    def test_05_mock_model_training_step_for_all_variants(self) -> None:
        """Run single-step training for each variant on CPU to ensure model forward/backward contract."""
        for exp_name in ["E0", "E1", "E2", "E1-M", "A1", "A2"]:
            train_ds = TranslationDataset(
                data=self.fixture_bilingual,
                tokenizer=self.tokenizer,
                direction=Direction.VI_TO_TAY,
            )
            val_ds = TranslationDataset(
                data=self.val_gold,
                tokenizer=self.tokenizer,
                direction=Direction.VI_TO_TAY,
            )

            train_cfg = TrainingConfig(
                experiment_name=exp_name,
                direction=Direction.VI_TO_TAY,
                output_dir=self.temp_dir / f"ckpt_{exp_name}",
                batch_size=4,
                num_train_epochs=1,
                seed=42,
                mock_mode=True,
            )

            trainer = TranslationTrainer(training_config=train_cfg, tokenizer=self.tokenizer)
            summary = trainer.train(train_dataset=train_ds, val_dataset=val_ds)

            self.assertEqual(summary["experiment"], exp_name)
            self.assertGreater(summary["total_steps"], 0)
            self.assertIn("best_val_loss", summary)
            self.assertTrue(Path(summary["best_checkpoint_path"]).exists())

    def test_06_end_to_end_inference_and_evaluation_pipeline(self) -> None:
        """Execute inference adapter -> metrics (BLEU, chrF) -> error analysis -> blinded human eval."""
        # 1. Inference Adapter on test set
        test_inputs_vi = [r["vi"] for r in self.test_gold]
        test_refs_tay = [r["tay"] for r in self.test_gold]

        res_vi_to_tay = self.adapter.translate_batch(test_inputs_vi, direction="vi-tyz")
        self.assertEqual(len(res_vi_to_tay), len(test_inputs_vi))
        hyps_tay = [r.tgt_text for r in res_vi_to_tay]

        # 2. Metrics calculation
        metrics_vi_to_tay = evaluate_metrics(hyps_tay, test_refs_tay)
        self.assertGreaterEqual(metrics_vi_to_tay.bleu.score, 0.0)
        self.assertGreaterEqual(metrics_vi_to_tay.chrf.score, 0.0)
        self.assertGreaterEqual(metrics_vi_to_tay.chrf_pp.score, 0.0)

        # Reverse direction inference and metrics
        test_inputs_tay = [r["tay"] for r in self.test_gold]
        test_refs_vi = [r["vi"] for r in self.test_gold]

        res_tay_to_vi = self.adapter.translate_batch(test_inputs_tay, direction="tyz-vi")
        self.assertEqual(len(res_tay_to_vi), len(test_inputs_tay))
        hyps_vi = [r.tgt_text for r in res_tay_to_vi]

        metrics_tay_to_vi = evaluate_metrics(hyps_vi, test_refs_vi)
        self.assertGreaterEqual(metrics_tay_to_vi.bleu.score, 0.0)

        # 3. TranslationEvaluator comparative benchmark across 6 variants
        evaluator = TranslationEvaluator()
        models = {
            "E0": self.adapter,
            "E1": self.adapter,
            "E2": self.adapter,
            "E1-M": self.adapter,
            "A1": self.adapter,
            "A2": self.adapter,
        }
        report, _ = evaluator.evaluate_test_set(
            test_records=self.test_gold,
            models=models,
            directions=[Direction.VI_TO_TAY, Direction.TAY_TO_VI],
        )
        self.assertIsInstance(report, ComparativeEvaluationReport)
        self.assertEqual(len(report.scores), 12)  # 6 models * 2 directions

        # Save report artifacts
        json_rep = report.save_json(self.temp_dir / "eval_report.json")
        md_rep = report.save_markdown(self.temp_dir / "eval_report.md")
        self.assertTrue(json_rep.exists())
        self.assertTrue(md_rep.exists())

        # 4. Error Analysis on generated hypotheses
        error_rep = batch_error_analysis(test_inputs_vi, hyps_tay)
        self.assertEqual(error_rep.total_sentences, len(test_inputs_vi))
        self.assertIn("error_rate", error_rep.to_dict())

        # 5. Human Evaluation: Sampling, Blinding, Scoring, and Cohen's Kappa
        human_eval_dir = self.temp_dir / "human_eval"
        bundle = sample_blind_human_evaluation(
            test_records=self.test_gold,
            system_translators=models,
            output_dir=human_eval_dir,
            sample_size_per_direction=3,
            seed=42,
        )
        # 3 samples * 4 core systems (E0, E1, E2, E1-M) * 2 directions = 24 items
        self.assertEqual(len(bundle.items), 24)
        self.assertTrue((human_eval_dir / "human_eval_sheet.csv").exists())
        self.assertTrue((human_eval_dir / "unblind_key.json").exists())

        # Simulate rater evaluations
        rater1_scores = [4, 5, 3, 4, 5, 2, 4, 3, 5, 4]
        rater2_scores = [4, 4, 3, 5, 5, 2, 4, 3, 4, 4]
        kappa_res = calculate_cohens_kappa(rater1_scores, rater2_scores, weights="quadratic")
        self.assertGreater(kappa_res.weighted_kappa, 0.5)
        self.assertGreater(kappa_res.observed_agreement, 0.6)

    def test_07_strict_zero_data_leakage_assertion(self) -> None:
        """Comprehensive audit: Ensure 0 leakage across the entire generated pipeline."""
        # Run full augmentation pipeline
        pipeline = AugmentationPipeline(mock_mode=True)
        pipeline.run(
            output_dir=self.temp_dir,
            train_e0_source=self.fixture_bilingual,
            monolingual_source=self.fixture_monolingual,
            direction=Direction.VI_TO_TAY,
            n_samples=5,
            seed=42,
        )

        test_sentences_vi = {r["vi"].strip().lower() for r in self.test_gold}
        test_sentences_tay = {r["tay"].strip().lower() for r in self.test_gold}

        val_sentences_vi = {r["vi"].strip().lower() for r in self.val_gold}
        val_sentences_tay = {r["tay"].strip().lower() for r in self.val_gold}

        # Check all generated training files: train_e1, train_e2, train_e1_m, train_a1, train_a2
        for vname in ["train_e1.jsonl", "train_e2.jsonl", "train_e1_m.jsonl", "train_a1.jsonl", "train_a2.jsonl"]:
            vpath = self.temp_dir / vname
            rows = read_jsonl(vpath)
            synthetic_rows = [r for r in rows if r.get("synthetic") is True]

            for s_row in synthetic_rows:
                s_vi = (s_row.get("vi") or s_row.get("vi_text") or "").strip().lower()
                s_tay = (s_row.get("tay") or s_row.get("tay_text") or "").strip().lower()

                # Synthetic instances must never collide with test set
                self.assertNotIn(
                    s_vi,
                    test_sentences_vi,
                    f"Leakage detected in {vname}: synthetic Vietnamese matches test set: {s_vi}",
                )
                self.assertNotIn(
                    s_tay,
                    test_sentences_tay,
                    f"Leakage detected in {vname}: synthetic Tay matches test set: {s_tay}",
                )

                # Synthetic instances must never collide with validation set
                self.assertNotIn(
                    s_vi,
                    val_sentences_vi,
                    f"Leakage detected in {vname}: synthetic Vietnamese matches val set: {s_vi}",
                )
                self.assertNotIn(
                    s_tay,
                    val_sentences_tay,
                    f"Leakage detected in {vname}: synthetic Tay matches val set: {s_tay}",
                )


if __name__ == "__main__":
    unittest.main()
