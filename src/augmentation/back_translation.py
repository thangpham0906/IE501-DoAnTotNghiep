"""Back-translation module for generating synthetic bilingual corpus (Dataset U).

Implements BackTranslator:
- Receives target monolingual texts.
- Leverages reverse-direction baseline model (E0) to synthesize source sentences.
- Ensures zero data leakage (Q02) by verifying against validation and test sets.
- Emits reproducible manifest with SHA-256 fingerprints, timestamps, and model provenance.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.data_pipeline.common import normalize_text, read_jsonl, sha256, write_json, write_jsonl
from src.data_pipeline.split_dataset import _text_signatures, is_near_duplicate
from src.models.config import Direction
from src.models.inference_adapter import TranslationInferenceAdapter, TranslationResult


class BackTranslator:
    """Generates synthetic bilingual pairs from monolingual corpus via reverse inference."""

    def __init__(
        self,
        adapter: Any | None = None,
        batch_size: int = 16,
        mock_mode: bool = False,
        model_version: str = "e0-reverse-baseline",
    ) -> None:
        self.batch_size = batch_size
        self.mock_mode = mock_mode
        self.model_version = model_version

        if adapter is not None:
            self.adapter = adapter
        else:
            self.adapter = TranslationInferenceAdapter(
                mock_mode=mock_mode,
                model_version=model_version,
            )

    @staticmethod
    def _extract_eval_sentence_data(
        eval_records: list[dict[str, Any]] | Path | None,
    ) -> tuple[set[str], list[tuple[str, set[str], set[str]]]]:
        """Extract normalized sentence strings and signatures from validation or test records."""
        if eval_records is None:
            return set(), []

        rows: list[dict[str, Any]]
        if isinstance(eval_records, Path):
            if not eval_records.is_file():
                return set(), []
            rows = read_jsonl(eval_records)
        else:
            rows = eval_records

        texts: set[str] = set()
        sigs: list[tuple[str, set[str], set[str]]] = []
        for row in rows:
            for key in ("tay", "tay_text", "vi", "vi_text", "text", "ty"):
                val = row.get(key)
                if isinstance(val, str) and val.strip():
                    norm = normalize_text(val).casefold()
                    if norm not in texts:
                        texts.add(norm)
                        sigs.append(_text_signatures(norm))
        return texts, sigs

    @staticmethod
    def _check_leakage(
        text: str,
        eval_texts: set[str],
        eval_sigs: list[tuple[str, set[str], set[str]]],
        near_dup_threshold: float = 0.85,
    ) -> tuple[bool, str, str]:
        """Check if text leaks into eval set via exact match or near-duplicate."""
        norm = normalize_text(text).casefold()
        if not norm:
            return False, "", ""

        if norm in eval_texts:
            return True, "exact_match", norm

        sig = _text_signatures(norm)
        for s in eval_sigs:
            if is_near_duplicate(sig, s, threshold=near_dup_threshold):
                return True, "near_duplicate", s[0]

        return False, "", ""

    def generate_u_dataset(
        self,
        monolingual_records: list[dict[str, Any]] | Path,
        generation_direction: Direction | str = Direction.TAY_TO_VI,
        output_path: Path | None = None,
        manifest_path: Path | None = None,
        val_records: list[dict[str, Any]] | Path | None = None,
        test_records: list[dict[str, Any]] | Path | None = None,
        target_model_direction: Direction | str | None = None,
        max_records: int | None = None,
        near_dup_threshold: float = 0.85,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Generate synthetic bilingual dataset U via back-translation.

        Args:
            monolingual_records: List of monolingual dicts or path to jsonl.
            generation_direction: Direction of E0 inference (e.g. tyz-vi).
            output_path: Optional path to write dataset U in jsonl.
            manifest_path: Optional path to write audit manifest in json.
            val_records: Validation records to check for leakage.
            test_records: Test records to check for leakage.
            target_model_direction: The intended training direction of the augmented model
                                    (default: opposite of generation_direction).
            max_records: Optional limit on number of monolingual sentences to process.
            near_dup_threshold: Similarity threshold for near-duplicate leakage detection.

        Returns:
            tuple[list[dict], dict]: (u_records, manifest)
        """
        start_time = time.perf_counter()

        gen_dir = Direction.normalize(generation_direction)
        if target_model_direction is not None:
            tgt_dir = Direction.normalize(target_model_direction)
        else:
            tgt_dir = (
                Direction.VI_TO_TAY
                if gen_dir == Direction.TAY_TO_VI
                else Direction.TAY_TO_VI
            )

        # 1. Load monolingual rows
        raw_rows: list[dict[str, Any]]
        if isinstance(monolingual_records, Path):
            raw_rows = read_jsonl(monolingual_records)
        else:
            raw_rows = list(monolingual_records)

        # 2. Extract anti-leakage protection data
        val_texts, val_sigs = self._extract_eval_sentence_data(val_records)
        test_texts, test_sigs = self._extract_eval_sentence_data(test_records)
        eval_texts = val_texts | test_texts
        eval_sigs = val_sigs + test_sigs

        # 3. Filter monolingual texts & deduplicate
        seen_texts: set[str] = set()
        clean_inputs: list[dict[str, Any]] = []
        leaked_records: list[dict[str, Any]] = []
        language_mismatched: list[dict[str, Any]] = []

        # Validate monolingual language matches reverse model source
        is_tay_source = (gen_dir == Direction.TAY_TO_VI)
        disallowed_lang_tags = {"vi", "vie", "vietnamese"} if is_tay_source else {"ty", "tay", "tyz", "tay_nung"}

        for idx, row in enumerate(raw_rows):
            # Check language tag if present
            row_lang = str(row.get("lang") or row.get("language") or "").strip().lower()
            if row_lang and row_lang in disallowed_lang_tags:
                language_mismatched.append({
                    "record_index": idx,
                    "lang": row_lang,
                    "reason": f"Mismatched monolingual language for generation direction {gen_dir.value}",
                })
                continue

            # Extract mono text according to expected language
            if is_tay_source:
                text = (
                    row.get("tay_text")
                    or row.get("tay")
                    or row.get("ty")
                    or row.get("text")
                    or ""
                )
            else:
                text = (
                    row.get("vi_text")
                    or row.get("vi")
                    or row.get("text")
                    or ""
                )

            if not isinstance(text, str) or not text.strip():
                continue

            norm_text = normalize_text(text)
            norm_key = norm_text.casefold()

            # Anti-leakage verification (Exact & Near-duplicate)
            is_leaked, leak_type, matched = self._check_leakage(
                norm_text, eval_texts, eval_sigs, near_dup_threshold=near_dup_threshold
            )
            if is_leaked:
                leaked_records.append({
                    "record_index": idx,
                    "text": norm_text,
                    "leak_type": leak_type,
                    "matched_eval_text": matched,
                    "reason": "matches_eval_set",
                })
                continue

            if norm_key in seen_texts:
                continue

            # Discard too short inputs (< 2 words) before inference
            if len(norm_text.split()) < 2:
                continue

            seen_texts.add(norm_key)
            clean_inputs.append({
                "original_record": row,
                "text": norm_text,
                "mono_id": row.get("document_id") or row.get("source_doc_id") or f"mono_{idx:05d}",
                "source_id": row.get("source_id") or "monolingual_corpus",
            })

            if max_records is not None and len(clean_inputs) >= max_records:
                break

        # 4. Perform back-translation inference
        texts_to_translate = [item["text"] for item in clean_inputs]

        translations: list[str] = []
        if hasattr(self.adapter, "translate_batch") and callable(self.adapter.translate_batch):
            batch_results = self.adapter.translate_batch(
                texts_to_translate,
                direction=gen_dir,
                batch_size=self.batch_size,
            )
            for res in batch_results:
                if isinstance(res, TranslationResult):
                    translations.append(res.tgt_text)
                elif isinstance(res, dict):
                    translations.append(res.get("tgt_text", ""))
                else:
                    translations.append(str(res))
        else:
            for text in texts_to_translate:
                res = self.adapter.translate(text, direction=gen_dir)
                if isinstance(res, TranslationResult):
                    translations.append(res.tgt_text)
                elif isinstance(res, dict):
                    translations.append(res.get("tgt_text", ""))
                else:
                    translations.append(str(res))

        # 5. Form synthetic bilingual records with post-translation anti-leakage & format sanity
        u_records: list[dict[str, Any]] = []
        synth_leaked_records: list[dict[str, Any]] = []
        format_rejected_count = 0
        seen_pair_hashes: set[str] = set()

        for idx, (inp, synth_text) in enumerate(zip(clean_inputs, translations)):
            mono_text = inp["text"]
            norm_synth = normalize_text(synth_text)

            # Sanity checks on synthetic output before QC
            if not norm_synth or len(norm_synth.split()) < 2:
                format_rejected_count += 1
                continue

            # Check if synthetic output verbatim copies monolingual source
            if norm_synth.casefold() == mono_text.casefold():
                format_rejected_count += 1
                continue

            # Anti-leakage check on the SYNTHETIC output against held-out sets
            is_synth_leaked, s_leak_type, s_matched = self._check_leakage(
                norm_synth, eval_texts, eval_sigs, near_dup_threshold=near_dup_threshold
            )
            if is_synth_leaked:
                synth_leaked_records.append({
                    "record_index": idx,
                    "synth_text": norm_synth,
                    "leak_type": s_leak_type,
                    "matched_eval_text": s_matched,
                    "reason": "synthetic_output_leaks_into_eval",
                })
                continue

            # Assign language roles based on generation direction
            if gen_dir == Direction.TAY_TO_VI:
                vi_val = norm_synth
                tay_val = mono_text
                synth_side = "vi"
                mono_lang = "ty"
            else:
                vi_val = mono_text
                tay_val = norm_synth
                synth_side = "ty"
                mono_lang = "vi"

            pair_hash = hashlib.sha256(
                json.dumps([normalize_text(tay_val).casefold(), normalize_text(vi_val).casefold()], ensure_ascii=False).encode("utf-8")
            ).hexdigest()

            if pair_hash in seen_pair_hashes:
                continue
            seen_pair_hashes.add(pair_hash)

            record: dict[str, Any] = {
                "u_id": f"u_{len(u_records):06d}_{pair_hash[:8]}",
                "tay": tay_val,
                "vi": vi_val,
                "tay_text": tay_val,
                "vi_text": vi_val,
                "synthetic": True,
                "source_type": "back_translation",
                "source_monolingual_id": inp["mono_id"],
                "source_monolingual_text": mono_text,
                "source_monolingual_lang": mono_lang,
                "synthetic_side": synth_side,
                "generation_model": self.model_version,
                "generation_direction": gen_dir.value,
                "target_model_direction": tgt_dir.value,
                "hash": pair_hash,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            u_records.append(record)

        duration_sec = round(time.perf_counter() - start_time, 3)

        # 6. Build Manifest
        manifest: dict[str, Any] = {
            "dataset_name": "U_synthetic_back_translation",
            "generation_model": self.model_version,
            "generation_direction": gen_dir.value,
            "target_model_direction": tgt_dir.value,
            "decoding_manifest": {
                "generator_checkpoint": self.model_version,
                "beam_size": 4,
                "max_length": 256,
                "repetition_penalty": 1.2,
                "batch_size": self.batch_size,
            },
            "total_monolingual_candidates": len(raw_rows),
            "language_mismatched_skipped": len(language_mismatched),
            "clean_inputs_processed": len(clean_inputs),
            "format_rejected_count": format_rejected_count,
            "u_records_generated": len(u_records),
            "anti_leakage": {
                "val_sentences_checked": len(val_texts),
                "test_sentences_checked": len(test_texts),
                "near_dup_threshold": near_dup_threshold,
                "source_leakage_count": len(leaked_records),
                "synth_leakage_count": len(synth_leaked_records),
                "leakage_count": len(leaked_records) + len(synth_leaked_records),
                "leaked_samples": (leaked_records + synth_leaked_records)[:10],
            },
            "duration_seconds": duration_sec,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # 7. Write to disk if paths provided
        if output_path is not None:
            output_path = Path(output_path)
            write_jsonl(output_path, u_records)
            manifest["output_file"] = str(output_path)
            manifest["output_sha256"] = sha256(output_path)

        if manifest_path is not None:
            manifest_path = Path(manifest_path)
            write_json(manifest_path, manifest)

        return u_records, manifest
