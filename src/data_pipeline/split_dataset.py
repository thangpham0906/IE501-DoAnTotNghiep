#!/usr/bin/env python3
"""Chia dữ liệu đã duyệt theo nhóm tài liệu và câu trùng ở từng phía."""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.common import (
    ensure_new,
    normalize_text,
    read_jsonl,
    run_report,
    sha256,
    text_pair,
    write_json,
    write_jsonl,
)


def _text_signatures(text: str) -> tuple[str, set[str], set[str]]:
    """Tạo chữ ký từ vựng và n-gram ký tự phục vụ phát hiện gần trùng (Near-Duplicate)."""
    norm = normalize_text(text).casefold()
    words = set(re.findall(r"\w+", norm, re.UNICODE))
    clean_chars = "".join(norm.split())
    char_3grams = (
        {clean_chars[i : i + 3] for i in range(len(clean_chars) - 2)}
        if len(clean_chars) >= 3
        else {clean_chars}
    )
    return norm, words, char_3grams


def is_near_duplicate(
    sig_a: tuple[str, set[str], set[str]],
    sig_b: tuple[str, set[str], set[str]],
    threshold: float = 0.85,
) -> bool:
    """Xác định hai chuỗi có phải là gần trùng (Near-Duplicate) hay không."""
    norm_a, words_a, ngrams_a = sig_a
    norm_b, words_b, ngrams_b = sig_b

    # 1. Trùng khớp hoàn toàn sau chuẩn hóa
    if norm_a == norm_b:
        return True

    # 2. Tương đồng từ vựng: Jaccard, Dice và tỷ lệ bao hàm (Word-level similarity)
    if len(words_a) >= 3 and len(words_b) >= 3:
        union_words = words_a | words_b
        intersection_words = words_a & words_b
        if union_words and intersection_words:
            # Jaccard từ vựng
            word_jaccard = len(intersection_words) / len(union_words)
            if word_jaccard >= threshold:
                return True

            # Sørensen-Dice từ vựng (chống phạt chênh lệch chiều dài nhẹ)
            word_dice = 2 * len(intersection_words) / (len(words_a) + len(words_b))
            if word_dice >= threshold:
                return True

            # Tỷ lệ bao hàm từ vựng (Containment với tỷ lệ chiều dài hợp lý)
            min_w = min(len(words_a), len(words_b))
            max_w = max(len(words_a), len(words_b))
            if min_w / max_w >= 0.5:
                containment = len(intersection_words) / min_w
                if containment >= threshold and containment >= 0.85:
                    return True

    # 3. Tương đồng 3-gram ký tự: Jaccard và Dice (Character 3-gram similarity)
    if len(ngrams_a) >= 4 and len(ngrams_b) >= 4:
        union_ngrams = ngrams_a | ngrams_b
        intersection_ngrams = ngrams_a & ngrams_b
        if union_ngrams and intersection_ngrams:
            # Jaccard 3-gram
            char_jaccard = len(intersection_ngrams) / len(union_ngrams)
            if char_jaccard >= threshold:
                return True

            # Sørensen-Dice 3-gram
            char_dice = 2 * len(intersection_ngrams) / (len(ngrams_a) + len(ngrams_b))
            if char_dice >= threshold:
                return True

    return False


