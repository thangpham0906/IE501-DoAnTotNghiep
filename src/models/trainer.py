"""Trainer for Vietnamese-Tay translation models.

Supports training loop, validation loss tracking, early stopping,
reproducible seed setting, and checkpoint saving.
Includes native PyTorch fallback Seq2Seq model when running in mock mode or on CPU/CI.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from src.models.config import Direction, ModelConfig, TrainingConfig
from src.models.dataset import TranslationDataset, collate_translation_batch
from src.models.tokenizer import TayTokenizerWrapper, prepare_model_for_tokenizer


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for transformer sequences."""

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # [1, max_len, d_model]
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1), :]
        return self.dropout(x)


class LocalSeq2SeqTransformer(nn.Module):
    """Local PyTorch Transformer for real Seq2Seq translation training and inference.

    Used for pipeline verification and smoke testing without downloading multi-GB weights.
    Implements multi-head self-attention, cross-attention, causal target masking,
    ignore_index=-100 loss calculation, and autoregressive greedy token generation.
    """

    def __init__(
        self,
        vocab_size: int = 32000,
        d_model: int = 128,
        nhead: int = 4,
        num_encoder_layers: int = 2,
        num_decoder_layers: int = 2,
        dim_feedforward: int = 256,
        dropout: float = 0.1,
        pad_token_id: int = 1,
        bos_token_id: int = 0,
        eos_token_id: int = 2,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.pad_token_id = pad_token_id
        self.bos_token_id = bos_token_id
        self.eos_token_id = eos_token_id
        self.vocab_size = vocab_size

        self.embedding = nn.Embedding(vocab_size, d_model, padding_idx=pad_token_id)
        self.pos_encoder = PositionalEncoding(d_model, max_len=512, dropout=dropout)
        self.transformer = nn.Transformer(
            d_model=d_model,
            nhead=nhead,
            num_encoder_layers=num_encoder_layers,
            num_decoder_layers=num_decoder_layers,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
        )
        self.lm_head = nn.Linear(d_model, vocab_size)
        self.loss_fn = nn.CrossEntropyLoss(ignore_index=-100)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        labels: torch.Tensor | None = None,
        decoder_input_ids: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        device = input_ids.device
        src_key_padding_mask = input_ids == self.pad_token_id

        src_emb = self.pos_encoder(self.embedding(input_ids) * math.sqrt(self.d_model))

        if labels is not None or decoder_input_ids is not None:
            if decoder_input_ids is None and labels is not None:
                # Right shift labels with BOS for autoregressive teacher forcing
                bsz, tgt_len = labels.shape
                dec_in = torch.full((bsz, tgt_len), self.pad_token_id, dtype=torch.long, device=device)
                dec_in[:, 0] = self.bos_token_id
                dec_in[:, 1:] = labels[:, :-1].clone()
                dec_in[dec_in == -100] = self.pad_token_id
            else:
                dec_in = decoder_input_ids

            tgt_len = dec_in.size(1)
            tgt_mask = nn.Transformer.generate_square_subsequent_mask(tgt_len, device=device)
            tgt_key_padding_mask = dec_in == self.pad_token_id

            tgt_emb = self.pos_encoder(self.embedding(dec_in) * math.sqrt(self.d_model))
            out = self.transformer(
                src=src_emb,
                tgt=tgt_emb,
                tgt_mask=tgt_mask,
                src_key_padding_mask=src_key_padding_mask,
                tgt_key_padding_mask=tgt_key_padding_mask,
                memory_key_padding_mask=src_key_padding_mask,
            )
            logits = self.lm_head(out)

            if labels is not None:
                loss = self.loss_fn(
                    logits.view(-1, logits.size(-1)), labels.view(-1)
                )
                return {"loss": loss, "logits": logits}
            return {"logits": logits}

        memory = self.transformer.encoder(src_emb, src_key_padding_mask=src_key_padding_mask)
        return {"memory": memory}

    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_length: int = 128,
        forced_bos_token_id: int | None = None,
        **kwargs: Any,
    ) -> torch.Tensor:
        """Autoregressive greedy generation using real transformer weights."""
        device = input_ids.device
        bsz = input_ids.size(0)
        src_key_padding_mask = input_ids == self.pad_token_id
        src_emb = self.pos_encoder(self.embedding(input_ids) * math.sqrt(self.d_model))
        memory = self.transformer.encoder(src_emb, src_key_padding_mask=src_key_padding_mask)

        if forced_bos_token_id is not None and forced_bos_token_id != self.bos_token_id:
            ys = torch.tensor([[self.bos_token_id, forced_bos_token_id]], dtype=torch.long, device=device).expand(bsz, -1)
        else:
            ys = torch.full((bsz, 1), self.bos_token_id, dtype=torch.long, device=device)
        finished = torch.zeros(bsz, dtype=torch.bool, device=device)

        for _ in range(max_length - 1):
            tgt_len = ys.size(1)
            tgt_mask = nn.Transformer.generate_square_subsequent_mask(tgt_len, device=device)
            tgt_key_padding_mask = ys == self.pad_token_id
            tgt_emb = self.pos_encoder(self.embedding(ys) * math.sqrt(self.d_model))

            out = self.transformer.decoder(
                tgt=tgt_emb,
                memory=memory,
                tgt_mask=tgt_mask,
                memory_key_padding_mask=src_key_padding_mask,
                tgt_key_padding_mask=tgt_key_padding_mask,
            )
            logits = self.lm_head(out[:, -1, :])
            next_tokens = torch.argmax(logits, dim=-1, keepdim=True)

            next_tokens[finished] = self.pad_token_id
            ys = torch.cat([ys, next_tokens], dim=1)

            finished = finished | (next_tokens.squeeze(-1) == self.eos_token_id)
            if finished.all():
                break

        return ys


