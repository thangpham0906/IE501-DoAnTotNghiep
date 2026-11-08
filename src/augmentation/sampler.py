"""Deterministic and reproducible sampling module for data augmentation experiments.

Implements AugmentationSampler:
- create_e2: Applies all 5 QC filters on U -> yields N curated samples.
- create_e1_m: Randomly samples without replacement exactly N samples from raw U (same seed as E2).
- create_a1: Ablation without R1 (length ratio), keeps R2, R3, R4, R5 -> samples N records.
- create_a2: Ablation without R2 (word/n-gram repetition), keeps R1, R3, R4, R5 -> samples N records.
- Tracks seeds, sample IDs, and sha256 checksums for 100% reproducibility (Q03).
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.augmentation.qc_filters import QCFilter, QualityControlFilter
from src.data_pipeline.common import sha256, write_json, write_jsonl


def sample_without_replacement(
    records: list[dict[str, Any]],
    n_samples: int,
    seed: int = 42,
    strict: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Sample exactly n_samples without replacement deterministically.

    Records are canonically sorted before sampling to ensure identical results
    across different systems, architectures, and Python runs.

    Args:
        records: List of candidate records.
        n_samples: Number of samples to extract.
        seed: Random seed for pseudo-random number generator.
        strict: If True, raises ValueError when n_samples > len(records).

    Returns:
        tuple[list[dict], dict]: (sampled_records, manifest_info)
    """
    if n_samples < 0:
        raise ValueError(f"n_samples must be non-negative, got {n_samples}")

    total_candidates = len(records)
    if total_candidates == 0:
        if n_samples > 0 and strict:
            raise ValueError("Không thể lấy mẫu từ danh sách rỗng (strict=True)")
        return [], {
            "seed": seed,
            "requested_n": n_samples,
            "actual_n": 0,
            "total_candidates": 0,
            "sampled_ids": [],
            "insufficient_candidates": n_samples > 0,
            "status": "unavailable" if n_samples > 0 else "completed",
        }

    # Canonical sorting key for absolute reproducibility
    def _sort_key(r: dict[str, Any]) -> str:
        return str(
            r.get("hash")
            or r.get("u_id")
            or r.get("document_id")
            or r.get("tay_text")
            or r.get("vi_text")
            or ""
        )

    sorted_records = sorted(records, key=_sort_key)

    if n_samples > total_candidates:
        if strict:
            raise ValueError(
                f"QC không đủ mẫu: yêu cầu N={n_samples} nhưng chỉ có {total_candidates} mẫu khả dụng. "
                f"Không thể tự ý giảm N (silent change N vi phạm quy chuẩn F06)."
            )
        sampled = list(sorted_records)
    elif n_samples == total_candidates:
        sampled = list(sorted_records)
    else:
        rng = random.Random(seed)
        sampled_indices = sorted(rng.sample(range(total_candidates), n_samples))
        sampled = [sorted_records[i] for i in sampled_indices]

    sampled_ids = [
        str(r.get("u_id") or r.get("hash") or f"idx_{i}") for i, r in enumerate(sampled)
    ]

    manifest_info = {
        "seed": seed,
        "requested_n": n_samples,
        "actual_n": len(sampled),
        "total_candidates": total_candidates,
        "sampled_ids": sampled_ids,
        "insufficient_candidates": n_samples > total_candidates,
        "status": "completed" if len(sampled) == n_samples else "unavailable",
    }
    return sampled, manifest_info


