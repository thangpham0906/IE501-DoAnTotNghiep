"""Human evaluation sampling, blinding, and inter-rater reliability module.

Fulfills requirements for T04 & T18:
1. Stratified sampling by source / length across 4 systems (E0, E1, E2, E1-M) on the exact same samples.
2. System blinding with randomized item permutation and reproducible seed (SYS_A, SYS_B, SYS_C, SYS_D).
3. Zero metadata leakage: unblind key strictly decoupled from evaluation sheet.
4. Scoring sheet export (CSV and JSONL) covering all three standard criteria on Likert 1-5 scale:
   - Adequacy / Semantic Accuracy (adequacy_1_5)
   - Completeness / Information Retention (completeness_1_5)
   - Fluency / Grammatical Naturalness (fluency_1_5)
5. Inter-annotator agreement metrics: Cohen's Kappa (unweighted, linear, and quadratic weighted).
6. Honest count reporting: small corpora evaluate actual available items without artificial inflation to 400.
"""

from __future__ import annotations

import csv
import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence


# ==============================================================================
# Data Structures
# ==============================================================================

@dataclass
class BlindTranslationItem:
    """A single candidate translation evaluated blindly by human judges."""

    item_id: str
    sample_id: str
    direction: str
    item_index: int
    source_text: str
    reference_text: str
    hypothesis_text: str
    blind_system_id: str  # e.g., 'SYS_A', 'SYS_B' (true identity hidden)
    adequacy_1_5: int | None = None  # Semantic Adequacy (1-5)
    completeness_1_5: int | None = None  # Completeness / Retention (1-5)
    fluency_1_5: int | None = None  # Fluency / Naturalness (1-5)
    annotator_id: str = ""
    error_notes: str = ""

    @property
    def semantic_accuracy_1_5(self) -> int | None:
        """Backward-compatible alias for adequacy_1_5."""
        return self.adequacy_1_5

    @semantic_accuracy_1_5.setter
    def semantic_accuracy_1_5(self, value: int | None) -> None:
        self.adequacy_1_5 = value

    def to_dict(self) -> dict[str, Any]:
        """Convert item to dictionary for serialization."""
        d = asdict(self)
        d["semantic_accuracy_1_5"] = self.adequacy_1_5
        return d


@dataclass
class HumanEvaluationBundle:
    """Complete bundle of blind evaluation items, unblind key, and manifest."""

    items: list[BlindTranslationItem]
    unblind_key: dict[str, dict[str, str]]  # sample_id -> {blind_id: true_system}
    manifest: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize bundle metadata and item counts."""
        return {
            "total_items": len(self.items),
            "manifest": self.manifest,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class KappaResult:
    """Detailed inter-annotator agreement evaluation result."""

    kappa: float
    observed_agreement: float
    chance_agreement: float
    weighted_kappa: float | None
    weights: str | None
    adjacent_agreement: float  # Percentage of scores differing by <= 1 point
    categories: list[Any]
    confusion_matrix: list[list[int]]
    interpretation: str
    sample_size: int

    def to_dict(self) -> dict[str, Any]:
        """Convert kappa result to dictionary."""
        d = asdict(self)
        if self.kappa is not None and math.isnan(self.kappa):
            d["kappa"] = None
        if self.weighted_kappa is not None and math.isnan(self.weighted_kappa):
            d["weighted_kappa"] = None
        return d

    def format_summary(self) -> str:
        """Formatted summary of Cohen's Kappa score and agreement statistics."""
        k_str = f"{self.kappa:.3f}" if (self.kappa is not None and not math.isnan(self.kappa)) else "Undefined"
        if self.weighted_kappa is not None:
            w_val = f"{self.weighted_kappa:.3f}" if not math.isnan(self.weighted_kappa) else "Undefined"
            w_str = f", Weighted Kappa ({self.weights}) = {w_val}"
        else:
            w_str = ""
        return (
            f"Cohen's Kappa = {k_str} [{self.interpretation}] "
            f"(Observed: {self.observed_agreement * 100.0:.1f}%, "
            f"Adjacent (diff<=1): {self.adjacent_agreement * 100.0:.1f}%, "
            f"Chance: {self.chance_agreement * 100.0:.1f}%, N={self.sample_size}{w_str})"
        )


