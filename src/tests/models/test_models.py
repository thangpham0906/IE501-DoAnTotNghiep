"""Unit tests for src/models module: config, tokenizer, dataset, trainer, inference_adapter."""

import tempfile
import unittest
from pathlib import Path

import torch

from src.models.config import (
    EXPERIMENT_SPECS,
    Direction,
    ExperimentName,
    ModelConfig,
    TrainingConfig,
)
from src.models.dataset import (
    TranslationCollator,
    TranslationDataset,
    collate_translation_batch,
    extract_pair,
)
from src.models.inference_adapter import (
    AdapterStatus,
    EmptyInputError,
    InferenceAdapter,
    InvalidDirectionError,
    MockTranslator,
    TextTooLongError,
    TranslationInferenceAdapter,
    TranslationResult,
)
from src.models.tokenizer import NLLBTokenizerWrapper, TayTokenizerWrapper
from src.models.trainer import MockSeq2SeqModel, TranslationTrainer


class TestModelConfig(unittest.TestCase):
    """Test configurations for 6 experiments and bidirectional translation."""

    def test_six_experiment_specs(self) -> None:
        expected_exps = ["E0", "E1", "E2", "E1-M", "A1", "A2"]
        for exp in expected_exps:
            self.assertIn(exp, EXPERIMENT_SPECS)
            spec = EXPERIMENT_SPECS[exp]
            self.assertEqual(spec.name, exp)
            self.assertTrue(len(spec.description) > 0)

        # Check E0 baseline doesn't use synthetic
        self.assertFalse(EXPERIMENT_SPECS["E0"].uses_synthetic)
        # Check E1 has uncurated synthetic
        self.assertTrue(EXPERIMENT_SPECS["E1"].uses_synthetic)
        self.assertFalse(EXPERIMENT_SPECS["E1"].qc_filtered)
        # Check E2 has full QC
        self.assertTrue(EXPERIMENT_SPECS["E2"].qc_filtered)
        # Check E1-M is random control
        self.assertEqual(EXPERIMENT_SPECS["E1-M"].sampling_strategy, "random_n_without_replacement")
        # Check Ablations A1 & A2
        self.assertEqual(EXPERIMENT_SPECS["A1"].ablation_rule_removed, "R1")
        self.assertEqual(EXPERIMENT_SPECS["A2"].ablation_rule_removed, "R2")

    def test_direction_normalization(self) -> None:
        self.assertEqual(Direction.normalize("vi-tyz"), Direction.VI_TO_TAY)
        self.assertEqual(Direction.normalize("vi->ty"), Direction.VI_TO_TAY)
        self.assertEqual(Direction.normalize("vi_to_ty"), Direction.VI_TO_TAY)
        self.assertEqual(Direction.normalize(("vi", "ty")), Direction.VI_TO_TAY)
        self.assertEqual(Direction.normalize("<2ty>"), Direction.VI_TO_TAY)

        self.assertEqual(Direction.normalize("tyz-vi"), Direction.TAY_TO_VI)
        self.assertEqual(Direction.normalize("ty->vi"), Direction.TAY_TO_VI)
        self.assertEqual(Direction.normalize(("ty", "vi")), Direction.TAY_TO_VI)
        self.assertEqual(Direction.normalize("<2vi>"), Direction.TAY_TO_VI)

        with self.assertRaises(ValueError):
            Direction.normalize("invalid-direction")

    def test_model_and_training_config_serialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            model_cfg = ModelConfig(
                experiment="E2",
                direction=Direction.VI_TO_TAY,
                mock_mode=True,
            )
            model_path = tmp_path / "model_config.json"
            model_cfg.save(model_path)
            loaded_model_cfg = ModelConfig.load(model_path)
            self.assertEqual(loaded_model_cfg.experiment, "E2")
            self.assertEqual(loaded_model_cfg.direction, Direction.VI_TO_TAY)
            self.assertEqual(loaded_model_cfg.tgt_lang_tag, "tyz_Latn")

            train_cfg = TrainingConfig(
                experiment_name="E1-M",
                direction=Direction.TAY_TO_VI,
                learning_rate=3e-5,
                output_dir=tmp_path / "checkpoints",
                mock_mode=True,
            )
            train_path = tmp_path / "train_config.json"
            train_cfg.save(train_path)
            loaded_train_cfg = TrainingConfig.load(train_path)
            self.assertEqual(loaded_train_cfg.experiment_name, "E1-M")
            self.assertEqual(loaded_train_cfg.learning_rate, 3e-5)
            self.assertEqual(loaded_train_cfg.direction, Direction.TAY_TO_VI)