class AugmentationSampler:
    """Manages the creation of E2, E1-M, A1, and A2 augmented sets."""

    def __init__(self, qc_filter: QualityControlFilter | None = None) -> None:
        self.qc_filter = qc_filter or QualityControlFilter()

    def create_e2(
        self,
        u_records: list[dict[str, Any]],
        n_samples: int | None = None,
        seed: int = 42,
        output_path: Path | None = None,
        strict: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Create E2 dataset: apply full QC filtering (R1-R5) and select N samples.

        If n_samples is None, selects all samples that pass full QC.
        """
        kept, rejected, qc_stats = self.qc_filter.filter_records(u_records)

        target_n = len(kept) if n_samples is None else n_samples
        if n_samples is not None and len(kept) < n_samples and strict:
            raise ValueError(
                f"QC không đủ mẫu cho E2: yêu cầu N={n_samples}, nhưng sau bộ lọc QC chỉ có {len(kept)} mẫu đạt chuẩn."
            )

        sampled, sample_info = sample_without_replacement(
            kept, n_samples=target_n, seed=seed, strict=strict
        )

        manifest = {
            "variant": "E2",
            "description": "Full QC filtering (R1 to R5)",
            "seed": seed,
            "target_n": target_n,
            "actual_n": len(sampled),
            "qc_passed_count": len(kept),
            "qc_rejected_count": len(rejected),
            "qc_stats": qc_stats,
            "sampling_manifest": sample_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if output_path is not None:
            output_path = Path(output_path)
            write_jsonl(output_path, sampled)
            manifest["output_file"] = str(output_path)
            manifest["output_sha256"] = sha256(output_path)

        return sampled, manifest

    def create_e1_m(
        self,
        u_records: list[dict[str, Any]],
        n_samples: int,
        seed: int = 42,
        output_path: Path | None = None,
        strict: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Create E1-M dataset: random sample without replacement of N samples from U.

        Uses the same seed as E2 to serve as an uncurated control set of identical size.
        """
        if len(u_records) < n_samples and strict:
            raise ValueError(
                f"Không đủ mẫu cho E1-M: yêu cầu N={n_samples}, nhưng U chỉ có {len(u_records)} mẫu."
            )

        sampled, sample_info = sample_without_replacement(
            u_records, n_samples=n_samples, seed=seed, strict=strict
        )

        manifest = {
            "variant": "E1-M",
            "description": "Random sampling without replacement from raw U (control)",
            "seed": seed,
            "target_n": n_samples,
            "actual_n": len(sampled),
            "sampling_manifest": sample_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if output_path is not None:
            output_path = Path(output_path)
            write_jsonl(output_path, sampled)
            manifest["output_file"] = str(output_path)
            manifest["output_sha256"] = sha256(output_path)

        return sampled, manifest

    def create_a1(
        self,
        u_records: list[dict[str, Any]],
        n_samples: int,
        seed: int = 42,
        output_path: Path | None = None,
        strict: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Create A1 ablation dataset: QC filtering with R1 (length ratio) DISABLED.

        Keeps R2, R3, R4, R5 active. Samples N records using seed.
        """
        kept, rejected, qc_stats = self.qc_filter.filter_records(
            u_records, disabled_rule="R1"
        )

        if len(kept) < n_samples and strict:
            raise ValueError(
                f"QC không đủ mẫu cho A1: yêu cầu N={n_samples}, nhưng A1 (bỏ R1) chỉ có {len(kept)} mẫu đạt chuẩn."
            )

        sampled, sample_info = sample_without_replacement(
            kept, n_samples=n_samples, seed=seed, strict=strict
        )

        manifest = {
            "variant": "A1",
            "description": "Ablation study 1: QC without rule R1 (Length ratio)",
            "disabled_rule": "R1",
            "seed": seed,
            "target_n": n_samples,
            "actual_n": len(sampled),
            "qc_passed_count": len(kept),
            "qc_rejected_count": len(rejected),
            "qc_stats": qc_stats,
            "sampling_manifest": sample_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if output_path is not None:
            output_path = Path(output_path)
            write_jsonl(output_path, sampled)
            manifest["output_file"] = str(output_path)
            manifest["output_sha256"] = sha256(output_path)

        return sampled, manifest

    def create_a2(
        self,
        u_records: list[dict[str, Any]],
        n_samples: int,
        seed: int = 42,
        output_path: Path | None = None,
        strict: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Create A2 ablation dataset: QC filtering with R2 (repetition) DISABLED.

        Keeps R1, R3, R4, R5 active. Samples N records using seed.
        """
        kept, rejected, qc_stats = self.qc_filter.filter_records(
            u_records, disabled_rule="R2"
        )

        if len(kept) < n_samples and strict:
            raise ValueError(
                f"QC không đủ mẫu cho A2: yêu cầu N={n_samples}, nhưng A2 (bỏ R2) chỉ có {len(kept)} mẫu đạt chuẩn."
            )

        sampled, sample_info = sample_without_replacement(
            kept, n_samples=n_samples, seed=seed, strict=strict
        )

        manifest = {
            "variant": "A2",
            "description": "Ablation study 2: QC without rule R2 (Repetition)",
            "disabled_rule": "R2",
            "seed": seed,
            "target_n": n_samples,
            "actual_n": len(sampled),
            "qc_passed_count": len(kept),
            "qc_rejected_count": len(rejected),
            "qc_stats": qc_stats,
            "sampling_manifest": sample_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if output_path is not None:
            output_path = Path(output_path)
            write_jsonl(output_path, sampled)
            manifest["output_file"] = str(output_path)
            manifest["output_sha256"] = sha256(output_path)

        return sampled, manifest

