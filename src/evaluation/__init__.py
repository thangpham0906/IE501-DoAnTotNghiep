"""Evaluation package for Vietnamese-Tay machine translation pipeline.

Provides:
- metrics: Pure-Python BLEU and chrF / chrF++ compatible with SacreBLEU format.
- evaluator: TranslationEvaluator for multi-model bidirectional benchmarking.
- human_eval: Tools for 4-system blind human evaluation and Cohen's Kappa agreement.
- error_analysis: Automated classification of translation defects (repetition, length, omission, encoding).
"""

from src.evaluation.error_analysis import (
    CorpusErrorReport,
    ErrorAnalyzer,
    ErrorCategory,
    SentenceErrorReport,
    Severity,
    TranslationError,
    batch_error_analysis,
    classify_translation_errors,
)
from src.evaluation.evaluator import (
    ComparativeEvaluationReport,
    ModelEvaluationScore,
    TranslationEvaluator,
)
from src.evaluation.human_eval import (
    BlindTranslationItem,
    HumanEvaluationBundle,
    HumanEvaluationSampler,
    KappaResult,
    calculate_cohens_kappa,
    export_guidelines_md,
    export_human_eval_sheet_csv,
    export_human_eval_sheet_jsonl,
    export_unblind_key,
    sample_blind_human_evaluation,
    unblind_evaluation_results,
)
from src.evaluation.metrics import (
    BLEUResult,
    CHRFResult,
    EvaluationMetrics,
    Tokenizer13a,
    compute_bleu,
    compute_chrf,
    compute_chrf_plus_plus,
    corpus_bleu,
    corpus_chrf,
    evaluate_metrics,
    sentence_bleu,
    sentence_chrf,
    tokenize_13a,
    tokenize_whitespace,
)

__all__ = [
    # Metrics
    "BLEUResult",
    "CHRFResult",
    "EvaluationMetrics",
    "Tokenizer13a",
    "tokenize_13a",
    "tokenize_whitespace",
    "compute_bleu",
    "compute_chrf",
    "compute_chrf_plus_plus",
    "corpus_bleu",
    "sentence_bleu",
    "corpus_chrf",
    "sentence_chrf",
    "evaluate_metrics",
    # Evaluator
    "TranslationEvaluator",
    "ModelEvaluationScore",
    "ComparativeEvaluationReport",
    # Human Evaluation
    "BlindTranslationItem",
    "HumanEvaluationBundle",
    "KappaResult",
    "HumanEvaluationSampler",
    "calculate_cohens_kappa",
    "sample_blind_human_evaluation",
    "export_human_eval_sheet_csv",
    "export_human_eval_sheet_jsonl",
    "export_unblind_key",
    "export_guidelines_md",
    "unblind_evaluation_results",
    # Error Analysis
    "ErrorCategory",
    "Severity",
    "TranslationError",
    "SentenceErrorReport",
    "CorpusErrorReport",
    "ErrorAnalyzer",
    "classify_translation_errors",
    "batch_error_analysis",
]