# ==============================================================================
# Inter-annotator Agreement: Cohen's Kappa
# ==============================================================================

def interpret_kappa(kappa: float | None) -> str:
    """Standard Landis & Koch (1977) interpretation of Cohen's Kappa."""
    if kappa is None or math.isnan(kappa):
        return "Undefined (Zero expected disagreement / rater variance is zero)"
    if kappa < 0.0:
        return "Poor (Kem hon ngau nhien)"
    elif kappa <= 0.20:
        return "Slight (Dong thuan rat thap)"
    elif kappa <= 0.40:
        return "Fair (Dong thuan trung binh thap)"
    elif kappa <= 0.60:
        return "Moderate (Dong thuan vua phai)"
    elif kappa <= 0.80:
        return "Substantial (Dong thuan cao)"
    else:
        return "Almost Perfect (Gan nhu dong thuan tuyet doi)"


def calculate_cohens_kappa(
    rater1_scores: Sequence[int | float | str],
    rater2_scores: Sequence[int | float | str],
    weights: str | None = "quadratic",
    categories: Sequence[Any] | None = None,
) -> KappaResult:
    """Calculate Cohen's Kappa inter-annotator agreement between two raters.

    Supports unweighted, linear weighted, and quadratic weighted Kappa for ordinal scales (1-5).
    Maintains fixed 1..5 category levels for Likert scales to prevent distance compression
    when specific intermediate score levels are unobserved.
    Identifies zero expected disagreement (pe >= 1.0) as mathematically undefined.
    """
    if len(rater1_scores) != len(rater2_scores):
        raise ValueError(
            f"Score count mismatch: rater1 has {len(rater1_scores)}, rater2 has {len(rater2_scores)}"
        )

    n = len(rater1_scores)
    if n == 0:
        raise ValueError("Cannot calculate Cohen's Kappa on empty score lists.")

    if categories is None:
        all_scores = list(rater1_scores) + list(rater2_scores)
        is_likert_1_5 = all(
            isinstance(s, (int, float)) and s in (1, 2, 3, 4, 5, 1.0, 2.0, 3.0, 4.0, 5.0)
            for s in all_scores
        )
        if is_likert_1_5:
            # Fixed 1..5 Likert categories: preserve true psychometric distance
            sorted_cats = [1, 2, 3, 4, 5]
        else:
            cat_set = set(rater1_scores) | set(rater2_scores)
            try:
                sorted_cats = sorted(list(cat_set))
            except TypeError:
                sorted_cats = list(cat_set)
    else:
        sorted_cats = list(categories)

    k = len(sorted_cats)
    cat_to_idx = {c: i for i, c in enumerate(sorted_cats)}

    cm = [[0] * k for _ in range(k)]
    adjacent_matches = 0

    for s1, s2 in zip(rater1_scores, rater2_scores):
        i = cat_to_idx[s1]
        j = cat_to_idx[s2]
        cm[i][j] += 1
        if isinstance(s1, (int, float)) and isinstance(s2, (int, float)):
            if abs(s1 - s2) <= 1.0:
                adjacent_matches += 1
        elif abs(i - j) <= 1:
            adjacent_matches += 1

    adjacent_agreement = adjacent_matches / n

    row_sums = [sum(cm[i][j] for j in range(k)) for i in range(k)]
    col_sums = [sum(cm[i][j] for i in range(k)) for j in range(k)]

    po = sum(cm[i][i] for i in range(k)) / n
    pe = sum(row_sums[i] * col_sums[i] for i in range(k)) / (n * n)

    # When expected agreement is 1.0, expected disagreement is zero, kappa is mathematically undefined
    if abs(1.0 - pe) <= 1e-12 or pe >= 1.0:
        unweighted_k = float("nan")
    else:
        unweighted_k = (po - pe) / (1.0 - pe)

    weighted_k: float | None = None
    if weights in ("linear", "quadratic") and k > 1:
        w_mat = [[0.0] * k for _ in range(k)]
        denom = float(k - 1)
        for i in range(k):
            for j in range(k):
                diff = abs(i - j)
                if weights == "linear":
                    w_mat[i][j] = 1.0 - (diff / denom)
                elif weights == "quadratic":
                    w_mat[i][j] = 1.0 - ((diff ** 2) / (denom ** 2))

        po_w = sum(w_mat[i][j] * cm[i][j] for i in range(k) for j in range(k)) / n
        pe_w = sum(
            w_mat[i][j] * row_sums[i] * col_sums[j] for i in range(k) for j in range(k)
        ) / (n * n)

        if abs(1.0 - pe_w) <= 1e-12 or pe_w >= 1.0:
            weighted_k = float("nan")
        else:
            weighted_k = (po_w - pe_w) / (1.0 - pe_w)

    primary_k = weighted_k if (weighted_k is not None and not math.isnan(weighted_k)) else unweighted_k
    interp = interpret_kappa(primary_k)

    return KappaResult(
        kappa=unweighted_k,
        observed_agreement=po,
        chance_agreement=pe,
        weighted_kappa=weighted_k,
        weights=weights,
        adjacent_agreement=adjacent_agreement,
        categories=sorted_cats,
        confusion_matrix=cm,
        interpretation=interp,
        sample_size=n,
    )


