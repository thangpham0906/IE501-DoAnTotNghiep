"""End-to-End Data Augmentation Pipeline.

Coordinates the complete workflow:
1. (Optional) Reverse inference via BackTranslator to synthesize bilingual dataset U.
2. Anti-leakage isolation against validation and test sets (Q02).
3. QC filtering across all 5 rules (R1 to R5).
4. Deterministic sampling to produce:
   - E1:   E0 train + full uncurated dataset U
   - E2:   E0 train + N samples passing all 5 QC filters
   - E1-M: E0 train + N random samples from U (identical size control)
   - A1:   E0 train + N samples with QC rule R1 (length ratio) disabled
   - A2:   E0 train + N samples with QC rule R2 (repetition) disabled
5. Generates comprehensive audit manifest tracking SHA-256 hashes, seeds, and metadata.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.augmentation.back_translation import BackTranslator
from src.augmentation.qc_filters import QCFilter, QCFilterConfig, QualityControlFilter
from src.augmentation.sampler import AugmentationSampler
from src.data_pipeline.common import normalize_text, read_jsonl, sha256, write_json, write_jsonl
from src.data_pipeline.split_dataset import _text_signatures, is_near_duplicate
from src.models.config import Direction


def validate_dataset_admissibility(
    records: list[dict[str, Any]],
    dataset_name: str = "dataset",
    is_synthetic: bool = False,
    val_records: list[dict[str, Any]] | None = None,
    test_records: list[dict[str, Any]] | None = None,
    near_dup_threshold: float = 0.85,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Kiểm tra điều kiện hợp lệ định dạng (Format Admissibility) và chống rò rỉ dữ liệu (Q02).

    Không dùng bộ lọc nghiên cứu QC thay thế cho việc xác thực định dạng cơ bản:
    - Kiểm tra cấu trúc bản ghi, chuỗi không rỗng ở cả hai phía (Tày và Việt).
    - Loại bỏ câu quá ngắn (< 2 từ) hoặc trùng hoàn toàn hai phía (identical src/tgt).
    - Khử trùng lặp nội bộ (Deduplication) dựa trên mã băm cặp câu chuẩn hóa.
    - Chặn triệt để rò rỉ trùng chính xác, trùng tài liệu và gần trùng vào tập validation và test.
    """
    eval_records = (val_records or []) + (test_records or [])
    eval_texts, eval_sigs = BackTranslator._extract_eval_sentence_data(eval_records)

    eval_docs: set[str] = set()
    for r in eval_records:
        for d in (r.get("source_documents") or []):
            if d:
                eval_docs.add(str(d).strip().casefold())
        doc_id = r.get("document_id") or r.get("source_doc_id")
        if doc_id:
            eval_docs.add(str(doc_id).strip().casefold())

    admissible_records: list[dict[str, Any]] = []
    seen_pair_hashes: set[str] = set()
    rejected_format: list[dict[str, Any]] = []
    rejected_leakage: list[dict[str, Any]] = []
    rejected_duplicate: int = 0

    for idx, r in enumerate(records):
        if not isinstance(r, dict):
            rejected_format.append({"index": idx, "reason": "not_a_dict"})
            continue

        tay = normalize_text(r.get("tay") or r.get("tay_text") or "")
        vi = normalize_text(r.get("vi") or r.get("vi_text") or "")

        if not tay or not vi:
            rejected_format.append({"index": idx, "reason": "empty_text_side"})
            continue

        if len(tay.split()) < 2 or len(vi.split()) < 2:
            rejected_format.append({"index": idx, "reason": "too_short_tokens"})
            continue

        if tay.casefold() == vi.casefold():
            rejected_format.append({"index": idx, "reason": "identical_source_target"})
            continue

        pair_hash = hashlib.sha256(
            json.dumps([tay.casefold(), vi.casefold()], ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if pair_hash in seen_pair_hashes:
            rejected_duplicate += 1
            continue
        seen_pair_hashes.add(pair_hash)

        # Anti-leakage checks (Q02)
        leaked_side = None
        leak_type = None
        matched_text = ""

        # Check Tay
        is_leaked_tay, ltype_tay, match_tay = BackTranslator._check_leakage(
            tay, eval_texts, eval_sigs, near_dup_threshold=near_dup_threshold
        )
        if is_leaked_tay:
            leaked_side = "tay"
            leak_type = ltype_tay
            matched_text = match_tay
        else:
            # Check Vi
            is_leaked_vi, ltype_vi, match_vi = BackTranslator._check_leakage(
                vi, eval_texts, eval_sigs, near_dup_threshold=near_dup_threshold
            )
            if is_leaked_vi:
                leaked_side = "vi"
                leak_type = ltype_vi
                matched_text = match_vi

        # Check Doc ID
        if not leaked_side and eval_docs:
            row_docs = []
            for d in (r.get("source_documents") or []):
                if d:
                    row_docs.append(str(d).strip().casefold())
            r_doc_id = r.get("document_id") or r.get("source_doc_id")
            if r_doc_id:
                row_docs.append(str(r_doc_id).strip().casefold())
            for d in row_docs:
                if d in eval_docs:
                    leaked_side = "document_id"
                    leak_type = "document_overlap"
                    matched_text = d
                    break

        if leaked_side:
            leak_info = {
                "index": idx,
                "leaked_side": leaked_side,
                "leak_type": leak_type,
                "matched_text": matched_text,
            }
            if not is_synthetic:
                raise ValueError(
                    f"Phát hiện rò rỉ dữ liệu nghiêm trọng từ {dataset_name} vào tập đánh giá (Q02): {leak_info}"
                )
            rejected_leakage.append(leak_info)
            continue

        item = copy.deepcopy(r)
        item["tay"] = tay
        item["vi"] = vi
        item["tay_text"] = tay
        item["vi_text"] = vi
        item["hash"] = pair_hash
        if is_synthetic:
            item["synthetic"] = True
            if not item.get("u_id"):
                item["u_id"] = f"u_{len(admissible_records):06d}_{pair_hash[:8]}"
        admissible_records.append(item)

    report = {
        "dataset_name": dataset_name,
        "is_synthetic": is_synthetic,
        "input_count": len(records),
        "admissible_count": len(admissible_records),
        "rejected_format_count": len(rejected_format),
        "rejected_duplicate_count": rejected_duplicate,
        "rejected_leakage_count": len(rejected_leakage),
        "rejected_leakage_samples": rejected_leakage[:5],
    }
    return admissible_records, report


class AugmentationPipeline:
    """Orchestrates back-translation, QC evaluation, and experimental subset construction."""

    def __init__(
        self,
        back_translator: BackTranslator | None = None,
        qc_filter: QualityControlFilter | None = None,
        sampler: AugmentationSampler | None = None,
        mock_mode: bool = False,
    ) -> None:
        self.qc_filter = qc_filter or QualityControlFilter()
        self.sampler = sampler or AugmentationSampler(qc_filter=self.qc_filter)
        self.back_translator = back_translator or BackTranslator(mock_mode=mock_mode)

    @staticmethod
    def _load_records(source: list[dict[str, Any]] | Path | str | None) -> list[dict[str, Any]]:
        """Safely load records from path or list."""
        if source is None:
            return []
        if isinstance(source, (str, Path)):
            p = Path(source)
            if not p.is_file():
                return []
            return read_jsonl(p)
        return list(source)

    def run(
        self,
        output_dir: Path | str,
        train_e0_source: list[dict[str, Any]] | Path | str | None = None,
        u_dataset_source: list[dict[str, Any]] | Path | str | None = None,
        monolingual_source: list[dict[str, Any]] | Path | str | None = None,
        val_source: list[dict[str, Any]] | Path | str | None = None,
        test_source: list[dict[str, Any]] | Path | str | None = None,
        direction: Direction | str = Direction.VI_TO_TAY,
        n_samples: int | None = None,
        seed: int = 42,
        save_standalone_subsets: bool = True,
    ) -> dict[str, Any]:
        """Execute the end-to-end augmentation pipeline.

        Args:
            output_dir: Directory where datasets and manifest will be written.
            train_e0_source: Clean baseline E0 bilingual records (path or list).
            u_dataset_source: Pre-existing synthetic dataset U (path or list).
            monolingual_source: Target monolingual texts to generate U if U is not provided.
            val_source: Validation records for anti-leakage checking.
            test_source: Test records for anti-leakage checking.
            direction: Translation direction of target model to be augmented.
            n_samples: Exact sample size N for E2, E1-M, A1, A2. If None, uses len(E2).
            seed: Master random seed for reproducible sampling.
            save_standalone_subsets: Whether to also save synthetic-only files.

        Returns:
            dict[str, Any]: Execution report and manifest.
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        target_dir = Direction.normalize(direction)
        # Reverse direction for back-translation
        gen_dir = (
            Direction.TAY_TO_VI
            if target_dir == Direction.VI_TO_TAY
            else Direction.VI_TO_TAY
        )

        val_records = self._load_records(val_source)
        test_records = self._load_records(test_source)

        train_e0_records, e0_admissibility = validate_dataset_admissibility(
            self._load_records(train_e0_source),
            dataset_name="train_e0",
            is_synthetic=False,
            val_records=val_records,
            test_records=test_records,
        )

        # 1. Obtain Dataset U (either pre-existing or generated from monolingual)
        u_records: list[dict[str, Any]]
        bt_manifest: dict[str, Any] = {}
        u_admissibility: dict[str, Any] = {}

        if u_dataset_source is not None:
            raw_u = self._load_records(u_dataset_source)
            u_records, u_admissibility = validate_dataset_admissibility(
                raw_u,
                dataset_name="u_dataset_loaded",
                is_synthetic=True,
                val_records=val_records,
                test_records=test_records,
            )
        elif monolingual_source is not None:
            mono_records = self._load_records(monolingual_source)
            u_path = out_dir / "u_synthetic.jsonl"
            bt_man_path = out_dir / "back_translation_manifest.json"
            gen_u, bt_manifest = self.back_translator.generate_u_dataset(
                monolingual_records=mono_records,
                generation_direction=gen_dir,
                target_model_direction=target_dir,
                val_records=val_records,
                test_records=test_records,
                output_path=None,
                manifest_path=bt_man_path,
            )
            u_records, u_admissibility = validate_dataset_admissibility(
                gen_u,
                dataset_name="u_dataset_generated",
                is_synthetic=True,
                val_records=val_records,
                test_records=test_records,
            )
        else:
            raise ValueError(
                "Either 'u_dataset_source' or 'monolingual_source' must be provided"
            )

        # Ghi tập U hợp lệ đã qua kiểm định định dạng & rò rỉ ra tệp
        u_path = out_dir / "u_synthetic.jsonl"
        write_jsonl(u_path, u_records)

        # 2. Generate E2 (full QC filtering)
        e2_path = out_dir / "e2_synthetic.jsonl" if save_standalone_subsets else None
        e2_synth, e2_manifest = self.sampler.create_e2(
            u_records=u_records,
            n_samples=n_samples,
            seed=seed,
            output_path=e2_path,
            strict=True,
        )

        # Phân loại minh bạch thiết kế lấy mẫu: không được tự tiện cắt N khác số đạt full QC mà tự xưng là chuẩn
        qc_passed_count = e2_manifest.get("qc_passed_count", len(e2_synth))
        if n_samples is None:
            n_effective = len(e2_synth)
            sampling_design = "full_qc_standard"
        else:
            n_effective = n_samples
            if n_samples == qc_passed_count:
                sampling_design = "full_qc_standard"
            elif n_samples < qc_passed_count:
                sampling_design = f"custom_subsampled_from_{qc_passed_count}_qc_passed"
            else:
                sampling_design = "unavailable"

        if n_effective == 0:
            raise ValueError(
                "Bộ lọc QC không chấp thuận mẫu nào từ tập U (N=0); không thể xây dựng các biến thể thực nghiệm E2, E1-M, A1, A2."
            )
        if len(e2_synth) < n_effective:
            raise ValueError(
                f"QC không đủ mẫu cho E2: yêu cầu N={n_effective}, nhưng sau QC chỉ có {len(e2_synth)} mẫu (không thể silently change N)."
            )

        # 3. Generate E1-M (random sample without replacement from U of size N)
        e1_m_path = out_dir / "e1_m_synthetic.jsonl" if save_standalone_subsets else None
        e1_m_synth, e1_m_manifest = self.sampler.create_e1_m(
            u_records=u_records,
            n_samples=n_effective,
            seed=seed,
            output_path=e1_m_path,
            strict=True,
        )

        # 4. Generate A1 (ablation without R1: length ratio)
        a1_path = out_dir / "a1_synthetic.jsonl" if save_standalone_subsets else None
        a1_synth, a1_manifest = self.sampler.create_a1(
            u_records=u_records,
            n_samples=n_effective,
            seed=seed,
            output_path=a1_path,
            strict=True,
        )

        # 5. Generate A2 (ablation without R2: repetition)
        a2_path = out_dir / "a2_synthetic.jsonl" if save_standalone_subsets else None
        a2_synth, a2_manifest = self.sampler.create_a2(
            u_records=u_records,
            n_samples=n_effective,
            seed=seed,
            output_path=a2_path,
            strict=True,
        )

        # Kiểm định tính bất biến khoa học: E2, E1-M, A1, A2 phải có cùng chính xác N mẫu
        if not (len(e2_synth) == len(e1_m_synth) == len(a1_synth) == len(a2_synth) == n_effective):
            raise ValueError(
                f"Lỗi bất biến số lượng mẫu thực nghiệm: kích thước không đồng nhất "
                f"(E2={len(e2_synth)}, E1-M={len(e1_m_synth)}, A1={len(a1_synth)}, A2={len(a2_synth)}, N={n_effective})"
            )

        # 6. Build Combined Experimental Datasets (E0 + synthetic)
        created_files: dict[str, str] = {}
        combined_counts: dict[str, int] = {}
        combined_id_mappings: dict[str, Any] = {}

        def _save_combined(name: str, synth_subset: list[dict[str, Any]]) -> None:
            filepath = out_dir / f"train_{name}.jsonl"
            combined = []
            seen_ids: set[str] = set()
            source_id_mapping: dict[str, str] = {}
            id_collisions: list[str] = []

            for idx, r in enumerate(train_e0_records):
                item = dict(r)
                item["synthetic"] = False
                item["provenance"] = "train_e0_gold"
                orig_id = str(item.get("id") or item.get("hash") or item.get("document_id") or f"e0_row_{idx:05d}")
                canonical_id = f"e0_{idx:05d}_{orig_id}"
                if canonical_id in seen_ids:
                    id_collisions.append(canonical_id)
                seen_ids.add(canonical_id)
                item["id"] = canonical_id
                source_id_mapping[canonical_id] = orig_id
                combined.append(item)

            for idx, r in enumerate(synth_subset):
                item = dict(r)
                item["synthetic"] = True
                item["provenance"] = f"synthetic_{name}"
                orig_id = str(item.get("u_id") or item.get("hash") or item.get("id") or f"synth_row_{idx:05d}")
                canonical_id = f"synth_{name}_{idx:05d}_{orig_id}"
                if canonical_id in seen_ids:
                    id_collisions.append(canonical_id)
                seen_ids.add(canonical_id)
                item["id"] = canonical_id
                source_id_mapping[canonical_id] = orig_id
                combined.append(item)

            if id_collisions:
                raise ValueError(f"Phát hiện xung đột ID trong tập kết hợp {name}: {id_collisions[:5]}")

            write_jsonl(filepath, combined)
            created_files[f"train_{name}"] = str(filepath)
            combined_counts[f"train_{name}"] = len(combined)
            combined_id_mappings[f"train_{name}"] = {
                "total_records": len(combined),
                "e0_records": len(train_e0_records),
                "synth_records": len(synth_subset),
                "sample_mapping": dict(list(source_id_mapping.items())[:10]),
            }

        # Save all 5 combined training sets
        _save_combined("e1", u_records)       # E1: Train gốc + toàn bộ U
        _save_combined("e2", e2_synth)        # E2: Train gốc + N mẫu qua đầy đủ QC
        _save_combined("e1_m", e1_m_synth)    # E1-M: Train gốc + N mẫu ngẫu nhiên từ U
        _save_combined("a1", a1_synth)        # A1: Train gốc + N mẫu không có R1
        _save_combined("a2", a2_synth)        # A2: Train gốc + N mẫu không có R2

        # 7. Generate Master Augmentation Manifest
        master_manifest: dict[str, Any] = {
            "pipeline": "AugmentationPipeline",
            "target_direction": target_dir.value,
            "generation_direction": gen_dir.value,
            "master_seed": seed,
            "n_effective": n_effective,
            "sampling_design": sampling_design,
            "train_e0_baseline_count": len(train_e0_records),
            "u_total_records": len(u_records),
            "admissibility": {
                "train_e0": e0_admissibility,
                "u_dataset": u_admissibility,
            },
            "dataset_sizes": {
                "train_e0": len(train_e0_records),
                **combined_counts,
                "u_synthetic": len(u_records),
                "e2_synthetic": len(e2_synth),
                "e1_m_synthetic": len(e1_m_synth),
                "a1_synthetic": len(a1_synth),
                "a2_synthetic": len(a2_synth),
            },
            "file_checksums": {
                name: sha256(Path(path)) for name, path in created_files.items()
            },
            "subsets": {
                "e2": e2_manifest,
                "e1_m": e1_m_manifest,
                "a1": a1_manifest,
                "a2": a2_manifest,
            },
            "back_translation": bt_manifest,
            "combined_id_mappings": combined_id_mappings,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        manifest_path = out_dir / "augmentation_manifest.json"
        write_json(manifest_path, master_manifest)
        master_manifest["manifest_path"] = str(manifest_path)

        return master_manifest


def run_augmentation_pipeline(
    output_dir: Path | str,
    train_e0_source: list[dict[str, Any]] | Path | str | None = None,
    u_dataset_source: list[dict[str, Any]] | Path | str | None = None,
    monolingual_source: list[dict[str, Any]] | Path | str | None = None,
    val_source: list[dict[str, Any]] | Path | str | None = None,
    test_source: list[dict[str, Any]] | Path | str | None = None,
    direction: Direction | str = Direction.VI_TO_TAY,
    n_samples: int | None = None,
    seed: int = 42,
    mock_mode: bool = False,
) -> dict[str, Any]:
    """Convenience function to run the full augmentation pipeline."""
    pipeline = AugmentationPipeline(mock_mode=mock_mode)
    return pipeline.run(
        output_dir=output_dir,
        train_e0_source=train_e0_source,
        u_dataset_source=u_dataset_source,
        monolingual_source=monolingual_source,
        val_source=val_source,
        test_source=test_source,
        direction=direction,
        n_samples=n_samples,
        seed=seed,
    )
