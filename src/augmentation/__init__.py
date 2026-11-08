"""Data Augmentation module for Vietnamese-Tay translation.

Includes:
- BackTranslator: Generation of synthetic bilingual pairs (dataset U) via reverse inference.
- QCFilter / QualityControlFilter: 5-rule filtering (R1 to R5) with ablation support.
- AugmentationSampler / sample_without_replacement: Deterministic sampling for E2, E1-M, A1, A2.
- AugmentationPipeline / run_augmentation_pipeline: End-to-end orchestration.
"""

from src.augmentation.back_translation import BackTranslator
from src.augmentation.pipeline import AugmentationPipeline, run_augmentation_pipeline
from src.augmentation.qc_filters import QCFilter, QCFilterConfig, QualityControlFilter
from src.augmentation.sampler import AugmentationSampler, sample_without_replacement

__all__ = [
    "BackTranslator",
    "QCFilter",
    "QualityControlFilter",
    "QCFilterConfig",
    "AugmentationSampler",
    "sample_without_replacement",
    "AugmentationPipeline",
    "run_augmentation_pipeline",
]
