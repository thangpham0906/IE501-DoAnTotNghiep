"""Quality Control (QC) filters for synthetic back-translation data.

Implements 5 core quality filtering rules (R1 to R5):
- R1 (Length ratio): Character and word length ratio between source and target.
- R2 (Word/n-gram repetition): Detects pathological NMT repetition / degeneration.
- R3 (Source copy): Detects verbatim or near-verbatim copying of the source text.
- R4 (Min/max length): Bounds on minimum and maximum words and characters.
- R5 (Target language heuristic): Script validation, character set, and language integrity.

Supports selective rule disabling (ablation studies A1 and A2) and comprehensive statistics.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass
class QCFilterConfig:
    """Configuration for Quality Control Filter rules."""

    # R1: Length ratio thresholds
    min_length_ratio: float = 0.4
    max_length_ratio: float = 2.5
    min_word_ratio: float = 0.3
    max_word_ratio: float = 3.0

    # R2: Repetition thresholds
    max_consecutive_word_repeat: int = 3
    max_consecutive_ngram_repeat: int = 2
    min_type_token_ratio: float = 0.4
    min_words_for_ttr_check: int = 6

    # R3: Source copy thresholds
    disallow_exact_copy: bool = True
    max_jaccard_overlap: float = 0.85
    min_words_for_overlap_check: int = 4

    # R4: Absolute length boundaries
    min_words: int = 2
    max_words: int = 200
    min_chars: int = 3
    max_chars: int = 1500

    # R5: Target language & script heuristics
    disallowed_unicode_ranges: tuple[str, ...] = (
        r"[一-鿿]",  # CJK unified ideographs (Chinese)
        r"[぀-ヿ]",  # Japanese Hiragana / Katakana
        r"[Ѐ-ӿ]",  # Cyrillic
        r"[؀-ۿ]",  # Arabic
        r"[฀-๿]",  # Thai
        r"[가-힯]",  # Hangul
    )
    disallowed_symbols: tuple[str, ...] = (
        "\ufffd",  # Unicode replacement character
        "\x00",    # Null byte
    )
    min_alpha_ratio: float = 0.60  # Minimum ratio of alphabetic chars to non-space chars

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)


class QualityControlFilter:
    """Evaluates and filters bilingual sentence pairs using 5 modular rules."""

    # Regex to extract words for length and repetition analysis
    WORD_REGEX = re.compile(r"\w+", re.UNICODE)

    def __init__(self, config: QCFilterConfig | None = None) -> None:
        self.config = config or QCFilterConfig()
        # Compile disallowed scripts
        self._compiled_disallowed = [
            re.compile(pattern) for pattern in self.config.disallowed_unicode_ranges
        ]

    def _normalize(self, text: str) -> str:
        """Normalize text using Unicode NFC form."""
        if not text:
            return ""
        return " ".join(unicodedata.normalize("NFC", text).split())

    def _extract_words(self, text: str) -> list[str]:
        """Extract lowercase words from text."""
        return [w.casefold() for w in self.WORD_REGEX.findall(text)]

    def _check_r1_length_ratio(
        self, src: str, tgt: str, src_words: list[str], tgt_words: list[str]
    ) -> list[str]:
        """R1: Verify length ratios (character and word)."""
        reasons: list[str] = []
        len_src_char = len(src)
        len_tgt_char = len(tgt)

        if len_src_char == 0 or len_tgt_char == 0:
            reasons.append("R1_empty_text")
            return reasons

        char_ratio = len_tgt_char / len_src_char
        if not (self.config.min_length_ratio <= char_ratio <= self.config.max_length_ratio):
            reasons.append(
                f"R1_char_ratio_{char_ratio:.2f}_outside_[{self.config.min_length_ratio},{self.config.max_length_ratio}]"
            )

        len_src_words = len(src_words)
        len_tgt_words = len(tgt_words)
        if len_src_words > 0 and len_tgt_words > 0:
            word_ratio = len_tgt_words / len_src_words
            if not (self.config.min_word_ratio <= word_ratio <= self.config.max_word_ratio):
                reasons.append(
                    f"R1_word_ratio_{word_ratio:.2f}_outside_[{self.config.min_word_ratio},{self.config.max_word_ratio}]"
                )

        return reasons

    def _check_r2_repetition(self, tgt_words: list[str]) -> list[str]:
        """R2: Detect word and n-gram repetition in target sentence."""
        reasons: list[str] = []
        if len(tgt_words) < 2:
            return reasons

        # 1. Consecutive word repetition
        consec_count = 1
        for i in range(1, len(tgt_words)):
            if tgt_words[i] == tgt_words[i - 1]:
                consec_count += 1
                if consec_count >= self.config.max_consecutive_word_repeat:
                    reasons.append(
                        f"R2_consecutive_word_repeat_{tgt_words[i]}_x{consec_count}"
                    )
                    break
            else:
                consec_count = 1

        # 2. Consecutive n-gram repetition (bigrams and trigrams)
        for n in (2, 3, 4):
            if len(tgt_words) < n * 2:
                continue
            i = 0
            while i <= len(tgt_words) - 2 * n:
                ngram = tuple(tgt_words[i : i + n])
                consec = 1
                j = i + n
                while j <= len(tgt_words) - n and tuple(tgt_words[j : j + n]) == ngram:
                    consec += 1
                    j += n
                if consec >= self.config.max_consecutive_ngram_repeat:
                    rep_str = " ".join(ngram)
                    reasons.append(
                        f"R2_consecutive_{n}gram_repeat_{rep_str}_x{consec}"
                    )
                    break
                i += 1
            if any(r.startswith(f"R2_consecutive_{n}gram") for r in reasons):
                break

        # 3. Lexical diversity check (Type-Token Ratio)
        if len(tgt_words) >= self.config.min_words_for_ttr_check:
            ttr = len(set(tgt_words)) / len(tgt_words)
            if ttr < self.config.min_type_token_ratio:
                reasons.append(
                    f"R2_low_ttr_{ttr:.2f}_below_{self.config.min_type_token_ratio}"
                )

        return reasons

    def _check_r3_source_copy(
        self, norm_src: str, norm_tgt: str, src_words: list[str], tgt_words: list[str]
    ) -> list[str]:
        """R3: Detect verbatim or high-overlap source copy."""
        reasons: list[str] = []

        # 1. Exact match
        if self.config.disallow_exact_copy and (norm_src.casefold() == norm_tgt.casefold()):
            reasons.append("R3_exact_source_copy")
            return reasons

        # 2. Jaccard word overlap
        if (
            len(src_words) >= self.config.min_words_for_overlap_check
            and len(tgt_words) >= self.config.min_words_for_overlap_check
        ):
            src_set = set(src_words)
            tgt_set = set(tgt_words)
            union = src_set | tgt_set
            if union:
                overlap = len(src_set & tgt_set) / len(union)
                if overlap >= self.config.max_jaccard_overlap:
                    reasons.append(
                        f"R3_high_jaccard_overlap_{overlap:.2f}_above_{self.config.max_jaccard_overlap}"
                    )

        return reasons

    def _check_r4_length_bounds(
        self, src: str, tgt: str, src_words: list[str], tgt_words: list[str]
    ) -> list[str]:
        """R4: Min/max length limits."""
        reasons: list[str] = []

        len_src_words = len(src_words)
        len_tgt_words = len(tgt_words)

        if len_src_words < self.config.min_words or len_tgt_words < self.config.min_words:
            reasons.append(
                f"R4_min_words_violation_src={len_src_words}_tgt={len_tgt_words}_min={self.config.min_words}"
            )
        if len_src_words > self.config.max_words or len_tgt_words > self.config.max_words:
            reasons.append(
                f"R4_max_words_violation_src={len_src_words}_tgt={len_tgt_words}_max={self.config.max_words}"
            )

        len_src_char = len(src)
        len_tgt_char = len(tgt)
        if len_src_char < self.config.min_chars or len_tgt_char < self.config.min_chars:
            reasons.append(
                f"R4_min_chars_violation_src={len_src_char}_tgt={len_tgt_char}_min={self.config.min_chars}"
            )
        if len_src_char > self.config.max_chars or len_tgt_char > self.config.max_chars:
            reasons.append(
                f"R4_max_chars_violation_src={len_src_char}_tgt={len_tgt_char}_max={self.config.max_chars}"
            )

        return reasons

    def _check_r5_target_heuristic(self, tgt: str, tgt_words: list[str]) -> list[str]:
        """R5: Target language script, alphabet, and encoding heuristics."""
        reasons: list[str] = []

        # 1. Corrupted characters / replacement glyphs
        for sym in self.config.disallowed_symbols:
            if sym and sym in tgt:
                reasons.append(f"R5_corrupted_symbol_{repr(sym)}")
                break

        # 2. Foreign non-Latin scripts (Chinese, Cyrillic, Thai, etc.)
        for pattern in self._compiled_disallowed:
            if pattern.search(tgt):
                reasons.append(f"R5_disallowed_foreign_script_{pattern.pattern}")
                break

        # 3. HTML tags / XML artifacts
        if re.search(r"<[^>]+>", tgt):
            reasons.append("R5_html_or_xml_tags")

        # 4. Alpha ratio check
        non_space_chars = [c for c in tgt if not c.isspace()]
        if non_space_chars:
            alpha_chars = [c for c in non_space_chars if c.isalpha()]
            alpha_ratio = len(alpha_chars) / len(non_space_chars)
            if alpha_ratio < self.config.min_alpha_ratio:
                reasons.append(
                    f"R5_low_alpha_ratio_{alpha_ratio:.2f}_below_{self.config.min_alpha_ratio}"
                )

        return reasons

    def evaluate_pair(
        self,
        src: str,
        tgt: str,
        disabled_rule: str | None = None,
        disabled_rules: Iterable[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """Evaluate a sentence pair across all 5 QC rules.

        Args:
            src: Source sentence.
            tgt: Synthetic target translation.
            disabled_rule: Single rule code to disable (e.g. 'R1' or 'R2') for ablation.
            disabled_rules: Iterable of rule codes to disable.

        Returns:
            tuple[bool, list[str]]: (is_accepted, rejection_reasons)
        """
        disabled = set()
        if disabled_rule:
            disabled.add(disabled_rule.strip().upper())
        if disabled_rules:
            for r in disabled_rules:
                disabled.add(str(r).strip().upper())

        norm_src = self._normalize(src)
        norm_tgt = self._normalize(tgt)

        src_words = self._extract_words(norm_src)
        tgt_words = self._extract_words(norm_tgt)

        all_rejections: list[str] = []

        # R4: Min/max length bounds (checked first for fast rejection)
        if "R4" not in disabled:
            all_rejections.extend(
                self._check_r4_length_bounds(norm_src, norm_tgt, src_words, tgt_words)
            )

        # R1: Length ratio
        if "R1" not in disabled:
            all_rejections.extend(
                self._check_r1_length_ratio(norm_src, norm_tgt, src_words, tgt_words)
            )

        # R2: Word and n-gram repetition
        if "R2" not in disabled:
            all_rejections.extend(self._check_r2_repetition(tgt_words))

        # R3: Source copy
        if "R3" not in disabled:
            all_rejections.extend(
                self._check_r3_source_copy(norm_src, norm_tgt, src_words, tgt_words)
            )

        # R5: Target language heuristics
        if "R5" not in disabled:
            all_rejections.extend(self._check_r5_target_heuristic(norm_tgt, tgt_words))

        is_accepted = len(all_rejections) == 0
        return is_accepted, all_rejections

    def filter_records(
        self,
        records: list[dict[str, Any]],
        disabled_rule: str | None = None,
        disabled_rules: Iterable[str] | None = None,
        src_key: str | None = None,
        tgt_key: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        """Filter a list of bilingual records.

        Args:
            records: List of record dictionaries.
            disabled_rule: Rule to disable for ablation (e.g. 'R1' or 'R2').
            disabled_rules: Multiple rules to disable.
            src_key: Custom key for source text. If None, auto-detected.
            tgt_key: Custom key for target text. If None, auto-detected.

        Returns:
            tuple[list[dict], list[dict], dict]:
                (kept_records, rejected_records, statistics)
        """
        kept: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        stats: dict[str, Any] = {
            "total_evaluated": len(records),
            "total_kept": 0,
            "total_rejected": 0,
            "acceptance_rate": 0.0,
            "rejections_by_rule": {
                "R1": 0,
                "R2": 0,
                "R3": 0,
                "R4": 0,
                "R5": 0,
            },
            "disabled_rules": sorted(
                list(
                    ({disabled_rule.strip().upper()} if disabled_rule else set())
                    | ({str(r).strip().upper() for r in disabled_rules} if disabled_rules else set())
                )
            ),
        }

        for record in records:
            # Extract src and tgt
            src = ""
            tgt = ""
            if src_key and tgt_key:
                src = str(record.get(src_key) or "")
                tgt = str(record.get(tgt_key) or "")
            else:
                # Common pairings in translation pipeline
                # If synthetic pair has explicit 'source_text' and 'target_text'
                if "source_text" in record and "target_text" in record:
                    src = str(record.get("source_text") or "")
                    tgt = str(record.get("target_text") or "")
                elif "vi_text" in record and "tay_text" in record:
                    # Depends on direction
                    dir_str = str(record.get("direction") or record.get("generation_direction") or "")
                    if "tyz-vi" in dir_str or "ty-vi" in dir_str:
                        src = str(record.get("tay_text") or "")
                        tgt = str(record.get("vi_text") or "")
                    else:
                        src = str(record.get("vi_text") or "")
                        tgt = str(record.get("tay_text") or "")
                elif "vi" in record and "tay" in record:
                    dir_str = str(record.get("direction") or record.get("generation_direction") or "")
                    if "tyz-vi" in dir_str or "ty-vi" in dir_str:
                        src = str(record.get("tay") or "")
                        tgt = str(record.get("vi") or "")
                    else:
                        src = str(record.get("vi") or "")
                        tgt = str(record.get("tay") or "")
                else:
                    src = str(record.get("src") or record.get("source") or "")
                    tgt = str(record.get("tgt") or record.get("target") or "")

            is_accepted, reasons = self.evaluate_pair(
                src=src,
                tgt=tgt,
                disabled_rule=disabled_rule,
                disabled_rules=disabled_rules,
            )

            if is_accepted:
                kept_record = dict(record)
                kept_record["qc_passed"] = True
                kept.append(kept_record)
            else:
                rejected_record = dict(record)
                rejected_record["qc_passed"] = False
                rejected_record["qc_rejection_reasons"] = reasons
                rejected.append(rejected_record)

                # Record rule counts
                for r_code in ("R1", "R2", "R3", "R4", "R5"):
                    if any(reason.startswith(r_code) for reason in reasons):
                        stats["rejections_by_rule"][r_code] += 1

        stats["total_kept"] = len(kept)
        stats["total_rejected"] = len(rejected)
        if len(records) > 0:
            stats["acceptance_rate"] = round(len(kept) / len(records), 4)

        return kept, rejected, stats


# Convenience alias
QCFilter = QualityControlFilter
