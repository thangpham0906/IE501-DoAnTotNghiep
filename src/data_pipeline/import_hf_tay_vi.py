"""T07: tải bộ dữ liệu Tày–Việt theo revision bất biến, lưu RAW chưa duyệt.

Điều kiện chạy: pip install 'datasets>=2.19' 'huggingface_hub>=0.23'
Chỉ xuất JSONL có chứng cứ tải thật và báo cáo SHA-256; không tự tạo bản dịch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

DATASET_ID = "HeyDunaX/tay-vietnamese-nmt"
DATASET_URL = "https://huggingface.co/datasets/HeyDunaX/tay-vietnamese-nmt"
LICENSE_CLAIM = "cc-by-nc-4.0"  # metadata trên dataset card, không xác minh quyền với từng nguồn


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def extract_pair(row: dict) -> tuple[str, str]:
    """Bảo toàn chuỗi từ nguồn; cấm chuyển đổi, dịch hoặc sinh câu mới."""
    if not isinstance(row, dict):
        raise ValueError("Upstream record must be a JSON object")
    trans = row.get("translation")
    if isinstance(trans, dict):
        tay, vi = trans.get("tay"), trans.get("viet")
    else:
        tay, vi = row.get("tay"), row.get("viet")
    if not isinstance(tay, str) or not tay.strip() or not isinstance(vi, str) or not vi.strip():
        raise ValueError("Missing original Tày/Vietnamese strings; no auto-repair")
    return tay, vi


def inspect_splits(train: list[dict], test: list[dict]) -> dict:
    """Kiểm toán trùng lặp, KHÔNG coi chuỗi khác nhau là bản dịch tương ứng."""
    def keys(rows):
        pair_keys, tay_keys, vi_keys = set(), set(), set()
        within_pair_dup = 0
        equal_sides = 0
        for row in rows:
            tay, vi = extract_pair(row)
            a, b = normalized(tay), normalized(vi)
            key = (a, b)
            within_pair_dup += key in pair_keys
            equal_sides += a == b
            pair_keys.add(key)
            tay_keys.add(a)
            vi_keys.add(b)
        return pair_keys, tay_keys, vi_keys, within_pair_dup, equal_sides

    t_pairs, t_tay, t_vi, t_dup, t_equal = keys(train)
    e_pairs, e_tay, e_vi, e_dup, e_equal = keys(test)
    return {
        "train_rows": len(train), "test_rows": len(test),
        "duplicate_pairs_within_train": t_dup,
        "duplicate_pairs_within_test": e_dup,
        "identical_tay_vi_within_train": t_equal,
        "identical_tay_vi_within_test": e_equal,
        "train_test_exact_pair_overlap": len(t_pairs & e_pairs),
        "train_test_tay_overlap": len(t_tay & e_tay),
        "train_test_viet_overlap": len(t_vi & e_vi),
        "near_duplicate_detection": "not_performed",
        "document_level_leakage": "not_assessable_without_document_ids",
    }


def _as_original_rows(dataset, split: str, revision: str) -> list[dict]:
    result = []
    for index, row in enumerate(dataset):
        tay, vi = extract_pair(row)
        result.append({
            "tay_text": tay,
            "vi_text": vi,
            "source_id": "hf_heydunax_tay_vietnamese_nmt",
            "source_url": DATASET_URL,
            "source_record_number": index + 1,
            "source_split": split,
            "source_revision": revision,
            "content_origin_status": "published_dataset_unverified",
            "language_review_status": "pending",
            "translation_review_status": "pending",
            "usage_permission_status": "not_confirmed",
            "training_approved": False,
        })
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_exclusive(path: Path, value, jsonl: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        if jsonl:
            for row in value:
                out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        else:
            json.dump(value, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.write("\n")


def save_import(train: list[dict], test: list[dict], revision: str,
                train_path: Path, test_path: Path, manifest_path: Path) -> dict:
    """Không ghi đè. Test vào quarantine; train chưa được duyệt."""
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("revision must be a full 40-character git commit SHA")
    paths = [train_path, test_path, manifest_path]
    if len({p.resolve() for p in paths}) != 3 or any(p.exists() for p in paths):
        raise FileExistsError("Output paths must be different and must not exist")
    audit = inspect_splits(train, test)
    train_rows = _as_original_rows(train, "train", revision)
    test_rows = _as_original_rows(test, "test", revision)
    created = []
    try:
        _write_exclusive(train_path, train_rows, True)
        created.append(train_path)
        _write_exclusive(test_path, test_rows, True)
        created.append(test_path)
        manifest = {
            "schema_version": 1,
            "stage": "t07_hf_acquisition",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "dataset_id": DATASET_ID, "dataset_url": DATASET_URL,
            "source_revision": revision, "license_claimed_by_card": LICENSE_CLAIM,
            "rights_independently_verified": False,
            "translation_review_complete": False,
            "training_approved": False,
            "split_policy": "Upstream test quarantined; never import test as training",
            "audit": audit,
            "outputs": [
                {"path": str(train_path), "sha256": _sha256(train_path), "records": len(train_rows), "split": "train"},
                {"path": str(test_path), "sha256": _sha256(test_path), "records": len(test_rows), "split": "test_quarantine"},
            ],
        }
        _write_exclusive(manifest_path, manifest, False)
        created.append(manifest_path)
        return manifest
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-output", type=Path, required=True)
    parser.add_argument("--test-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--revision", help="Optional pinned 40-char SHA; otherwise resolve current upstream HEAD")
    args = parser.parse_args()
    try:
        from datasets import load_dataset
        from huggingface_hub import HfApi
    except ImportError as exc:
        parser.error(f"Cần cài dependencies để tải nguồn thực: {exc}")
    info = HfApi().dataset_info(DATASET_ID, revision=args.revision)
    revision = info.sha
    if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise RuntimeError("Unable to resolve immutable source revision")
    if args.revision and revision != args.revision:
        raise RuntimeError("Upstream revision mismatch")
    upstream = load_dataset(DATASET_ID, revision=revision)
    if "train" not in upstream or "test" not in upstream:
        raise RuntimeError("Missing published train/test split; refuse to invent split")
    train = [dict(row) for row in upstream["train"]]
    test = [dict(row) for row in upstream["test"]]
    manifest = save_import(train, test, revision,
                           args.train_output, args.test_output, args.manifest)
    print(json.dumps(manifest["audit"], ensure_ascii=False))


if __name__ == "__main__":
    main()