class TestTayTokenizerWrapper(unittest.TestCase):
    """Test tokenization, language tags, and subword fragmentation analysis."""

    def setUp(self) -> None:
        self.tokenizer = TayTokenizerWrapper(mock_mode=True)

    def test_alias(self) -> None:
        self.assertIs(NLLBTokenizerWrapper, TayTokenizerWrapper)

    def test_encode_and_decode(self) -> None:
        text = "Tháng giêng mở hội lượn"
        encoded = self.tokenizer.encode(text, lang_code="vie_Latn", add_special_tokens=True)
        self.assertIn("input_ids", encoded)
        self.assertIn("attention_mask", encoded)
        self.assertEqual(encoded["input_ids"][0], self.tokenizer.bos_token_id)
        self.assertEqual(encoded["input_ids"][-1], self.tokenizer.eos_token_id)

        decoded = self.tokenizer.decode(encoded["input_ids"])
        # Decoded text should preserve the words
        self.assertIn("giêng", decoded)
        self.assertIn("lượn", decoded)

    def test_subword_fragmentation_analysis(self) -> None:
        texts = [
            "Bươn chiêng lăng tết slíp ngà bản mường khui hội lượn.",
            "Báo sáo chang bản păn pây chơ xuân lượn nàng hai.",
            "Cần tày kin khẩu nặm rườn phja sang đong thâm.",
        ]
        metrics = self.tokenizer.measure_fragmentation(texts, lang_code="tyz_Latn")
        self.assertEqual(metrics["sample_count"], 3)
        self.assertGreater(metrics["total_words"], 0)
        self.assertGreater(metrics["total_subwords"], 0)
        self.assertGreaterEqual(metrics["tokens_per_word"], 1.0)
        self.assertGreater(metrics["char_to_token_ratio"], 0.0)
        self.assertIn("unknown_token_rate", metrics)


class TestTranslationDatasetAndCollator(unittest.TestCase):
    """Test PyTorch dataset and collator with fixture data."""

    def setUp(self) -> None:
        self.tokenizer = TayTokenizerWrapper(mock_mode=True)
        self.fixture_path = (
            Path(__file__).parent.parent / "fixtures" / "sample_bilingual.jsonl"
        )

    def test_dataset_loading_vi_to_tay(self) -> None:
        dataset = TranslationDataset(
            data=self.fixture_path,
            tokenizer=self.tokenizer,
            direction=Direction.VI_TO_TAY,
        )
        self.assertGreater(len(dataset), 0)
        sample = dataset[0]
        self.assertIn("input_ids", sample)
        self.assertIn("attention_mask", sample)
        self.assertIn("labels", sample)
        self.assertIn("src_text", sample)
        self.assertIn("tgt_text", sample)
        self.assertEqual(sample["direction"], "vi-tyz")
        # In vi-tyz, src is Vietnamese and tgt is Tay
        self.assertIn("Tháng giêng", sample["src_text"])
        self.assertIn("Bươn chiêng", sample["tgt_text"])

    def test_dataset_loading_tay_to_vi(self) -> None:
        dataset = TranslationDataset(
            data=self.fixture_path,
            tokenizer=self.tokenizer,
            direction=Direction.TAY_TO_VI,
        )
        sample = dataset[0]
        self.assertEqual(sample["direction"], "tyz-vi")
        self.assertIn("Bươn chiêng", sample["src_text"])
        self.assertIn("Tháng giêng", sample["tgt_text"])

    def test_collator_dynamic_padding(self) -> None:
        dataset = TranslationDataset(
            data=self.fixture_path,
            tokenizer=self.tokenizer,
            direction=Direction.VI_TO_TAY,
        )
        batch_items = [dataset[0], dataset[1], dataset[2]]
        collated = collate_translation_batch(batch_items, pad_token_id=1, label_pad_token_id=-100)

        self.assertIsInstance(collated["input_ids"], torch.Tensor)
        self.assertIsInstance(collated["attention_mask"], torch.Tensor)
        self.assertIsInstance(collated["labels"], torch.Tensor)
        self.assertEqual(collated["input_ids"].shape[0], 3)
        self.assertEqual(collated["attention_mask"].shape[0], 3)
        self.assertEqual(collated["labels"].shape[0], 3)


