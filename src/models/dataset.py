"""PyTorch Dataset and Collator for Vietnamese-Tay translation.

Handles dynamic padding, attention masking, language tags, and bidirectional mapping.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import Dataset

from src.models.config import Direction
from src.models.tokenizer import TayTokenizerWrapper


def extract_pair(
    item: dict[str, Any], direction: Direction
) -> tuple[str, str]:
    """Extract source and target texts based on translation direction.

    Supports diverse dictionary keys:
    - Vietnamese: 'vi_text', 'vi', 'vietnamese', 'src_text'
    - Tay: 'tay_text', 'tay', 'ty', 'tyz', 'tgt_text'
    """
    vi_val = (
        item.get("vi_text")
        or item.get("vi")
        or item.get("vietnamese")
        or item.get("src_text", "")
    )
    tay_val = (
        item.get("tay_text")
        or item.get("tay")
        or item.get("ty")
        or item.get("tyz")
        or item.get("tgt_text", "")
    )

    if direction == Direction.VI_TO_TAY:
        return str(vi_val).strip(), str(tay_val).strip()
    return str(tay_val).strip(), str(vi_val).strip()


class TranslationDataset(Dataset):
    """PyTorch Dataset for Vietnamese-Tay bilingual sentence pairs.

    Loads from in-memory records or JSONL file path, and tokenizes on the fly.
    """

    def __init__(
        self,
        data: list[dict[str, Any]] | Path | str,
        tokenizer: TayTokenizerWrapper,
        direction: Direction | str = Direction.VI_TO_TAY,
        max_source_length: int = 256,
        max_target_length: int = 256,
    ) -> None:
        self.tokenizer = tokenizer
        self.direction = Direction.normalize(direction)
        self.max_source_length = max_source_length
        self.max_target_length = max_target_length
        self.records: list[dict[str, Any]] = []

        if isinstance(data, (str, Path)):
            p = Path(data)
            if not p.exists():
                raise FileNotFoundError(f"Dataset file not found: {p}")
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.records.append(json.loads(line))
        elif isinstance(data, list):
            self.records = data
        else:
            raise TypeError(f"Expected list or Path/str for data, got {type(data)}")

        # Auto-fit vocabulary on training texts if tokenizer is unfrozen (train-only rule)
        if hasattr(self.tokenizer, "fit_dataset") and not getattr(self.tokenizer, "is_frozen", False):
            self.tokenizer.fit_dataset(self)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.records[idx]
        src_text, tgt_text = extract_pair(item, self.direction)

        src_lang = self.direction.source_tag
        tgt_lang = self.direction.target_tag

        # Encode source with source language tag: [BOS, src_lang, w1, ..., EOS]
        src_encoded = self.tokenizer.encode(
            src_text,
            lang_code=src_lang,
            max_length=self.max_source_length,
            add_special_tokens=True,
        )

        # Encode target with target language tag: [BOS, tgt_lang, w1, ..., EOS]
        tgt_encoded = self.tokenizer.encode(
            tgt_text,
            lang_code=tgt_lang,
            max_length=self.max_target_length,
            add_special_tokens=True,
        )

        tgt_ids = list(tgt_encoded["input_ids"])
        # Standard Seq2Seq target alignment:
        # labels is target sequence starting from target_lang_tag to EOS (shifted target)
        labels = tgt_ids[1:] if len(tgt_ids) > 1 else tgt_ids
        # decoder_input_ids starts with BOS and includes up to token before EOS
        decoder_input_ids = tgt_ids[:-1] if len(tgt_ids) > 1 else tgt_ids

        return {
            "input_ids": src_encoded["input_ids"],
            "attention_mask": src_encoded["attention_mask"],
            "labels": labels,
            "decoder_input_ids": decoder_input_ids,
            "src_text": src_text,
            "tgt_text": tgt_text,
            "direction": self.direction.value,
        }


class TranslationCollator:
    """Collator for dynamic padding of sequence batches."""

    def __init__(
        self,
        pad_token_id: int = 1,
        label_pad_token_id: int = -100,
    ) -> None:
        self.pad_token_id = pad_token_id
        self.label_pad_token_id = label_pad_token_id

    def __call__(self, batch: list[dict[str, Any]]) -> dict[str, Any]:
        return collate_translation_batch(
            batch,
            pad_token_id=self.pad_token_id,
            label_pad_token_id=self.label_pad_token_id,
        )


def collate_translation_batch(
    batch: list[dict[str, Any]],
    pad_token_id: int = 1,
    label_pad_token_id: int = -100,
) -> dict[str, Any]:
    """Dynamic padding of input_ids, attention_mask, and labels to the max length in the batch.

    Args:
        batch: List of samples returned by TranslationDataset.__getitem__.
        pad_token_id: ID used to pad input sequences.
        label_pad_token_id: ID used to pad target sequences (default -100 for CrossEntropyLoss ignore).

    Returns:
        dict of PyTorch tensors:
            - input_ids: LongTensor [batch_size, max_src_len]
            - attention_mask: LongTensor [batch_size, max_src_len]
            - labels: LongTensor [batch_size, max_tgt_len]
            - src_texts: list[str]
            - tgt_texts: list[str]
            - direction: str
    """
    if not batch:
        return {
            "input_ids": torch.empty((0, 0), dtype=torch.long),
            "attention_mask": torch.empty((0, 0), dtype=torch.long),
            "labels": torch.empty((0, 0), dtype=torch.long),
            "src_texts": [],
            "tgt_texts": [],
            "direction": "",
        }

    max_src_len = max(len(x["input_ids"]) for x in batch)
    max_tgt_len = max(len(x["labels"]) for x in batch)
    has_dec_in = any("decoder_input_ids" in x for x in batch)
    max_dec_len = max(len(x.get("decoder_input_ids", [])) for x in batch) if has_dec_in else 0

    batch_input_ids: list[list[int]] = []
    batch_attention_mask: list[list[int]] = []
    batch_labels: list[list[int]] = []
    batch_dec_in: list[list[int]] = []
    src_texts: list[str] = []
    tgt_texts: list[str] = []

    for item in batch:
        # Pad input_ids and attention_mask
        ids = list(item["input_ids"])
        mask = list(item["attention_mask"])
        src_pad_len = max_src_len - len(ids)
        ids.extend([pad_token_id] * src_pad_len)
        mask.extend([0] * src_pad_len)
        batch_input_ids.append(ids)
        batch_attention_mask.append(mask)

        # Pad labels with label_pad_token_id (-100)
        labels = list(item["labels"])
        tgt_pad_len = max_tgt_len - len(labels)
        labels.extend([label_pad_token_id] * tgt_pad_len)
        batch_labels.append(labels)

        # Pad decoder_input_ids with pad_token_id if present
        if has_dec_in:
            dec_in = list(item.get("decoder_input_ids", []))
            dec_pad_len = max_dec_len - len(dec_in)
            dec_in.extend([pad_token_id] * dec_pad_len)
            batch_dec_in.append(dec_in)

        src_texts.append(item.get("src_text", ""))
        tgt_texts.append(item.get("tgt_text", ""))

    direction = batch[0].get("direction", "")

    result: dict[str, Any] = {
        "input_ids": torch.tensor(batch_input_ids, dtype=torch.long),
        "attention_mask": torch.tensor(batch_attention_mask, dtype=torch.long),
        "labels": torch.tensor(batch_labels, dtype=torch.long),
        "src_texts": src_texts,
        "tgt_texts": tgt_texts,
        "direction": direction,
    }
    if has_dec_in:
        result["decoder_input_ids"] = torch.tensor(batch_dec_in, dtype=torch.long)
    return result
