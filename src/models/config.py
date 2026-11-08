"""Model and training configurations for Vietnamese-Tay translation pipeline.

Supports 6 experimental configurations:
- E0: Baseline trained on verified bilingual data only.
- E1: E0 + uncurated synthetic back-translation data (U).
- E2: E0 + N synthetic samples passing all 5 QC filters.
- E1-M: E0 + N synthetic samples randomly drawn from U without replacement (control).
- A1: E0 + N synthetic samples without QC rule R1 (ablation 1).
- A2: E0 + N synthetic samples without QC rule R2 (ablation 2).

Supports bidirectional translation:
- Vietnamese to Tay (vi-tyz / vi->ty / <2ty>)
- Tay to Vietnamese (tyz-vi / ty->vi / <2vi>)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Direction(str, Enum):
    """Translation directions for Vietnamese-Tay."""

    VI_TO_TAY = "vi-tyz"
    TAY_TO_VI = "tyz-vi"

    @classmethod
    def normalize(cls, value: str | Direction | tuple[str, str]) -> Direction:
        """Normalize various direction string representations into Direction enum.

        Supports:
        - "vi-tyz", "tyz-vi"
        - "vi->ty", "ty->vi", "vi->tyz", "tyz->vi"
        - "vi_to_ty", "ty_to_vi", "vi_to_tyz", "tyz_to_vi"
        - "vi-ty", "ty-vi"
        - ("vi", "ty"), ("ty", "vi"), ("vi", "tyz"), ("tyz", "vi")
        """
        if isinstance(value, Direction):
            return value

        if isinstance(value, tuple) and len(value) == 2:
            src, tgt = value[0].strip().lower(), value[1].strip().lower()
            if src in ("vi", "vie", "vie_latn") and tgt in ("ty", "tyz", "tay", "tyz_latn"):
                return cls.VI_TO_TAY
            if src in ("ty", "tyz", "tay", "tyz_latn") and tgt in ("vi", "vie", "vie_latn"):
                return cls.TAY_TO_VI
            raise ValueError(f"Unsupported language pair tuple: ({src}, {tgt})")

        val = str(value).strip().lower().replace(" ", "")
        mapping = {
            "vi-tyz": cls.VI_TO_TAY,
            "vi_to_tyz": cls.VI_TO_TAY,
            "vi->tyz": cls.VI_TO_TAY,
            "vi-ty": cls.VI_TO_TAY,
            "vi_to_ty": cls.VI_TO_TAY,
            "vi->ty": cls.VI_TO_TAY,
            "vi_to_tay": cls.VI_TO_TAY,
            "vi-tay": cls.VI_TO_TAY,
            "vi->tay": cls.VI_TO_TAY,
            "vi_ty": cls.VI_TO_TAY,
            "vity": cls.VI_TO_TAY,
            "<2ty>": cls.VI_TO_TAY,
            "tyz-vi": cls.TAY_TO_VI,
            "tyz_to_vi": cls.TAY_TO_VI,
            "tyz->vi": cls.TAY_TO_VI,
            "ty-vi": cls.TAY_TO_VI,
            "ty_to_vi": cls.TAY_TO_VI,
            "ty->vi": cls.TAY_TO_VI,
            "tay_to_vi": cls.TAY_TO_VI,
            "tay-vi": cls.TAY_TO_VI,
            "tay->vi": cls.TAY_TO_VI,
            "ty_vi": cls.TAY_TO_VI,
            "tyvi": cls.TAY_TO_VI,
            "<2vi>": cls.TAY_TO_VI,
        }
        if val in mapping:
            return mapping[val]
        raise ValueError(
            f"Invalid translation direction: '{value}'. Expected one of: "
            f"['vi-tyz', 'tyz-vi', 'vi->ty', 'ty->vi']"
        )

    @property
    def source_lang(self) -> str:
        """Return ISO-like source language code."""
        return "vi" if self == Direction.VI_TO_TAY else "ty"

    @property
    def target_lang(self) -> str:
        """Return ISO-like target language code."""
        return "ty" if self == Direction.VI_TO_TAY else "vi"

    @property
    def source_tag(self) -> str:
        """Return NLLB-style source language tag."""
        return "vie_Latn" if self == Direction.VI_TO_TAY else "tyz_Latn"

    @property
    def target_tag(self) -> str:
        """Return NLLB-style target language tag."""
        return "tyz_Latn" if self == Direction.VI_TO_TAY else "vie_Latn"

    @property
    def special_target_token(self) -> str:
        """Return prefix token for target direction."""
        return "<2ty>" if self == Direction.VI_TO_TAY else "<2vi>"


class ExperimentName(str, Enum):
    """Recognized experiment configurations in the project."""

    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E1_M = "E1-M"
    A1 = "A1"
    A2 = "A2"


@dataclass(frozen=True)
class ExperimentSpec:
    """Detailed metadata for an experiment configuration."""

    name: str
    description: str
    uses_synthetic: bool
    qc_filtered: bool
    sampling_strategy: str
    ablation_rule_removed: str | None = None


EXPERIMENT_SPECS: dict[str, ExperimentSpec] = {
    "E0": ExperimentSpec(
        name="E0",
        description="Baseline trained on verified bilingual corpus only",
        uses_synthetic=False,
        qc_filtered=False,
        sampling_strategy="none",
    ),
    "E1": ExperimentSpec(
        name="E1",
        description="E0 + uncurated back-translated synthetic data (U)",
        uses_synthetic=True,
        qc_filtered=False,
        sampling_strategy="full_synthetic",
    ),
    "E2": ExperimentSpec(
        name="E2",
        description="E0 + N synthetic samples passing all 5 QC rules",
        uses_synthetic=True,
        qc_filtered=True,
        sampling_strategy="all_qc_passed",
    ),
    "E1-M": ExperimentSpec(
        name="E1-M",
        description="E0 + N random synthetic samples from U without replacement (fair control with E2)",
        uses_synthetic=True,
        qc_filtered=False,
        sampling_strategy="random_n_without_replacement",
    ),
    "A1": ExperimentSpec(
        name="A1",
        description="E0 + N synthetic samples without rule R1 (ablation 1: length/ratio)",
        uses_synthetic=True,
        qc_filtered=True,
        sampling_strategy="ablation_r1_removed",
        ablation_rule_removed="R1",
    ),
    "A2": ExperimentSpec(
        name="A2",
        description="E0 + N synthetic samples without rule R2 (ablation 2: script/language-id)",
        uses_synthetic=True,
        qc_filtered=True,
        sampling_strategy="ablation_r2_removed",
        ablation_rule_removed="R2",
    ),
}


@dataclass
class ModelConfig:
    """Configuration for NLLB/Seq2Seq model architecture and tokenization."""

    model_name_or_path: str = "facebook/nllb-200-distilled-600M"
    experiment: str = "E0"
    direction: Direction = Direction.VI_TO_TAY
    max_source_length: int = 256
    max_target_length: int = 256
    vocab_size: int = 256206
    pad_token_id: int = 1
    bos_token_id: int = 0
    eos_token_id: int = 2
    src_lang_tag: str = "vie_Latn"
    tgt_lang_tag: str = "tyz_Latn"
    dropout: float = 0.1
    mock_mode: bool = False
    model_type: str = "gru"  # "gru", "transformer", "nllb"
    d_model: int = 128
    nhead: int = 4
    num_encoder_layers: int = 2
    num_decoder_layers: int = 2
    dim_feedforward: int = 256

    def __post_init__(self) -> None:
        if isinstance(self.direction, str):
            self.direction = Direction.normalize(self.direction)
        if self.direction == Direction.VI_TO_TAY:
            self.src_lang_tag = "vie_Latn"
            self.tgt_lang_tag = "tyz_Latn"
        else:
            self.src_lang_tag = "tyz_Latn"
            self.tgt_lang_tag = "vie_Latn"

        norm_exp = self.experiment.upper().replace("_", "-")
        if norm_exp in EXPERIMENT_SPECS:
            self.experiment = norm_exp

    def to_dict(self) -> dict[str, Any]:
        """Convert config to JSON-serializable dictionary."""
        d = asdict(self)
        d["direction"] = self.direction.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelConfig:
        """Create config from dictionary."""
        data_copy = dict(data)
        if "direction" in data_copy:
            data_copy["direction"] = Direction.normalize(data_copy["direction"])
        return cls(**data_copy)

    def save(self, path: Path | str) -> None:
        """Save configuration to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path | str) -> ModelConfig:
        """Load configuration from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


@dataclass
class TrainingConfig:
    """Hyperparameters and runtime settings for training."""

    experiment_name: str = "E0"
    direction: Direction = Direction.VI_TO_TAY
    output_dir: Path = field(default_factory=lambda: Path("models/checkpoints"))
    learning_rate: float = 5e-5
    weight_decay: float = 0.01
    batch_size: int = 16
    gradient_accumulation_steps: int = 1
    num_train_epochs: int = 5
    max_steps: int = -1
    warmup_steps: int = 100
    early_stopping_patience: int = 3
    eval_steps: int = 100
    save_steps: int = 100
    logging_steps: int = 20
    seed: int = 42
    fp16: bool = False
    device: str = "cpu"
    mock_mode: bool = False
    save_total_limit: int = 2
    cpu_threads: int = 4

    def __post_init__(self) -> None:
        if isinstance(self.direction, str):
            self.direction = Direction.normalize(self.direction)
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to JSON-serializable dictionary."""
        d = asdict(self)
        d["direction"] = self.direction.value
        d["output_dir"] = str(self.output_dir)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingConfig:
        """Create config from dictionary."""
        data_copy = dict(data)
        if "direction" in data_copy:
            data_copy["direction"] = Direction.normalize(data_copy["direction"])
        if "output_dir" in data_copy:
            data_copy["output_dir"] = Path(data_copy["output_dir"])
        return cls(**data_copy)

    def save(self, path: Path | str) -> None:
        """Save configuration to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path | str) -> TrainingConfig:
        """Load configuration from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
