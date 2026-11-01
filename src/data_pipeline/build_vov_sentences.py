#!/usr/bin/env python3
"""Tách mô tả VOV4 thành câu Tày–Nùng ứng viên để chạy back-translation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.build_vov_candidates import normalize_text
from src.data_pipeline.common import comparison, ensure_new, read_jsonl, run_report, write_json, write_jsonl


def split_sentences(text: str, max_chars: int = 300) -> list[str]:
    initial = re.split(r"(?<=[.!?])\s+", normalize_text(text))
    pieces: list[str] = []
    for sentence in initial:
        sentence = sentence.strip()
        if len(sentence) <= max_chars:
            if len(sentence) >= 20:
                pieces.append(sentence)
            continue
        current = ""
        for part in re.split(r"(?<=[,;:])\s+", sentence):
            proposed = f"{current} {part}".strip()
            if current and len(proposed) > max_chars:
                pieces.append(current)
                current = part
            else:
                current = proposed
        if len(current) >= 20:
            pieces.append(current)
    return pieces


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/interim/vov4_document_candidates.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/interim/vov4_sentence_candidates.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/sentences_run.json"))
    parser.add_argument("--compare-to", type=Path)
    args = parser.parse_args()

    ensure_new(args.output, args.manifest)
    if args.compare_to is not None and not args.compare_to.is_file():
        parser.error("--compare-to phải trỏ tới file có sẵn")

    rows = []
    seen = set()
    documents = read_jsonl(args.input)
    for document in documents:
        for index, sentence in enumerate(split_sentences(str(document["tay_text"]))):
            fingerprint = hashlib.sha256(sentence.casefold().encode("utf-8")).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            row = dict(document)
            row["pair_id"] = f"{document['pair_id']}-s{index:03d}"
            row["tay_text"] = sentence
            row["vi_text"] = ""
            row["alignment_level"] = "monolingual_sentence_candidate"
            row["alignment_method"] = "punctuation_sentence_split"
            row["quality_flags"] = list(dict.fromkeys(document["quality_flags"] + ["sentence_split_heuristic"]))
            rows.append(row)

    write_jsonl(args.output, rows)
    check = comparison(args.output, args.compare_to)
    write_json(args.manifest, run_report("sentence_candidates", [args.input], [args.output],
               documents=len(documents), sentence_candidates=len(rows), comparison=check))
    print(json.dumps({"sentence_candidates": len(rows), "output": str(args.output), "comparison": check}))
    if check.get("byte_identical") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