# ==============================================================================
# Human Evaluation Sampler & Blinding Engine
# ==============================================================================

class HumanEvaluationSampler:
    """Tool for stratified sampling and blinding candidate translations for human evaluation."""

    CORE_SYSTEMS: list[str] = ["E0", "E1", "E2", "E1-M"]
    BLIND_LABELS: list[str] = ["SYS_A", "SYS_B", "SYS_C", "SYS_D"]

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def _stratify_by_source_and_length(
        self,
        records: list[dict[str, Any]],
        text_key: str,
        n_samples: int,
    ) -> list[dict[str, Any]]:
        """Stratified proportional sampling across source/domain and 3 length strata without lexical bias.

        Guarantees:
        1. Exact n_samples output (when records >= n_samples).
        2. Sampling without replacement and unique record IDs.
        3. Proportional stratum allocation (Largest Remainder method) with RNG-seeded tie-breaking,
           preventing lexical bias when n_samples < number of strata or when remainders tie.
        4. Strict determinism: identical output for identical seed.
        """
        if len(records) <= n_samples:
            return list(records)

        buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for r in records:
            src = str(r.get("source") or r.get("source_doc_id") or r.get("topic") or "default_source")
            text = r.get(text_key) or r.get("vi") or r.get("tay", "")
            words = text.split()
            if len(words) < 10:
                l_stratum = "short"
            elif len(words) <= 25:
                l_stratum = "medium"
            else:
                l_stratum = "long"
            key = (src, l_stratum)
            buckets.setdefault(key, []).append(r)

        total = len(records)
        sorted_strata = sorted(buckets.keys())

        # Step 1: Base integer quotas and fractional remainders (Largest Remainder Method)
        quotas: dict[tuple[str, str], int] = {}
        remainders: dict[tuple[str, str], float] = {}

        for k in sorted_strata:
            s_k = len(buckets[k])
            exact_quota = n_samples * s_k / total
            base_q = min(int(exact_quota), s_k)
            quotas[k] = base_q
            remainders[k] = exact_quota - int(exact_quota)

        # Step 2: Distribute remaining deficit slots without lexical bias
        deficit = n_samples - sum(quotas.values())
        if deficit > 0:
            eligible_strata = [k for k in sorted_strata if len(buckets[k]) > quotas[k]]
            strata_scores = []
            for k in eligible_strata:
                u = self.rng.random()
                strata_scores.append((remainders[k], u, k))

            strata_scores.sort(key=lambda item: (item[0], item[1]), reverse=True)
            for _, _, k in strata_scores[:deficit]:
                quotas[k] += 1

        # Step 3: Sample without replacement from each bucket according to assigned quota
        sampled: list[dict[str, Any]] = []
        for k in sorted_strata:
            q = quotas.get(k, 0)
            if q > 0:
                bucket = buckets[k]
                chosen_indices = self.rng.sample(range(len(bucket)), q)
                for ci in chosen_indices:
                    sampled.append(bucket[ci])

        return sampled

    def _stratify_by_length(
        self,
        records: list[dict[str, Any]],
        text_key: str,
        n_samples: int,
    ) -> list[dict[str, Any]]:
        """Stratified sampling helper (alias for backward compatibility)."""
        return self._stratify_by_source_and_length(records, text_key, n_samples)

    def sample_blind_evaluation(
        self,
        test_records: Sequence[dict[str, Any]],
        system_translators: dict[str, Any | Callable[[str, str], str]],
        sample_size_per_direction: int = 50,
        systems: list[str] | None = None,
    ) -> HumanEvaluationBundle:
        """Sample test sentences and generate blinded evaluation items.

        Preserves identical source sample IDs across all 4 systems (E0, E1, E2, E1-M).
        Always yields reproducible samples for the same seed regardless of prior instance calls.
        """
        # Always reset RNG at the start of sampling for exact reproducibility across multiple calls
        self.rng = random.Random(self.seed)

        active_systems = systems or self.CORE_SYSTEMS

        canonical_records = sorted(
            list(test_records),
            key=lambda r: (
                str(r.get("id") or r.get("hash") or r.get("source_doc_id", ""))
                + "_"
                + str(r.get("vi_text", r.get("vi", "")))
            ),
        )

        valid_records = [
            r for r in canonical_records
            if (r.get("vi_text") or r.get("vi")) and (r.get("tay_text") or r.get("ty") or r.get("tay"))
        ]

        # Stratified sampling for Vietnamese -> Tay across source and length
        sampled_vi = self._stratify_by_source_and_length(
            records=valid_records,
            text_key="vi_text",
            n_samples=min(sample_size_per_direction, len(valid_records)),
        )

        # Stratified sampling for Tay -> Vietnamese using identical base pool with independent deterministic RNG
        dir_sampler = HumanEvaluationSampler(seed=self.seed + 101)
        sampled_tay = dir_sampler._stratify_by_source_and_length(
            records=valid_records,
            text_key="tay_text",
            n_samples=min(sample_size_per_direction, len(valid_records)),
        )

        bundle_items: list[BlindTranslationItem] = []
        unblind_key: dict[str, dict[str, Any]] = {}

        # 1. Process Vietnamese -> Tay
        for idx, rec in enumerate(sampled_vi, 1):
            src_text = rec.get("vi_text") or rec.get("vi", "")
            ref_text = rec.get("tay_text") or rec.get("ty") or rec.get("tay", "")
            rec_id = str(rec.get("id") or rec.get("hash") or f"src_vi_{idx:03d}")
            prov = {
                "source": rec.get("source", ""),
                "source_doc_id": rec.get("source_doc_id", ""),
                "topic": rec.get("topic", ""),
            }
            sample_id = f"eval_vi_ty_{idx:03d}"

            candidates: dict[str, str] = {}
            for sys_name in active_systems:
                candidates[sys_name] = self._translate(
                    translator=system_translators[sys_name],
                    text=src_text,
                    direction="vi-tyz",
                )

            # Randomized blind labels per sample (shuffled per item)
            blind_labels = list(self.BLIND_LABELS[: len(active_systems)])
            item_rng = random.Random(self.seed + idx * 13)
            item_rng.shuffle(blind_labels)

            system_mapping = {}
            for sys_name, blind_label in zip(active_systems, blind_labels):
                system_mapping[blind_label] = sys_name
                # Unique item id without revealing system order
                unique_item_id = f"{sample_id}_{blind_label}"
                bundle_items.append(
                    BlindTranslationItem(
                        item_id=unique_item_id,
                        sample_id=sample_id,
                        direction="vi-tyz",
                        item_index=idx,
                        source_text=src_text,
                        reference_text=ref_text,
                        hypothesis_text=candidates[sys_name],
                        blind_system_id=blind_label,
                    )
                )

            unblind_key[sample_id] = {
                "original_id": rec_id,
                "provenance": prov,
                "systems": system_mapping,
                **system_mapping,
            }

        # 2. Process Tay -> Vietnamese
        for idx, rec in enumerate(sampled_tay, 1):
            src_text = rec.get("tay_text") or rec.get("ty") or rec.get("tay", "")
            ref_text = rec.get("vi_text") or rec.get("vi", "")
            rec_id = str(rec.get("id") or rec.get("hash") or f"src_ty_{idx:03d}")
            prov = {
                "source": rec.get("source", ""),
                "source_doc_id": rec.get("source_doc_id", ""),
                "topic": rec.get("topic", ""),
            }
            sample_id = f"eval_ty_vi_{idx:03d}"

            candidates = {}
            for sys_name in active_systems:
                candidates[sys_name] = self._translate(
                    translator=system_translators[sys_name],
                    text=src_text,
                    direction="tyz-vi",
                )

            blind_labels = list(self.BLIND_LABELS[: len(active_systems)])
            item_rng = random.Random(self.seed + 5000 + idx * 17)
            item_rng.shuffle(blind_labels)

            system_mapping = {}
            for sys_name, blind_label in zip(active_systems, blind_labels):
                system_mapping[blind_label] = sys_name
                unique_item_id = f"{sample_id}_{blind_label}"
                bundle_items.append(
                    BlindTranslationItem(
                        item_id=unique_item_id,
                        sample_id=sample_id,
                        direction="tyz-vi",
                        item_index=idx,
                        source_text=src_text,
                        reference_text=ref_text,
                        hypothesis_text=candidates[sys_name],
                        blind_system_id=blind_label,
                    )
                )

            unblind_key[sample_id] = {
                "original_id": rec_id,
                "provenance": prov,
                "systems": system_mapping,
                **system_mapping,
            }

        # Final randomized presentation order to prevent judge fatigue bias across directions
        bundle_rng = random.Random(self.seed + 999)
        bundle_rng.shuffle(bundle_items)

        is_truncated = (len(sampled_vi) < sample_size_per_direction or len(sampled_tay) < sample_size_per_direction)
        manifest = {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "seed": self.seed,
            "systems": active_systems,
            "sample_size_per_direction": sample_size_per_direction,
            "actual_samples_vi_to_tay": len(sampled_vi),
            "actual_samples_tay_to_vi": len(sampled_tay),
            "total_evaluated_translations": len(bundle_items),
            "standard_target_translations": 400,
            "is_truncated": is_truncated,
            "blinding_mode": "random_per_sample_permutation",
            "stratification": "source_and_length",
            "criteria": [
                "adequacy_1_5 (Độ chính xác ngữ nghĩa)",
                "completeness_1_5 (Độ đầy đủ thông tin)",
                "fluency_1_5 (Độ trôi chảy ngôn ngữ)",
            ],
            "count_note": (
                f"Corpus khả dụng gồm {len(sampled_vi)} câu vi->ty và {len(sampled_tay)} câu ty->vi; "
                "đánh giá toàn bộ mẫu khả dụng thực tế, không nhân bản để làm tròn thành 400."
                if is_truncated
                else "Đạt chỉ tiêu mẫu chuẩn."
            ),
        }

        return HumanEvaluationBundle(
            items=bundle_items,
            unblind_key=unblind_key,
            manifest=manifest,
        )

    def _translate(self, translator: Any, text: str, direction: str) -> str:
        """Call translator instance or callable function safely."""
        if hasattr(translator, "translate"):
            res = translator.translate(text, direction=direction)
            if hasattr(res, "tgt_text"):
                return str(res.tgt_text)
            return str(res)
        elif callable(translator):
            return str(translator(text, direction))
        elif isinstance(translator, dict):
            return str(translator.get(text, text))
        return str(translator)


