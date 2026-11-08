"""Automated translation error classification module (Surface Heuristics).

IMPORTANT METHODOLOGICAL NOTE:
The defect categories and rules implemented here are automated surface heuristics
(regex patterns, character/word length ratios, and token overlap counters).
They serve as automated operational screening indicators (flags) and DO NOT
constitute definitive assertions of linguistic, syntactic, or cultural translation quality.
Definitive linguistic quality assessment requires qualified native-speaker human evaluation.

Heuristic categories:
1. Repetition (consecutive word loops, n-gram loops, low vocabulary richness/TTR).
2. Length Anomaly (truncation/under-translation, hallucinatory explosion, empty string).
3. Omission & Untranslated (verbatim source copy, high lexical overlap, missing numbers).
4. Corrupted Script/Encoding (CJK/alien scripts, null bytes, unicode replacement chars).
5. Cultural/Domain Term Flag (lexical absence flag for culturally significant terms).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Sequence


class ErrorCategory(str, Enum):
    """Categories of automated translation defects."""

    REPETITION = "repetition"
    LENGTH_ANOMALY = "length_anomaly"
    OMISSION = "omission"
    UNTRANSLATED_COPY = "untranslated_copy"
    MISSING_NUMERICAL = "missing_numerical"
    CORRUPTED_ENCODING = "corrupted_encoding"
    CULTURAL_TERM_LOSS = "cultural_term_loss"


class Severity(str, Enum):
    """Defect severity classification."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


@dataclass
class TranslationError:
    """Individual detected translation defect."""

    category: ErrorCategory
    severity: Severity
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class SentenceErrorReport:
    """Error analysis report for a single translation pair."""

    index: int
    src: str
    hyp: str
    ref: str | None
    errors: list[TranslationError] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        """True if any error is flagged."""
        return len(self.errors) > 0

    @property
    def critical_errors(self) -> list[TranslationError]:
        """List of critical severity errors."""
        return [e for e in self.errors if e.severity == Severity.CRITICAL]

    def to_dict(self) -> dict[str, Any]:
        """Convert sentence report to dictionary."""
        return {
            "index": self.index,
            "src": self.src,
            "hyp": self.hyp,
            "ref": self.ref,
            "has_error": self.has_error,
            "error_count": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
        }


@dataclass
class CorpusErrorReport:
    """Aggregate error analysis report across an entire test corpus."""

    total_sentences: int
    sentences_with_errors: int
    clean_sentences: int
    error_rate: float
    counts_by_category: dict[str, int]
    counts_by_severity: dict[str, int]
    detailed_sentence_reports: list[SentenceErrorReport]

    def to_dict(self) -> dict[str, Any]:
        """Convert corpus report to dictionary."""
        return {
            "total_sentences": self.total_sentences,
            "sentences_with_errors": self.sentences_with_errors,
            "clean_sentences": self.clean_sentences,
            "error_rate": self.error_rate,
            "counts_by_category": self.counts_by_category,
            "counts_by_severity": self.counts_by_severity,
            "detailed_sentence_reports": [
                r.to_dict() for r in self.detailed_sentence_reports
            ],
        }

    def format_markdown_summary(self) -> str:
        """Produce markdown summary table of error statistics with explicit heuristic caveat."""
        lines = [
            "### Báo cáo Phân tích Cờ Lỗi Dịch thuật Tự động (Automated Surface Error Heuristics)",
            "> **Lưu ý phương pháp luận:** Các danh mục lỗi dưới đây là cờ chỉ báo tự động (automated surface heuristics) "
            "dựa trên tỷ lệ ký tự, từ vựng và regex. Chúng phục vụ lọc lỗi thô và sàng lọc kỹ thuật, "
            "tuyệt đối KHÔNG khẳng định chất lượng ngôn ngữ học hay ngữ pháp chiều sâu (cần giám khảo bản ngữ thẩm định).",
            "",
            f"- **Tổng số câu đánh giá:** {self.total_sentences}",
            f"- **Số câu phát hiện cờ cảnh báo:** {self.sentences_with_errors} ({self.error_rate:.1f}%)",
            f"- **Số câu không phát hiện cờ lỗi tự động:** {self.clean_sentences} ({100.0 - self.error_rate:.1f}%)",
            "",
            "| Nhóm Cờ Lỗi (Category) | Số lượng phát hiện | Tỷ lệ trên tổng số câu |",
            "| :--- | :---: | :---: |",
        ]
        for cat in ErrorCategory:
            c = self.counts_by_category.get(cat.value, 0)
            rate = (c / self.total_sentences * 100.0) if self.total_sentences > 0 else 0.0
            lines.append(f"| `{cat.value}` | {c} | {rate:.1f}% |")

        lines.extend([
            "",
            "| Mức độ nghiêm trọng (Severity) | Số lượng |",
            "| :--- | :---: |",
        ])
        for sev in Severity:
            lines.append(f"| `{sev.value}` | {self.counts_by_severity.get(sev.value, 0)} |")

        return "\n".join(lines)


