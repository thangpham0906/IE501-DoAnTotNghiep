"""Inference Adapter for Vietnamese-Tay translation.

Official interface contract for web demo (feat/web-demo) and downstream modules.
Provides TranslationInferenceAdapter (alias InferenceAdapter) and MockTranslator fallback.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import torch

from src.models.config import Direction, ModelConfig
from src.models.tokenizer import TayTokenizerWrapper
from src.models.trainer import LocalSeq2SeqTransformer, MockSeq2SeqModel


class AdapterStatus(str, Enum):
    """Lifecycle and operational status of the inference adapter."""

    UNINITIALIZED = "uninitialized"
    READY = "ready"
    MOCK = "mock_mode"
    ERROR = "error"


class EmptyInputError(ValueError):
    """Raised when translation input text is empty or whitespace only."""

    pass


class TextTooLongError(ValueError):
    """Raised when input text exceeds maximum supported character length."""

    pass


class InvalidDirectionError(ValueError):
    """Raised when translation direction is not recognized or supported."""

    pass


class ModelNotReadyError(RuntimeError):
    """Raised when inference is requested before model initialization."""

    pass


class InferenceTimeoutError(TimeoutError):
    """Raised when model inference latency exceeds acceptable threshold."""

    pass


@dataclass
class TranslationResult:
    """Standardized translation output contract."""

    src_text: str
    tgt_text: str
    direction: str
    model_version: str
    latency_ms: float
    status: str
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for JSON API responses."""
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        """Allow dict-like indexing (e.g. res['tgt_text'])."""
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        """Allow dict-like get method."""
        return getattr(self, item, default)