# ==============================================================================
# Exporters (CSV, JSONL, Key, and Guidelines)
# ==============================================================================

def export_human_eval_sheet_csv(
    bundle: HumanEvaluationBundle,
    csv_path: str | Path,
    include_reference: bool = True,
) -> Path:
    """Export blind human evaluation sheet to CSV file.

    Evaluators fill columns:
    - adequacy_1_5 (1-5)
    - completeness_1_5 (1-5)
    - fluency_1_5 (1-5)
    - error_notes (text)
    """
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "item_id",
        "sample_id",
        "direction",
        "item_index",
        "blind_system_id",
        "source_text",
        "reference_text" if include_reference else "",
        "hypothesis_text",
        "adequacy_1_5",
        "completeness_1_5",
        "fluency_1_5",
        "semantic_accuracy_1_5",  # alias column
        "error_notes",
        "annotator_id",
    ]
    fieldnames = [f for f in fieldnames if f]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in bundle.items:
            row = {
                "item_id": item.item_id,
                "sample_id": item.sample_id,
                "direction": item.direction,
                "item_index": item.item_index,
                "blind_system_id": item.blind_system_id,
                "source_text": item.source_text,
                "hypothesis_text": item.hypothesis_text,
                "adequacy_1_5": item.adequacy_1_5 or "",
                "completeness_1_5": item.completeness_1_5 or "",
                "fluency_1_5": item.fluency_1_5 or "",
                "semantic_accuracy_1_5": item.adequacy_1_5 or "",
                "error_notes": item.error_notes or "",
                "annotator_id": item.annotator_id or "",
            }
            if include_reference:
                row["reference_text"] = item.reference_text
            writer.writerow(row)

    return path


