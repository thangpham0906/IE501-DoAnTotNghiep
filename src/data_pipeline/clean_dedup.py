#!/usr/bin/env python3
"""Chuẩn hóa và khử trùng lặp các bản ghi được duyệt trong source registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.common import (ensure_new, normalize_text, read_jsonl,
                                     run_report, sha256, text_pair, write_json, write_jsonl)


def get_hash(tay: str, vi: str) -> str:
    payload = json.dumps([normalize_text(tay).casefold(), normalize_text(vi).casefold()],
                         ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def approved_numbers(source: dict, count: int) -> set[int]:
    if source.get('training_approved') is not True:
        return set()
    required = {'content_origin_status': 'verified', 'language_review_status': 'approved',
                'translation_review_status': 'approved', 'usage_permission_status': 'confirmed'}
    if any(source.get(key) != value for key, value in required.items()):
        raise ValueError('Nguồn được bật training_approved nhưng thiếu xác minh nguồn/ngôn ngữ/bản dịch/quyền sử dụng')
    if not isinstance(source.get('reviewed_by'), str) or not source['reviewed_by'].strip():
        raise ValueError('Thiếu reviewed_by')
    evidence = source.get('review_evidence')
    if not isinstance(evidence, list) or not evidence or not all(isinstance(x, str) and x.strip() for x in evidence):
        raise ValueError('Thiếu review_evidence')
    numbers = source.get('approved_record_numbers')
    if not isinstance(numbers, list) or not numbers or any(type(n) is not int or n < 1 or n > count for n in numbers):
        raise ValueError('approved_record_numbers phải là các số thứ tự bản ghi hợp lệ, bắt đầu từ 1')
    return set(numbers)


def process_all_raw_data(raw_dir: Path, output_path: Path, registry_path: Path,
                         report_path: Path, project_root: Path = ROOT) -> dict:
    ensure_new(output_path, report_path)
    registry = json.loads(registry_path.read_text(encoding='utf-8'))
    sources = registry['sources']
    registered = set()
    loaded = []
    # Validate every registered input before writing any dataset.
    for source in sources:
        path = (project_root / source['path']).resolve()
        if not path.is_relative_to(raw_dir.resolve()):
            raise ValueError(f'Nguồn nằm ngoài raw_dir: {source["path"]}')
        if path in registered:
            raise ValueError(f'Nguồn bị khai báo lặp: {source["path"]}')
        registered.add(path)
        if sha256(path) != source['sha256']:
            raise ValueError(f'Checksum nguồn đã đổi; cần kiểm kê và duyệt lại: {source["path"]}')
        rows = read_jsonl(path)
        loaded.append((source, path, rows, approved_numbers(source, len(rows))))
    unregistered = {p.resolve() for p in raw_dir.rglob('*.jsonl')} - registered
    if unregistered:
        raise ValueError('Có JSONL chưa được khai báo trong source registry')

    unique = {}
    decisions = []
    approved_count = 0
    tay_to_vis = {}
    vi_to_tays = {}
    one_sided_duplicates = {"identical_tay_different_vi": 0, "identical_vi_different_tay": 0}

    for source, path, rows, selected in loaded:
        accepted = 0
        for number, row in enumerate(rows, 1):
            if number not in selected:
                continue
            tay, vi = text_pair(row)
            if not tay or not vi:
                raise ValueError(f'{path}: bản ghi {number} được duyệt nhưng thiếu một phía văn bản')
            if row.get('synthetic') is True or row.get('source_type') == 'back_translation':
                raise ValueError('Dữ liệu tổng hợp cần luồng riêng, không đưa vào E0')
            doc = row.get('source_doc_id')
            url = row.get('source_url')
            if not doc and not url:
                raise ValueError(f'{path}: bản ghi {number} thiếu tài liệu nguồn để chia tập')
            documents = []
            if doc:
                documents.append(f'{source["source_id"]}:{doc}')
            if url:
                documents.append(f'url:{url}')
            reference = {'path': source['path'], 'sha256': source['sha256'], 'record_number': number}
            existing_refs = row.get('source_records', [])
            if not isinstance(existing_refs, list):
                existing_refs = []
            fingerprint = get_hash(tay, vi)

            # Theo dõi một phía trùng lặp
            norm_tay = tay.casefold()
            norm_vi = vi.casefold()
            if norm_tay in tay_to_vis and norm_vi not in tay_to_vis[norm_tay]:
                one_sided_duplicates["identical_tay_different_vi"] += 1
            tay_to_vis.setdefault(norm_tay, set()).add(norm_vi)

            if norm_vi in vi_to_tays and norm_tay not in vi_to_tays[norm_vi]:
                one_sided_duplicates["identical_vi_different_tay"] += 1
            vi_to_tays.setdefault(norm_vi, set()).add(norm_tay)

            if fingerprint in unique:
                unique[fingerprint]['source_records'].append(reference)
                unique[fingerprint]['source_documents'] = sorted(set(
                    unique[fingerprint]['source_documents'] + documents))
            else:
                combined_refs = [reference] + [r for r in existing_refs if r != reference]
                unique[fingerprint] = {
                    **row, 'tay': tay, 'vi': vi, 'tay_text': tay, 'vi_text': vi,
                    'hash': fingerprint, 'source_documents': sorted(documents),
                    'source_records': combined_refs, 'training_approved': True,
                }
            accepted += 1
        approved_count += accepted
        decisions.append({'path': source['path'], 'records': len(rows),
                          'approved_records': accepted, 'held_records': len(rows)-accepted,
                          'reason': 'explicit_record_review' if selected else 'source_not_approved'})
    rows = list(unique.values())
    if rows:
        write_jsonl(output_path, rows)
    report = run_report('clean_dedup', [registry_path] + [p for _, p, _, _ in loaded],
                        [output_path] if rows else [],
                        status='completed' if rows else 'no_approved_data',
                        input_records=sum(len(r) for _, _, r, _ in loaded),
                        approved_records=approved_count, kept_pairs=len(rows),
                        duplicate_approved_pairs=approved_count-len(rows),
                        source_decisions=decisions,
                        one_sided_duplicates=one_sided_duplicates,
                        normalization='NFC and collapsed whitespace; dedup on casefolded pair')
    write_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir', type=Path, default=Path('data/raw'))
    parser.add_argument('--registry', type=Path, default=Path('data/manifests/source_registry.json'))
    parser.add_argument('--output', type=Path, default=Path('data/processed/all_sources_cleaned.jsonl'))
    parser.add_argument('--manifest', type=Path, default=Path('data/manifests/cleaning_run.json'))
    args = parser.parse_args()
    report = process_all_raw_data(args.raw_dir, args.output, args.registry, args.manifest)
    print(json.dumps({k: report[k] for k in ('status','input_records','approved_records','kept_pairs')}))


if __name__ == '__main__':
    main()