class MockSeq2SeqModel(nn.Module):
    """Lightweight PyTorch Seq2Seq model for mock mode and fast testing without HF weights."""

    def __init__(
        self,
        vocab_size: int = 32000,
        embed_dim: int = 64,
        hidden_dim: int = 64,
        pad_token_id: int = 1,
        bos_token_id: int = 0,
        eos_token_id: int = 2,
    ) -> None:
        super().__init__()
        self.pad_token_id = pad_token_id
        self.bos_token_id = bos_token_id
        self.eos_token_id = eos_token_id
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=pad_token_id)
        self.encoder = nn.GRU(embed_dim, hidden_dim, batch_first=True)
        self.decoder = nn.GRU(embed_dim, hidden_dim, batch_first=True)
        self.lm_head = nn.Linear(hidden_dim, vocab_size)
        self.loss_fn = nn.CrossEntropyLoss(ignore_index=-100)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        labels: torch.Tensor | None = None,
        decoder_input_ids: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        embeds = self.embedding(input_ids)
        lengths = (input_ids != self.pad_token_id).sum(dim=1).clamp(min=1).cpu()
        packed = nn.utils.rnn.pack_padded_sequence(embeds, lengths, batch_first=True, enforce_sorted=False)
        packed_out, hidden = self.encoder(packed)
        enc_out, _ = nn.utils.rnn.pad_packed_sequence(packed_out, batch_first=True, total_length=input_ids.size(1))

        if labels is not None or decoder_input_ids is not None:
            if decoder_input_ids is None and labels is not None:
                bsz, tgt_len = labels.shape
                dec_in = torch.full((bsz, tgt_len), self.pad_token_id, dtype=torch.long, device=input_ids.device)
                dec_in[:, 0] = self.bos_token_id
                dec_in[:, 1:] = labels[:, :-1].clone()
                dec_in[dec_in == -100] = self.pad_token_id
            else:
                dec_in = decoder_input_ids

            dec_embeds = self.embedding(dec_in)
            dec_out, _ = self.decoder(dec_embeds, hidden)
            logits = self.lm_head(dec_out)

            if labels is not None:
                loss = self.loss_fn(
                    logits.view(-1, logits.size(-1)), labels.view(-1)
                )
                return {"loss": loss, "logits": logits}
            return {"logits": logits}

        dec_out, _ = self.decoder(embeds, hidden)
        logits = self.lm_head(dec_out)
        return {"logits": logits}

    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_length: int = 128,
        forced_bos_token_id: int | None = None,
        **kwargs: Any,
    ) -> torch.Tensor:
        """Autoregressive greedy generation using real GRU weights."""
        device = input_ids.device
        bsz = input_ids.size(0)

        embeds = self.embedding(input_ids)
        lengths = (input_ids != self.pad_token_id).sum(dim=1).clamp(min=1).cpu()
        packed = nn.utils.rnn.pack_padded_sequence(embeds, lengths, batch_first=True, enforce_sorted=False)
        _, hidden = self.encoder(packed)

        if forced_bos_token_id is not None and forced_bos_token_id != self.bos_token_id:
            ys = torch.tensor([[self.bos_token_id, forced_bos_token_id]], dtype=torch.long, device=device).expand(bsz, -1)
        else:
            ys = torch.full((bsz, 1), self.bos_token_id, dtype=torch.long, device=device)

        curr_hidden = hidden
        finished = torch.zeros(bsz, dtype=torch.bool, device=device)

        for _ in range(max_length - 1):
            dec_in = ys[:, -1:]
            dec_embeds = self.embedding(dec_in)
            dec_out, curr_hidden = self.decoder(dec_embeds, curr_hidden)
            logits = self.lm_head(dec_out.squeeze(1))
            next_token = torch.argmax(logits, dim=-1, keepdim=True)
            next_token[finished] = self.pad_token_id
            ys = torch.cat([ys, next_token], dim=1)
            finished = finished | (next_token.squeeze(-1) == self.eos_token_id)
            if finished.all():
                break
        return ys


