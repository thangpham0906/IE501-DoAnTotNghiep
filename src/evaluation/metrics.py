"""Evaluation metrics for Machine Translation (BLEU, chrF, chrF++).

Utilizes official SacreBLEU standards (Papineni et al., 2002; Post, 2018; Popović, 2015, 2017)
with full signature reporting, Unicode NFC normalization, and graceful handling of edge cases.
Includes a pure-Python reference fallback for standalone environments. Note: for official
benchmark reporting and absolute compliance across arbitrary multilingual edge cases,
install the official sacrebleu library (sacrebleu>=2.4.0).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Sequence

# Official sacrebleu library discovery
try:
    import sacrebleu
    _HAS_SACREBLEU = True
    _SACREBLEU_VERSION = getattr(sacrebleu, "__version__", "2.6.0")
except ImportError:
    sacrebleu = None  # type: ignore
    _HAS_SACREBLEU = False
    _SACREBLEU_VERSION = "2.6.0-standalone-fallback"

STANDALONE_SUPPORTED_BLEU_TOKENIZERS = {"13a", "whitespace", "none"}
STANDALONE_SUPPORTED_BLEU_SMOOTH = {"exp", "floor", "add-k", "none"}
_STANDALONE_EXPLICIT_VERSION = "2.6.0-standalone"
_STANDALONE_FALLBACK_VERSION = "2.6.0-standalone-fallback"


# ==============================================================================
# Tokenizers (Compatible with SacreBLEU 13a standard)
# ==============================================================================

class Tokenizer13a:
    """SacreBLEU 13a standard tokenizer implemented with pure Python regex.

    Matches mteval-v13a tokenization used in WMT benchmarks.
    """

    _REGEX_SPLITS = [
        # Western / Universal punctuation splitting
        (re.compile(r"([\{-\~\[-\` -\&\(-\+\:-\@\/])"), r" \1 "),
        # Tokenize period and comma unless preceded by digit
        (re.compile(r"([^0-9])([\.,])"), r"\1 \2 "),
        # Tokenize period and comma unless followed by digit
        (re.compile(r"([\.,])([^0-9])"), r" \1 \2"),
        # Tokenize dash when preceded by digit
        (re.compile(r"([0-9])(-)"), r"\1 \2 "),
    ]

    @classmethod
    def tokenize(cls, line: str) -> list[str]:
        """Tokenize a string into list of word/punctuation tokens."""
        line = line.replace("<skipped>", "")
        line = line.replace("-\n", "")
        line = line.replace("\n", " ")

        if "&" in line:
            line = line.replace("&quot;", '"')
            line = line.replace("&amp;", "&")
            line = line.replace("&lt;", "<")
            line = line.replace("&gt;", ">")

        line = f" {line} "
        for pattern, replacement in cls._REGEX_SPLITS:
            line = pattern.sub(replacement, line)

        return line.strip().split()


def tokenize_13a(line: str) -> list[str]:
    """Tokenize line using SacreBLEU 13a standard tokenizer."""
    return Tokenizer13a.tokenize(line)


def tokenize_whitespace(line: str) -> list[str]:
    """Tokenize line using whitespace separation only."""
    return line.strip().split()


# Punctuation set for chrF word-level extraction
CHRF_PUNCTS = {
    "-", "}", "*", "^", "[", "_", "$", ".", "&", "@", ">", "{",
    "(", ";", ":", ",", "~", "?", "=", "|", "\\", "+", ")", "%",
    "/", "!", "]", "#", "<", "`", "'", '"',
}


def _chrf_remove_punctuation(sent: str) -> list[str]:
    """Separates out boundary punctuation from words for chrF++ word n-grams."""
    tokenized: list[str] = []
    for w in sent.split():
        if len(w) == 1:
            tokenized.append(w)
        else:
            if w[-1] in CHRF_PUNCTS:
                tokenized.extend([w[:-1], w[-1]])
            elif w[0] in CHRF_PUNCTS:
                tokenized.extend([w[0], w[1:]])
            else:
                tokenized.append(w)
    return tokenized


def normalize_unicode(text: str) -> str:
    """Normalize text to canonical Unicode NFC form.

    Crucial for Vietnamese and Tay to prevent artificial 0-matches between
    decomposed (NFD) and composed (NFC) diacritical vowel representations.
    """
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)


# ==============================================================================
# Metric Data Containers
# ==============================================================================

@dataclass
class BLEUResult:
    """Standard container for BLEU metric computation results."""

    score: float
    counts: list[int]
    totals: list[int]
    precisions: list[float]
    bp: float
    sys_len: int
    ref_len: int
    smooth_method: str = "exp"
    signature: str = ""

    def format_str(self) -> str:
        """Formatted string representation matching SacreBLEU output style."""
        prec_str = "/".join(f"{p:.1f}" for p in self.precisions)
        ratio = self.sys_len / self.ref_len if self.ref_len > 0 else 0.0
        sig_str = f" [{self.signature}]" if self.signature else ""
        return (
            f"BLEU = {self.score:.2f} {prec_str} "
            f"(BP = {self.bp:.3f} ratio = {ratio:.3f} "
            f"hyp_len = {self.sys_len} ref_len = {self.ref_len}){sig_str}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return asdict(self)


@dataclass
class CHRFResult:
    """Standard container for chrF and chrF++ metric computation results."""

    score: float
    char_order: int
    word_order: int
    beta: float
    char_prec: float = 0.0
    char_rec: float = 0.0
    word_prec: float | None = None
    word_rec: float | None = None
    signature: str = ""

    def format_str(self) -> str:
        """Formatted string representation."""
        mode_str = "chrF++" if self.word_order > 0 else "chrF"
        sig_str = f" [{self.signature}]" if self.signature else ""
        return (
            f"{mode_str} = {self.score:.2f} "
            f"(char_order = {self.char_order}, word_order = {self.word_order}, "
            f"beta = {self.beta:.1f}){sig_str}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return asdict(self)


@dataclass
class EvaluationMetrics:
    """Consolidated translation quality metrics."""

    bleu: BLEUResult
    chrf: CHRFResult
    chrf_pp: CHRFResult

    def to_dict(self) -> dict[str, Any]:
        """Convert composite metrics to nested dictionary."""
        return {
            "bleu": self.bleu.to_dict(),
            "chrf": self.chrf.to_dict(),
            "chrf_plus_plus": self.chrf_pp.to_dict(),
        }


# ==============================================================================
# Helper Functions for N-gram Counting & Reference Normalization
# ==============================================================================

def _extract_word_ngrams(tokens: list[str], n: int) -> Counter[tuple[str, ...]]:
    """Extract word-level n-grams from a token sequence."""
    if len(tokens) < n or n <= 0:
        return Counter()
    return Counter(tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1))


def _extract_char_ngrams(
    line: str,
    max_order: int,
    whitespace: bool = False,
) -> list[Counter[str]]:
    """Extract character n-grams from 1 to max_order."""
    if not whitespace:
        line = "".join(line.split())

    counters: list[Counter[str]] = []
    line_len = len(line)
    for n in range(1, max_order + 1):
        if line_len < n:
            counters.append(Counter())
        else:
            counters.append(Counter(line[i : i + n] for i in range(line_len - n + 1)))
    return counters


def _normalize_refs(
    references: Sequence[str] | Sequence[Sequence[str]],
    num_samples: int,
) -> list[list[str]]:
    """Normalize references into a list of references per hypothesis.

    Supports:
    1. Single reference per item: ['ref1', 'ref2']
    2. Multiple references per item: [['ref1a', 'ref1b'], ['ref2a', 'ref2b']]
    3. SacreBLEU reference stream format: [['ref1a', 'ref2a'], ['ref1b', 'ref2b']]
    """
    if not references or num_samples == 0:
        return [[] for _ in range(num_samples)]

    # Case 1: Flat list of strings: ["ref1", "ref2", ...]
    if isinstance(references[0], str):
        return [[normalize_unicode(str(ref))] for ref in references]  # type: ignore

    # Case 2: SacreBLEU reference streams: list of K streams, each having num_samples elements
    if len(references) != num_samples and all(len(stream) == num_samples for stream in references):
        return [
            [normalize_unicode(str(stream[i])) for stream in references]
            for i in range(num_samples)
        ]  # type: ignore

    # Case 3: List of references per hypothesis: [["ref1a", "ref1b"], ...]
    return [
        [normalize_unicode(str(r)) for r in ref_list]
        for ref_list in references
    ]  # type: ignore


# ==============================================================================
# BLEU Computation (SacreBLEU standard)
# ==============================================================================

def compute_bleu(
    hypotheses: str | Sequence[str],
    references: str | Sequence[str] | Sequence[Sequence[str]],
    smooth_method: str = "exp",
    smooth_value: float | None = None,
    max_ngram_order: int = 4,
    tokenize: str = "13a",
    lowercase: bool = False,
    effective_order: bool = False,
    engine: str = "auto",
) -> BLEUResult:
    """Calculate corpus or sentence BLEU score using official SacreBLEU or pure-Python standalone engine.

    Args:
        hypotheses: Single translation hypothesis or list of hypotheses.
        references: Single reference, list of references, or list of multi-references.
        smooth_method: Smoothing method ('exp', 'floor', 'add-k', 'none').
        smooth_value: Value for 'floor' (default 0.1) or 'add-k' (default 1.0).
        max_ngram_order: Maximum n-gram order (default 4).
        tokenize: Tokenizer type ('13a', 'none', 'whitespace').
        lowercase: Lowercase all strings before computing.
        effective_order: Scale maximum order to observed tokens if shorter than max_ngram_order.
        engine: Computation engine ('auto', 'sacrebleu', 'standalone').

    Returns:
        BLEUResult instance with score in [0, 100] and reproducible signature.
    """
    valid_engines = ("auto", "sacrebleu", "standalone")
    if engine not in valid_engines:
        raise ValueError(f"Invalid engine '{engine}'. Supported engines: {valid_engines}")

    use_official = False
    if engine == "sacrebleu":
        if not _HAS_SACREBLEU or sacrebleu is None:
            raise RuntimeError("SacreBLEU library is not installed in the environment (sacrebleu>=2.4.0 required).")
        use_official = True
    elif engine == "auto":
        use_official = (_HAS_SACREBLEU and sacrebleu is not None)
    elif engine == "standalone":
        use_official = False

    if isinstance(hypotheses, str):
        hyps = [normalize_unicode(hypotheses)]
    else:
        hyps = [normalize_unicode(str(h)) for h in hypotheses]

    if isinstance(references, str):
        refs = [[normalize_unicode(references)]]
    else:
        refs = _normalize_refs(references, len(hyps))

    # Validate input dimensions
    if len(hyps) != len(refs):
        raise ValueError(
            f"Length mismatch: {len(hyps)} hypotheses vs {len(refs)} reference groups"
        )
    if max_ngram_order <= 0:
        raise ValueError(f"max_ngram_order must be positive integer, got {max_ngram_order}")

    # Empty corpus edge case
    if len(hyps) == 0:
        sig_ver = (
            _SACREBLEU_VERSION
            if use_official
            else (_STANDALONE_EXPLICIT_VERSION if engine == "standalone" else _STANDALONE_FALLBACK_VERSION)
        )
        return BLEUResult(
            score=0.0,
            counts=[0] * max_ngram_order,
            totals=[0] * max_ngram_order,
            precisions=[0.0] * max_ngram_order,
            bp=0.0,
            sys_len=0,
            ref_len=0,
            smooth_method=smooth_method,
            signature=f"nrefs:0|case:{'lc' if lowercase else 'mixed'}|eff:{'yes' if effective_order else 'no'}|tok:{tokenize}|smooth:{smooth_method}|version:{sig_ver}",
        )

    # --------------------------------------------------------------------------
    # Official SacreBLEU Library Execution Path
    # --------------------------------------------------------------------------
    if use_official and sacrebleu is not None:
        max_refs = max(len(r_list) for r_list in refs)
        if max_refs == 0:
            sacre_refs = [[""] * len(hyps)]
        else:
            sacre_refs = []
            for ref_idx in range(max_refs):
                stream = [
                    r_list[ref_idx] if ref_idx < len(r_list) else ""
                    for r_list in refs
                ]
                sacre_refs.append(stream)

        try:
            bleu_metric = sacrebleu.BLEU(
                smooth_method=smooth_method,
                smooth_value=smooth_value,
                max_ngram_order=max_ngram_order,
                tokenize=tokenize,
                lowercase=lowercase,
                effective_order=effective_order,
            )
        except (KeyError, ValueError) as err:
            raise ValueError(f"SacreBLEU configuration error: {err}") from err
        except Exception as err:
            raise RuntimeError(f"SacreBLEU runtime initialization error: {err}") from err

        score_obj = bleu_metric.corpus_score(hyps, sacre_refs)
        signature = str(bleu_metric.get_signature())

        return BLEUResult(
            score=float(score_obj.score),
            counts=list(score_obj.counts),
            totals=list(score_obj.totals),
            precisions=list(score_obj.precisions),
            bp=float(score_obj.bp),
            sys_len=int(score_obj.sys_len),
            ref_len=int(score_obj.ref_len),
            smooth_method=smooth_method,
            signature=signature,
        )

    # --------------------------------------------------------------------------
    # Pure-Python Standalone Reference Implementation
    # --------------------------------------------------------------------------
    if tokenize not in STANDALONE_SUPPORTED_BLEU_TOKENIZERS:
        raise ValueError(
            f"Unsupported tokenize option '{tokenize}' for standalone BLEU engine. "
            f"Supported: {sorted(STANDALONE_SUPPORTED_BLEU_TOKENIZERS)}"
        )
    if smooth_method not in STANDALONE_SUPPORTED_BLEU_SMOOTH:
        raise ValueError(
            f"Unsupported smooth_method '{smooth_method}' for standalone BLEU engine. "
            f"Supported: {sorted(STANDALONE_SUPPORTED_BLEU_SMOOTH)}"
        )
    if smooth_value is None:
        if smooth_method == "floor":
            smooth_value = 0.1
        elif smooth_method == "add-k":
            smooth_value = 1.0

    tok_func = Tokenizer13a.tokenize if tokenize == "13a" else tokenize_whitespace

    correct_counts = [0] * max_ngram_order
    total_counts = [0] * max_ngram_order
    sys_len_total = 0
    ref_len_total = 0

    for hyp_str, ref_list in zip(hyps, refs):
        if lowercase:
            hyp_str = hyp_str.lower()
            ref_list = [r.lower() for r in ref_list]

        hyp_tokens = tok_func(hyp_str)
        sys_len = len(hyp_tokens)
        sys_len_total += sys_len

        ref_tokens_list = [tok_func(r) for r in ref_list if r.strip()]
        ref_lens = [len(r_toks) for r_toks in ref_tokens_list]

        if ref_lens:
            closest_ref_len = min(ref_lens, key=lambda r_len: (abs(r_len - sys_len), r_len))
            ref_len_total += closest_ref_len
        else:
            ref_len_total += 0

        for n in range(1, max_ngram_order + 1):
            hyp_ngrams = _extract_word_ngrams(hyp_tokens, n)
            total_counts[n - 1] += sum(hyp_ngrams.values())

            max_ref_counts: Counter[tuple[str, ...]] = Counter()
            for r_toks in ref_tokens_list:
                r_ngrams = _extract_word_ngrams(r_toks, n)
                for ngram, count in r_ngrams.items():
                    if count > max_ref_counts[ngram]:
                        max_ref_counts[ngram] = count

            clipped = 0
            for ngram, count in hyp_ngrams.items():
                clipped += min(count, max_ref_counts[ngram])
            correct_counts[n - 1] += clipped

    # Brevity penalty
    bp = 1.0
    if sys_len_total < ref_len_total:
        bp = math.exp(1 - ref_len_total / sys_len_total) if sys_len_total > 0 else 0.0

    max_nrefs = max((len(r) for r in refs), default=1)
    sig_ver = (
        _STANDALONE_EXPLICIT_VERSION if engine == "standalone" else _STANDALONE_FALLBACK_VERSION
    )
    sig = (
        f"nrefs:{max_nrefs}|case:{'lc' if lowercase else 'mixed'}|"
        f"eff:{'yes' if effective_order else 'no'}|tok:{tokenize}|"
        f"smooth:{smooth_method}|version:{sig_ver}"
    )

    if not any(correct_counts):
        return BLEUResult(
            score=0.0,
            counts=correct_counts,
            totals=total_counts,
            precisions=[0.0] * max_ngram_order,
            bp=bp,
            sys_len=sys_len_total,
            ref_len=ref_len_total,
            smooth_method=smooth_method,
            signature=sig,
        )

    precisions = [0.0] * max_ngram_order
    smooth_mteval = 1.0
    eff_order = max_ngram_order

    for n in range(1, max_ngram_order + 1):
        c = correct_counts[n - 1]
        t = total_counts[n - 1]

        if smooth_method == "add-k" and n > 1 and smooth_value is not None:
            c += smooth_value
            t += smooth_value

        if t == 0:
            break

        if effective_order:
            eff_order = n

        if c == 0:
            if smooth_method == "exp":
                smooth_mteval *= 2
                precisions[n - 1] = 100.0 / (smooth_mteval * t)
            elif smooth_method == "floor" and smooth_value is not None:
                precisions[n - 1] = 100.0 * smooth_value / t
            elif smooth_method == "none":
                precisions[n - 1] = 0.0
        else:
            precisions[n - 1] = 100.0 * c / t

    if eff_order == 0:
        score = 0.0
    else:
        log_prec_sum = 0.0
        for p in precisions[:eff_order]:
            if p <= 0.0:
                log_prec_sum = -math.inf
                break
            log_prec_sum += math.log(p)

        if math.isinf(log_prec_sum):
            score = 0.0
        else:
            score = bp * math.exp(log_prec_sum / eff_order)

    return BLEUResult(
        score=score,
        counts=correct_counts,
        totals=total_counts,
        precisions=precisions,
        bp=bp,
        sys_len=sys_len_total,
        ref_len=ref_len_total,
        smooth_method=smooth_method,
        signature=sig,
    )


def corpus_bleu(
    hypotheses: Sequence[str],
    references: Sequence[str] | Sequence[Sequence[str]],
    **kwargs: Any,
) -> BLEUResult:
    """Convenience alias for corpus-level BLEU."""
    return compute_bleu(hypotheses, references, **kwargs)


def sentence_bleu(
    hypothesis: str,
    reference: str | Sequence[str],
    **kwargs: Any,
) -> BLEUResult:
    """Convenience alias for sentence-level BLEU with effective_order support."""
    kwargs.setdefault("effective_order", True)
    kwargs.setdefault("smooth_method", "exp")
    refs = [reference] if isinstance(reference, str) else list(reference)
    return compute_bleu([hypothesis], [refs], **kwargs)


# ==============================================================================
# chrF and chrF++ Computation (Popović 2015, 2017)
# ==============================================================================

def compute_chrf(
    hypotheses: str | Sequence[str],
    references: str | Sequence[str] | Sequence[Sequence[str]],
    char_order: int = 6,
    word_order: int = 0,
    beta: float = 2.0,
    lowercase: bool = False,
    whitespace: bool = False,
    eps_smoothing: bool = False,
    engine: str = "auto",
) -> CHRFResult:
    """Compute chrF (word_order=0) or chrF++ (word_order=2) score.

    Args:
        hypotheses: Translation hypothesis or list of hypotheses.
        references: Gold reference or list of references.
        char_order: Character n-gram max order (default 6).
        word_order: Word n-gram max order (0 for chrF, 2 for chrF++).
        beta: Parameter weighting recall vs precision (default 2.0, recall weighted higher).
        lowercase: Lowercase inputs before computation.
        whitespace: Include whitespace in character n-grams if True.
        eps_smoothing: Use epsilon smoothing per segment instead of effective order.
        engine: Computation engine ('auto', 'sacrebleu', 'standalone').

    Returns:
        CHRFResult instance with score in [0, 100] and reproducible signature.
    """
    valid_engines = ("auto", "sacrebleu", "standalone")
    if engine not in valid_engines:
        raise ValueError(f"Invalid engine '{engine}'. Supported engines: {valid_engines}")

    use_official = False
    if engine == "sacrebleu":
        if not _HAS_SACREBLEU or sacrebleu is None:
            raise RuntimeError("SacreBLEU library is not installed in the environment (sacrebleu>=2.4.0 required).")
        use_official = True
    elif engine == "auto":
        use_official = (_HAS_SACREBLEU and sacrebleu is not None)
    elif engine == "standalone":
        use_official = False

    if isinstance(hypotheses, str):
        hyps = [normalize_unicode(hypotheses)]
    else:
        hyps = [normalize_unicode(str(h)) for h in hypotheses]

    if isinstance(references, str):
        refs = [[normalize_unicode(references)]]
    else:
        refs = _normalize_refs(references, len(hyps))

    if len(hyps) != len(refs):
        raise ValueError(
            f"Length mismatch: {len(hyps)} hypotheses vs {len(refs)} reference groups"
        )
    if char_order <= 0:
        raise ValueError(f"char_order must be positive integer, got {char_order}")
    if word_order < 0:
        raise ValueError(f"word_order must be non-negative integer, got {word_order}")
    if beta <= 0:
        raise ValueError(f"beta must be positive float, got {beta}")

    # Empty input edge case
    if len(hyps) == 0:
        sig_ver = (
            _SACREBLEU_VERSION
            if use_official
            else (_STANDALONE_EXPLICIT_VERSION if engine == "standalone" else _STANDALONE_FALLBACK_VERSION)
        )
        return CHRFResult(
            score=0.0,
            char_order=char_order,
            word_order=word_order,
            beta=beta,
            signature=f"nrefs:0|case:{'lc' if lowercase else 'mixed'}|eff:yes|nc:{char_order}|nw:{word_order}|space:{'yes' if whitespace else 'no'}|version:{sig_ver}",
        )

    # --------------------------------------------------------------------------
    # Official SacreBLEU Library Execution Path
    # --------------------------------------------------------------------------
    if use_official and sacrebleu is not None:
        max_refs = max(len(r_list) for r_list in refs)
        if max_refs == 0:
            sacre_refs = [[""] * len(hyps)]
        else:
            sacre_refs = []
            for ref_idx in range(max_refs):
                stream = [
                    r_list[ref_idx] if ref_idx < len(r_list) else ""
                    for r_list in refs
                ]
                sacre_refs.append(stream)

        try:
            chrf_metric = sacrebleu.CHRF(
                char_order=char_order,
                word_order=word_order,
                beta=beta,
                lowercase=lowercase,
                whitespace=whitespace,
                eps_smoothing=eps_smoothing,
            )
        except (KeyError, ValueError) as err:
            raise ValueError(f"SacreBLEU CHRF configuration error: {err}") from err
        except Exception as err:
            raise RuntimeError(f"SacreBLEU CHRF runtime initialization error: {err}") from err

        score_obj = chrf_metric.corpus_score(hyps, sacre_refs)
        signature = str(chrf_metric.get_signature())

        return CHRFResult(
            score=float(score_obj.score),
            char_order=char_order,
            word_order=word_order,
            beta=beta,
            char_prec=getattr(score_obj, "char_prec", 0.0),
            char_rec=getattr(score_obj, "char_rec", 0.0),
            word_prec=getattr(score_obj, "word_prec", None),
            word_rec=getattr(score_obj, "word_rec", None),
            signature=signature,
        )

    # --------------------------------------------------------------------------
    # Pure-Python Standalone Reference Implementation
    # --------------------------------------------------------------------------
    if char_order <= 0:
        raise ValueError(f"char_order must be positive integer, got {char_order}")
    if word_order < 0:
        raise ValueError(f"word_order must be non-negative integer, got {word_order}")
    if beta <= 0:
        raise ValueError(f"beta must be positive float, got {beta}")

    num_orders = char_order + word_order
    total_stats = [0] * (3 * num_orders)

    for hyp_str, ref_list in zip(hyps, refs):
        if lowercase:
            hyp_str = hyp_str.lower()
            ref_list = [r.lower() for r in ref_list]

        hyp_char_ngrams = _extract_char_ngrams(hyp_str, char_order, whitespace)
        all_hyp_ngrams = list(hyp_char_ngrams)

        if word_order > 0:
            hyp_words = _chrf_remove_punctuation(hyp_str)
            for w_n in range(1, word_order + 1):
                all_hyp_ngrams.append(_extract_word_ngrams(hyp_words, w_n))

        best_stats: list[int] = []
        best_f = -1.0

        for r_str in ref_list:
            ref_char_ngrams = _extract_char_ngrams(r_str, char_order, whitespace)
            all_ref_ngrams = list(ref_char_ngrams)
            if word_order > 0:
                ref_words = _chrf_remove_punctuation(r_str)
                for w_n in range(1, word_order + 1):
                    all_ref_ngrams.append(_extract_word_ngrams(ref_words, w_n))

            seg_stats: list[int] = []
            for h_counter, r_counter in zip(all_hyp_ngrams, all_ref_ngrams):
                n_hyp = sum(h_counter.values())
                n_ref = sum(r_counter.values())
                n_match = sum(min(count, r_counter[ng]) for ng, count in h_counter.items())
                seg_stats.extend([n_hyp, n_ref, n_match])

            seg_f = _calculate_chrf_f_score(seg_stats, num_orders, beta, eps_smoothing)
            if seg_f > best_f:
                best_f = seg_f
                best_stats = seg_stats

        if best_stats:
            for idx, val in enumerate(best_stats):
                total_stats[idx] += val

    final_score = _calculate_chrf_f_score(total_stats, num_orders, beta, eps_smoothing)

    char_prec_sum, char_rec_sum, char_count = 0.0, 0.0, 0
    for i in range(char_order):
        n_hyp, n_ref, n_match = total_stats[3 * i : 3 * i + 3]
        if n_hyp > 0:
            char_prec_sum += n_match / n_hyp
        if n_ref > 0:
            char_rec_sum += n_match / n_ref
        char_count += 1
    char_prec = (char_prec_sum / char_count) * 100.0 if char_count > 0 else 0.0
    char_rec = (char_rec_sum / char_count) * 100.0 if char_count > 0 else 0.0

    word_prec, word_rec = None, None
    if word_order > 0:
        w_prec_sum, w_rec_sum, w_count = 0.0, 0.0, 0
        for i in range(char_order, num_orders):
            n_hyp, n_ref, n_match = total_stats[3 * i : 3 * i + 3]
            if n_hyp > 0:
                w_prec_sum += n_match / n_hyp
            if n_ref > 0:
                w_rec_sum += n_match / n_ref
            w_count += 1
        word_prec = (w_prec_sum / w_count) * 100.0 if w_count > 0 else 0.0
        word_rec = (w_rec_sum / w_count) * 100.0 if w_count > 0 else 0.0

    max_nrefs = max((len(r) for r in refs), default=1)
    sig_ver = (
        _STANDALONE_EXPLICIT_VERSION if engine == "standalone" else _STANDALONE_FALLBACK_VERSION
    )
    sig = (
        f"nrefs:{max_nrefs}|case:{'lc' if lowercase else 'mixed'}|eff:yes|"
        f"nc:{char_order}|nw:{word_order}|space:{'yes' if whitespace else 'no'}|"
        f"version:{sig_ver}"
    )

    return CHRFResult(
        score=final_score,
        char_order=char_order,
        word_order=word_order,
        beta=beta,
        char_prec=char_prec,
        char_rec=char_rec,
        word_prec=word_prec,
        word_rec=word_rec,
        signature=sig,
    )


def _calculate_chrf_f_score(
    stats: list[int],
    order: int,
    beta: float,
    eps_smoothing: bool = False,
) -> float:
    """Calculate F-beta score from flattened [n_hyp, n_ref, n_match] statistics."""
    eps = 1e-16
    factor = beta ** 2
    avg_prec, avg_rec = 0.0, 0.0
    effective_order = 0
    score = 0.0

    for i in range(order):
        n_hyp, n_ref, n_match = stats[3 * i : 3 * i + 3]
        prec = n_match / n_hyp if n_hyp > 0 else eps
        rec = n_match / n_ref if n_ref > 0 else eps

        denom = factor * prec + rec
        score += ((1 + factor) * prec * rec / denom) if denom > 0 else eps

        if n_hyp > 0 and n_ref > 0:
            avg_prec += prec
            avg_rec += rec
            effective_order += 1

    if eps_smoothing:
        return 100.0 * score / order

    if effective_order == 0:
        return 0.0

    avg_prec /= effective_order
    avg_rec /= effective_order

    if (avg_prec + avg_rec) > 0:
        f_score = (1 + factor) * avg_prec * avg_rec / ((factor * avg_prec) + avg_rec)
        return 100.0 * f_score

    return 0.0


def compute_chrf_plus_plus(
    hypotheses: str | Sequence[str],
    references: str | Sequence[str] | Sequence[Sequence[str]],
    char_order: int = 6,
    word_order: int = 2,
    beta: float = 2.0,
    **kwargs: Any,
) -> CHRFResult:
    """Convenience helper for chrF++ score (character order 6 + word order 2)."""
    return compute_chrf(
        hypotheses=hypotheses,
        references=references,
        char_order=char_order,
        word_order=word_order,
        beta=beta,
        **kwargs,
    )


def corpus_chrf(
    hypotheses: Sequence[str],
    references: Sequence[str] | Sequence[Sequence[str]],
    **kwargs: Any,
) -> CHRFResult:
    """Convenience alias for corpus chrF."""
    return compute_chrf(hypotheses, references, **kwargs)


def sentence_chrf(
    hypothesis: str,
    reference: str | Sequence[str],
    **kwargs: Any,
) -> CHRFResult:
    """Convenience alias for sentence chrF."""
    refs = [reference] if isinstance(reference, str) else list(reference)
    return compute_chrf([hypothesis], [refs], **kwargs)


# ==============================================================================
# Unified Evaluation Wrapper
# ==============================================================================

def evaluate_metrics(
    hypotheses: str | Sequence[str],
    references: str | Sequence[str] | Sequence[Sequence[str]],
    lowercase: bool = False,
    engine: str = "auto",
) -> EvaluationMetrics:
    """Calculate all standard metrics (BLEU, chrF, chrF++) simultaneously.

    Args:
        hypotheses: Single sentence or list of candidate translations.
        references: Single sentence, list of single refs, or list of multi-refs.
        lowercase: If True, lowercase strings before computing.
        engine: Computation engine ('auto', 'sacrebleu', 'standalone').

    Returns:
        EvaluationMetrics instance containing BLEU, chrF, and chrF++ results with signatures.
    """
    bleu_res = compute_bleu(hypotheses, references, lowercase=lowercase, engine=engine)
    chrf_res = compute_chrf(hypotheses, references, word_order=0, lowercase=lowercase, engine=engine)
    chrf_pp_res = compute_chrf_plus_plus(hypotheses, references, lowercase=lowercase, engine=engine)

    return EvaluationMetrics(
        bleu=bleu_res,
        chrf=chrf_res,
        chrf_pp=chrf_pp_res,
    )