class TestTranslationTrainer(unittest.TestCase):
    """Test trainer with lightweight mock Seq2Seq model on CPU."""

    def test_train_loop_and_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tokenizer = TayTokenizerWrapper(mock_mode=True)
            fixture_path = (
                Path(__file__).parent.parent / "fixtures" / "sample_bilingual.jsonl"
            )

            train_ds = TranslationDataset(fixture_path, tokenizer, direction="vi-tyz")
            val_ds = TranslationDataset(fixture_path, tokenizer, direction="vi-tyz")

            train_cfg = TrainingConfig(
                experiment_name="E0-test",
                direction=Direction.VI_TO_TAY,
                output_dir=tmp_path / "checkpoints",
                batch_size=4,
                num_train_epochs=2,
                early_stopping_patience=2,
                seed=42,
                mock_mode=True,
            )

            trainer = TranslationTrainer(training_config=train_cfg, tokenizer=tokenizer)
            summary = trainer.train(train_dataset=train_ds, val_dataset=val_ds)

            self.assertEqual(summary["experiment"], "E0-test")
            self.assertGreater(summary["total_steps"], 0)
            self.assertIn("best_val_loss", summary)
            self.assertIsNotNone(summary["best_checkpoint_path"])

            # Verify checkpoint files exist
            ckpt_dir = Path(summary["best_checkpoint_path"])
            self.assertTrue((ckpt_dir / "model.pt").exists())
            self.assertTrue((ckpt_dir / "model_config.json").exists())
            self.assertTrue((ckpt_dir / "training_config.json").exists())
            self.assertTrue((ckpt_dir / "metadata.json").exists())

    def test_real_model_loading_failure_raises_runtime_error(self) -> None:
        """Verify that when mock_mode=False, trainer raises RuntimeError if model cannot be loaded."""
        train_cfg = TrainingConfig(
            experiment_name="E0-real-fail",
            mock_mode=False,
        )
        model_cfg = ModelConfig(
            model_name_or_path="non_existent_hf_repo_12345_xyz",
            mock_mode=False,
        )
        tokenizer = TayTokenizerWrapper(mock_mode=True)

        with self.assertRaises(RuntimeError) as ctx:
            TranslationTrainer(
                training_config=train_cfg,
                model_config=model_cfg,
                tokenizer=tokenizer,
            )
        self.assertIn("mock_mode is False", str(ctx.exception))

    def test_mock_mode_initializes_mock_model(self) -> None:
        """Verify that when mock_mode=True, trainer initializes MockSeq2SeqModel."""
        train_cfg = TrainingConfig(mock_mode=True)
        tokenizer = TayTokenizerWrapper(mock_mode=True)
        trainer = TranslationTrainer(training_config=train_cfg, tokenizer=tokenizer)
        self.assertIsInstance(trainer.model, MockSeq2SeqModel)

    def test_gradient_accumulation_and_weight_update(self) -> None:
        """Verify gradient accumulation scales loss and actually updates model weights."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tokenizer = TayTokenizerWrapper(mock_mode=True)
            fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_train.jsonl"

            train_ds = TranslationDataset(fixture_path, tokenizer, direction="vi-tyz")
            train_cfg = TrainingConfig(
                experiment_name="E0-accum",
                direction=Direction.VI_TO_TAY,
                output_dir=tmp_path / "checkpoints",
                batch_size=4,
                gradient_accumulation_steps=2,
                num_train_epochs=1,
                mock_mode=True,
                seed=42,
            )
            trainer = TranslationTrainer(training_config=train_cfg, tokenizer=tokenizer)

            # Record initial model weight
            initial_weight = trainer.model.lm_head.weight.clone()

            summary = trainer.train(train_dataset=train_ds)

            # Check that weights actually changed during training
            updated_weight = trainer.model.lm_head.weight
            self.assertFalse(torch.equal(initial_weight, updated_weight))

            # With 20 samples and batch_size 4 -> 5 batches.
            # accum_steps=2: updates at step 2, step 4, step 5 (end of loader) -> 3 global steps.
            self.assertEqual(summary["total_steps"], 3)

    def test_checkpoint_save_and_load_roundtrip(self) -> None:
        """Verify saving checkpoint and loading it back restores exact model weights."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ckpt_dir = Path(tmp_dir) / "test_ckpt"
            train_cfg = TrainingConfig(output_dir=Path(tmp_dir), mock_mode=True)
            tokenizer = TayTokenizerWrapper(mock_mode=True)

            trainer1 = TranslationTrainer(training_config=train_cfg, tokenizer=tokenizer)
            # Mutate weight to non-default state
            with torch.no_grad():
                trainer1.model.lm_head.weight.fill_(0.42)
            trainer1.save_checkpoint(ckpt_dir, is_best=True)

            trainer2 = TranslationTrainer(training_config=train_cfg, tokenizer=tokenizer)
            self.assertFalse(torch.equal(trainer1.model.lm_head.weight, trainer2.model.lm_head.weight))

            trainer2.load_checkpoint(ckpt_dir)
            self.assertTrue(torch.equal(trainer1.model.lm_head.weight, trainer2.model.lm_head.weight))


