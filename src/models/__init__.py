"""Models package for Vietnamese-Tay machine translation pipeline.

Provides configurations, tokenizer wrappers, PyTorch dataset and trainer,
and inference adapter contracts.
"""

from src.models.config import (
    EXPERIMENT_SPECS,
    Direction,
    ExperimentName,
    ExperimentSpec,
    ModelConfig,
    TrainingConfig,
)
from src.models.dataset import (
    TranslationCollator,
    TranslationDataset,
    collate_translation_batch,
    extract_pair,
)
from src.models.inference_adapter import (
    AdapterStatus,
    EmptyInputError,
    InferenceAdapter,
    InferenceTimeoutError,
    InvalidDirectionError,
    MockTranslator,
    ModelNotReadyError,
    TextTooLongError,
    TranslationInferenceAdapter,
    TranslationResult,
)
from src.models.tokenizer import (
    NLLBTokenizerWrapper,
    TAY_SPECIAL_TOKENS,
    TayTokenizerWrapper,
    prepare_model_for_tokenizer,
)
from src.models.trainer import (
    LocalSeq2SeqTransformer,
    MockSeq2SeqModel,
    PositionalEncoding,
    TranslationTrainer,
)

__all__ = [
    # Config
    "Direction",
    "ModelConfig",
    "TrainingConfig",
    "ExperimentName",
    "ExperimentSpec",
    "EXPERIMENT_SPECS",
    # Tokenizer
    "TayTokenizerWrapper",
    "NLLBTokenizerWrapper",
    "TAY_SPECIAL_TOKENS",
    "prepare_model_for_tokenizer",
    # Dataset
    "TranslationDataset",
    "TranslationCollator",
    "collate_translation_batch",
    "extract_pair",
    # Trainer
    "TranslationTrainer",
    "LocalSeq2SeqTransformer",
    "PositionalEncoding",
    "MockSeq2SeqModel",
    # Inference Adapter
    "TranslationInferenceAdapter",
    "InferenceAdapter",
    "MockTranslator",
    "TranslationResult",
    "AdapterStatus",
    "EmptyInputError",
    "TextTooLongError",
    "InvalidDirectionError",
    "ModelNotReadyError",
    "InferenceTimeoutError",
]
