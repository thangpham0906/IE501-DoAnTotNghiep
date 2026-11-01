#!/usr/bin/env python3
"""Chia dữ liệu đã duyệt theo nhóm tài liệu và câu trùng ở từng phía."""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.common import ensure_new, read_jsonl, run_report, sha256, text_pair, write_json, write_jsonl


def connected_groups(rows: list[dict]) -> list[list[dict]]:
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first = {}
    for i, row in enumerate(rows):
        tay, vi = text_pair(row)
        docs = row.get('source_documents')
        if row.get('training_approved') is not True or not tay or not vi:
            raise ValueError('Chỉ chia cặp song ngữ đã được duyệt')
        if not isinstance(docs, list) or not docs or not all(isinstance(d,str) and d.strip() for d in docs):
            raise ValueError('Thiếu source_documents hợp lệ')
        keys = [('doc', d) for d in docs] + [('tay', tay.casefold()), ('vi', vi.casefold())]
        for key in keys:
            if key in first:
                parent[find(i)] = find(first[key])
            else:
                first[key] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[find(i)].append(row)
    return list(groups.values())


def split_dataset(input_path: Path, output_dir: Path, clean_manifest: Path,
                  manifest: Path, train_ratio: float = 0.8, val_ratio: float = 0.1,
                  seed: int = 42) -> dict:
    if not (0 < train_ratio < 1 and 0 < val_ratio < 1 and train_ratio + val_ratio < 1):
        raise ValueError('Tỷ lệ train và val phải > 0, tổng < 1')
    names = ['train_e0.jsonl', 'val.jsonl', 'test.jsonl']
    outputs = [output_dir / name for name in names]
    ensure_new(*outputs, manifest)
    receipt = json.loads(clean_manifest.read_text(encoding='utf-8'))
    if receipt.get('stage') != 'clean_dedup' or receipt.get('status') != 'completed':
        raise ValueError('Chưa có kết quả làm sạch hợp lệ')
    if not any(item.get('sha256') == sha256(input_path) for item in receipt.get('outputs', [])):
        raise ValueError('Dữ liệu không khớp checksum đầu ra làm sạch')
    rows = read_jsonl(input_path)
    if len(rows) != receipt.get('kept_pairs'):
        raise ValueError('Số bản ghi không khớp manifest làm sạch')
    groups = connected_groups(rows)
    if len(groups) < 3:
        raise ValueError('Cần ít nhất 3 nhóm độc lập để có train/val/test không rỗng')
    random.Random(seed).shuffle(groups)
    n = len(groups)
    n_train = min(max(1, int(n * train_ratio)), n - 2)
    n_val = min(max(1, int(n * val_ratio)), n - n_train - 1)
    chunks = [groups[:n_train], groups[n_train:n_train+n_val], groups[n_train+n_val:]]
    stats = {}
    for name, path, chunk in zip(names, outputs, chunks):
        selected = [row for group in chunk for row in group]
        write_jsonl(path, selected)
        stats[name] = {'groups': len(chunk), 'pairs': len(selected)}
    report = run_report('split_dataset', [input_path, clean_manifest], outputs,
                        status='completed', seed=seed, train_ratio=train_ratio, val_ratio=val_ratio,
                        grouping='Connected components: shared document OR normalized Tay OR normalized Vietnamese',
                        stats=stats, near_duplicate_detection='not_performed')
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
