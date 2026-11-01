#!/usr/bin/env python3
"""Tạo cặp tài liệu ứng viên Tày–Việt từ pilot VOV4, không tạo gold data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.common import comparison, ensure_new, read_jsonl, run_report, write_json, write_jsonl


VI_WORDS = {
    "là", "và", "của", "được", "người", "trong", "những", "không", "một",
    "các", "cho", "đã", "với", "này", "nhà", "nước", "thì", "có", "đến",
    "tại", "trên", "khi", "để", "về", "từ", "nhưng", "cũng", "theo",
}
TAY_CUES = {
    "pỉ", "noọng", "bấu", "đảy", "cúa", "lẻ", "lừ", "nẳm", "mì", "slon",
    "bại", "khau", "hẩư", "pền", "tầư", "cằm", "toẹn", "bươn", "vằn",
}
SKIP_BLOCKS = {"(bản test)", "tiểu phẩm.", "----", "(nhạc)", "(hết)"}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return re.sub(r"\s+", " ", value).strip()


def word_set(value: str) -> set[str]:
    return set(re.findall(r"[^\W\d_]+", value.casefold(), flags=re.UNICODE))


def language_scores(value: str) -> tuple[float, float]:
    words = word_set(value)
    if not words:
        return 0.0, 0.0
    vi = len(words & VI_WORDS) / len(words)
    tay = len(words & TAY_CUES) / len(words)
    return vi, tay


def select_vietnamese_context(blocks: list[str], max_chars: int = 2500) -> str:
    selected: list[str] = []
    for raw in blocks:
        block = normalize_text(raw)
        if not block or block.casefold() in SKIP_BLOCKS or len(block) < 40:
            continue
        vi_score, tay_score = language_scores(block)
        if vi_score <= tay_score:
            continue
        selected.append(block)
        if sum(map(len, selected)) >= max_chars:
            break
    return normalize_text(" ".join(selected))[:max_chars]


def build_candidate(row: dict[str, object]) -> dict[str, object] | None:
    tay_candidate = normalize_text(str(row.get("summary_taynung_candidate", "")))
    blocks = [str(item) for item in row.get("body_blocks", [])]
    vi_context = select_vietnamese_context(blocks)
    if len(tay_candidate) < 40:
        return None
    vi_summary_score, tay_summary_score = language_scores(tay_candidate)
    vi_body_score, tay_body_score = language_scores(vi_context)
    pair_id = hashlib.sha256(str(row["source_url"]).encode("utf-8")).hexdigest()[:20]
    return {
        "pair_id": f"vov4-doc-{pair_id}",
        "tay_text": tay_candidate,
        "vi_text": vi_context,
        "source_url": row["source_url"],
        "source_doc_id": pair_id,
        "source_type": "web_document",
        "source_name": "VOV4 Tay-Nung",
        "license_status": "permission_required",
        "language_label": "unverified_tay_nung",
        "alignment_level": "document_candidate" if vi_context else "monolingual_taynung_candidate",
        "alignment_method": "summary_to_body_heuristic" if vi_context else "none",
        "review_status": "needs_native_and_alignment_review",
        "synthetic": False,
        "heuristic_scores": {
            "summary_vi": round(vi_summary_score, 5),
            "summary_tay": round(tay_summary_score, 5),
            "body_vi": round(vi_body_score, 5),
            "body_tay": round(tay_body_score, 5),
        },
        "quality_flags": [
            flag
            for flag, condition in (
                ("summary_not_clearly_tay", tay_summary_score <= vi_summary_score),
                ("missing_vietnamese_context", not vi_context),
                ("body_not_clearly_vietnamese", bool(vi_context) and vi_body_score <= tay_body_score),
                ("not_sentence_aligned", bool(vi_context)),
                ("tay_nung_not_separated", True),
                ("permission_not_confirmed", True),
            )
            if condition
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/vov4/articles.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/interim/vov4_document_candidates.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/candidates_run.json"))
    parser.add_argument("--compare-to", type=Path, help="Đối chiếu byte với file có sẵn, không thay đổi file đó")
    args = parser.parse_args()
    ensure_new(args.output, args.manifest)
    if args.compare_to is not None and not args.compare_to.is_file():
        parser.error("--compare-to phải trỏ tới file có sẵn")
    inputs = read_jsonl(args.input)
    rows = [candidate for row in inputs if (candidate := build_candidate(row)) is not None]
    write_jsonl(args.output, rows)
    check = comparison(args.output, args.compare_to)
    report = run_report("document_candidates", [args.input], [args.output],
                        input_rows=len(inputs), candidates=len(rows),
                        skipped_short_summary=len(inputs)-len(rows), comparison=check)
    write_json(args.manifest, report)
    print(json.dumps({"input_rows": len(inputs), "candidates": len(rows), "comparison": check}))
    if check.get("byte_identical") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
