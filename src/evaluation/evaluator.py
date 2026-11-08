"""Comprehensive translation evaluation engine for Vietnamese-Tay MT pipeline.

Evaluates test datasets across bidirectional directions (vi->tyz, tyz-vi)
for core experimental variants:
- E0: Baseline (clean gold parallel data)
- E1: Baseline + raw synthetic U (unfiltered back-translation)
- E2: Baseline + N QC-filtered synthetic samples (full 5-rule filter)
- E1-M: Baseline + N random synthetic samples (fair control vs E2)
- A1: Ablation 1 (R1 length ratio rule disabled)
- A2: Ablation 2 (R2 repetition rule disabled)

Generates comparison tables (BLEU, chrF, chrF++, Error Rates, Latency) and manifests,
strictly distinguishing between Mock simulations and Real trained model checkpoints.
Preserves sample IDs, document provenance, and full SacreBLEU signatures.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from src.evaluation.error_analysis import CorpusErrorReport, ErrorAnalyzer
from src.evaluation.metrics import (
    BLEUResult,
    CHRFResult,
    compute_bleu,
    compute_chrf,
    compute_chrf_plus_plus,
)
from src.models.config import Direction


@dataclass
class ModelEvaluationScore:
    """Consolidated evaluation metrics for a specific model variant and direction."""

    model_name: str
    direction: str
    bleu: BLEUResult
    chrf: CHRFResult
    chrf_pp: CHRFResult
    error_report: CorpusErrorReport
    sample_count: int
    mean_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    throughput_sps: float  # Sentences per second
    is_mock: bool = False
    evaluation_tier: str = "smoke_technical"  # 'mock_simulation', 'smoke_fixture', or 'research_corpus'
    checkpoint_metadata: dict[str, Any] = field(default_factory=dict)
    signature_bleu: str = ""
    signature_chrf: str = ""
    signature_chrf_pp: str = ""

    def __post_init__(self) -> None:
        if not self.signature_bleu and self.bleu:
            self.signature_bleu = self.bleu.signature
        if not self.signature_chrf and self.chrf:
            self.signature_chrf = self.chrf.signature
        if not self.signature_chrf_pp and self.chrf_pp:
            self.signature_chrf_pp = self.chrf_pp.signature

    def to_dict(self) -> dict[str, Any]:
        """Convert score container to dictionary."""
        return {
            "model_name": self.model_name,
            "direction": self.direction,
            "is_mock": self.is_mock,
            "evaluation_tier": self.evaluation_tier,
            "is_research_verified": (self.evaluation_tier == "research_corpus"),
            "checkpoint_metadata": self.checkpoint_metadata,
            "sample_count": self.sample_count,
            "bleu": self.bleu.to_dict(),
            "chrf": self.chrf.to_dict(),
            "chrf_plus_plus": self.chrf_pp.to_dict(),
            "signatures": {
                "bleu": self.signature_bleu,
                "chrf": self.signature_chrf,
                "chrf_plus_plus": self.signature_chrf_pp,
            },
            "error_rate": self.error_report.error_rate,
            "error_counts_by_category": self.error_report.counts_by_category,
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "median_latency_ms": round(self.median_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "throughput_sps": round(self.throughput_sps, 2),
        }


@dataclass
class ComparativeEvaluationReport:
    """Holistic comparative report across multiple models and directions."""

    scores: list[ModelEvaluationScore] = field(default_factory=list)
    dataset_name: str = "test"
    dataset_size: int = 0
    created_at: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert entire comparative report to dictionary."""
        return {
            "created_at": self.created_at,
            "dataset_name": self.dataset_name,
            "dataset_size": self.dataset_size,
            "metadata": self.metadata,
            "results": [s.to_dict() for s in self.scores],
        }

    def generate_markdown_table(self) -> str:
        """Produce a formatted Markdown comparison table for research reports."""
        has_technical_eval = any(
            s.is_mock or s.evaluation_tier in ("mock_simulation", "smoke_fixture")
            for s in self.scores
        )
        disclaimer = ""
        if has_technical_eval:
            disclaimer = (
                "> **CẢNH BÁO KIỂM TOÁN (AUDIT DISCLAIMER):** Kết quả trong bảng này thuộc tầng kiểm thử kỹ thuật "
                "(Mock simulation hoặc Neural Smoke trên fixture). Tuyệt đối KHÔNG phải kết quả nghiên cứu khoa học "
                "trên ngữ liệu tiếng Tày thật.\n\n"
            )

        lines = [
            f"## Bảng Tổng hợp Kết quả Đánh giá Thực nghiệm ({self.dataset_name.upper()})",
            f"*Thời điểm tạo: {self.created_at} | Số câu đánh giá: {self.dataset_size}*",
            "",
            disclaimer,
            "| Mô hình / Biến thể | Chế độ | Chiều dịch | BLEU ↑ | chrF ↑ | chrF++ ↑ | Cờ lỗi (%) ↓ | Latency (ms) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        sorted_scores = sorted(self.scores, key=lambda s: (s.direction, s.model_name))
        for s in sorted_scores:
            if "vi-ty" in s.direction or "vi_to_tay" in s.direction or s.direction.startswith("vi"):
                dir_str = "Việt → Tày"
            else:
                dir_str = "Tày → Việt"

            if s.is_mock or s.evaluation_tier == "mock_simulation":
                mode_str = "MOCK"
            elif s.evaluation_tier == "smoke_fixture":
                mode_str = "SMOKE (Neural/Fixture)"
            elif s.evaluation_tier == "research_corpus":
                mode_str = "RESEARCH"
            else:
                mode_str = "SMOKE"

            lines.append(
                f"| **{s.model_name}** | `{mode_str}` | {dir_str} | "
                f"**{s.bleu.score:.2f}** | {s.chrf.score:.2f} | {s.chrf_pp.score:.2f} | "
                f"{s.error_report.error_rate:.1f}% | {s.mean_latency_ms:.1f}ms |"
            )

        return "\n".join(lines).strip()

    def save_json(self, output_path: str | Path) -> Path:
        """Save report to JSON file."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return p

    def save_markdown(self, output_path: str | Path) -> Path:
        """Save report markdown table to file."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.generate_markdown_table() + "\n")
        return p


# ==============================================================================
# Translation Evaluator Engine
# ==============================================================================

class TranslationEvaluator:
    """Comprehensive test set evaluation engine for Vietnamese-Tay models."""

    CORE_VARIANTS = ["E0", "E1", "E2", "E1-M", "A1", "A2"]

    def __init__(
        self,
        error_analyzer: ErrorAnalyzer | None = None,
    ) -> None:
        self.error_analyzer = error_analyzer or ErrorAnalyzer()

    def evaluate_model(
        self,
        model_name: str,
        translator: Any | Callable[[str, str], str],
        sources: Sequence[str],
        references: Sequence[str],
        direction: Direction | str = Direction.VI_TO_TAY,
        batch_size: int = 32,
        sample_ids: Sequence[str] | None = None,
        provenance_list: Sequence[dict[str, Any]] | None = None,
        checkpoint_metadata: dict[str, Any] | None = None,
    ) -> tuple[ModelEvaluationScore, list[dict[str, Any]]]:
        """Evaluate a single model on a source-reference parallel list.

        Preserves sample IDs, document provenance, and distinguishes mock vs real execution.
        """
        norm_dir = Direction.normalize(direction)
        dir_str = norm_dir.value

        # Pre-execution validation: strictly guard against mismatched vector lengths
        if len(sources) != len(references):
            raise ValueError(
                f"Source and reference length mismatch: {len(sources)} sources vs {len(references)} references"
            )
        if sample_ids is not None and len(sample_ids) != len(sources):
            raise ValueError(
                f"Sample IDs length mismatch: {len(sample_ids)} IDs vs {len(sources)} sources"
            )
        if provenance_list is not None and len(provenance_list) != len(sources):
            raise ValueError(
                f"Provenance list length mismatch: {len(provenance_list)} items vs {len(sources)} sources"
            )

        # Detect whether translator is in mock mode (fail-closed default: mock/synthetic unless proven real)
        is_mock = True
        cls_name = translator.__class__.__name__.lower()
        mock_keywords = ("mock", "dummy", "synthetic", "random", "fake", "stub", "simulat")
        is_mock_named = any(kw in cls_name for kw in mock_keywords)

        if is_mock_named:
            is_mock = True
        elif hasattr(translator, "mock_mode"):
            is_mock = bool(translator.mock_mode)
        elif hasattr(translator, "is_mock"):
            is_mock = bool(translator.is_mock)
        elif getattr(translator, "status", None) == "mock_mode":
            is_mock = True
        elif getattr(translator, "status", None) == "ready" and hasattr(translator, "checkpoint_dir") and translator.checkpoint_dir is not None:
            # Verified real checkpoint adapter with status == ready
            is_mock = False
        elif hasattr(translator, "checkpoint_path") and translator.checkpoint_path is not None:
            is_mock = False
        elif getattr(translator, "is_real", False) is True:
            is_mock = False
        else:
            # Unknown callable, lambda, dict, or test stub must NEVER default to REAL research results
            is_mock = True

        ckpt_meta = dict(checkpoint_metadata or {})
        if hasattr(translator, "model_version"):
            ckpt_meta.setdefault("model_version", getattr(translator, "model_version"))

        # Determine evaluation tier separating mock simulation, smoke on fixture, and real research
        ckpt_str = str(getattr(translator, "checkpoint_dir", "") or getattr(translator, "checkpoint_path", "") or "")
        model_ver = str(getattr(translator, "model_version", "") or ckpt_meta.get("model_version", ""))

        is_fixture_source = any(
            isinstance(p, dict) and p.get("source") in ("fixture", "synthetic_fixture", "sample_test", "mock")
            for p in (provenance_list or [])
        ) or any("sample_" in str(s) or "fixture" in str(s) for s in (sample_ids or []))

        is_fixture_model = (
            "fixture" in ckpt_str.lower()
            or "mock" in ckpt_str.lower()
            or "temp" in ckpt_str.lower()
            or "sample" in model_ver.lower()
            or ckpt_meta.get("is_fixture", False)
            or ckpt_meta.get("is_smoke_test", False)
        )

        if is_mock:
            eval_tier = "mock_simulation"
        elif is_fixture_source or is_fixture_model or not ckpt_meta.get("is_gold_research", False):
            # Adapter loaded neural weights, but on fixtures or smoke test!
            eval_tier = "smoke_fixture"
        else:
            eval_tier = "research_corpus"

        hypotheses: list[str] = []
        latencies: list[float] = []
        prediction_details: list[dict[str, Any]] = []

        # Run translations with latency tracking
        for idx, (src, ref) in enumerate(zip(sources, references)):
            t0 = time.perf_counter()
            hyp = self._call_translate(translator, src, norm_dir)
            t1 = time.perf_counter()

            latency_ms = (t1 - t0) * 1000.0
            latencies.append(latency_ms)
            hypotheses.append(hyp)

            s_id = (
                sample_ids[idx]
                if sample_ids is not None and idx < len(sample_ids)
                else f"sample_{idx:04d}"
            )
            prov = (
                provenance_list[idx]
                if provenance_list is not None and idx < len(provenance_list)
                else {}
            )

            prediction_details.append({
                "index": idx,
                "sample_id": s_id,
                "provenance": prov,
                "model_name": model_name,
                "direction": dir_str,
                "src": src,
                "ref": ref,
                "hyp": hyp,
                "latency_ms": round(latency_ms, 2),
                "is_mock": is_mock,
            })

        # Calculate translation metrics with full signatures
        bleu_res = compute_bleu(hypotheses, references)
        chrf_res = compute_chrf(hypotheses, references, word_order=0)
        chrf_pp_res = compute_chrf_plus_plus(hypotheses, references, word_order=2)

        # Run automated surface error classification
        error_report = self.error_analyzer.analyze_corpus(
            sources=sources,
            hypotheses=hypotheses,
            references=references,
            direction=dir_str,
        )

        # Latency statistics
        n = len(latencies)
        mean_lat = statistics.mean(latencies) if n > 0 else 0.0
        med_lat = statistics.median(latencies) if n > 0 else 0.0
        sorted_lat = sorted(latencies)
        p95_idx = int(n * 0.95)
        p95_lat = sorted_lat[min(p95_idx, n - 1)] if n > 0 else 0.0
        total_time_sec = sum(latencies) / 1000.0
        throughput = (n / total_time_sec) if total_time_sec > 0 else 0.0

        score = ModelEvaluationScore(
            model_name=model_name,
            direction=dir_str,
            bleu=bleu_res,
            chrf=chrf_res,
            chrf_pp=chrf_pp_res,
            error_report=error_report,
            sample_count=n,
            mean_latency_ms=mean_lat,
            median_latency_ms=med_lat,
            p95_latency_ms=p95_lat,
            throughput_sps=throughput,
            is_mock=is_mock,
            evaluation_tier=eval_tier,
            checkpoint_metadata=ckpt_meta,
            signature_bleu=bleu_res.signature,
            signature_chrf=chrf_res.signature,
            signature_chrf_pp=chrf_pp_res.signature,
        )

        return score, prediction_details

    def evaluate_test_set(
        self,
        test_records: Sequence[dict[str, Any]],
        models: dict[str, Any],
        directions: Sequence[Direction | str] = (Direction.VI_TO_TAY, Direction.TAY_TO_VI),
        dataset_name: str = "test",
        max_samples: int | None = None,
    ) -> tuple[ComparativeEvaluationReport, list[dict[str, Any]]]:
        """Run full bidirectional benchmark across all supplied model variants.

        Preserves sample IDs, document provenance, and separates mock simulations.
        """
        records = list(test_records)
        if max_samples:
            records = records[:max_samples]

        all_scores: list[ModelEvaluationScore] = []
        all_predictions: list[dict[str, Any]] = []

        for d in directions:
            norm_dir = Direction.normalize(d)

            # Extract source, ref, sample_ids, and provenance according to direction
            valid_src: list[str] = []
            valid_ref: list[str] = []
            valid_ids: list[str] = []
            valid_provenance: list[dict[str, Any]] = []

            for idx, r in enumerate(records):
                if norm_dir == Direction.VI_TO_TAY:
                    src = r.get("vi_text") or r.get("vi", "")
                    ref = r.get("tay_text") or r.get("ty") or r.get("tay", "")
                else:
                    src = r.get("tay_text") or r.get("ty") or r.get("tay", "")
                    ref = r.get("vi_text") or r.get("vi", "")

                if src.strip() and ref.strip():
                    valid_src.append(src)
                    valid_ref.append(ref)
                    s_id = str(r.get("id") or r.get("hash") or f"test_{idx:04d}")
                    valid_ids.append(s_id)
                    prov = {
                        "source": r.get("source", ""),
                        "source_doc_id": r.get("source_doc_id", ""),
                        "topic": r.get("topic", ""),
                    }
                    valid_provenance.append(prov)

            for model_name, translator in models.items():
                score, preds = self.evaluate_model(
                    model_name=model_name,
                    translator=translator,
                    sources=valid_src,
                    references=valid_ref,
                    direction=norm_dir,
                    sample_ids=valid_ids,
                    provenance_list=valid_provenance,
                )
                all_scores.append(score)
                all_predictions.extend(preds)

        has_mock = any(s.is_mock for s in all_scores)

        report = ComparativeEvaluationReport(
            scores=all_scores,
            dataset_name=dataset_name,
            dataset_size=len(records),
            metadata={
                "evaluated_models": list(models.keys()),
                "evaluated_directions": [Direction.normalize(d).value for d in directions],
                "has_mock_models": has_mock,
                "audit_note": (
                    "Tất cả hoặc một số mô hình chạy trong chế độ MOCK / kiểm thử chu trình. "
                    "Kết quả chỉ chứng minh tính thông suốt của pipeline, chưa phải kết quả thực nghiệm chính thức."
                    if has_mock
                    else "Đánh giá trên checkpoint mô hình thật."
                ),
            },
        )

        return report, all_predictions

    def _call_translate(self, translator: Any, text: str, direction: Direction) -> str:
        """Call translate with fallback for various interface signatures."""
        if hasattr(translator, "translate"):
            try:
                res = translator.translate(text, direction=direction)
            except TypeError:
                res = translator.translate(text, direction.value)
            if hasattr(res, "tgt_text"):
                return str(res.tgt_text)
            return str(res)
        elif callable(translator):
            try:
                return str(translator(text, direction.value))
            except TypeError:
                return str(translator(text, direction))
        return str(translator)
