"""Tests for training mechanics, gradient accumulation, anti-fallback, and bidirectional updates.

Test suite verifying core training mechanics:
1. Gradient accumulation: optimizer.step() is called strictly every `accum_steps` batches.
2. Anti-silent fallback: mock_mode=False on non-existent model path MUST raise RuntimeError.
3. Bidirectional weight updates (vi-tyz and tyz-vi):
   - Model weights change after 1 epoch of training.
   - Saved checkpoint restores exact weights and bit-identical logits in a new model.
   - InferenceAdapter loads the trained checkpoint and produces valid translations.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import torch

from src.models.config import Direction, ModelConfig, TrainingConfig
from src.models.dataset import TranslationDataset
from src.models.inference_adapter import (
    InferenceAdapter,
    ModelNotReadyError,
    TranslationInferenceAdapter,
    TranslationResult,
)
from src.models.tokenizer import TayTokenizerWrapper
from src.models.trainer import (
    LocalSeq2SeqTransformer,
    MockSeq2SeqModel,
    TranslationTrainer,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
TRAIN_FILE = FIXTURES_DIR / "sample_train.jsonl"
VAL_FILE = FIXTURES_DIR / "sample_val.jsonl"


class TestTrainingMechanics(unittest.TestCase):
    """Verification suite for model training mechanics and safety guards."""

    @classmethod
    def setUpClass(cls) -> None:
        if not TRAIN_FILE.exists() or not VAL_FILE.exists():
            raise FileNotFoundError(
                f"Missing fixtures: train={TRAIN_FILE.exists()}, val={VAL_FILE.exists()}"
            )

    def test_01_gradient_accumulation_step_frequency(self) -> None:
        """Test 1: Verify gradient accumulation calls optimizer.step() strictly every 2 batches.

        Configuration:
            batch_size = 2
            accum_steps = 2
            sample_train.jsonl = 20 samples => exactly 10 batches.

        Verification:
            - Model forward is executed for every batch (10 times total).
            - optimizer.step() is called ONLY at batch boundaries: [2, 4, 6, 8, 10].
            - optimizer.step() is NOT called at odd batches: [1, 3, 5, 7, 9].
            - Total optimizer.step() invocations == 5.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tokenizer = TayTokenizerWrapper(mock_mode=True)
            train_ds = TranslationDataset(
                TRAIN_FILE, tokenizer=tokenizer, direction=Direction.VI_TO_TAY
            )
            self.assertEqual(len(train_ds), 20)

            train_cfg = TrainingConfig(
                experiment_name="test-accum-step-freq",
                direction=Direction.VI_TO_TAY,
                output_dir=tmp_path / "checkpoints",
                batch_size=2,
                gradient_accumulation_steps=2,
                num_train_epochs=1,
                mock_mode=True,
                seed=42,
            )
            trainer = TranslationTrainer(training_config=train_cfg, tokenizer=tokenizer)

            # Instrument forward and step calls to track batch boundaries
            forward_count = 0
            step_at_forward_counts: list[int] = []

            orig_forward = trainer.model.forward

            def tracked_forward(*args, **kwargs):
                nonlocal forward_count
                forward_count += 1
                return orig_forward(*args, **kwargs)

            orig_step = trainer.optimizer.step

            def tracked_step(*args, **kwargs):
                step_at_forward_counts.append(forward_count)
                return orig_step(*args, **kwargs)

            trainer.model.forward = tracked_forward
            trainer.optimizer.step = tracked_step

            summary = trainer.train(train_dataset=train_ds)

            # Total batches forwarded in 1 epoch
            self.assertEqual(forward_count, 10)

            # Step must be called strictly at even batch numbers
            expected_step_counts = [2, 4, 6, 8, 10]
            self.assertEqual(
                step_at_forward_counts,
                expected_step_counts,
                f"optimizer.step() called at {step_at_forward_counts}, expected {expected_step_counts}",
            )
            self.assertEqual(len(step_at_forward_counts), 5)
            self.assertEqual(summary["total_steps"], 5)

    def test_02_block_silent_fallback_on_missing_model_path(self) -> None:
        """Test 2: Verify that mock_mode=False on non-existent path raises RuntimeError.

        Must NOT silently fall back to MockSeq2SeqModel or mock mode.
        """
        non_existent_path = "/non_existent/model/path/checkpoint_nllb_missing_xyz_99999"
        train_cfg = TrainingConfig(
            experiment_name="test-block-silent-fallback",
            direction=Direction.VI_TO_TAY,
            mock_mode=False,
            device="cpu",
        )
        model_cfg = ModelConfig(
            model_name_or_path=non_existent_path,
            mock_mode=False,
        )
        tokenizer = TayTokenizerWrapper(mock_mode=True)

        with self.assertRaises(RuntimeError) as ctx:
            TranslationTrainer(
                training_config=train_cfg,
                model_config=model_cfg,
                tokenizer=tokenizer,
            )

        err_msg = str(ctx.exception)
        self.assertIn("mock_mode is False", err_msg)
        self.assertIn("Failed to load real model", err_msg)
        self.assertIn(non_existent_path, err_msg)

    def _run_bidirectional_weight_update_and_checkpoint_test(
        self, direction: Direction
    ) -> None:
        """Helper executing full lifecycle test for a specific translation direction."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tokenizer = TayTokenizerWrapper(mock_mode=True)

            train_ds = TranslationDataset(
                TRAIN_FILE, tokenizer=tokenizer, direction=direction
            )
            val_ds = TranslationDataset(
                VAL_FILE, tokenizer=tokenizer, direction=direction
            )

            train_cfg = TrainingConfig(
                experiment_name=f"test-weight-update-{direction.value}",
                direction=direction,
                output_dir=tmp_path / "checkpoints",
                batch_size=4,
                num_train_epochs=1,
                mock_mode=True,
                seed=42,
            )
            trainer = TranslationTrainer(training_config=train_cfg, tokenizer=tokenizer)

            # Step 1: Capture initial state_dict of MockSeq2SeqModel
            initial_state_dict = {
                k: v.clone() for k, v in trainer.model.state_dict().items()
            }

            # Step 2: Run 1 epoch training with sample_train.jsonl and sample_val.jsonl
            summary = trainer.train(train_dataset=train_ds, val_dataset=val_ds)
            self.assertEqual(summary["total_epochs"], 1)
            self.assertGreater(summary["total_steps"], 0)
            self.assertIn("best_val_loss", summary)

            # Step 3: Assert at least some weights changed (weight_after != weight_before)
            after_state_dict = trainer.model.state_dict()
            changed_keys = [
                k
                for k in initial_state_dict
                if not torch.equal(initial_state_dict[k], after_state_dict[k])
            ]
            self.assertGreater(
                len(changed_keys),
                0,
                f"No weights changed during training for direction {direction.value}!",
            )
            # Verify core output projection layer updated
            self.assertIn("lm_head.weight", changed_keys)

            # Step 4: Save checkpoint, load into new model, assert logits match 100%
            ckpt_dir = tmp_path / f"ckpt_{direction.value}"
            trainer.save_checkpoint(ckpt_dir, is_best=True)
            self.assertTrue((ckpt_dir / "model.pt").exists())
            self.assertTrue((ckpt_dir / "model_config.json").exists())
            self.assertTrue((ckpt_dir / "training_config.json").exists())
            self.assertTrue((ckpt_dir / "metadata.json").exists())

            # Instantiate a fresh uninitialized MockSeq2SeqModel
            new_model = MockSeq2SeqModel(
                vocab_size=32000,
                embed_dim=64,
                hidden_dim=64,
                pad_token_id=1,
            )

            test_input_ids = torch.tensor([[101, 202, 303, 404, 1]], dtype=torch.long)
            trainer.model.eval()
            new_model.eval()

            with torch.no_grad():
                logits_orig = trainer.model(test_input_ids)["logits"]
                logits_before_load = new_model(test_input_ids)["logits"]

            # Before loading, weights & logits must differ
            self.assertFalse(torch.equal(logits_orig, logits_before_load))

            # Load checkpoint into new model
            loaded_state = torch.load(
                ckpt_dir / "model.pt", map_location="cpu", weights_only=True
            )
            new_model.load_state_dict(loaded_state)

            # Also verify loading via TranslationTrainer.load_checkpoint
            trainer_reloaded = TranslationTrainer(
                training_config=train_cfg, tokenizer=tokenizer
            )
            trainer_reloaded.load_checkpoint(ckpt_dir)
            trainer_reloaded.model.eval()

            with torch.no_grad():
                logits_new = new_model(test_input_ids)["logits"]
                logits_reloaded = trainer_reloaded.model(test_input_ids)["logits"]

            # Assert logits match 100% bit-for-bit
            self.assertTrue(torch.equal(logits_orig, logits_new))
            self.assertTrue(torch.equal(logits_orig, logits_reloaded))

            # Step 5: InferenceAdapter loads trained checkpoint and returns valid translation
            adapter = InferenceAdapter(
                checkpoint_dir=ckpt_dir,
                direction=direction,
            )
            self.assertTrue(adapter.is_ready())
            self.assertTrue(adapter.get_metadata()["has_neural_weights"])

            sample_text = (
                "Tháng giêng mở hội lượn"
                if direction == Direction.VI_TO_TAY
                else "Bươn chiêng khui hội lượn"
            )
            result = adapter.translate(sample_text, direction=direction)

            self.assertIsInstance(result, TranslationResult)
            self.assertEqual(result.direction, direction.value)
            self.assertGreater(len(result.tgt_text), 0)
            self.assertEqual(result.status, "success")
            self.assertGreater(result.latency_ms, 0.0)

    def test_03_weight_update_and_checkpoint_vi_to_tay(self) -> None:
        """Test 3a: Bidirectional weight update and checkpoint roundtrip for vi-tyz."""
        self._run_bidirectional_weight_update_and_checkpoint_test(Direction.VI_TO_TAY)

    def test_04_weight_update_and_checkpoint_tay_to_vi(self) -> None:
        """Test 3b: Bidirectional weight update and checkpoint roundtrip for tyz-vi."""
        self._run_bidirectional_weight_update_and_checkpoint_test(Direction.TAY_TO_VI)

    def test_05_inference_adapter_fail_closed_missing_checkpoint(self) -> None:
        """Test 5: Verify InferenceAdapter raises ModelNotReadyError when mock_mode=False and checkpoint_dir is None."""
        with self.assertRaises(ModelNotReadyError) as ctx:
            TranslationInferenceAdapter(checkpoint_dir=None, mock_mode=False)
        self.assertIn("mock_mode=False requires a valid checkpoint_dir", str(ctx.exception))

    def test_06_inference_adapter_fail_closed_nonexistent_checkpoint(self) -> None:
        """Test 6: Verify InferenceAdapter raises FileNotFoundError when checkpoint path does not exist."""
        with self.assertRaises(FileNotFoundError):
            TranslationInferenceAdapter(
                checkpoint_dir=Path("/non_existent_ckpt_path_99999"), mock_mode=False
            )

    def test_07_inference_adapter_fail_closed_runtime_generation_failure(self) -> None:
        """Test 7: Verify runtime generation error raises RuntimeError and does NOT fall back to MockTranslator."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tok = TayTokenizerWrapper(mock_mode=True)
            train_ds = TranslationDataset(TRAIN_FILE, tokenizer=tok, direction=Direction.VI_TO_TAY)
            train_cfg = TrainingConfig(output_dir=tmp_path, batch_size=4, num_train_epochs=1, mock_mode=True)
            trainer = TranslationTrainer(training_config=train_cfg, tokenizer=tok)
            summary = trainer.train(train_ds)
            ckpt = Path(summary["best_checkpoint_path"])

            adapter = TranslationInferenceAdapter(checkpoint_dir=ckpt, mock_mode=False)
            self.assertTrue(adapter.is_ready())

            # Deliberately make native model fail during generate
            def broken_generate(*args, **kwargs):
                raise RuntimeError("CUDA device assert or synthetic generator failure")

            adapter._native_model.generate = broken_generate

            # With raise_exceptions=True, must raise RuntimeError, never silently fall back
            with self.assertRaises(RuntimeError) as ctx:
                adapter.translate("Tháng giêng mở hội", direction="vi-tyz", raise_exceptions=True)
            self.assertIn("Native model generation failed", str(ctx.exception))

            # With raise_exceptions=False, must return status='error'
            res = adapter.translate("Tháng giêng mở hội", direction="vi-tyz", raise_exceptions=False)
            self.assertEqual(res.status, "error")
            self.assertEqual(res.tgt_text, "")
            self.assertIn("synthetic generator failure", res.error_message)

    def test_08_inference_adapter_all_calling_conventions(self) -> None:
        """Test 8: Verify all 3 supported calling conventions work identically without error."""
        adapter = TranslationInferenceAdapter(mock_mode=True)

        # Convention 1: translate(text, "vi", "ty")
        r1 = adapter.translate("Tháng giêng", "vi", "ty")
        self.assertEqual(r1.direction, "vi-tyz")
        self.assertEqual(r1.status, "mock_mode")

        # Convention 2: translate(text, "vi-tyz") -> positional second argument as direction string
        r2 = adapter.translate("Tháng giêng", "vi-tyz")
        self.assertEqual(r2.direction, "vi-tyz")

        # Convention 3: translate(text, direction="vi-tyz") -> keyword argument
        r3 = adapter.translate("Tháng giêng", direction="vi-tyz")
        self.assertEqual(r3.direction, "vi-tyz")

    def test_09_tokenizer_fail_closed_when_mock_mode_false(self) -> None:
        """Test 9: Verify TayTokenizerWrapper raises RuntimeError when mock_mode=False on missing model."""
        with self.assertRaises(RuntimeError) as ctx:
            TayTokenizerWrapper(model_name_or_path="non_existent_hf_tokenizer_abc_123", mock_mode=False)
        self.assertIn("mock_mode is False", str(ctx.exception))

    def test_10_local_seq2seq_transformer_train_and_generate(self) -> None:
        """Test 10: Verify LocalSeq2SeqTransformer trains with attention, saves checkpoint, and generates tokens."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tok = TayTokenizerWrapper(mock_mode=True)
            train_ds = TranslationDataset(TRAIN_FILE, tokenizer=tok, direction=Direction.VI_TO_TAY)
            val_ds = TranslationDataset(VAL_FILE, tokenizer=tok, direction=Direction.VI_TO_TAY)

            train_cfg = TrainingConfig(
                experiment_name="E0-transformer-smoke",
                direction=Direction.VI_TO_TAY,
                output_dir=tmp_path / "checkpoints",
                batch_size=4,
                gradient_accumulation_steps=2,
                num_train_epochs=1,
                mock_mode=True,
                seed=42,
            )
            model_cfg = ModelConfig(
                experiment="E0-transformer-smoke",
                direction=Direction.VI_TO_TAY,
                mock_mode=True,
                model_type="transformer",
                d_model=64,
                nhead=2,
                num_encoder_layers=1,
                num_decoder_layers=1,
                dim_feedforward=128,
            )

            trainer = TranslationTrainer(
                training_config=train_cfg,
                model_config=model_cfg,
                tokenizer=tok,
            )
            self.assertIsInstance(trainer.model, LocalSeq2SeqTransformer)

            init_weight = trainer.model.lm_head.weight.clone()
            summary = trainer.train(train_dataset=train_ds, val_dataset=val_ds)
            self.assertFalse(torch.equal(init_weight, trainer.model.lm_head.weight))

            ckpt_dir = Path(summary["best_checkpoint_path"])
            self.assertTrue((ckpt_dir / "model.pt").exists())

            # Load into InferenceAdapter with mock_mode=False
            adapter = TranslationInferenceAdapter(
                checkpoint_dir=ckpt_dir,
                direction=Direction.VI_TO_TAY,
                mock_mode=False,
            )
            self.assertTrue(adapter.is_ready())
            self.assertIsInstance(adapter._native_model, LocalSeq2SeqTransformer)

            res = adapter.translate("Bản làng vào xuân.", direction="vi-tyz")
            self.assertEqual(res.status, "success")
            self.assertGreater(len(res.tgt_text), 0)

    def test_11_equal_update_budget_max_steps(self) -> None:
        """Test 11: Verify max_steps terminates training at exactly configured update step."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tok = TayTokenizerWrapper(mock_mode=True)
            train_ds = TranslationDataset(TRAIN_FILE, tokenizer=tok, direction=Direction.VI_TO_TAY)

            train_cfg = TrainingConfig(
                experiment_name="test-max-steps",
                direction=Direction.VI_TO_TAY,
                output_dir=tmp_path / "checkpoints",
                batch_size=2,
                gradient_accumulation_steps=2,
                num_train_epochs=20,  # Many epochs
                max_steps=4,  # Hard limit on updates
                mock_mode=True,
                seed=42,
            )
            trainer = TranslationTrainer(training_config=train_cfg, tokenizer=tok)
            summary = trainer.train(train_dataset=train_ds)

            # Must stop exactly at max_steps == 4
            self.assertEqual(summary["total_steps"], 4)

    def test_12_deterministic_initialization_with_seed(self) -> None:
        """Test 12: Verify seed controls weight initialization deterministically."""
        tok = TayTokenizerWrapper(mock_mode=True)
        cfg1 = TrainingConfig(seed=1337, mock_mode=True)
        cfg2 = TrainingConfig(seed=1337, mock_mode=True)
        cfg3 = TrainingConfig(seed=9999, mock_mode=True)

        m_cfg = ModelConfig(mock_mode=True, model_type="transformer")

        t1 = TranslationTrainer(training_config=cfg1, model_config=m_cfg, tokenizer=tok)
        t2 = TranslationTrainer(training_config=cfg2, model_config=m_cfg, tokenizer=tok)
        t3 = TranslationTrainer(training_config=cfg3, model_config=m_cfg, tokenizer=tok)

        # Same seed -> 100% bit-identical parameters
        for (k1, v1), (k2, v2) in zip(t1.model.state_dict().items(), t2.model.state_dict().items()):
            self.assertEqual(k1, k2)
            self.assertTrue(torch.equal(v1, v2), f"Weight mismatch for {k1} under identical seed 1337!")

        # Different seed -> weights differ
        diff_count = sum(
            not torch.equal(v1, v3)
            for v1, v3 in zip(t1.model.state_dict().values(), t3.model.state_dict().values())
        )
        self.assertGreater(diff_count, 0, "Different seeds unexpectedly produced identical weights!")

    def test_13_equal_update_budget_across_different_dataset_sizes(self) -> None:
        """Test 13: Verify equal update budget (max_steps) across asymmetric dataset sizes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tok = TayTokenizerWrapper(mock_mode=True)

            # Full dataset (20 samples)
            ds_large = TranslationDataset(TRAIN_FILE, tokenizer=tok, direction=Direction.VI_TO_TAY)
            # Smaller subset (8 samples)
            ds_small = TranslationDataset(list(ds_large.records[:8]), tokenizer=tok, direction=Direction.VI_TO_TAY)

            budget_target = 6
            cfg_large = TrainingConfig(
                experiment_name="exp-large",
                output_dir=tmp_path / "large",
                batch_size=2,
                gradient_accumulation_steps=2,
                num_train_epochs=1,  # Epoch count would exhaust early without step loop
                max_steps=budget_target,
                mock_mode=True,
                seed=42,
            )
            cfg_small = TrainingConfig(
                experiment_name="exp-small",
                output_dir=tmp_path / "small",
                batch_size=2,
                gradient_accumulation_steps=2,
                num_train_epochs=1,
                max_steps=budget_target,
                mock_mode=True,
                seed=42,
            )

            t_large = TranslationTrainer(training_config=cfg_large, tokenizer=tok)
            s_large = t_large.train(ds_large)

            t_small = TranslationTrainer(training_config=cfg_small, tokenizer=tok)
            s_small = t_small.train(ds_small)

            self.assertEqual(s_large["total_steps"], budget_target)
            self.assertEqual(s_small["total_steps"], budget_target)

    def test_14_checkpoint_checksum_validation_and_tamper_detection(self) -> None:
        """Test 14: Verify load_checkpoint detects tampered model weights and raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ckpt_dir = Path(tmp_dir) / "ckpt_tamper"
            tok = TayTokenizerWrapper(mock_mode=True)
            cfg = TrainingConfig(output_dir=Path(tmp_dir), mock_mode=True)
            trainer = TranslationTrainer(training_config=cfg, tokenizer=tok)

            trainer.save_checkpoint(ckpt_dir, is_best=True)

            # Tamper model.pt file
            weights_file = ckpt_dir / "model.pt"
            with open(weights_file, "r+b") as f:
                f.seek(10)
                orig_byte = f.read(1)
                f.seek(10)
                f.write(bytes([(orig_byte[0] ^ 0xFF)]))

            # Attempting to load must fail closed with Checksum mismatch
            trainer2 = TranslationTrainer(training_config=cfg, tokenizer=tok)
            with self.assertRaises(ValueError) as ctx:
                trainer2.load_checkpoint(ckpt_dir)
            self.assertIn("Checksum mismatch", str(ctx.exception))

    def test_15_checkpoint_architecture_mismatch_detection(self) -> None:
        """Test 15: Verify load_checkpoint detects architecture mismatch and raises ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ckpt_dir = Path(tmp_dir) / "ckpt_arch_mismatch"
            tok = TayTokenizerWrapper(mock_mode=True)

            # Save checkpoint with MockSeq2SeqModel
            cfg_gru = TrainingConfig(output_dir=Path(tmp_dir), mock_mode=True)
            m_cfg_gru = ModelConfig(mock_mode=True, model_type="gru")
            t_gru = TranslationTrainer(training_config=cfg_gru, model_config=m_cfg_gru, tokenizer=tok)
            t_gru.save_checkpoint(ckpt_dir, is_best=True)

            # Attempt to load into LocalSeq2SeqTransformer
            cfg_trans = TrainingConfig(output_dir=Path(tmp_dir), mock_mode=True)
            m_cfg_trans = ModelConfig(mock_mode=True, model_type="transformer")
            t_trans = TranslationTrainer(training_config=cfg_trans, model_config=m_cfg_trans, tokenizer=tok)

            with self.assertRaises(ValueError) as ctx:
                t_trans.load_checkpoint(ckpt_dir)
            self.assertIn("Model architecture mismatch", str(ctx.exception))

    def test_16_tokenizer_save_load_roundtrip(self) -> None:
        """Test 16: Verify TayTokenizerWrapper save and load roundtrip."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tok_dir = Path(tmp_dir) / "tok_test"
            tok1 = TayTokenizerWrapper(mock_mode=True, vocab_size=32000)
            tok1.encode("Tháng giêng mở hội lượn cùng nhau đi chợ xuân.")
            tok1.freeze()

            tok1.save(tok_dir)
            self.assertTrue((tok_dir / "tokenizer_config.json").exists())
            self.assertTrue((tok_dir / "vocab.json").exists())

            tok2 = TayTokenizerWrapper.load(tok_dir)
            self.assertEqual(len(tok1), len(tok2))
            self.assertTrue(tok2.is_frozen)
            self.assertEqual(tok1._vocab, tok2._vocab)

    def test_17_tokenizer_freeze_train_only_no_leakage(self) -> None:
        """Test 17: Verify frozen tokenizer does NOT mutate vocabulary when encoding unseen text."""
        tok = TayTokenizerWrapper(mock_mode=True)
        tok.freeze()
        initial_vocab_keys = set(tok._vocab.keys())

        # Novel unseen sentence
        unseen_text = "Hệ thống vũ trụ học phi thuyền không gian vi mô."
        enc = tok.encode(unseen_text, add_special_tokens=False)

        # Vocabulary must NOT have mutated
        self.assertEqual(set(tok._vocab.keys()), initial_vocab_keys)
        # All token IDs must remain strictly within valid bounds
        for tid in enc["input_ids"]:
            self.assertLess(tid, len(tok))

    def test_18_inference_adapter_uses_neural_weights_not_mock_lexicon(self) -> None:
        """Test 18: Verify TranslationInferenceAdapter executes loaded neural weights, returning status='success'."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tok = TayTokenizerWrapper(mock_mode=True)
            train_ds = TranslationDataset(TRAIN_FILE, tokenizer=tok, direction=Direction.VI_TO_TAY)
            train_cfg = TrainingConfig(output_dir=tmp_path, batch_size=4, num_train_epochs=1, mock_mode=True)
            trainer = TranslationTrainer(training_config=train_cfg, tokenizer=tok)
            summary = trainer.train(train_ds)
            ckpt = Path(summary["best_checkpoint_path"])

            adapter = TranslationInferenceAdapter(checkpoint_dir=ckpt, mock_mode=False)
            self.assertTrue(adapter.is_ready())
            self.assertTrue(adapter.get_metadata()["has_neural_weights"])

            res = adapter.translate("Tháng giêng mở hội", direction="vi-tyz")
            self.assertEqual(res.status, "success")
            self.assertGreater(len(res.tgt_text), 0)


if __name__ == "__main__":
    unittest.main()
