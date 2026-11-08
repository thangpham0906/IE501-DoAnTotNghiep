"""Unit tests for MockExperimentRunner and 6-configuration mock pipeline."""

import tempfile
import unittest
from pathlib import Path

from src.models.run_mock_experiments import MockExperimentRunner

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
TRAIN_FILE = FIXTURES_DIR / "sample_train.jsonl"
VAL_FILE = FIXTURES_DIR / "sample_val.jsonl"
TEST_FILE = FIXTURES_DIR / "sample_test.jsonl"
MONO_FILE = FIXTURES_DIR / "sample_monolingual.jsonl"


class TestMockExperimentRunner(unittest.TestCase):
    """Test suite verifying end-to-end execution of mock experiments."""

    @classmethod
    def setUpClass(cls) -> None:
        for f in [TRAIN_FILE, VAL_FILE, TEST_FILE, MONO_FILE]:
            if not f.exists():
                raise FileNotFoundError(f"Fixture missing: {f}")

    def test_mock_experiment_runner_full_cycle(self) -> None:
        """Verify that MockExperimentRunner completes full cycle without error.

        Checks:
        1. All 6 variants trained and checkpointed.
        2. Reverse E0 trained and checkpointed.
        3. Fair control N: len(E2) == len(E1-M) == len(A1) == len(A2).
        4. Evaluation scores generated for all variants.
        5. Verification Markdown and JSON reports written.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            doc_path = tmp_path / "MOCK_VERIFICATION.md"

            runner = MockExperimentRunner(
                output_dir=tmp_path / "exp_run",
                train_file=TRAIN_FILE,
                val_file=VAL_FILE,
                test_file=TEST_FILE,
                mono_file=MONO_FILE,
                epochs=1,
                batch_size=4,
                seed=42,
                device="cpu",
                report_doc_path=doc_path,
            )

            results = runner.run_full_cycle()

            # 1. Reverse E0
            self.assertIn("reverse_info", results)
            self.assertTrue(Path(results["reverse_info"]["checkpoint_dir"]).exists())

            # 2. Augmentation & N equality
            aug_report = results["aug_info"]["aug_report"]
            sizes = aug_report["dataset_sizes"]
            n_eff = results["aug_info"]["n_effective"]
            self.assertEqual(sizes["e2_synthetic"], n_eff)
            self.assertEqual(sizes["e1_m_synthetic"], n_eff)
            self.assertEqual(sizes["a1_synthetic"], n_eff)
            self.assertEqual(sizes["a2_synthetic"], n_eff)

            # 3. All 6 variants trained
            training_results = results["training_results"]
            for v in ["E0", "E1", "E2", "E1-M", "A1", "A2"]:
                self.assertIn(v, training_results)
                ckpt_dir = Path(training_results[v]["checkpoint_dir"])
                self.assertTrue((ckpt_dir / "model.pt").exists())
                self.assertTrue((ckpt_dir / "metadata.json").exists())

            # 4. Evaluation scores
            eval_scores = results["evaluation_scores"]
            for v in ["E0", "E1", "E2", "E1-M", "A1", "A2"]:
                self.assertIn(v, eval_scores)
                self.assertIn("bleu", eval_scores[v])
                self.assertIn("chrf", eval_scores[v])
                self.assertIn("test_loss", eval_scores[v])

            # 5. Report generated
            self.assertTrue(doc_path.exists())
            content = doc_path.read_text(encoding="utf-8")
            self.assertIn("BÁO CÁO KIỂM CHỨNG CHU TRÌNH THỰC NGHIỆM TRÊN DỮ LIỆU MÔ PHỎNG", content)
            self.assertIn("KHÔNG PHẢI KẾT QUẢ NGHIÊN CỨU CHÍNH THỨC", content)


if __name__ == "__main__":
    unittest.main()