class TestInferenceAdapterAndMockTranslator(unittest.TestCase):
    """Test TranslationInferenceAdapter, MockTranslator, error codes, and contracts."""

    def setUp(self) -> None:
        self.adapter = TranslationInferenceAdapter(mock_mode=True)

    def test_mock_translator_bidirectional(self) -> None:
        translator = MockTranslator()

        # Vietnamese to Tay
        vi_sample = "Tháng giêng mở hội lượn, trai gái đi chợ xuân."
        tay_out = translator.translate_vi_to_tay(vi_sample)
        self.assertIn("bươn chiêng", tay_out.lower())
        self.assertIn("báo sáo", tay_out.lower())
        self.assertIn("pây chơ", tay_out.lower())

        # Tay to Vietnamese
        tay_sample = "Bươn chiêng khui hội lượn, báo sáo pây chơ xuân."
        vi_out = translator.translate_tay_to_vi(tay_sample)
        self.assertIn("tháng giêng", vi_out.lower())
        self.assertIn("trai gái", vi_out.lower())
        self.assertIn("đi chợ", vi_out.lower())

    def test_adapter_readiness_and_metadata(self) -> None:
        self.assertTrue(self.adapter.is_ready())
        meta = self.adapter.get_metadata()
        self.assertIn("model_version", meta)
        self.assertIn("supported_directions", meta)
        self.assertIn("vi-tyz", meta["supported_directions"])
        self.assertIn("tyz-vi", meta["supported_directions"])

    def test_adapter_translate_with_src_tgt_lang(self) -> None:
        # Contract required: translate(text, src_lang, tgt_lang) -> dict or TranslationResult
        res = self.adapter.translate("Tháng giêng mở hội lượn", src_lang="vi", tgt_lang="ty")
        self.assertIsInstance(res, TranslationResult)
        self.assertEqual(res.status, "mock_mode")
        self.assertEqual(res.direction, "vi-tyz")
        self.assertGreater(len(res.tgt_text), 0)
        self.assertGreater(res.latency_ms, 0.0)

        # Access like dict
        d = res.to_dict()
        self.assertIn("tgt_text", d)
        self.assertIn("latency_ms", d)
        self.assertEqual(res["tgt_text"], d["tgt_text"])

    def test_adapter_translate_reverse_direction(self) -> None:
        res = self.adapter.translate("Bươn chiêng khui hội lượn", src_lang="ty", tgt_lang="vi")
        self.assertEqual(res.direction, "tyz-vi")
        self.assertIn("tháng giêng", res.tgt_text.lower())

    def test_adapter_translate_with_direction_param(self) -> None:
        res = self.adapter.translate("Ăn cơm uống nước", direction="vi-tyz")
        self.assertEqual(res.direction, "vi-tyz")
        self.assertIn("kin khẩu", res.tgt_text.lower())

    def test_adapter_batch_translate(self) -> None:
        texts = [
            "Tháng giêng mở hội lượn",
            "Trai gái đi chợ xuân",
            "Ăn cơm uống nước về nhà",
        ]
        results = self.adapter.translate_batch(texts, direction="vi-tyz")
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIsInstance(r, TranslationResult)
            self.assertGreater(len(r.tgt_text), 0)

    def test_validation_empty_input_error(self) -> None:
        with self.assertRaises(EmptyInputError):
            self.adapter.translate("", src_lang="vi", tgt_lang="ty")

        with self.assertRaises(EmptyInputError):
            self.adapter.translate("   \n\t  ", direction="vi-tyz")

        # Non-raising mode returns status
        res = self.adapter.translate("  ", direction="vi-tyz", raise_exceptions=False)
        self.assertEqual(res.status, "emptyinputerror")
        self.assertIsNotNone(res.error_message)

    def test_validation_text_too_long_error(self) -> None:
        huge_text = "Tháng giêng " * 300  # > 2000 chars
        with self.assertRaises(TextTooLongError):
            self.adapter.translate(huge_text, direction="vi-tyz")

    def test_validation_invalid_direction_error(self) -> None:
        with self.assertRaises(InvalidDirectionError):
            self.adapter.translate("Xin chào", src_lang="en", tgt_lang="fr")