def connected_groups(
    rows: list[dict],
    near_dup_threshold: float = 0.85,
    return_stats: bool = False,
) -> list[list[dict]] | tuple[list[list[dict]], dict]:
    """Gom nhóm liên thông theo tài liệu nguồn, trùng chính xác và gần trùng từng phía (Q02)."""
    parent = list(range(len(rows)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    first: dict[tuple[str, str], int] = {}
    signatures: list[tuple[tuple[str, set[str], set[str]], tuple[str, set[str], set[str]]]] = []
    word_to_indices_tay: dict[str, list[int]] = defaultdict(list)
    word_to_indices_vi: dict[str, list[int]] = defaultdict(list)

    for i, row in enumerate(rows):
        tay, vi = text_pair(row)
        docs = row.get("source_documents")
        if row.get("training_approved") is not True or not tay or not vi:
            raise ValueError("Chỉ chia cặp song ngữ đã được duyệt")
        if not isinstance(docs, list) or not docs or not all(isinstance(d, str) and d.strip() for d in docs):
            raise ValueError("Thiếu source_documents hợp lệ")

        sig_tay = _text_signatures(tay)
        sig_vi = _text_signatures(vi)
        signatures.append((sig_tay, sig_vi))

        # Gom theo tài liệu và trùng khớp chính xác từng phía
        keys = [("doc", d) for d in docs] + [("tay", sig_tay[0]), ("vi", sig_vi[0])]
        for key in keys:
            if key in first:
                union(i, first[key])
            else:
                first[key] = i

        # Lập chỉ mục từ vựng để so khớp gần trùng nhanh
        for w in sig_tay[1]:
            if len(w) >= 3:
                word_to_indices_tay[w].append(i)
        for w in sig_vi[1]:
            if len(w) >= 3:
                word_to_indices_vi[w].append(i)

    # Phát hiện và hợp nhất các bản ghi gần trùng (Near-Duplicates)
    near_dup_merges = 0
    checked_pairs: set[tuple[int, int]] = set()

    for word_map, side_idx in ((word_to_indices_tay, 0), (word_to_indices_vi, 1)):
        for word, candidate_indices in word_map.items():
            if len(candidate_indices) > 1 and len(candidate_indices) < 200:
                for idx_a in range(len(candidate_indices)):
                    i = candidate_indices[idx_a]
                    for idx_b in range(idx_a + 1, len(candidate_indices)):
                        j = candidate_indices[idx_b]
                        pair = (min(i, j), max(i, j))
                        if pair in checked_pairs:
                            continue
                        checked_pairs.add(pair)
                        if find(i) != find(j):
                            sig_i = signatures[i][side_idx]
                            sig_j = signatures[j][side_idx]
                            if is_near_duplicate(sig_i, sig_j, threshold=near_dup_threshold):
                                union(i, j)
                                near_dup_merges += 1

    groups_map = defaultdict(list)
    for i, row in enumerate(rows):
        groups_map[find(i)].append(row)

    groups_list = list(groups_map.values())
    stats = {
        "total_records": len(rows),
        "connected_groups_count": len(groups_list),
        "near_duplicate_merges": near_dup_merges,
        "near_dup_threshold": near_dup_threshold,
    }
    if return_stats:
        return groups_list, stats
    return groups_list


def verify_zero_leakage(
    train_rows: list[dict],
    val_rows: list[dict],
    test_rows: list[dict],
    near_dup_threshold: float = 0.85,
) -> dict:
    """Xác minh nghiêm ngặt không có rò rỉ ID tài liệu, câu trùng hoặc gần trùng giữa các tập (Q02)."""
    splits = {
        "train": train_rows,
        "val": val_rows,
        "test": test_rows,
    }

    # 1. Kiểm tra tài liệu nguồn (Document ID Isolation)
    docs_by_split: dict[str, set[str]] = {}
    for name, rows in splits.items():
        docs = set()
        for r in rows:
            for d in r.get("source_documents", []):
                docs.add(d)
        docs_by_split[name] = docs

    doc_leaks = {
        "train_val": list(docs_by_split["train"] & docs_by_split["val"]),
        "train_test": list(docs_by_split["train"] & docs_by_split["test"]),
        "val_test": list(docs_by_split["val"] & docs_by_split["test"]),
    }
    if any(doc_leaks.values()):
        raise ValueError(f"Rò rỉ ID tài liệu giữa các tập chia: {doc_leaks}")

    # 2. Kiểm tra trùng khớp và gần trùng câu ở từng phía ngôn ngữ
    signatures_by_split = {
        name: [(_text_signatures(text_pair(r)[0]), _text_signatures(text_pair(r)[1])) for r in rows]
        for name, rows in splits.items()
    }

    leakage_findings = []
    split_pairs = [("train", "val"), ("train", "test"), ("val", "test")]

    for s1, s2 in split_pairs:
        list_1 = signatures_by_split[s1]
        list_2 = signatures_by_split[s2]
        for (tay1, vi1) in list_1:
            for (tay2, vi2) in list_2:
                # Trùng chính xác Tày
                if tay1[0] == tay2[0]:
                    leakage_findings.append(f"Exact Tay match between {s1} and {s2}: '{tay1[0]}'")
                # Trùng chính xác Việt
                if vi1[0] == vi2[0]:
                    leakage_findings.append(f"Exact Vi match between {s1} and {s2}: '{vi1[0]}'")
                # Gần trùng Tày
                if is_near_duplicate(tay1, tay2, threshold=near_dup_threshold):
                    leakage_findings.append(f"Near-duplicate Tay match between {s1} and {s2}: '{tay1[0]}' vs '{tay2[0]}'")
                # Gần trùng Việt
                if is_near_duplicate(vi1, vi2, threshold=near_dup_threshold):
                    leakage_findings.append(f"Near-duplicate Vi match between {s1} and {s2}: '{vi1[0]}' vs '{vi2[0]}'")

    if leakage_findings:
        raise ValueError(
            f"Phát hiện rò rỉ dữ liệu đánh giá vào huấn luyện (Q02):\n"
            + "\n".join(leakage_findings[:5])
        )

    return {
        "zero_leakage_verified": True,
        "doc_isolation": "100% disjoint",
        "near_duplicate_cross_split_checked": True,
        "checked_splits": list(splits.keys()),
    }


def split_dataset(
    input_path: Path,
    output_dir: Path,
    clean_manifest: Path,
    manifest: Path,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    seed: int = 42,
    near_dup_threshold: float = 0.85,
) -> dict:
    if not (0 < train_ratio < 1 and 0 < val_ratio < 1 and train_ratio + val_ratio < 1):
        raise ValueError("Tỷ lệ train và val phải > 0, tổng < 1")
    names = ["train_e0.jsonl", "val.jsonl", "test.jsonl"]
    outputs = [output_dir / name for name in names]
    ensure_new(*outputs, manifest)
    receipt = json.loads(clean_manifest.read_text(encoding="utf-8"))
    if receipt.get("stage") != "clean_dedup" or receipt.get("status") != "completed":
        raise ValueError("Chưa có kết quả làm sạch hợp lệ")
    if not any(item.get("sha256") == sha256(input_path) for item in receipt.get("outputs", [])):
        raise ValueError("Dữ liệu không khớp checksum đầu ra làm sạch")
    rows = read_jsonl(input_path)
    if len(rows) != receipt.get("kept_pairs"):
        raise ValueError("Số bản ghi không khớp manifest làm sạch")

    groups, group_stats = connected_groups(rows, near_dup_threshold=near_dup_threshold, return_stats=True)
    if len(groups) < 3:
        raise ValueError("Cần ít nhất 3 nhóm độc lập để có train/val/test không rỗng")

    random.Random(seed).shuffle(groups)
    n = len(groups)
    n_train = min(max(1, int(n * train_ratio)), n - 2)
    n_val = min(max(1, int(n * val_ratio)), n - n_train - 1)
    chunks = [groups[:n_train], groups[n_train : n_train + n_val], groups[n_train + n_val :]]

    split_rows = {
        name: [row for group in chunk for row in group]
        for name, chunk in zip(names, chunks)
    }

    # Xác minh rò rỉ dữ liệu trước khi xuất tệp
    leakage_check = verify_zero_leakage(
        train_rows=split_rows["train_e0.jsonl"],
        val_rows=split_rows["val.jsonl"],
        test_rows=split_rows["test.jsonl"],
        near_dup_threshold=near_dup_threshold,
    )

    stats = {}
    for name, path, chunk in zip(names, outputs, chunks):
        selected = split_rows[name]
        write_jsonl(path, selected)
        stats[name] = {"groups": len(chunk), "pairs": len(selected)}

    report = run_report(
        "split_dataset",
        [input_path, clean_manifest],
        outputs,
        status="completed",
        seed=seed,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        grouping="Connected components: shared document OR exact Tay/Vi OR near-duplicate Tay/Vi",
        stats=stats,
        grouping_diagnostics=group_stats,
        near_duplicate_detection={
            "status": "completed",
            "method": "token_and_char_3gram_jaccard",
            "threshold": near_dup_threshold,
            "merges_performed": group_stats["near_duplicate_merges"],
            "verification": leakage_check,
        },
    )
    write_json(manifest, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('data/processed/all_sources_cleaned.jsonl'))
    parser.add_argument('--output-dir', type=Path, default=Path('data/processed/splits'))
    parser.add_argument('--clean-manifest', type=Path, default=Path('data/manifests/cleaning_run.json'))
    parser.add_argument('--manifest', type=Path, default=Path('data/manifests/split_run.json'))
    parser.add_argument('--train-ratio', type=float, default=0.8)
    parser.add_argument('--val-ratio', type=float, default=0.1)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    report = split_dataset(args.input, args.output_dir, args.clean_manifest, args.manifest,
                           args.train_ratio, args.val_ratio, args.seed)
    print(json.dumps(report['stats'], ensure_ascii=False))


if __name__ == '__main__':
    main()