class MockTranslator:
    """Rule-based and lexicon-backed translator for fast offline simulation."""

    # Lexicon mapping between Vietnamese and Tay phrases/syllables
    VI_TO_TAY_LEXICON: list[tuple[str, str]] = [
        # Cultural & folklore phrases
        ("tháng giêng", "bươn chiêng"),
        ("sau tết", "lăng tết"),
        ("ngày mười lăm", "slíp ngà"),
        ("mười lăm", "slíp ngà"),
        ("mười", "slíp"),
        ("bản làng", "bản mường"),
        ("mở hội", "khui hội"),
        ("hát lượn", "lượn"),
        ("hội lượn", "hội lượn"),
        ("trai gái", "báo sáo"),
        ("trong bản", "chang bản"),
        ("cùng nhau", "păn"),
        ("đi chợ xuân", "pây chơ xuân"),
        ("đi chợ", "pây chơ"),
        ("chợ xuân", "chơ xuân"),
        ("nàng hai", "nàng hai"),
        ("ăn cơm", "kin khẩu"),
        ("uống nước", "kin nặm"),
        ("uống rượu", "kin lảu"),
        ("về nhà", "mừa rườn"),
        ("lên nương", "khửn rẩy"),
        ("xuống ruộng", "lồng nà"),
        ("người tày", "cần tày"),
        ("con người", "cần"),
        ("người già", "cần ké"),
        ("trẻ con", "lục éc"),
        ("núi cao", "phja sang"),
        ("rừng sâu", "đong thâm"),
        ("sông suối", "thêm ta"),
        ("con trâu", "tô vài"),
        ("con ngựa", "tô mạ"),
        ("xin chào", "tỏn chào"),
        ("cảm ơn", "chè ơn"),
        ("tạm biệt", "mừa nơ"),
        ("rất đẹp", "đầy lai"),
        ("rất tốt", "đầy lai"),
        ("chăm chỉ", "hăng hết việc"),
        ("làm việc", "hết việc"),
        ("mùa xuân", "bươn xuân"),
        ("mùa hè", "bươn đét"),
        ("mùa đông", "bươn nảo"),
        ("mặt trời", "bươn đét"),
        ("mặt trăng", "bươn"),
        ("hoa đào", "bjoóc đào"),
        ("hoa mận", "bjoóc mận"),
        ("ngôi nhà", "rườn"),
        ("ngày mai", "mơ ngoài"),
        ("hôm nay", "văn nẩy"),
        ("hôm qua", "văn ngòi"),
    ]

    TAY_TO_VI_LEXICON: list[tuple[str, str]] = [
        (t, v) for v, t in VI_TO_TAY_LEXICON
    ]

    def __init__(self) -> None:
        # Sort by length descending to match longest phrases first
        self.vi_to_tay_sorted = sorted(
            self.VI_TO_TAY_LEXICON, key=lambda x: len(x[0]), reverse=True
        )
        self.tay_to_vi_sorted = sorted(
            self.TAY_TO_VI_LEXICON, key=lambda x: len(x[0]), reverse=True
        )

    def translate_vi_to_tay(self, text: str) -> str:
        """Translate Vietnamese text to Tay using lexicon and grammatical rules."""
        result = text
        for vi_phrase, tay_phrase in self.vi_to_tay_sorted:
            # Case-insensitive replacement preserving casing style
            pattern = re.compile(re.escape(vi_phrase), re.IGNORECASE)
            result = pattern.sub(tay_phrase, result)

        # Word-level fallback for common particles
        word_map = {
            "và": "vạ",
            "của": "tứ",
            "trong": "chang",
            "ở": "tế",
            "này": "nẩy",
            "ấy": "tế",
            "đi": "pây",
            "về": "mừa",
            "ăn": "kin",
            "uống": "kin",
            "nhà": "rườn",
            "núi": "phja",
            "rừng": "đong",
            "sông": "thêm",
            "suối": "ta",
            "người": "cần",
            "con": "tô",
            "hai": "sloong",
            "ba": "sam",
            "bốn": "xế",
            "năm": "hả",
            "sáu": "hốc",
            "bảy": "chất",
            "tám": "pet",
            "chín": "cửu",
            "mười": "slíp",
        }
        words = result.split()
        translated_words: list[str] = []
        for w in words:
            clean_w = re.sub(r"[^\w]", "", w).lower()
            if clean_w in word_map:
                translated_words.append(word_map[clean_w])
            else:
                translated_words.append(w)

        res_str = " ".join(translated_words)
        # Restore capitalization for the first character
        if text and text[0].isupper() and res_str:
            res_str = res_str[0].upper() + res_str[1:]
        return res_str

    def translate_tay_to_vi(self, text: str) -> str:
        """Translate Tay text to Vietnamese using lexicon and grammatical rules."""
        result = text
        for tay_phrase, vi_phrase in self.tay_to_vi_sorted:
            pattern = re.compile(re.escape(tay_phrase), re.IGNORECASE)
            result = pattern.sub(vi_phrase, result)

        word_map = {
            "vạ": "và",
            "tứ": "từ",
            "chang": "trong",
            "tế": "ở",
            "nẩy": "này",
            "pây": "đi",
            "mừa": "về",
            "kin": "ăn",
            "rườn": "nhà",
            "phja": "núi",
            "đong": "rừng",
            "thêm": "sông",
            "ta": "suối",
            "cần": "người",
            "tô": "con",
            "sloong": "hai",
            "sam": "ba",
            "xế": "bốn",
            "hả": "năm",
            "hốc": "sáu",
            "chất": "bảy",
            "pet": "tám",
            "cửu": "chín",
            "slíp": "mười",
        }
        words = result.split()
        translated_words: list[str] = []
        for w in words:
            clean_w = re.sub(r"[^\w]", "", w).lower()
            if clean_w in word_map:
                translated_words.append(word_map[clean_w])
            else:
                translated_words.append(w)

        res_str = " ".join(translated_words)
        if text and text[0].isupper() and res_str:
            res_str = res_str[0].upper() + res_str[1:]
        return res_str

    def translate(self, text: str, direction: Direction) -> str:
        """Route translation based on direction."""
        if direction == Direction.VI_TO_TAY:
            return self.translate_vi_to_tay(text)
        return self.translate_tay_to_vi(text)