class TranslationTrainer:
    """Trainer coordinating model optimization, validation, and checkpoint management."""

    def __init__(
        self,
        training_config: TrainingConfig,
        model_config: ModelConfig | None = None,
        model: nn.Module | None = None,
        tokenizer: TayTokenizerWrapper | None = None,
    ) -> None:
        self.config = training_config
        self.model_config = model_config or ModelConfig(
            experiment=self.config.experiment_name,
            direction=self.config.direction,
            mock_mode=self.config.mock_mode,
        )
        self.tokenizer = tokenizer or TayTokenizerWrapper(
            mock_mode=self.config.mock_mode
        )

        if self.config.device == "cpu":
            self.device = torch.device("cpu")
        else:
            try:
                self.device = torch.device(self.config.device if torch.cuda.is_available() else "cpu")
            except Exception:
                self.device = torch.device("cpu")

        # Crucial fix: call _set_seed() BEFORE _init_model() so seed controls weight initialization
        self._set_seed()

        self.model = model or self._init_model()
        self.model.to(self.device)

        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        self.history: list[dict[str, Any]] = []
        self.best_val_loss = float("inf")
        self.best_checkpoint_path: Path | None = None

    def _init_model(self) -> nn.Module:
        """Initialize real HuggingFace model or native PyTorch model."""
        model_type = getattr(self.model_config, "model_type", "transformer")

        # When mock_mode is False:
        if not self.config.mock_mode and not self.model_config.mock_mode:
            # If explicit NLLB model requested or HF path/repo provided:
            is_nllb = (
                model_type == "nllb"
                or "nllb" in self.model_config.model_name_or_path.lower()
                or "/" in self.model_config.model_name_or_path
            )
            if is_nllb or model_type not in ("transformer",):
                try:
                    from transformers import AutoModelForSeq2SeqLM

                    model = AutoModelForSeq2SeqLM.from_pretrained(
                        self.model_config.model_name_or_path
                    )
                    prepare_model_for_tokenizer(model, self.tokenizer)
                    return model
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to load real model '{self.model_config.model_name_or_path}' while mock_mode is False: {e}"
                    ) from e

            # Real local Seq2Seq Transformer (neural smoke, real weights, real autograd)
            return LocalSeq2SeqTransformer(
                vocab_size=len(self.tokenizer),
                d_model=getattr(self.model_config, "d_model", 128),
                nhead=getattr(self.model_config, "nhead", 4),
                num_encoder_layers=getattr(self.model_config, "num_encoder_layers", 2),
                num_decoder_layers=getattr(self.model_config, "num_decoder_layers", 2),
                dim_feedforward=getattr(self.model_config, "dim_feedforward", 256),
                dropout=self.model_config.dropout,
                pad_token_id=self.model_config.pad_token_id,
                bos_token_id=self.model_config.bos_token_id,
                eos_token_id=self.model_config.eos_token_id,
            )

        # Native PyTorch fallback model (mock_mode=True)
        if model_type == "gru":
            return MockSeq2SeqModel(
                vocab_size=len(self.tokenizer),
                embed_dim=64,
                hidden_dim=64,
                pad_token_id=self.model_config.pad_token_id,
                bos_token_id=self.model_config.bos_token_id,
                eos_token_id=self.model_config.eos_token_id,
            )

        return LocalSeq2SeqTransformer(
            vocab_size=len(self.tokenizer),
            d_model=getattr(self.model_config, "d_model", 128),
            nhead=getattr(self.model_config, "nhead", 4),
            num_encoder_layers=getattr(self.model_config, "num_encoder_layers", 2),
            num_decoder_layers=getattr(self.model_config, "num_decoder_layers", 2),
            dim_feedforward=getattr(self.model_config, "dim_feedforward", 256),
            dropout=self.model_config.dropout,
            pad_token_id=self.model_config.pad_token_id,
            bos_token_id=self.model_config.bos_token_id,
            eos_token_id=self.model_config.eos_token_id,
        )

    def _set_seed(self) -> None:
        """Ensure reproducible training and optimize thread contention."""
        seed = self.config.seed
        random.seed(seed)
        os.environ["PYTHONHASHSEED"] = str(seed)
        try:
            import numpy as np

            np.random.seed(seed)
        except ImportError:
            pass

        torch.manual_seed(seed)
        if self.device.type == "cuda" and torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False

        # Constrain CPU threads to prevent resource contention
        if hasattr(torch, "set_num_threads"):
            threads = max(1, getattr(self.config, "cpu_threads", 4))
            try:
                torch.set_num_threads(threads)
            except Exception:
                pass

    def evaluate(self, val_dataset: TranslationDataset) -> dict[str, float]:
        """Compute validation loss and perplexity on the validation dataset."""
        if len(val_dataset) == 0:
            return {"val_loss": 0.0, "val_perplexity": 1.0}

        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            collate_fn=collate_translation_batch,
        )

        self.model.eval()
        total_loss = 0.0
        total_batches = 0

        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(self.device)
                attention_mask = batch["attention_mask"].to(self.device)
                labels = batch["labels"].to(self.device)

                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                )
                loss = outputs["loss"] if isinstance(outputs, dict) else outputs.loss
                total_loss += loss.item()
                total_batches += 1

        avg_loss = total_loss / max(1, total_batches)
        try:
            ppl = math.exp(min(avg_loss, 20.0))
        except OverflowError:
            ppl = float("inf")

        return {"val_loss": round(avg_loss, 4), "val_perplexity": round(ppl, 4)}

    def train(
        self,
        train_dataset: TranslationDataset,
        val_dataset: TranslationDataset | None = None,
    ) -> dict[str, Any]:
        """Execute the full training loop with early stopping and checkpoint saving.

        Args:
            train_dataset: Dataset for training.
            val_dataset: Optional validation dataset for checkpointing and early stopping.

        Returns:
            dict containing training summary, best loss, and metric history.
        """
        self._set_seed()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # Freeze tokenizer to strictly enforce train-only rule and prevent val/test leakage
        if hasattr(self.tokenizer, "freeze") and not getattr(self.tokenizer, "is_frozen", False):
            self.tokenizer.freeze()

        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            collate_fn=collate_translation_batch,
        )

        accum_steps = max(1, getattr(self.config, "gradient_accumulation_steps", 1))
        patience_counter = 0
        global_step = 0
        start_time = time.perf_counter()
        num_batches = len(train_loader)

        epoch = 0
        while True:
            epoch += 1
            self.model.train()
            running_loss = 0.0
            epoch_steps = 0
            self.optimizer.zero_grad()

            for step_idx, batch in enumerate(train_loader):
                input_ids = batch["input_ids"].to(self.device)
                attention_mask = batch["attention_mask"].to(self.device)
                labels = batch["labels"].to(self.device)

                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                )
                loss = outputs["loss"] if isinstance(outputs, dict) else outputs.loss

                # Calculate unbiased accumulation factor for remainder micro-batches
                window_start = (step_idx // accum_steps) * accum_steps
                window_size = min(accum_steps, num_batches - window_start)
                scaled_loss = loss / window_size
                scaled_loss.backward()

                running_loss += loss.item()
                epoch_steps += 1

                is_accum_boundary = (
                    (step_idx + 1) % accum_steps == 0
                    or (step_idx + 1) == num_batches
                )
                if is_accum_boundary:
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                    self.optimizer.step()
                    self.optimizer.zero_grad()
                    global_step += 1

                    if self.config.max_steps > 0 and global_step >= self.config.max_steps:
                        break

            avg_train_loss = running_loss / max(1, epoch_steps)
            val_metrics = (
                self.evaluate(val_dataset)
                if val_dataset is not None
                else {"val_loss": avg_train_loss, "val_perplexity": 1.0}
            )

            record = {
                "epoch": epoch,
                "step": global_step,
                "train_loss": round(avg_train_loss, 4),
                "val_loss": val_metrics["val_loss"],
                "val_perplexity": val_metrics["val_perplexity"],
                "elapsed_sec": round(time.perf_counter() - start_time, 2),
            }
            self.history.append(record)

            # Checkpoint on validation improvement
            current_val_loss = val_metrics["val_loss"]
            if current_val_loss < self.best_val_loss:
                self.best_val_loss = current_val_loss
                patience_counter = 0
                ckpt_dir = self.config.output_dir / f"checkpoint-best-{self.config.experiment_name}-{self.config.direction.value}"
                self.save_checkpoint(ckpt_dir, is_best=True)
                self.best_checkpoint_path = ckpt_dir
            else:
                patience_counter += 1
                if self.config.max_steps <= 0 and patience_counter >= self.config.early_stopping_patience:
                    break

            if self.config.max_steps > 0:
                if global_step >= self.config.max_steps:
                    break
            elif epoch >= self.config.num_train_epochs:
                break

        if self.best_checkpoint_path is None:
            ckpt_dir = self.config.output_dir / f"checkpoint-best-{self.config.experiment_name}-{self.config.direction.value}"
            self.save_checkpoint(ckpt_dir, is_best=True)
            self.best_checkpoint_path = ckpt_dir

        total_time = round(time.perf_counter() - start_time, 2)
        summary = {
            "experiment": self.config.experiment_name,
            "direction": self.config.direction.value,
            "best_val_loss": self.best_val_loss,
            "total_epochs": epoch,
            "total_steps": global_step,
            "total_time_sec": total_time,
            "best_checkpoint_path": str(self.best_checkpoint_path) if self.best_checkpoint_path else None,
            "history": self.history,
        }

        # Save training summary log with direction isolation
        summary_path = self.config.output_dir / f"training_summary_{self.config.experiment_name}_{self.config.direction.value}.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        return summary

    def save_checkpoint(self, path: Path | str, is_best: bool = False) -> Path:
        """Save model weights, configuration, and training state with SHA-256 integrity hash."""
        save_path = Path(path)
        save_path.mkdir(parents=True, exist_ok=True)

        is_hf_model = (
            hasattr(self.model, "save_pretrained")
            and not isinstance(self.model, (LocalSeq2SeqTransformer, MockSeq2SeqModel))
        )

        weights_sha256 = None
        if is_hf_model:
            self.model.save_pretrained(str(save_path))
            weights_file = save_path / "model.safetensors"
            if not weights_file.exists():
                weights_file = save_path / "pytorch_model.bin"
            if weights_file.exists():
                hasher = hashlib.sha256()
                with open(weights_file, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                weights_sha256 = hasher.hexdigest()
        else:
            # Native PyTorch weights
            weights_file = save_path / "model.pt"
            torch.save(self.model.state_dict(), weights_file)

            # Compute SHA-256 of weights file
            hasher = hashlib.sha256()
            with open(weights_file, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            weights_sha256 = hasher.hexdigest()

        # Save configs
        self.model_config.save(save_path / "model_config.json")
        self.config.save(save_path / "training_config.json")

        # Save tokenizer and extract fingerprint
        tokenizer_info = None
        if hasattr(self.tokenizer, "save"):
            self.tokenizer.save(save_path / "tokenizer")
        if hasattr(self.tokenizer, "get_vocab_fingerprint"):
            tokenizer_info = self.tokenizer.get_vocab_fingerprint()

        meta = {
            "experiment": self.config.experiment_name,
            "direction": self.config.direction.value,
            "is_best": is_best,
            "best_val_loss": self.best_val_loss,
            "saved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "weights_file": weights_file.name if weights_file.exists() else "model.pt",
            "weights_sha256": weights_sha256,
            "model_architecture": self.model.__class__.__name__,
            "is_hf_model": is_hf_model,
            "tokenizer_info": tokenizer_info,
            "vocab_size": getattr(self.model, "vocab_size", len(self.tokenizer)),
        }
        with open(save_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return save_path

    def load_checkpoint(self, path: Path | str) -> None:
        """Load weights from a checkpoint folder safely using weights_only=True with integrity validation."""
        p = Path(path)
        meta_file = p / "metadata.json"
        meta: dict[str, Any] = {}
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

        is_hf = meta.get("is_hf_model", False)
        weights_name = meta.get("weights_file", "model.pt")
        weights_file = p / weights_name

        if not weights_file.exists() and not is_hf:
            weights_file = p / "model.pt"
            if not weights_file.exists():
                raise FileNotFoundError(f"Weights file not found at: {p}")

        # 1. Validate SHA-256 hash if weights file exists
        if weights_file.exists():
            expected_sha256 = meta.get("weights_sha256")
            if expected_sha256:
                hasher = hashlib.sha256()
                with open(weights_file, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                actual_sha256 = hasher.hexdigest()
                if actual_sha256 != expected_sha256:
                    raise ValueError(
                        f"Checksum mismatch for weights file '{weights_file}': "
                        f"expected {expected_sha256}, got {actual_sha256}."
                    )

        # 2. Validate model architecture
        expected_arch = meta.get("model_architecture")
        current_arch = self.model.__class__.__name__
        if expected_arch and expected_arch != current_arch:
            raise ValueError(
                f"Model architecture mismatch: checkpoint has '{expected_arch}', "
                f"but current trainer model is '{current_arch}'."
            )

        # 3. Validate tokenizer compatibility (special tokens & vocabulary fingerprint)
        expected_tok = meta.get("tokenizer_info")
        if expected_tok and hasattr(self, "tokenizer") and self.tokenizer is not None:
            if hasattr(self.tokenizer, "get_vocab_fingerprint"):
                curr_tok = self.tokenizer.get_vocab_fingerprint()
                # Check special token IDs
                for spec_key in ("pad_token_id", "bos_token_id", "eos_token_id", "unk_token_id"):
                    if expected_tok.get(spec_key) is not None and curr_tok.get(spec_key) is not None:
                        if expected_tok[spec_key] != curr_tok[spec_key]:
                            raise ValueError(
                                f"Tokenizer special token mismatch for '{spec_key}': "
                                f"checkpoint expects {expected_tok[spec_key]}, but trainer has {curr_tok[spec_key]}."
                            )
                # Check vocabulary SHA-256 for local tokenizers
                exp_hash = expected_tok.get("vocab_sha256")
                curr_hash = curr_tok.get("vocab_sha256")
                if exp_hash and curr_hash and exp_hash != curr_hash:
                    raise ValueError(
                        f"Tokenizer vocabulary mismatch! Checkpoint vocab hash '{exp_hash}' "
                        f"does not match current tokenizer vocab hash '{curr_hash}' (token IDs or entries were altered)."
                    )

        # 4. Load weights
        if is_hf and hasattr(self.model, "from_pretrained"):
            from transformers import AutoModelForSeq2SeqLM

            self.model = AutoModelForSeq2SeqLM.from_pretrained(str(p))
            self.model.to(self.device)
            self.model.eval()
        else:
            state_dict = torch.load(weights_file, map_location=self.device, weights_only=True)
            self.model.load_state_dict(state_dict)
            self.model.eval()