def export_human_eval_sheet_jsonl(
    bundle: HumanEvaluationBundle,
    jsonl_path: str | Path,
) -> Path:
    """Export blind human evaluation items to JSONL file."""
    path = Path(jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for item in bundle.items:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    return path


def export_unblind_key(
    bundle: HumanEvaluationBundle,
    key_path: str | Path,
) -> Path:
    """Export unblinding key to separate isolated JSON file."""
    path = Path(key_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "manifest": bundle.manifest,
        "unblind_key": bundle.unblind_key,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path


def export_guidelines_md(doc_path: str | Path) -> Path:
    """Export comprehensive human evaluation rubrics and instructions in Vietnamese."""
    path = Path(doc_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    content = """# HƯỚNG DẪN CHẤM ĐIỂM ĐÁNH GIÁ THỦ CÔNG DỊCH MÁY VIỆT — TÀY
## Quy chuẩn thực nghiệm (T04, T18) — Đánh giá ẩn danh (Blind Evaluation)

### 1. Nguyên tắc chấm độc lập và bảo mật ẩn danh
- Tên các hệ thống mô hình đã được ẩn danh dưới dạng mã ngẫu nhiên (`SYS_A`, `SYS_B`, `SYS_C`, `SYS_D`). Thứ tự các hệ thống được xáo trộn ngẫu nhiên độc lập cho từng câu.
- Người chấm không suy đoán mô hình; chỉ căn cứ vào câu gốc (source) và câu tham chiếu chuẩn (reference).
- Giám khảo thực hiện chấm điểm độc lập hoàn toàn, không thảo luận trong quá trình chấm điểm để bảo đảm tính khách quan khi tính hệ số nhất trí Cohen's Kappa.

---

### 2. Tiêu chí 1: Độ tương đương nghĩa (Adequacy / Semantic Accuracy)
Đo lường mức độ truyền tải chính xác thông điệp và ý nghĩa từ câu gốc sang câu dịch (thang điểm 1–5):

| Điểm | Mức độ | Định nghĩa & Hướng dẫn chi tiết |
| :---: | :--- | :--- |
| **5** | **Hoàn toàn chuẩn xác** | Bảo toàn trọn vẹn 100% ý nghĩa câu nguồn. Không sai lệch, thuật ngữ văn hóa/đời sống Tày chuẩn xác. |
| **4** | **Chuẩn xác phần lớn** | Truyền tải đúng >80% nội dung chính. Chỉ có sai lệch chi tiết rất nhỏ không đổi nghĩa tổng thể. |
| **3** | **Đúng một phần** | Hiểu được ý chính, nhưng một số từ quan trọng bị dịch nhầm hoặc làm mờ nghĩa câu. |
| **2** | **Sai lệch nhiều** | Hiểu sai phần lớn câu nguồn, làm xuyên tạc thông điệp cốt lõi hoặc đảo lộn chủ-vị. |
| **1** | **Vô nghĩa / Sai hoàn toàn** | Bản dịch hoàn toàn vô nghĩa, không liên quan đến câu nguồn, lặp từ thoái hóa. |

---

### 3. Tiêu chí 2: Độ đầy đủ thông tin (Completeness / Information Retention)
Đo lường mức độ bảo toàn các thực thể, số lượng, điều kiện và không bị cắt cụt hay thêm thắt hoang tưởng (thang điểm 1–5):

| Điểm | Mức độ | Định nghĩa & Hướng dẫn chi tiết |
| :---: | :--- | :--- |
| **5** | **Đầy đủ trọn vẹn** | Bảo toàn đầy đủ tất cả các thành phần câu, số liệu, thực thể thời gian, địa danh, không sót từ nào. |
| **4** | **Thiếu sót rất nhỏ** | Bỏ sót hoặc thêm từ đệm không quan trọng, các thông tin cốt lõi (chủ ngữ, số lượng, hành động) giữ nguyên. |
| **3** | **Thiếu một phần** | Bị mất một vế phụ, mất một trạng ngữ hoặc bỏ quên một thực thể số nhưng còn vế chính. |
| **2** | **Cắt cụt nghiêm trọng** | Mất hơn một nửa thông tin, bị ngắt cụt câu nửa chừng hoặc hallucination thêm câu lạ. |
| **1** | **Mất trắng / Chỉ vài từ** | Câu dịch bị cụt hoàn toàn (chỉ còn 1-2 từ rời rạc) hoặc câu rỗng so với câu nguồn dài. |

---

### 4. Tiêu chí 3: Độ trôi chảy ngôn ngữ (Fluency / Naturalness)
Đo lường tính tự nhiên về ngữ pháp, trật tự từ và cách diễn đạt trong tiếng đích (thang điểm 1–5):

| Điểm | Mức độ | Định nghĩa & Hướng dẫn chi tiết |
| :---: | :--- | :--- |
| **5** | **Rất tự nhiên** | Ngữ pháp chuẩn mực, hành văn thuần thục như người bản ngữ, đúng phong cách và cấu trúc tiếng Tày/Việt. |
| **4** | **Tốt / Dễ đọc** | Ngữ pháp đúng, trật tự từ tự nhiên, chỉ hơi gượng nhẹ trong cách phối từ nhưng đọc thông suốt. |
| **3** | **Trung bình** | Người đọc vẫn hiểu được nhưng câu văn gãy góc, mang nặng dấu vết dịch từng chữ (word-for-word). |
| **2** | **Kém / Khó hiểu** | Sai ngữ pháp nặng, trật tự từ đảo lộn, rất gượng gạo và đòi hỏi phải dừng lại suy đoán. |
| **1** | **Hỏng ngữ pháp hoàn toàn** | Chuỗi từ ngữ rời rạc, cấu trúc ngữ pháp bị vỡ vụn hoặc lặp từ bất tận. |

---

### 5. Ghi chú lỗi (Error Notes)
Ghi vắn tắt các mã lỗi thường gặp nếu phát hiện:
- `lap_tu`: Lặp từ hoặc cụm từ liên tiếp không kiểm soát.
- `cut_cau`: Câu dịch bị cắt cụt, thiếu mệnh đề.
- `khong_dich`: Chép nguyên văn từ câu nguồn mà không chuyển ngữ.
- `sai_so`: Bỏ sót hoặc dịch sai con số, ngày tháng, định lượng.
- `mat_thuat_ngu`: Mất hoặc sai lệch thuật ngữ văn hóa (then, lượn, tính tẩu, phja...).
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def unblind_evaluation_results(
    completed_items: Sequence[dict[str, Any] | BlindTranslationItem],
    unblind_key: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Calculate aggregate human evaluation metrics per true system (E0, E1, E2, E1-M)."""
    systems_summary: dict[str, dict[str, list[float]]] = {}

    for item in completed_items:
        if isinstance(item, BlindTranslationItem):
            s_id = item.sample_id
            b_id = item.blind_system_id
            ade = item.adequacy_1_5
            comp = item.completeness_1_5
            flu = item.fluency_1_5
            direction = item.direction
        else:
            s_id = item["sample_id"]
            b_id = item["blind_system_id"]
            ade = item.get("adequacy_1_5") or item.get("semantic_accuracy_1_5")
            comp = item.get("completeness_1_5")
            flu = item.get("fluency_1_5")
            direction = item.get("direction", "unknown")

        sample_meta = unblind_key.get(s_id, {})
        if "systems" in sample_meta and isinstance(sample_meta["systems"], dict):
            true_system = sample_meta["systems"].get(b_id) or sample_meta.get(b_id, "unknown")
        else:
            true_system = sample_meta.get(b_id, "unknown")
        if true_system not in systems_summary:
            systems_summary[true_system] = {
                "adequacy_all": [],
                "completeness_all": [],
                "fluency_all": [],
                "adequacy_vi_to_tay": [],
                "completeness_vi_to_tay": [],
                "fluency_vi_to_tay": [],
                "adequacy_tay_to_vi": [],
                "completeness_tay_to_vi": [],
                "fluency_tay_to_vi": [],
                # Backward-compatibility alias lists
                "semantic_all": [],
                "semantic_vi_to_tay": [],
                "semantic_tay_to_vi": [],
            }

        def _record(val: Any, all_key: str, dir_key: str, alias_all: str | None = None, alias_dir: str | None = None) -> None:
            if val is not None and str(val).strip() != "":
                v = float(val)
                systems_summary[true_system][all_key].append(v)
                if direction in ("vi_to_tay", "vi-tyz"):
                    systems_summary[true_system][dir_key.replace("DIR", "vi_to_tay")].append(v)
                elif direction in ("tay_to_vi", "tyz-vi"):
                    systems_summary[true_system][dir_key.replace("DIR", "tay_to_vi")].append(v)
                if alias_all:
                    systems_summary[true_system][alias_all].append(v)
                if alias_dir:
                    if direction in ("vi_to_tay", "vi-tyz"):
                        systems_summary[true_system][alias_dir.replace("DIR", "vi_to_tay")].append(v)
                    elif direction in ("tay_to_vi", "tyz-vi"):
                        systems_summary[true_system][alias_dir.replace("DIR", "tay_to_vi")].append(v)

        _record(ade, "adequacy_all", "adequacy_DIR", "semantic_all", "semantic_DIR")
        _record(comp, "completeness_all", "completeness_DIR")
        _record(flu, "fluency_all", "fluency_DIR")

    results: dict[str, Any] = {}
    for sys_name, scores in systems_summary.items():
        results[sys_name] = {}
        for key, vals in scores.items():
            if vals:
                mean = sum(vals) / len(vals)
                variance = sum((x - mean) ** 2 for x in vals) / len(vals)
                std = variance ** 0.5
                results[sys_name][key] = {
                    "count": len(vals),
                    "mean": round(mean, 2),
                    "std": round(std, 2),
                }
            else:
                results[sys_name][key] = {"count": 0, "mean": 0.0, "std": 0.0}

    return results


def sample_blind_human_evaluation(
    test_records: Sequence[dict[str, Any]],
    system_translators: dict[str, Any],
    output_dir: str | Path,
    sample_size_per_direction: int = 50,
    seed: int = 42,
) -> HumanEvaluationBundle:
    """Convenience helper to sample, blind, and export all sheets and keys."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    sampler = HumanEvaluationSampler(seed=seed)
    bundle = sampler.sample_blind_evaluation(
        test_records=test_records,
        system_translators=system_translators,
        sample_size_per_direction=sample_size_per_direction,
    )

    export_human_eval_sheet_csv(bundle, out / "human_eval_sheet.csv")
    export_human_eval_sheet_jsonl(bundle, out / "human_eval_sheet.jsonl")
    export_unblind_key(bundle, out / "unblind_key.json")
    export_guidelines_md(out / "HUMAN_EVAL_GUIDELINES.md")

    return bundle