# ==============================================================================
# Domain Lexicons and Patterns
# ==============================================================================

# Key cultural folklore terms in Tay and Vietnamese
TAY_CULTURAL_TERMS = {
    "lượn", "then", "tính tẩu", "nàng hai", "phja", "bản mường",
    "khui hội", "báo sáo", "kin khẩu", "rườn", "nà", "rẩy",
    "vài", "mạ", "slíp", "bươn chiêng", "cần ké", "lục éc",
    "đong thâm", "thêm ta", "bjoóc", "lảu", "cần tày",
}

VI_CULTURAL_TERMS = {
    "hát lượn", "then", "đàn tính", "nàng hai", "núi cao", "bản làng",
    "mở hội", "trai gái", "ăn cơm", "ngôi nhà", "ruộng", "nương",
    "con trâu", "con ngựa", "mười lăm", "tháng giêng", "người già",
    "trẻ con", "rừng sâu", "sông suối", "hoa đào", "rượu", "người tày",
}

# Regex for foreign characters (CJK, Cyrillic, Thai, Arabic, Hangul)
ALIEN_SCRIPT_REGEX = re.compile(
    r"[一-鿿぀-ヿЀ-ӿ฀-๿؀-ۿ가-힯]"
)

# Regex for extracting digits/numbers
NUMERICAL_REGEX = re.compile(r"\b\d+(?:[\.,]\d+)?\b")


# ==============================================================================
# Error Analyzer Class
# ==============================================================================