class TranslationInferenceAdapter:
    """Production and testing inference adapter for Vietnamese-Tay translation.

    Serves as the clean API boundary between model weights and Web Demo / Evaluation.
    """

    MAX_INPUT_LENGTH: int = 2000

    def __init__(
        self,
        checkpoint_dir: str | Path | None = None,
        direction: Direction | str = Direction.VI_TO_TAY,
        device: str = "cpu",
        mock_mode: bool = False,
        model_version: str = "nllb-200-distilled-600M-tay",
    ) -> None:
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self.default_direction = Direction.normalize(direction)
        self.device = device
        self.mock_mode = mock_mode
        self.model_version = model_version

        self.status = AdapterStatus.UNINITIALIZED
        self.mock_translator = MockTranslator()
        self._hf_model = None
        self._hf_tokenizer = None
        self._native_model = None
        self._native_tokenizer = None
        self._trained_direction: str | None = None

        self._initialize()

    def _initialize(self) -> None:
        """Initialize weights or fallback to Mock mode. Fail closed if mock_mode=False and weights fail to load."""
        if self.checkpoint_dir is None:
            if self.mock_mode:
                self.status = AdapterStatus.MOCK
                return
            self.status = AdapterStatus.ERROR
            raise ModelNotReadyError(
                "mock_mode=False requires a valid checkpoint_dir containing trained weights, but None was provided."
            )

        if not self.checkpoint_dir.exists():
            self.status = AdapterStatus.ERROR
            raise FileNotFoundError(
                f"Checkpoint directory does not exist: {self.checkpoint_dir}"
            )

        # 1. Read metadata.json if present
        meta_file = self.checkpoint_dir / "metadata.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self._trained_direction = meta.get("direction")
            except Exception:
                pass

        # 2. Check for HuggingFace Transformers model
        is_hf = meta.get("is_hf_model", False) or (self.checkpoint_dir / "config.json").exists()
        if is_hf and not (self.checkpoint_dir / "model_config.json").exists():
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                self._hf_tokenizer = AutoTokenizer.from_pretrained(str(self.checkpoint_dir))
                self._hf_model = AutoModelForSeq2SeqLM.from_pretrained(str(self.checkpoint_dir))
                self._hf_model.to(self.device)
                self._hf_model.eval()
                self.status = AdapterStatus.READY
                return
            except Exception as err:
                self.status = AdapterStatus.ERROR
                raise RuntimeError(
                    f"Failed to load HuggingFace checkpoint from '{self.checkpoint_dir}' while mock_mode is False: {err}"
                ) from err

        # 3. Check for native PyTorch checkpoint (model.pt)
        model_file = self.checkpoint_dir / "model.pt"
        if model_file.exists():
            try:
                # Validate SHA-256 checksum
                expected_sha256 = meta.get("weights_sha256")
                if expected_sha256:
                    hasher = hashlib.sha256()
                    with open(model_file, "rb") as f:
                        while chunk := f.read(65536):
                            hasher.update(chunk)
                    actual_sha256 = hasher.hexdigest()
                    if actual_sha256 != expected_sha256:
                        raise ValueError(
                            f"Checksum mismatch for weights file '{model_file}': "
                            f"expected {expected_sha256}, got {actual_sha256}."
                        )

                cfg_file = self.checkpoint_dir / "model_config.json"
                model_cfg = ModelConfig.load(cfg_file) if cfg_file.exists() else ModelConfig()
                if not self._trained_direction:
                    self._trained_direction = model_cfg.direction.value

                tok_dir = self.checkpoint_dir / "tokenizer"
                if tok_dir.exists():
                    self._native_tokenizer = TayTokenizerWrapper.load(tok_dir)
                elif (self.checkpoint_dir / "vocab.json").exists():
                    self._native_tokenizer = TayTokenizerWrapper.load(self.checkpoint_dir)
                else:
                    vocab_size = meta.get("vocab_size", getattr(model_cfg, "vocab_size", 32000))
                    self._native_tokenizer = TayTokenizerWrapper(mock_mode=True, vocab_size=vocab_size)

                self._native_tokenizer.freeze()
                vocab_size = meta.get("vocab_size", getattr(model_cfg, "vocab_size", len(self._native_tokenizer)))

                model_arch = meta.get("model_architecture")
                if model_arch == "MockSeq2SeqModel" or getattr(model_cfg, "model_type", "transformer") == "gru":
                    native_model = MockSeq2SeqModel(
                        vocab_size=vocab_size,
                        embed_dim=64,
                        hidden_dim=64,
                        pad_token_id=model_cfg.pad_token_id,
                        bos_token_id=model_cfg.bos_token_id,
                        eos_token_id=model_cfg.eos_token_id,
                    )
                else:
                    native_model = LocalSeq2SeqTransformer(
                        vocab_size=vocab_size,
                        d_model=getattr(model_cfg, "d_model", 128),
                        nhead=getattr(model_cfg, "nhead", 4),
                        num_encoder_layers=getattr(model_cfg, "num_encoder_layers", 2),
                        num_decoder_layers=getattr(model_cfg, "num_decoder_layers", 2),
                        dim_feedforward=getattr(model_cfg, "dim_feedforward", 256),
                        dropout=model_cfg.dropout,
                        pad_token_id=model_cfg.pad_token_id,
                        bos_token_id=model_cfg.bos_token_id,
                        eos_token_id=model_cfg.eos_token_id,
                    )
                state_dict = torch.load(model_file, map_location=self.device, weights_only=True)
                native_model.load_state_dict(state_dict)
                native_model.to(self.device)
                native_model.eval()
                self._native_model = native_model
                self.status = AdapterStatus.READY
                return
            except Exception as err:
                self.status = AdapterStatus.ERROR
                raise RuntimeError(
                    f"Failed to load native checkpoint from '{self.checkpoint_dir}': {err}"
                ) from err

        # Fallback to HuggingFace Transformers model
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            self._hf_tokenizer = AutoTokenizer.from_pretrained(str(self.checkpoint_dir))
            self._hf_model = AutoModelForSeq2SeqLM.from_pretrained(str(self.checkpoint_dir))
            self._hf_model.to(self.device)
            self._hf_model.eval()
            self.status = AdapterStatus.READY
            return
        except Exception as err:
            self.status = AdapterStatus.ERROR
            raise RuntimeError(
                f"Failed to load checkpoint from '{self.checkpoint_dir}' while mock_mode is False: {err}"
            ) from err

    def is_ready(self) -> bool:
        """Check if adapter is operational (in ready mode with loaded weights, or mock mode)."""
        if self._hf_model is not None or self._native_model is not None:
            return True
        if self.mock_mode or self.status == AdapterStatus.MOCK:
            return True
        return self.status == AdapterStatus.READY

    def _resolve_direction(
        self,
        src_lang: str | None = None,
        tgt_lang: str | None = None,
        direction: Direction | str | None = None,
    ) -> Direction:
        """Normalize direction from either (src_lang, tgt_lang), direction kwarg, or direction as 2nd positional arg."""
        try:
            if direction is not None:
                return Direction.normalize(direction)
            if isinstance(src_lang, Direction):
                return src_lang
            if isinstance(src_lang, str):
                s = src_lang.strip().lower()
                if "-" in s or ">" in s or "_" in s or s.startswith("<2") or s in ("vity", "tyvi", "vi-tyz", "tyz-vi", "vi-ty", "ty-vi"):
                    return Direction.normalize(s)
            if src_lang is not None and tgt_lang is not None:
                return Direction.normalize((src_lang, tgt_lang))
            return self.default_direction
        except ValueError as err:
            raise InvalidDirectionError(f"Chiều dịch không hợp lệ: {err}") from err

    def validate_input(self, text: str) -> None:
        """Validate input text against length and emptiness rules.

        Raises:
            EmptyInputError: If text is empty or contains only whitespace.
            TextTooLongError: If text exceeds MAX_INPUT_LENGTH characters.
        """
        if not text or not text.strip():
            raise EmptyInputError("Vui lòng nhập văn bản cần dịch.")
        if len(text) > self.MAX_INPUT_LENGTH:
            raise TextTooLongError(
                f"Văn bản quá dài ({len(text)} ký tự). Vui lòng nhập dưới {self.MAX_INPUT_LENGTH} ký tự."
            )

    def translate(
        self,
        text: str,
        src_lang: str | None = None,
        tgt_lang: str | None = None,
        direction: Direction | str | None = None,
        max_length: int = 256,
        num_beams: int = 4,
        raise_exceptions: bool = True,
    ) -> dict[str, Any] | TranslationResult:
        """Translate a single sentence or paragraph.

        Supports two calling conventions:
        1. adapter.translate(text, "vi", "ty")
        2. adapter.translate(text, direction="vi-tyz")

        Returns:
            TranslationResult (which also implements dict-like indexing and .to_dict()).
        """
        start_time = time.perf_counter()

        try:
            self.validate_input(text)
            dir_enum = self._resolve_direction(src_lang, tgt_lang, direction)
        except (EmptyInputError, TextTooLongError, InvalidDirectionError) as err:
            if raise_exceptions:
                raise
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            error_code = type(err).__name__
            return TranslationResult(
                src_text=text,
                tgt_text="",
                direction=str(direction or self.default_direction.value),
                model_version=self.model_version,
                latency_ms=latency_ms,
                status=error_code.lower(),
                error_message=str(err),
            )

        # 1. Real model inference if ready and weights loaded
        if self.status == AdapterStatus.READY:
            # Case A: Hugging Face Model
            if self._hf_model is not None and self._hf_tokenizer is not None:
                try:
                    tgt_tag = dir_enum.target_tag
                    forced_bos_token_id = None
                    if hasattr(self._hf_tokenizer, "lang_code_to_id") and isinstance(self._hf_tokenizer.lang_code_to_id, dict):
                        forced_bos_token_id = self._hf_tokenizer.lang_code_to_id.get(tgt_tag)
                    if forced_bos_token_id is None and hasattr(self._hf_tokenizer, "convert_tokens_to_ids"):
                        tid = self._hf_tokenizer.convert_tokens_to_ids(tgt_tag)
                        if tid is not None and tid != getattr(self._hf_tokenizer, "unk_token_id", 3):
                            forced_bos_token_id = tid

                    inputs = self._hf_tokenizer(
                        text, return_tensors="pt", max_length=max_length, truncation=True
                    ).to(self.device)

                    with torch.no_grad():
                        gen_kwargs = {
                            "max_length": max_length,
                            "num_beams": num_beams,
                        }
                        if forced_bos_token_id is not None:
                            gen_kwargs["forced_bos_token_id"] = forced_bos_token_id

                        generated_tokens = self._hf_model.generate(**inputs, **gen_kwargs)

                    translated_text = self._hf_tokenizer.batch_decode(
                        generated_tokens, skip_special_tokens=True
                    )[0].strip()

                    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return TranslationResult(
                        src_text=text,
                        tgt_text=translated_text,
                        direction=dir_enum.value,
                        model_version=self.model_version,
                        latency_ms=latency_ms,
                        status="success",
                    )
                except Exception as err:
                    if raise_exceptions:
                        raise RuntimeError(f"Real HuggingFace generation failed: {err}") from err
                    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return TranslationResult(
                        src_text=text,
                        tgt_text="",
                        direction=dir_enum.value,
                        model_version=self.model_version,
                        latency_ms=latency_ms,
                        status="error",
                        error_message=str(err),
                    )

            # Case B: Native PyTorch Model (e.g. LocalSeq2SeqTransformer or MockSeq2SeqModel)
            elif self._native_model is not None and self._native_tokenizer is not None:
                try:
                    enc = self._native_tokenizer.encode(
                        text, lang_code=dir_enum.source_tag, max_length=max_length, return_tensors="pt"
                    )
                    input_ids = enc["input_ids"].to(self.device)
                    if input_ids.dim() == 1:
                        input_ids = input_ids.unsqueeze(0)

                    target_tag = dir_enum.target_tag
                    forced_bos_id = self._native_tokenizer.bos_token_id
                    if hasattr(self._native_tokenizer, "resolve_lang_code"):
                        tag_code = self._native_tokenizer.resolve_lang_code(target_tag)
                        if tag_code in getattr(self._native_tokenizer, "_vocab", {}):
                            forced_bos_id = self._native_tokenizer._vocab[tag_code]

                    with torch.no_grad():
                        generated_ids = self._native_model.generate(
                            input_ids=input_ids,
                            max_length=max_length,
                            forced_bos_token_id=forced_bos_id,
                        )
                    translated_text = self._native_tokenizer.decode(
                        generated_ids[0], skip_special_tokens=True
                    )

                    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return TranslationResult(
                        src_text=text,
                        tgt_text=translated_text,
                        direction=dir_enum.value,
                        model_version=self.model_version,
                        latency_ms=latency_ms,
                        status="success",
                    )
                except Exception as err:
                    if raise_exceptions:
                        raise RuntimeError(f"Native model generation failed: {err}") from err
                    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    return TranslationResult(
                        src_text=text,
                        tgt_text="",
                        direction=dir_enum.value,
                        model_version=self.model_version,
                        latency_ms=latency_ms,
                        status="error",
                        error_message=str(err),
                    )

        # 2. Rule-based / Lexicon mock translation ONLY when in mock mode without neural weights
        if (self._hf_model is None and self._native_model is None) and (self.mock_mode or self.status == AdapterStatus.MOCK):
            tgt_text = self.mock_translator.translate(text, dir_enum)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            return TranslationResult(
                src_text=text,
                tgt_text=tgt_text,
                direction=dir_enum.value,
                model_version=f"{self.model_version}-mock",
                latency_ms=latency_ms,
                status="mock_mode",
            )

        # 3. Fail closed if mock_mode=False and no ready model
        raise ModelNotReadyError(
            f"Model is not ready for inference (status={self.status.value}). "
            "Ensure a valid checkpoint is loaded or set mock_mode=True explicitly."
        )

    def translate_batch(
        self,
        texts: list[str],
        src_lang: str | None = None,
        tgt_lang: str | None = None,
        direction: Direction | str | None = None,
        batch_size: int = 16,
    ) -> list[TranslationResult]:
        """Translate a batch of sentences for evaluation or synthetic generation."""
        results: list[TranslationResult] = []
        dir_enum = self._resolve_direction(src_lang, tgt_lang, direction)

        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            for text in chunk:
                res = self.translate(
                    text,
                    direction=dir_enum,
                    raise_exceptions=False,
                )
                if isinstance(res, TranslationResult):
                    results.append(res)
                else:
                    results.append(TranslationResult(**res))

        return results

    def get_metadata(self) -> dict[str, Any]:
        """Return adapter configuration and operational status metadata."""
        return {
            "model_version": self.model_version,
            "status": self.status.value,
            "is_ready": self.is_ready(),
            "has_neural_weights": (self._hf_model is not None or self._native_model is not None),
            "checkpoint_dir": str(self.checkpoint_dir) if self.checkpoint_dir else None,
            "default_direction": self.default_direction.value,
            "device": self.device,
            "mock_mode": self.mock_mode,
            "supported_directions": [Direction.VI_TO_TAY.value, Direction.TAY_TO_VI.value],
            "max_input_length": self.MAX_INPUT_LENGTH,
        }


# Alias for compatibility with leader.md specification
InferenceAdapter = TranslationInferenceAdapter
