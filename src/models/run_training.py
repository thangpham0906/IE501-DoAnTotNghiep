"""CLI Runner for training Vietnamese-Tay translation models (E0, E1, E2, E1-M, A1, A2).

Integrates host hardware recommendations from configs/hardware_profile.json
and coordinates TranslationDataset, TayTokenizerWrapper, and TranslationTrainer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import torch

from src.models.config import Direction, ModelConfig, TrainingConfig
from src.models.dataset import TranslationDataset
from src.models.tokenizer import TayTokenizerWrapper
from src.models.trainer import TranslationTrainer


def compute_file_sha256(path: Path | str) -> str | None:
    p = Path(path)
    if not p.exists() or p.is_dir():
        return None
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_git_info() -> dict[str, str | None]:
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        return {"git_branch": branch, "git_commit": commit}
    except Exception:
        return {"git_branch": None, "git_commit": None}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run training for Vietnamese-Tay translation experiment configurations."
    )
    parser.add_argument(
        "--experiment",
        "-e",
        type=str,
        default="E0",
        choices=["E0", "E1", "E2", "E1-M", "A1", "A2"],
        help="Experiment variant to train (default: E0).",
    )
    parser.add_argument(
        "--direction",
        "-d",
        type=str,
        default="vi-tyz",
        choices=["vi-tyz", "tyz-vi", "vi->ty", "ty->vi"],
        help="Translation direction (default: vi-tyz).",
    )
    parser.add_argument(
        "--train-file",
        type=str,
        default="src/tests/fixtures/sample_train.jsonl",
        help="Path to training JSONL file.",
    )
    parser.add_argument(
        "--val-file",
        type=str,
        default="src/tests/fixtures/sample_val.jsonl",
        help="Path to validation JSONL file.",
    )
    parser.add_argument(
        "--test-file",
        type=str,
        default="src/tests/fixtures/sample_test.jsonl",
        help="Path to test JSONL file for final evaluation.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs (default: 3).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Batch size (default: auto-detected from hardware profile or 8).",
    )
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=None,
        help="Gradient accumulation steps (default: auto-detected from hardware profile or 2).",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Device to use ('cpu' or 'cuda'; default: auto-detected from hardware profile).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/checkpoints",
        help="Directory to save checkpoints and training summaries.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=-1,
        help="Maximum optimization steps for equal budget across variants (default: -1 for epoch-based).",
    )
    parser.add_argument(
        "--cpu-threads",
        type=int,
        default=4,
        help="Number of CPU threads to allocate for PyTorch operations (default: 4).",
    )
    parser.add_argument(
        "--model-type",
        type=str,
        default="transformer",
        choices=["transformer", "gru", "nllb"],
        help="Model architecture for local/smoke training (default: transformer).",
    )
    parser.add_argument(
        "--mock-mode",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use mock/local model mode (default: True, pass --no-mock-mode or --real for production training).",
    )
    parser.add_argument(
        "--real",
        dest="mock_mode",
        action="store_false",
        help="Alias to disable mock mode and run real training.",
    )
    return parser.parse_args()


def load_hardware_strategy() -> dict[str, any]:
    """Load hardware recommendations if available."""
    hw_file = Path("configs/hardware_profile.json")
    if hw_file.exists():
        try:
            with open(hw_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("execution_strategy", {})
        except Exception:
            pass
    return {"device": "cpu", "batch_size": 8, "gradient_accumulation_steps": 2}


def run_training_pipeline(args: argparse.Namespace) -> dict[str, any]:
    """Execute training workflow based on provided CLI arguments."""
    hw_strategy = load_hardware_strategy()
    device = args.device or hw_strategy.get("device", "cpu")
    batch_size = args.batch_size or hw_strategy.get("batch_size", 8)
    gradient_accumulation_steps = (
        args.gradient_accumulation_steps
        if getattr(args, "gradient_accumulation_steps", None) is not None
        else hw_strategy.get("gradient_accumulation_steps", 2)
    )
    direction = Direction.normalize(args.direction)

    print("=" * 65)
    print(f" KHỞI CHẠY HUẤN LUYỆN: {args.experiment} ({direction.value})")
    print("=" * 65)
    print(f"• Thiết bị sử dụng : {device.upper()}")
    print(f"• Kích thước Batch : {batch_size}")
    print(f"• Tích lũy Gradient: {gradient_accumulation_steps}")
    print(f"• Số Epochs        : {args.epochs}")
    print(f"• File Train       : {args.train_file}")
    print(f"• File Validation  : {args.val_file}")
    print(f"• File Test        : {getattr(args, 'test_file', None)}")
    print(f"• Chế độ Mock      : {args.mock_mode}")
    print("=" * 65)

    # 1. Setup Tokenizer and Datasets
    tokenizer = TayTokenizerWrapper(mock_mode=args.mock_mode)
    train_path = Path(args.train_file)
    if not train_path.exists():
        print(f"Lỗi: Không tìm thấy file dữ liệu huấn luyện tại: {train_path}", file=sys.stderr)
        sys.exit(1)

    train_ds = TranslationDataset(
        data=train_path,
        tokenizer=tokenizer,
        direction=direction,
        max_source_length=128,
        max_target_length=128,
    )
    print(f"✔ Đã nạp {len(train_ds)} mẫu huấn luyện.")

    val_ds = None
    if args.val_file:
        val_path = Path(args.val_file)
        if val_path.exists():
            val_ds = TranslationDataset(
                data=val_path,
                tokenizer=tokenizer,
                direction=direction,
                max_source_length=128,
                max_target_length=128,
            )
            print(f"✔ Đã nạp {len(val_ds)} mẫu validation.")

    test_ds = None
    if getattr(args, "test_file", None):
        test_path = Path(args.test_file)
        if test_path.exists():
            test_ds = TranslationDataset(
                data=test_path,
                tokenizer=tokenizer,
                direction=direction,
                max_source_length=128,
                max_target_length=128,
            )
            print(f"✔ Đã nạp {len(test_ds)} mẫu kiểm thử (test).")

    # 2. Configure Training Hyperparameters
    training_cfg = TrainingConfig(
        experiment_name=args.experiment,
        direction=direction,
        output_dir=Path(args.output_dir),
        batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        num_train_epochs=args.epochs,
        max_steps=getattr(args, "max_steps", -1),
        cpu_threads=getattr(args, "cpu_threads", 4),
        device=device,
        mock_mode=args.mock_mode,
        seed=42,
    )

    model_cfg = ModelConfig(
        experiment=args.experiment,
        direction=direction,
        mock_mode=args.mock_mode,
        model_type=getattr(args, "model_type", "transformer"),
    )

    # 3. Instantiate Trainer and Execute Loop
    trainer = TranslationTrainer(
        training_config=training_cfg,
        model_config=model_cfg,
        tokenizer=tokenizer,
    )

    print("\nĐang tiến hành tối ưu hóa mô hình...")
    summary = trainer.train(train_dataset=train_ds, val_dataset=val_ds)

    # 4. Evaluate on Test Dataset if provided
    test_metrics = None
    if test_ds is not None:
        print("\nĐang đánh giá mô hình trên tập kiểm thử (test)...")
        if summary.get("best_checkpoint_path"):
            trainer.load_checkpoint(summary["best_checkpoint_path"])
        test_metrics = trainer.evaluate(test_ds)
        summary["test_metrics"] = test_metrics

        summary_path = training_cfg.output_dir / f"training_summary_{training_cfg.experiment_name}.json"
        if summary_path.exists():
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)

    # 5. Generate and Save Run Provenance Manifest
    git_info = get_git_info()
    best_ckpt = summary.get("best_checkpoint_path")
    best_ckpt_sha256 = compute_file_sha256(Path(best_ckpt) / "model.pt") if best_ckpt else None

    manifest = {
        "manifest_version": "1.0",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_id": f"run-{args.experiment}-{direction.value}-{int(time.time())}",
        "experiment": args.experiment,
        "direction": direction.value,
        "run_type": "smoke_test_local" if args.mock_mode else "production_research",
        "command_line": sys.argv,
        "git": git_info,
        "environment": {
            "python_version": platform.python_version(),
            "pytorch_version": torch.__version__,
            "platform": platform.platform(),
            "cpu_threads_allocated": getattr(args, "cpu_threads", 4),
            "device": device,
        },
        "datasets": {
            "train": {
                "path": str(train_path),
                "samples": len(train_ds),
                "sha256": compute_file_sha256(train_path),
            },
            "validation": {
                "path": str(args.val_file) if args.val_file else None,
                "samples": len(val_ds) if val_ds else 0,
                "sha256": compute_file_sha256(args.val_file) if args.val_file else None,
            },
            "test": {
                "path": str(args.test_file) if getattr(args, "test_file", None) else None,
                "samples": len(test_ds) if test_ds else 0,
                "sha256": compute_file_sha256(args.test_file) if getattr(args, "test_file", None) else None,
            },
        },
        "hyperparameters": {
            "epochs": args.epochs,
            "max_steps": getattr(args, "max_steps", -1),
            "batch_size": batch_size,
            "gradient_accumulation_steps": gradient_accumulation_steps,
            "effective_batch_size": batch_size * gradient_accumulation_steps,
            "learning_rate": training_cfg.learning_rate,
            "weight_decay": training_cfg.weight_decay,
            "seed": training_cfg.seed,
            "model_type": getattr(args, "model_type", "transformer"),
        },
        "results": {
            "total_steps": summary["total_steps"],
            "total_time_sec": summary["total_time_sec"],
            "best_val_loss": summary["best_val_loss"],
            "best_checkpoint_path": best_ckpt,
            "best_checkpoint_sha256": best_ckpt_sha256,
            "test_metrics": test_metrics,
        },
    }

    manifest_file = training_cfg.output_dir / f"run_manifest_{args.experiment}_{direction.value}.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"✔ Đã ghi hồ sơ nguồn gốc thực nghiệm (Provenance Manifest): {manifest_file}")

    print("\n" + "=" * 65)
    print(" HUẤN LUYỆN HOÀN TẤT THÀNH CÔNG!")
    print("=" * 65)
    print(f"• Tổng số bước (Steps) : {summary['total_steps']}")
    print(f"• Thời gian chạy       : {summary['total_time_sec']}s")
    print(f"• Validation Loss tốt nhất : {summary['best_val_loss']}")
    if test_metrics is not None:
        print(f"• Test Loss            : {test_metrics['val_loss']}")
        print(f"• Test Perplexity      : {test_metrics['val_perplexity']}")
    if summary.get("best_checkpoint_path"):
        print(f"• Checkpoint đã lưu tại: {summary['best_checkpoint_path']}")
    print("=" * 65)

    return summary


if __name__ == "__main__":
    cli_args = parse_args()
    run_training_pipeline(cli_args)