class TestModelEdgeCasesAndPadding(unittest.TestCase):
    """Test suite covering edge cases, dynamic padding, label masking, and tokenization."""

    def setUp(self) -> None:
        self.tokenizer = TayTokenizerWrapper(mock_mode=True)
        self.adapter = TranslationInferenceAdapter(mock_mode=True)

    def test_padding_mask_and_loss_ignore(self) -> None:
        """Verify dynamic batch padding and cross-entropy ignore_index=-100 compatibility."""
        batch = [
            {
                "input_ids": [0, 6, 10, 11, 2],  # len 5
                "attention_mask": [1, 1, 1, 1, 1],
                "labels": [0, 7, 20, 2],  # len 4
                "direction": "vi-tyz",
            },
            {
                "input_ids": [0, 6, 10, 2],  # len 4
                "attention_mask": [1, 1, 1, 1],
                "labels": [0, 7, 20, 21, 22, 2],  # len 6
                "direction": "vi-tyz",
            },
        ]
        collated = collate_translation_batch(batch, pad_token_id=1, label_pad_token_id=-100)

        # Check input_ids shape and pad token
        self.assertEqual(collated["input_ids"].shape, (2, 5))
        self.assertEqual(collated["input_ids"][1, 4].item(), 1)
        self.assertEqual(collated["attention_mask"][1, 4].item(), 0)

        # Check labels shape and -100 masking
        self.assertEqual(collated["labels"].shape, (2, 6))
        self.assertEqual(collated["labels"][0, 4].item(), -100)
        self.assertEqual(collated["labels"][0, 5].item(), -100)

        # Verify PyTorch CrossEntropyLoss correctly ignores -100 without NaN
        vocab_size = 50
        logits = torch.randn(2, 6, vocab_size)
        loss = torch.nn.functional.cross_entropy(
            logits.view(-1, vocab_size),
            collated["labels"].view(-1),
            ignore_index=-100,
        )
        self.assertFalse(torch.isnan(loss))
        self.assertGreater(loss.item(), 0.0)

    def test_tokenizer_truncation_max_length(self) -> None:
        """Verify tokenizer truncates long sequences to max_length and preserves EOS token."""
        long_text = "Tháng giêng mở hội " * 30
        enc = self.tokenizer.encode(long_text, max_length=12, add_special_tokens=True)
        self.assertEqual(len(enc["input_ids"]), 12)
        self.assertEqual(enc["input_ids"][-1], self.tokenizer.eos_token_id)
        self.assertEqual(len(enc["attention_mask"]), 12)

    def test_tokenizer_empty_and_whitespace(self) -> None:
        """Verify tokenizing empty or whitespace text returns valid BOS/EOS sequences."""
        enc_empty = self.tokenizer.encode("", add_special_tokens=True)
        self.assertIn("input_ids", enc_empty)
        self.assertEqual(enc_empty["input_ids"][0], self.tokenizer.bos_token_id)
        self.assertEqual(enc_empty["input_ids"][-1], self.tokenizer.eos_token_id)

        enc_ws = self.tokenizer.encode("   \n\t  ", add_special_tokens=True)
        self.assertEqual(enc_ws["input_ids"], enc_empty["input_ids"])

    def test_tokenizer_batch_encode_empty(self) -> None:
        """Verify batch_encode on empty list returns empty structures without error."""
        res = self.tokenizer.batch_encode([])
        self.assertEqual(res["input_ids"], [])
        self.assertEqual(res["attention_mask"], [])

        res_pt = self.tokenizer.batch_encode([], return_tensors="pt")
        self.assertEqual(res_pt["input_ids"].shape, (0, 0))

    def test_tokenizer_batch_decode_tensor_and_list(self) -> None:
        """Verify batch_decode works with both Python list and PyTorch Tensor."""
        seqs = [[0, 6, 26, 27, 2], [0, 6, 28, 29, 2]]
        decoded_list = self.tokenizer.batch_decode(seqs)
        self.assertEqual(len(decoded_list), 2)

        tensor_seqs = torch.tensor(seqs, dtype=torch.long)
        decoded_tensor = self.tokenizer.batch_decode(tensor_seqs)
        self.assertEqual(decoded_list, decoded_tensor)

    def test_measure_fragmentation_edge_cases(self) -> None:
        """Verify measure_fragmentation handles empty lists and single words."""
        empty_res = self.tokenizer.measure_fragmentation([])
        self.assertEqual(empty_res["sample_count"], 0)
        self.assertEqual(empty_res["tokens_per_word"], 0.0)

        single_res = self.tokenizer.measure_fragmentation(["lượn"], lang_code="tyz_Latn")
        self.assertEqual(single_res["sample_count"], 1)
        self.assertEqual(single_res["total_words"], 1)
        self.assertGreaterEqual(single_res["tokens_per_word"], 1.0)

    def test_direction_properties_and_normalization(self) -> None:
        """Verify Direction properties and diverse input formats."""
        v2t = Direction.VI_TO_TAY
        self.assertEqual(v2t.source_lang, "vi")
        self.assertEqual(v2t.target_lang, "ty")
        self.assertEqual(v2t.source_tag, "vie_Latn")
        self.assertEqual(v2t.target_tag, "tyz_Latn")

        t2v = Direction.TAY_TO_VI
        self.assertEqual(t2v.source_lang, "ty")
        self.assertEqual(t2v.target_lang, "vi")
        self.assertEqual(t2v.source_tag, "tyz_Latn")
        self.assertEqual(t2v.target_tag, "vie_Latn")

        # Tuple normalization
        self.assertEqual(Direction.normalize(("vie", "tay")), Direction.VI_TO_TAY)
        self.assertEqual(Direction.normalize(("tyz", "vie")), Direction.TAY_TO_VI)

    def test_extract_pair_fallbacks(self) -> None:
        """Verify extract_pair resolves different dictionary schemas."""
        item1 = {"vi": "Cơm", "tay": "Khẩu"}
        self.assertEqual(extract_pair(item1, Direction.VI_TO_TAY), ("Cơm", "Khẩu"))
        self.assertEqual(extract_pair(item1, Direction.TAY_TO_VI), ("Khẩu", "Cơm"))

        item2 = {"vietnamese": "Nước", "ty": "Nặm"}
        self.assertEqual(extract_pair(item2, Direction.VI_TO_TAY), ("Nước", "Nặm"))

        item3 = {"src_text": "Rừng", "tgt_text": "Đong"}
        self.assertEqual(extract_pair(item3, Direction.VI_TO_TAY), ("Rừng", "Đong"))

    def test_adapter_batch_translate_empty(self) -> None:
        """Verify adapter batch translation handles empty input cleanly."""
        res = self.adapter.translate_batch([], direction="vi-tyz")
        self.assertEqual(res, [])