class ErrorAnalyzer:
    """Automated translation quality error detection and classification engine."""

    def __init__(
        self,
        min_word_repeat: int = 3,
        min_ngram_repeat: int = 2,
        min_length_ratio: float = 0.4,
        max_length_ratio: float = 2.5,
        min_ttr: float = 0.4,
        source_copy_jaccard_threshold: float = 0.70,
    ) -> None:
        self.min_word_repeat = min_word_repeat
        self.min_ngram_repeat = min_ngram_repeat
        self.min_length_ratio = min_length_ratio
        self.max_length_ratio = max_length_ratio
        self.min_ttr = min_ttr
        self.source_copy_jaccard_threshold = source_copy_jaccard_threshold

    def analyze_sentence(
        self,
        src: str,
        hyp: str,
        ref: str | None = None,
        index: int = 0,
        direction: str = "vi_to_tay",
    ) -> SentenceErrorReport:
        """Run all automated error detectors on a single translation hypothesis."""
        errors: list[TranslationError] = []

        norm_src = unicodedata.normalize("NFC", src.strip())
        norm_hyp = unicodedata.normalize("NFC", hyp.strip())
        norm_ref = unicodedata.normalize("NFC", ref.strip()) if ref else None

        # 1. Empty / Whitespace only
        if not norm_hyp:
            errors.append(
                TranslationError(
                    category=ErrorCategory.LENGTH_ANOMALY,
                    severity=Severity.CRITICAL,
                    message="Bản dịch rỗng hoặc chỉ chứa khoảng trắng.",
                    details={"hyp_length": len(norm_hyp)},
                )
            )
            return SentenceErrorReport(
                index=index, src=src, hyp=hyp, ref=ref, errors=errors
            )

        hyp_words = norm_hyp.split()
        src_words = norm_src.split()
        ref_words = norm_ref.split() if norm_ref else []

        # 2. Corrupted Encoding & Foreign Scripts
        alien_chars = ALIEN_SCRIPT_REGEX.findall(norm_hyp)
        if alien_chars:
            errors.append(
                TranslationError(
                    category=ErrorCategory.CORRUPTED_ENCODING,
                    severity=Severity.CRITICAL,
                    message=f"Chứa ký tự chữ ngoại lai không thuộc bảng chữ cái Latin: {set(alien_chars)}",
                    details={"alien_chars": list(set(alien_chars))},
                )
            )

        if "�" in norm_hyp or "\x00" in norm_hyp:
            errors.append(
                TranslationError(
                    category=ErrorCategory.CORRUPTED_ENCODING,
                    severity=Severity.CRITICAL,
                    message="Phát hiện ký tự Unicode lỗi hoặc null byte (\\ufffd, \\x00).",
                    details={"raw": repr(norm_hyp)},
                )
            )

        # 3. Length Anomaly (ratio with source and ref)
        if len(norm_src) > 0:
            char_ratio = len(norm_hyp) / len(norm_src)
            word_ratio = len(hyp_words) / len(src_words) if src_words else 1.0

            if char_ratio < self.min_length_ratio or word_ratio < 0.3:
                errors.append(
                    TranslationError(
                        category=ErrorCategory.LENGTH_ANOMALY,
                        severity=Severity.MAJOR,
                        message=f"Bản dịch bị cụt ngắt bất thường (Truncation/Under-translation). Tỷ lệ ký tự: {char_ratio:.2f}",
                        details={"char_ratio": char_ratio, "word_ratio": word_ratio},
                    )
                )
            elif char_ratio > self.max_length_ratio or word_ratio > 3.0:
                errors.append(
                    TranslationError(
                        category=ErrorCategory.LENGTH_ANOMALY,
                        severity=Severity.MAJOR,
                        message=f"Bản dịch bị phóng đại độ dài bất thường (Hallucinatory explosion). Tỷ lệ ký tự: {char_ratio:.2f}",
                        details={"char_ratio": char_ratio, "word_ratio": word_ratio},
                    )
                )

        # Absolute length boundaries
        if len(hyp_words) < 2 and len(src_words) >= 3:
            errors.append(
                TranslationError(
                    category=ErrorCategory.OMISSION,
                    severity=Severity.MAJOR,
                    message=f"Bản dịch quá ngắn ({len(hyp_words)} từ) so với câu gốc ({len(src_words)} từ).",
                    details={"hyp_words": len(hyp_words), "src_words": len(src_words)},
                )
            )

        # 4. Repetition (Consecutive words and n-grams)
        rep_error = self._check_repetition(hyp_words)
        if rep_error:
            errors.append(rep_error)

        # Type-Token Ratio (Vocabulary Richness) for sentences >= 6 words
        if len(hyp_words) >= 6:
            unique_words = len(set(w.casefold() for w in hyp_words))
            ttr = unique_words / len(hyp_words)
            if ttr < self.min_ttr:
                errors.append(
                    TranslationError(
                        category=ErrorCategory.REPETITION,
                        severity=Severity.MAJOR,
                        message=f"Độ đa dạng từ vựng quá thấp (TTR={ttr:.2f} < {self.min_ttr}), dấu hiệu suy thoái lặp từ.",
                        details={"ttr": ttr, "unique_words": unique_words, "total_words": len(hyp_words)},
                    )
                )

        # 5. Untranslated Copy / High Lexical Overlap with Source
        if norm_hyp.casefold() == norm_src.casefold() and len(src_words) >= 2:
            errors.append(
                TranslationError(
                    category=ErrorCategory.UNTRANSLATED_COPY,
                    severity=Severity.CRITICAL,
                    message="Bản dịch sao chép nguyên xi câu nguồn mà không dịch.",
                    details={"src": norm_src, "hyp": norm_hyp},
                )
            )
        elif len(src_words) >= 4 and len(hyp_words) >= 4:
            src_set = set(w.casefold() for w in src_words)
            hyp_set = set(w.casefold() for w in hyp_words)
            overlap = len(src_set & hyp_set) / len(src_set | hyp_set)
            if overlap >= self.source_copy_jaccard_threshold:
                errors.append(
                    TranslationError(
                        category=ErrorCategory.UNTRANSLATED_COPY,
                        severity=Severity.MAJOR,
                        message=f"Độ trùng lặp từ vựng với câu nguồn quá cao (Jaccard={overlap:.2f}), dấu hiệu không dịch.",
                        details={"jaccard_overlap": overlap},
                    )
                )

        # 6. Missing Numerical Entities
        src_numbers = NUMERICAL_REGEX.findall(norm_src)
        if src_numbers:
            hyp_text_lower = norm_hyp.casefold()
            missing_nums = [n for n in src_numbers if n not in hyp_text_lower]
            if missing_nums:
                errors.append(
                    TranslationError(
                        category=ErrorCategory.MISSING_NUMERICAL,
                        severity=Severity.MAJOR,
                        message=f"Bỏ sót hoặc làm sai lệch thực thể số: {missing_nums}",
                        details={"missing_numbers": missing_nums, "src_numbers": src_numbers},
                    )
                )

        # 7. Cultural/Domain Term Loss
        if direction in ("vi_to_tay", "vi->ty"):
            # When translating from Vietnamese to Tay, check if source cultural concepts are lost
            for vi_term in VI_CULTURAL_TERMS:
                if vi_term in norm_src.casefold() and norm_ref:
                    # Check if candidate contains relevant Tay words from reference
                    ref_term_candidates = [
                        tw for tw in TAY_CULTURAL_TERMS if tw in norm_ref.casefold()
                    ]
                    if ref_term_candidates:
                        found_in_hyp = any(tw in norm_hyp.casefold() for tw in ref_term_candidates)
                        if not found_in_hyp:
                            errors.append(
                                TranslationError(
                                    category=ErrorCategory.CULTURAL_TERM_LOSS,
                                    severity=Severity.MINOR,
                                    message=f"Có dấu hiệu thất thoát thuật ngữ văn hóa Tày '{ref_term_candidates[0]}' cho khái niệm '{vi_term}'.",
                                    details={"concept": vi_term, "expected_terms": ref_term_candidates},
                                )
                            )
                            break

        return SentenceErrorReport(
            index=index,
            src=src,
            hyp=hyp,
            ref=ref,
            errors=errors,
        )

    def _check_repetition(self, words: list[str]) -> TranslationError | None:
        """Detect consecutive word or n-gram repetition."""
        if len(words) < 3:
            return None

        # 1. Check consecutive single words (e.g., word word word)
        repeat_count = 1
        for i in range(1, len(words)):
            if words[i].casefold() == words[i - 1].casefold():
                repeat_count += 1
                if repeat_count >= self.min_word_repeat:
                    return TranslationError(
                        category=ErrorCategory.REPETITION,
                        severity=Severity.CRITICAL,
                        message=f"Lặp từ đơn liên tiếp '{words[i]}' ({repeat_count} lần).",
                        details={"word": words[i], "repeats": repeat_count},
                    )
            else:
                repeat_count = 1

        # 2. Check consecutive bigrams / trigrams
        for n in (2, 3, 4):
            if len(words) < n * 2:
                continue
            for i in range(len(words) - 2 * n + 1):
                gram1 = [w.casefold() for w in words[i : i + n]]
                gram2 = [w.casefold() for w in words[i + n : i + 2 * n]]
                if gram1 == gram2:
                    gram_str = " ".join(gram1)
                    return TranslationError(
                        category=ErrorCategory.REPETITION,
                        severity=Severity.MAJOR,
                        message=f"Lặp cụm {n}-gram liên tiếp: '{gram_str}'",
                        details={"ngram_order": n, "phrase": gram_str},
                    )

        return None

    def analyze_corpus(
        self,
        sources: Sequence[str],
        hypotheses: Sequence[str],
        references: Sequence[str] | None = None,
        direction: str = "vi_to_tay",
    ) -> CorpusErrorReport:
        """Run batch error classification on an entire corpus."""
        if len(sources) != len(hypotheses):
            raise ValueError(
                f"Count mismatch: {len(sources)} sources vs {len(hypotheses)} hypotheses"
            )

        refs = list(references) if references is not None else [None] * len(sources)
        reports: list[SentenceErrorReport] = []

        category_counts: dict[str, int] = {cat.value: 0 for cat in ErrorCategory}
        severity_counts: dict[str, int] = {sev.value: 0 for sev in Severity}
        sentences_with_errors = 0

        for idx, (src, hyp, ref) in enumerate(zip(sources, hypotheses, refs)):
            report = self.analyze_sentence(
                src=src,
                hyp=hyp,
                ref=ref,
                index=idx,
                direction=direction,
            )
            reports.append(report)

            if report.has_error:
                sentences_with_errors += 1
                for err in report.errors:
                    category_counts[err.category.value] = (
                        category_counts.get(err.category.value, 0) + 1
                    )
                    severity_counts[err.severity.value] = (
                        severity_counts.get(err.severity.value, 0) + 1
                    )

        total = len(sources)
        clean = total - sentences_with_errors
        error_rate = (sentences_with_errors / total * 100.0) if total > 0 else 0.0

        return CorpusErrorReport(
            total_sentences=total,
            sentences_with_errors=sentences_with_errors,
            clean_sentences=clean,
            error_rate=error_rate,
            counts_by_category=category_counts,
            counts_by_severity=severity_counts,
            detailed_sentence_reports=reports,
        )

    def compare_model_errors(
        self,
        model_outputs: dict[str, list[str]],
        sources: list[str],
        references: list[str],
        direction: str = "vi_to_tay",
    ) -> dict[str, Any]:
        """Compare error rates across multiple model variations (E0, E1, E2, E1-M, etc.)."""
        comparison: dict[str, Any] = {}
        for model_name, hyps in model_outputs.items():
            rep = self.analyze_corpus(
                sources=sources,
                hypotheses=hyps,
                references=references,
                direction=direction,
            )
            comparison[model_name] = {
                "total_sentences": rep.total_sentences,
                "sentences_with_errors": rep.sentences_with_errors,
                "error_rate": rep.error_rate,
                "counts_by_category": rep.counts_by_category,
                "counts_by_severity": rep.counts_by_severity,
            }
        return comparison


def classify_translation_errors(
    src: str,
    hyp: str,
    ref: str | None = None,
    direction: str = "vi_to_tay",
) -> list[TranslationError]:
    """Convenience helper to classify defects in a single sentence pair."""
    analyzer = ErrorAnalyzer()
    report = analyzer.analyze_sentence(src=src, hyp=hyp, ref=ref, direction=direction)
    return report.errors


def batch_error_analysis(
    sources: Sequence[str],
    hypotheses: Sequence[str],
    references: Sequence[str] | None = None,
    direction: str = "vi_to_tay",
) -> CorpusErrorReport:
    """Convenience helper to run error analysis on a batch of translations."""
    analyzer = ErrorAnalyzer()
    return analyzer.analyze_corpus(
        sources=sources,
        hypotheses=hypotheses,
        references=references,
        direction=direction,
    )
