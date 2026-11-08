"""Tokenizer wrapper for Vietnamese-Tay translation.

Provides TayTokenizerWrapper (alias NLLBTokenizerWrapper) which:
1. Handles NLLB language codes (`vie_Latn`, `tyz_Latn`) and special direction tokens (`<2vi>`, `<2ty>`).
   * Note on Tay representation: Tay (`tyz_Latn` / ISO 639-3 `tyz`) is NOT in Flores-200 / NLLB-200 native vocabulary.
     The project strategy is to explicitly add `tyz_Latn`, `<2ty>`, `<2vi>` as special tokens to the tokenizer,
     and resize the model's token embeddings (`model.resize_token_embeddings(len(tokenizer))`).
2. Measures subword fragmentation (T02 requirement: tokens per word, fertility, character-to-token ratio).
3. Provides deterministic subword/whitespace mock tokenization ONLY when mock_mode=True is explicitly set.
   When mock_mode=False, fails closed (raises RuntimeError) rather than silently falling back.
4. Supports SentencePieceProcessor when a trained spm model is provided.
5. Train-only tokenizer rule: Fitting/induction must only occur on training data (zero leakage to val/test).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zlib
from pathlib import Path
from typing import Any

SPECIAL_TOKENS = {
    "<s>": 0,
    "<pad>": 1,
    "</s>": 2,
    "<unk>": 3,
    "<2vi>": 4,
    "<2ty>": 5,
    "vie_Latn": 6,
    "tyz_Latn": 7,
}

# Explicit list of custom special tokens added for Vietnamese-Tay
TAY_SPECIAL_TOKENS = ["<2vi>", "<2ty>", "tyz_Latn"]

# Standard NLLB language codes for Vietnamese and Tay (or closest script tag)
LANG_TAG_MAP = {
    "vi": "vie_Latn",
    "vie": "vie_Latn",
    "vie_latn": "vie_Latn",
    "<2vi>": "vie_Latn",
    "ty": "tyz_Latn",
    "tyz": "tyz_Latn",
    "tay": "tyz_Latn",
    "tyz_latn": "tyz_Latn",
    "<2ty>": "tyz_Latn",
}

DIRECTION_TAG_MAP = {
    "vi-tyz": "<2ty>",
    "tyz-vi": "<2vi>",
    "vi->ty": "<2ty>",
    "ty->vi": "<2vi>",
}


def prepare_model_for_tokenizer(model: Any, tokenizer: Any) -> int:
    """Ensure model token embedding matrix matches tokenizer vocabulary size.

    When new special tokens (e.g. `tyz_Latn`, `<2ty>`, `<2vi>`) are added,
    the embedding layer must be resized to prevent CUDA/CPU out-of-bounds indexing.

    Args:
        model: HuggingFace PreTrainedModel or PyTorch Seq2Seq module.
        tokenizer: TayTokenizerWrapper or HuggingFace PreTrainedTokenizer.

    Returns:
        Current vocabulary size of the model.
    """
    if hasattr(tokenizer, "__len__"):
        tok_len = len(tokenizer)
    elif hasattr(tokenizer, "vocab_size"):
        tok_len = tokenizer.vocab_size
    else:
        tok_len = getattr(tokenizer, "_vocab_len", 32000)

    if hasattr(model, "resize_token_embeddings"):
        model.resize_token_embeddings(tok_len)
        return tok_len
    if hasattr(model, "embedding") and hasattr(model.embedding, "num_embeddings"):
        return model.embedding.num_embeddings
    return tok_len


class TayTokenizerWrapper:
    """Tokenizer wrapper for Vietnamese - Tay bilingual models.

    Supports HuggingFace AutoTokenizer if available; falls back to SentencePiece or
    deterministic subword/mock tokenizer ONLY when mock_mode=True is explicitly set.
    """

    def __init__(
        self,
        model_name_or_path: str = "facebook/nllb-200-distilled-600M",
        mock_mode: bool = False,
        sp_model_path: str | None = None,
        max_length: int = 256,
        vocab_size: int = 32000,
        allow_vocab_growth: bool = True,
    ) -> None:
        self.model_name_or_path = model_name_or_path
        self.mock_mode = mock_mode
        self.sp_model_path = sp_model_path
        self.max_length = max_length
        self._vocab_size = vocab_size
        self.allow_vocab_growth = allow_vocab_growth
        self._is_frozen = False
        self._next_id = 8

        self.pad_token_id = 1
        self.bos_token_id = 0
        self.eos_token_id = 2
        self.unk_token_id = 3

        self._hf_tokenizer = None
        self._sp_processor = None
        self._vocab: dict[str, int] = dict(SPECIAL_TOKENS)
        self._id2vocab: dict[int, str] = {v: k for k, v in SPECIAL_TOKENS.items()}

        self._initialize()

    def __len__(self) -> int:
        if self._hf_tokenizer is not None and not self.mock_mode:
            return len(self._hf_tokenizer)
        if self._sp_processor is not None and not self.mock_mode:
            return self._sp_processor.get_piece_size()
        return self._vocab_size

    @property
    def vocab_size(self) -> int:
        return len(self)

    @property
    def is_frozen(self) -> bool:
        return self._is_frozen

    def freeze(self) -> None:
        """Freeze vocabulary to strictly prevent data leakage during val/test/inference."""
        self._is_frozen = True
        self.allow_vocab_growth = False

    def fit(self, texts: list[str]) -> None:
        """Fit vocabulary strictly on training texts (train-only rule)."""
        if self._is_frozen:
            raise RuntimeError("Cannot fit tokenizer: vocabulary is frozen to prevent leakage.")
        for text in texts:
            pieces = self._split_into_pieces(text)
            for piece in pieces:
                if piece not in self._vocab and self._next_id < self._vocab_size:
                    self._vocab[piece] = self._next_id
                    self._id2vocab[self._next_id] = piece
                    self._next_id += 1

    def fit_dataset(self, dataset: Any) -> None:
        """Fit vocabulary from dataset records before freezing."""
        if self._is_frozen:
            return
        texts: list[str] = []
        records = getattr(dataset, "records", None)
        if records:
            for r in records:
                for k in ("vi_text", "vi", "vietnamese", "tay_text", "tay", "ty", "tyz", "src_text", "tgt_text", "text"):
                    v = r.get(k)
                    if isinstance(v, str) and v.strip():
                        texts.append(v)
        self.fit(texts)

    def get_vocab_fingerprint(self) -> dict[str, Any]:
        """Compute structural fingerprint and cryptographic hash of vocabulary."""
        if self._hf_tokenizer is not None and not self.mock_mode:
            return {
                "tokenizer_type": "huggingface",
                "model_name_or_path": str(self.model_name_or_path),
                "vocab_size": len(self),
                "pad_token_id": self.pad_token_id,
                "bos_token_id": self.bos_token_id,
                "eos_token_id": self.eos_token_id,
                "unk_token_id": self.unk_token_id,
            }
        if self._sp_processor is not None and not self.mock_mode:
            return {
                "tokenizer_type": "sentencepiece",
                "sp_model_path": str(self.sp_model_path),
                "vocab_size": len(self),
                "pad_token_id": self.pad_token_id,
                "bos_token_id": self.bos_token_id,
                "eos_token_id": self.eos_token_id,
                "unk_token_id": self.unk_token_id,
            }
        # Local vocabulary fingerprint
        sorted_vocab = sorted(self._vocab.items())
        vocab_bytes = json.dumps(sorted_vocab, ensure_ascii=False).encode("utf-8")
        vocab_sha256 = hashlib.sha256(vocab_bytes).hexdigest()
        return {
            "tokenizer_type": "local_vocab",
            "vocab_sha256": vocab_sha256,
            "vocab_size": len(self),
            "pad_token_id": self.pad_token_id,
            "bos_token_id": self.bos_token_id,
            "eos_token_id": self.eos_token_id,
            "unk_token_id": self.unk_token_id,
            "special_tokens": dict(SPECIAL_TOKENS),
        }

    def _initialize(self) -> None:
        """Initialize underlying tokenizer engine (HF, SentencePiece, or Fallback)."""
        if self.mock_mode:
            self._init_fallback_vocab()
            return

        # Attempt to load SentencePiece if path provided
        if self.sp_model_path:
            try:
                import sentencepiece as spm

                sp = spm.SentencePieceProcessor()
                sp.load(str(self.sp_model_path))
                self._sp_processor = sp
                self.pad_token_id = sp.pad_id() if sp.pad_id() >= 0 else 1
                self.bos_token_id = sp.bos_id() if sp.bos_id() >= 0 else 0
                self.eos_token_id = sp.eos_id() if sp.eos_id() >= 0 else 2
                self.unk_token_id = sp.unk_id() if sp.unk_id() >= 0 else 3
                return
            except Exception as e:
                raise RuntimeError(
                    f"Failed to load SentencePiece model from '{self.sp_model_path}' while mock_mode is False: {e}"
                ) from e

        # Attempt HuggingFace Transformers
        try:
            from transformers import AutoTokenizer

            self._hf_tokenizer = AutoTokenizer.from_pretrained(
                self.model_name_or_path,
                additional_special_tokens=TAY_SPECIAL_TOKENS,
                src_lang="vie_Latn",
                tgt_lang="tyz_Latn",
            )
            self.pad_token_id = getattr(self._hf_tokenizer, "pad_token_id", 1)
            self.bos_token_id = getattr(self._hf_tokenizer, "bos_token_id", 0)
            self.eos_token_id = getattr(self._hf_tokenizer, "eos_token_id", 2)
            self.unk_token_id = getattr(self._hf_tokenizer, "unk_token_id", 3)
            return
        except Exception as e:
            # FAIL CLOSED: Do not silently switch mock_mode to True!
            raise RuntimeError(
                f"Failed to load HuggingFace tokenizer '{self.model_name_or_path}' while mock_mode is False: {e}. "
                "Ensure `transformers` is installed and model checkpoint is accessible, or explicitly set mock_mode=True."
            ) from e

    def _init_fallback_vocab(self) -> None:
        """Populate fallback vocabulary with common Vietnamese and Tay syllables."""
        common_syllables = [
            # Vietnamese common words
            "và", "là", "của", "các", "có", "trong", "được", "người", "với", "cho",
            "không", "những", "này", "đã", "để", "khi", "tại", "từ", "ngày", "năm",
            "tháng", "giêng", "sau", "tết", "mười", "lăm", "bản", "làng", "mở", "hội",
            "lượn", "trai", "gái", "cùng", "nhau", "đi", "chợ", "xuân", "hát", "nàng",
            "hai", "cơm", "nước", "nhà", "núi", "rừng", "sông", "suối", "ruộng", "nương",
            # Tay common syllables
            "bươn", "chiêng", "lăng", "slíp", "ngà", "mường", "khui", "báo", "sáo", "chang",
            "păn", "pây", "chơ", "kin", "khẩu", "nặm", "rườn", "phja", "đong", "thêm",
            "ta", "nà", "rẩy", "sloong", "sam", "xế", "hả", "hốc", "chất", "pet", "cửu",
            "cần", "boong", "tỏn", "tiểm", "nẩy", "tế", "vạ", "lèo", "mi", "tứ", "vài",
        ]
        next_id = 8
        for word in common_syllables:
            if word not in self._vocab:
                self._vocab[word] = next_id
                self._id2vocab[next_id] = word
                next_id += 1
        self._next_id = next_id

    def resolve_lang_code(self, code: str) -> str:
        """Map generic language or tag name to normalized code."""
        code_norm = code.strip().lower()
        return LANG_TAG_MAP.get(code_norm, code)

    def resolve_direction_token(self, direction: str) -> str:
        """Map direction to target language tag or prefix token."""
        return DIRECTION_TAG_MAP.get(direction, "<2ty>")

    def _split_into_pieces(self, text: str) -> list[str]:
        """Split text into words and sub-tokens deterministically."""
        words = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        pieces: list[str] = []
        for word in words:
            w_lower = word.lower()
            if w_lower in self._vocab:
                pieces.append(w_lower)
            elif len(word) > 4:
                # Subword split simulation (e.g. prefix + suffix)
                pieces.append(w_lower[:3])
                pieces.append(w_lower[3:])
            else:
                pieces.append(w_lower)
        return pieces

    def encode(
        self,
        text: str,
        lang_code: str = "vie_Latn",
        max_length: int | None = None,
        add_special_tokens: bool = True,
        return_tensors: str | None = None,
    ) -> dict[str, Any]:
        """Tokenize text into input_ids and attention_mask.

        Args:
            text: Text to encode.
            lang_code: Source or prefix language tag (e.g. 'vie_Latn', 'tyz_Latn', '<2ty>').
            max_length: Maximum sequence length.
            add_special_tokens: Whether to add BOS/EOS/language tags.
            return_tensors: If 'pt', returns PyTorch Tensors.

        Returns:
            dict containing 'input_ids' and 'attention_mask'.
        """
        max_len = max_length or self.max_length

        if self._hf_tokenizer is not None and not self.mock_mode:
            lang_tag = self.resolve_lang_code(lang_code)
            try:
                self._hf_tokenizer.src_lang = lang_tag
            except Exception:
                pass
            res = self._hf_tokenizer(
                text,
                max_length=max_len,
                truncation=True,
                padding=False,
                add_special_tokens=add_special_tokens,
                return_tensors=return_tensors,
            )
            return {"input_ids": res["input_ids"], "attention_mask": res["attention_mask"]}

        if self._sp_processor is not None and not self.mock_mode:
            ids = self._sp_processor.encode_as_ids(text)
            if add_special_tokens:
                ids = [self.bos_token_id] + ids + [self.eos_token_id]
            if len(ids) > max_len:
                ids = ids[: max_len - 1] + [self.eos_token_id]
            mask = [1] * len(ids)
            if return_tensors == "pt":
                import torch

                return {
                    "input_ids": torch.tensor(ids, dtype=torch.long),
                    "attention_mask": torch.tensor(mask, dtype=torch.long),
                }
            return {"input_ids": ids, "attention_mask": mask}

        # Fallback / Mock encoding
        pieces = self._split_into_pieces(text)
        token_ids: list[int] = []

        if add_special_tokens:
            token_ids.append(self.bos_token_id)
            tag = self.resolve_lang_code(lang_code)
            if tag in self._vocab:
                token_ids.append(self._vocab[tag])

        for piece in pieces:
            if piece in self._vocab:
                token_ids.append(self._vocab[piece])
            elif not self._is_frozen and self.allow_vocab_growth and self._next_id < self._vocab_size:
                new_id = self._next_id
                self._vocab[piece] = new_id
                self._id2vocab[new_id] = piece
                self._next_id += 1
                token_ids.append(new_id)
            else:
                token_ids.append(self.unk_token_id)

        if add_special_tokens:
            token_ids.append(self.eos_token_id)

        # Truncate
        if len(token_ids) > max_len:
            token_ids = token_ids[: max_len - 1] + [self.eos_token_id]

        attention_mask = [1] * len(token_ids)

        if return_tensors == "pt":
            import torch

            return {
                "input_ids": torch.tensor(token_ids, dtype=torch.long),
                "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            }

        return {"input_ids": token_ids, "attention_mask": attention_mask}

    def decode(
        self,
        token_ids: list[int] | Any,
        skip_special_tokens: bool = True,
    ) -> str:
        """Decode token IDs back to a text string.

        Args:
            token_ids: List of integer token IDs or PyTorch 1D Tensor.
            skip_special_tokens: Whether to strip BOS/EOS/PAD and language tags.

        Returns:
            Decoded plain string.
        """
        # Handle PyTorch tensor or numpy array
        if hasattr(token_ids, "tolist"):
            token_ids = token_ids.tolist()

        if self._hf_tokenizer is not None and not self.mock_mode:
            return self._hf_tokenizer.decode(
                token_ids, skip_special_tokens=skip_special_tokens
            ).strip()

        if self._sp_processor is not None and not self.mock_mode:
            ids_to_decode = [
                tid
                for tid in token_ids
                if not (skip_special_tokens and tid in (self.bos_token_id, self.eos_token_id, self.pad_token_id))
            ]
            return self._sp_processor.decode_ids(ids_to_decode).strip()

        words: list[str] = []
        special_ids = set(SPECIAL_TOKENS.values())

        for tid in token_ids:
            if skip_special_tokens and tid in special_ids:
                continue
            if tid in self._id2vocab:
                words.append(self._id2vocab[tid])
            elif tid == self.unk_token_id:
                if not skip_special_tokens:
                    words.append("<unk>")
            else:
                # Unknown hash piece
                words.append(f"tok_{tid}")

        # Stitch pieces back into coherent sentence
        text = " ".join(words)
        # Clean up punctuation spacing
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)
        return text.strip()

    def batch_encode(
        self,
        texts: list[str],
        lang_code: str = "vie_Latn",
        max_length: int | None = None,
        padding: bool = True,
        return_tensors: str | None = None,
    ) -> dict[str, Any]:
        """Batch encode a list of texts with dynamic or fixed padding."""
        if not texts:
            if return_tensors == "pt":
                import torch

                return {
                    "input_ids": torch.empty((0, 0), dtype=torch.long),
                    "attention_mask": torch.empty((0, 0), dtype=torch.long),
                }
            return {"input_ids": [], "attention_mask": []}

        encoded_list = [self.encode(t, lang_code=lang_code, max_length=max_length) for t in texts]
        max_len = max(len(item["input_ids"]) for item in encoded_list) if padding else None

        batch_input_ids = []
        batch_attention_mask = []

        for item in encoded_list:
            ids = list(item["input_ids"])
            mask = list(item["attention_mask"])
            if padding and max_len is not None and len(ids) < max_len:
                pad_len = max_len - len(ids)
                ids.extend([self.pad_token_id] * pad_len)
                mask.extend([0] * pad_len)
            batch_input_ids.append(ids)
            batch_attention_mask.append(mask)

        if return_tensors == "pt":
            import torch

            return {
                "input_ids": torch.tensor(batch_input_ids, dtype=torch.long),
                "attention_mask": torch.tensor(batch_attention_mask, dtype=torch.long),
            }

        return {"input_ids": batch_input_ids, "attention_mask": batch_attention_mask}

    def batch_decode(
        self,
        batch_ids: list[list[int]] | Any,
        skip_special_tokens: bool = True,
    ) -> list[str]:
        """Decode a batch of token sequences."""
        if hasattr(batch_ids, "tolist"):
            batch_ids = batch_ids.tolist()
        return [self.decode(seq, skip_special_tokens=skip_special_tokens) for seq in batch_ids]

    def measure_fragmentation(
        self,
        texts: list[str],
        lang_code: str = "tyz_Latn",
    ) -> dict[str, float | int]:
        """Measure subword fragmentation statistics on a corpus (T02 requirement).

        Metrics:
        - total_words: Total whitespace-delimited words.
        - total_subwords: Total subword tokens generated (excluding special tags).
        - tokens_per_word (fragmentation_ratio): total_subwords / total_words.
        - char_to_token_ratio: Total characters / total_subwords.
        - unknown_token_count: Number of unk tokens produced.
        - unknown_token_rate: Ratio of unk tokens over total subwords.
        - max_tokens_per_word: Maximum subwords produced by a single word.
        - sample_count: Number of sentences analyzed.

        Returns:
            dict containing computed quantitative metrics.
        """
        if not texts:
            return {
                "sample_count": 0,
                "total_words": 0,
                "total_subwords": 0,
                "tokens_per_word": 0.0,
                "char_to_token_ratio": 0.0,
                "unknown_token_count": 0,
                "unknown_token_rate": 0.0,
                "max_tokens_per_word": 0,
            }

        total_words = 0
        total_subwords = 0
        total_chars = 0
        total_unk = 0
        max_tpw = 1

        for text in texts:
            words = text.strip().split()
            word_count = len(words)
            if word_count == 0:
                continue

            total_words += word_count
            total_chars += len(text)

            # Encode without special tokens to get true subwords
            enc = self.encode(text, lang_code=lang_code, add_special_tokens=False)
            ids = enc["input_ids"]
            subword_count = len(ids)
            total_subwords += subword_count
            unk_count = ids.count(self.unk_token_id)
            total_unk += unk_count

            ratio = subword_count / max(1, word_count)
            if ratio > max_tpw:
                max_tpw = int(ratio + 0.99)

        tpw = round(total_subwords / max(1, total_words), 4)
        cpt = round(total_chars / max(1, total_subwords), 4)
        unk_rate = round(total_unk / max(1, total_subwords), 6)

        return {
            "sample_count": len(texts),
            "total_words": total_words,
            "total_subwords": total_subwords,
            "tokens_per_word": tpw,
            "char_to_token_ratio": cpt,
            "unknown_token_count": total_unk,
            "unknown_token_rate": unk_rate,
            "max_tokens_per_word": max_tpw,
        }

    def save(self, save_directory: str | Path) -> Path:
        """Save tokenizer configuration and vocabulary to directory."""
        p = Path(save_directory)
        p.mkdir(parents=True, exist_ok=True)
        if self._hf_tokenizer is not None and not self.mock_mode:
            self._hf_tokenizer.save_pretrained(str(p))
            meta = {
                "tokenizer_type": "huggingface",
                "model_name_or_path": str(self.model_name_or_path),
                "vocab_size": len(self),
                "pad_token_id": self.pad_token_id,
                "bos_token_id": self.bos_token_id,
                "eos_token_id": self.eos_token_id,
                "unk_token_id": self.unk_token_id,
            }
            with open(p / "tokenizer_metadata.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            return p

        if self._sp_processor is not None and not self.mock_mode:
            if self.sp_model_path and Path(self.sp_model_path).exists():
                shutil.copy2(self.sp_model_path, p / "spm.model")
            meta = {
                "tokenizer_type": "sentencepiece",
                "sp_model_file": "spm.model",
                "vocab_size": len(self),
                "pad_token_id": self.pad_token_id,
                "bos_token_id": self.bos_token_id,
                "eos_token_id": self.eos_token_id,
                "unk_token_id": self.unk_token_id,
            }
            with open(p / "tokenizer_metadata.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            return p

        # Local / mock vocabulary serialization
        sorted_vocab = sorted(self._vocab.items())
        vocab_bytes = json.dumps(sorted_vocab, ensure_ascii=False).encode("utf-8")
        vocab_sha256 = hashlib.sha256(vocab_bytes).hexdigest()

        config = {
            "tokenizer_type": "local_vocab",
            "model_name_or_path": self.model_name_or_path,
            "mock_mode": self.mock_mode,
            "vocab_size": self._vocab_size,
            "vocab_sha256": vocab_sha256,
            "max_length": self.max_length,
            "pad_token_id": self.pad_token_id,
            "bos_token_id": self.bos_token_id,
            "eos_token_id": self.eos_token_id,
            "unk_token_id": self.unk_token_id,
            "is_frozen": self._is_frozen,
            "special_tokens": dict(SPECIAL_TOKENS),
        }
        with open(p / "tokenizer_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        with open(p / "vocab.json", "w", encoding="utf-8") as f:
            json.dump(self._vocab, f, indent=2, ensure_ascii=False)
        return p

    @classmethod
    def load(cls, save_directory: str | Path) -> TayTokenizerWrapper:
        """Load tokenizer from directory, preserving exact engine type and configuration."""
        p = Path(save_directory)
        if not p.exists():
            raise FileNotFoundError(f"Tokenizer directory not found: {p}")

        # Check for SentencePiece model file
        sp_model_file = p / "spm.model"
        if sp_model_file.exists():
            return cls(sp_model_path=str(sp_model_file), mock_mode=False)

        # Check for tokenizer_metadata.json (e.g. from saved SentencePiece or HF)
        meta_file = p / "tokenizer_metadata.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("tokenizer_type") == "sentencepiece":
                sp_f = p / meta.get("sp_model_file", "spm.model")
                if sp_f.exists():
                    return cls(sp_model_path=str(sp_f), mock_mode=False)
            elif meta.get("tokenizer_type") == "huggingface":
                return cls(model_name_or_path=str(p), mock_mode=False)

        # Check for local vocab config
        vocab_file = p / "vocab.json"
        config_file = p / "tokenizer_config.json"
        if vocab_file.exists() and config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            with open(vocab_file, "r", encoding="utf-8") as f:
                vocab = json.load(f)
            mock_mode = cfg.get("mock_mode", False)
            tok = cls(
                model_name_or_path=cfg.get("model_name_or_path", "local-transformer"),
                mock_mode=mock_mode,
                max_length=cfg.get("max_length", 256),
                vocab_size=cfg.get("vocab_size", 32000),
                allow_vocab_growth=not cfg.get("is_frozen", True),
            )
            tok._vocab = {k: int(v) for k, v in vocab.items()}
            tok._id2vocab = {int(v): k for k, v in vocab.items()}
            tok._is_frozen = cfg.get("is_frozen", True)
            tok._next_id = max(tok._vocab.values()) + 1 if tok._vocab else 8
            return tok

        # Check for Hugging Face standard files
        if (p / "tokenizer.json").exists() or (p / "vocab.json").exists():
            return cls(model_name_or_path=str(p), mock_mode=False)

        return cls(model_name_or_path=str(p), mock_mode=False)


# Alias for compatibility with leader.md specification
NLLBTokenizerWrapper = TayTokenizerWrapper