class TestHardwareProfilerAndRunner(unittest.TestCase):
    """Test suite for T02 hardware profiling, throughput benchmarking, and training runner."""

    def setUp(self) -> None:
        from src.models.hardware_profile import HardwareProfiler

        self.profiler = HardwareProfiler()

    def test_inspect_host_returns_valid_specs(self) -> None:
        specs = self.profiler.inspect_host()
        self.assertGreater(specs.cpu_cores_logical, 0)
        self.assertGreater(specs.ram_total_gb, 0.0)
        self.assertGreater(specs.disk_free_gb, 0.0)
        self.assertIn(specs.os_system, ["Linux", "Darwin", "Windows"])

    def test_determine_execution_strategy_fallback(self) -> None:
        # Incompatible GPU or low VRAM -> CPU
        strat_cpu = self.profiler.determine_execution_strategy(
            available_ram_gb=8.0, vram_gb=4.0, is_gpu_compatible=False
        )
        self.assertEqual(strat_cpu["device"], "cpu")
        self.assertEqual(strat_cpu["batch_size"], 8)
        self.assertEqual(strat_cpu["gradient_accumulation_steps"], 2)

        # High VRAM compatible GPU -> CUDA
        strat_gpu = self.profiler.determine_execution_strategy(
            available_ram_gb=16.0, vram_gb=8.0, is_gpu_compatible=True
        )
        self.assertEqual(strat_gpu["device"], "cuda")
        self.assertEqual(strat_gpu["batch_size"], 8)

    def test_benchmark_throughput(self) -> None:
        metrics = self.profiler.benchmark_throughput(iterations=10)
        self.assertGreater(metrics["tokens_per_second"], 0.0)
        self.assertGreater(metrics["samples_per_second"], 0.0)
        self.assertGreater(metrics["estimated_step_latency_ms"], 0.0)

    def test_generate_report_budgets_all_six_experiments(self) -> None:
        report = self.profiler.generate_report()
        self.assertEqual(len(report.experiment_budgets), 6)
        exp_names = [b.experiment_name for b in report.experiment_budgets]
        for expected in ["E0", "E1", "E2", "E1-M", "A1", "A2"]:
            self.assertIn(expected, exp_names)

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "profile.json"
            report.save(out_file)
            self.assertTrue(out_file.exists())

    def test_run_training_pipeline_smoke(self) -> None:
        from argparse import Namespace
        from src.models.run_training import run_training_pipeline

        with tempfile.TemporaryDirectory() as tmp_dir:
            args = Namespace(
                experiment="E0",
                direction="vi-tyz",
                train_file="src/tests/fixtures/sample_train.jsonl",
                val_file="src/tests/fixtures/sample_val.jsonl",
                test_file="src/tests/fixtures/sample_test.jsonl",
                epochs=1,
                batch_size=8,
                gradient_accumulation_steps=2,
                device="cpu",
                output_dir=tmp_dir,
                mock_mode=True,
            )
            summary = run_training_pipeline(args)
            self.assertEqual(summary["experiment"], "E0")
            self.assertGreater(summary["total_steps"], 0)
            self.assertIsNotNone(summary["best_checkpoint_path"])
            self.assertIn("test_metrics", summary)
            self.assertIn("val_loss", summary["test_metrics"])
            ckpt_path = Path(summary["best_checkpoint_path"])
            self.assertTrue((ckpt_path / "model.pt").exists())
            self.assertTrue((ckpt_path / "metadata.json").exists())


if __name__ == "__main__":
    unittest.main()
