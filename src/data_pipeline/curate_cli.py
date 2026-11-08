#!/usr/bin/env python3
"""Công cụ hỗ trợ người bản ngữ và chuyên gia kiểm duyệt dữ liệu song ngữ/đơn ngữ."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.common import (
    ensure_new,
    normalize_text,
    read_jsonl,
    sha256,
    text_pair,
    write_json,
    write_jsonl,
)
from src.data_pipeline.split_dataset import _text_signatures, is_near_duplicate

# Phân loại lý do từ chối chuẩn cho người bản ngữ
REJECTION_TAXONOMY = {
    "1": "wrong_language: Không phải tiếng Tày (lẫn tiếng Việt, chữ Hán, ngôn ngữ khác)",
    "2": "bad_translation: Dịch sai lệch nghĩa hoặc dịch máy thô sơ chưa chỉnh sửa",
    "3": "incomplete_text: Câu bị cắt cụt, đứt đoạn, mất ngữ cảnh hoặc thiếu vế",
    "4": "poor_quality: Lỗi chính tả nghiêm trọng, ký tự rác, lỗi mã hóa",
    "5": "duplicate_or_boilerplate: Tiêu đề lặp lại, câu rập khuôn, không có giá trị học",
    "6": "other: Lý do khác (ghi chú tự do)",
}


def parse_number_ranges(spec: str, max_val: int) -> list[int]:
    """Phân tích cú pháp chuỗi phạm vi số thứ tự (vd: '1,2,5-8,10') thành danh sách số nguyên."""
    if not spec or not spec.strip():
        return []
    result = set()
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            bounds = [b.strip() for b in part.split("-")]
            if len(bounds) != 2 or not bounds[0].isdigit() or not bounds[1].isdigit():
                raise ValueError(f"Dải số thứ tự không hợp lệ: '{part}'")
            start, end = int(bounds[0]), int(bounds[1])
            if start > end:
                raise ValueError(f"Dải số ngược: {start} > {end}")
            for num in range(start, end + 1):
                if num < 1 or num > max_val:
                    raise ValueError(f"Số thứ tự {num} nằm ngoài phạm vi 1..{max_val}")
                result.add(num)
        else:
            if not part.isdigit():
                raise ValueError(f"Số thứ tự không hợp lệ: '{part}'")
            num = int(part)
            if num < 1 or num > max_val:
                raise ValueError(f"Số thứ tự {num} nằm ngoài phạm vi 1..{max_val}")
            result.add(num)
    return sorted(result)


def validate_source_file(file_path: Path, expected_sha256: str | None = None) -> tuple[str, list[dict]]:
    """Xác thực tệp nguồn JSONL và kiểm tra mã băm SHA-256."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Tệp nguồn không tồn tại: {file_path}")
    current_sha256 = sha256(file_path)
    if expected_sha256 is not None and current_sha256 != expected_sha256:
        raise ValueError(
            f"Mã băm SHA-256 không khớp cho {file_path}:\n"
            f"  Dự kiến : {expected_sha256}\n"
            f"  Thực tế : {current_sha256}\n"
            f"Dữ liệu có thể đã bị sửa đổi trái phép; cần kiểm tra lại."
        )
    rows = read_jsonl(file_path)
    return current_sha256, rows


def _atomic_write_json(target_path: Path, data: dict) -> None:
    """Ghi tệp JSON an toàn bằng tệp tạm để tránh ghi đè lỗi làm hỏng registry."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(f".tmp.{os.getpid()}")
    try:
        with tmp_path.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        tmp_path.replace(target_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def review_batch(
    registry_path: Path,
    source_id: str,
    approved_numbers: list[int] | set[int],
    reviewer: str,
    evidence: list[str],
    output_registry_path: Path | None = None,
    content_origin_status: str = "verified",
    language_review_status: str = "approved",
    translation_review_status: str = "approved",
    usage_permission_status: str = "confirmed",
    rejection_reasons: dict[int, str] | None = None,
    reviewer_notes: str = "",
    project_root: Path = ROOT,
    log_path: Path | None = None,
) -> dict:
    """Cập nhật source_registry.json với danh sách bản ghi được phê duyệt.

    Args:
        registry_path: Đường dẫn tới source_registry.json.
        source_id: ID nguồn cần duyệt (vd: 'vov4', 'sample_bilingual').
        approved_numbers: Danh sách số thứ tự bản ghi được duyệt (1-indexed).
        reviewer: Tên/định danh người duyệt bản ngữ/chuyên gia.
        evidence: Danh sách bằng chứng kiểm duyệt (tài liệu đối chiếu, ghi chú).
        output_registry_path: Đường dẫn ghi file mới (nếu None, ghi đè an toàn vào registry_path).
        content_origin_status: Trạng thái nguồn gốc ('verified').
        language_review_status: Trạng thái ngôn ngữ ('approved').
        translation_review_status: Trạng thái bản dịch ('approved').
        usage_permission_status: Trạng thái bản quyền ('confirmed').
        rejection_reasons: Bảng ánh xạ số bản ghi bị từ chối -> lý do từ chối.
        reviewer_notes: Ghi chú bổ sung từ người duyệt.
        project_root: Thư mục gốc dự án.
        log_path: Đường dẫn ghi tệp nhật ký kiểm duyệt chi tiết.

    Returns:
        dict: Mục nguồn đã được cập nhật đầy đủ các trường kiểm định theo tiêu chuẩn clean_dedup.py.
    """
    if not registry_path.is_file():
        raise FileNotFoundError(f"Registry không tồn tại: {registry_path}")

    registry_content = json.loads(registry_path.read_text(encoding="utf-8"))
    sources = registry_content.get("sources", [])
    source = next((s for s in sources if s.get("source_id") == source_id), None)
    if source is None:
        raise ValueError(f"Không tìm thấy source_id '{source_id}' trong registry: {registry_path}")

    raw_path = (project_root / source["path"]).resolve()
    current_sha256, rows = validate_source_file(raw_path, source.get("sha256"))
    total_records = len(rows)

    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Thiếu reviewed_by (tên người duyệt không được để trống)")

    disallowed_placeholders = {
        "admin", "test", "tester", "unknown", "placeholder", "tbd", "none", "n/a", "bot", "auto"
    }
    if reviewer.strip().lower() in disallowed_placeholders:
        raise ValueError(
            f"reviewed_by không được dùng tên placeholder chung chung: '{reviewer}'. "
            f"Cần định danh cụ thể của chuyên gia / người bản ngữ Tày."
        )

    if (
        not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(x, str) and len(x.strip()) >= 3 for x in evidence)
    ):
        raise ValueError("Thiếu review_evidence (cần danh sách chuỗi bằng chứng kiểm duyệt thực chất)")

    approved_set = set(int(n) for n in approved_numbers)
    for n in approved_set:
        if n < 1 or n > total_records:
            raise ValueError(f"approved_record_numbers phải từ 1 đến {total_records}: gặp {n}")

    now_utc = datetime.now(timezone.utc).isoformat()
    # Chỉ xác nhận training_approved khi có mẫu duyệt VÀ toàn bộ 4 chiều thẩm định đều đạt chuẩn
    dimensions_approved = (
        content_origin_status == "verified"
        and language_review_status == "approved"
        and translation_review_status == "approved"
        and usage_permission_status == "confirmed"
    )
    is_approved = bool(len(approved_set) > 0 and dimensions_approved)

    source["training_approved"] = is_approved
    source["content_origin_status"] = content_origin_status if is_approved else "unverified"
    source["language_review_status"] = language_review_status if is_approved else "not_reviewed"
    source["translation_review_status"] = translation_review_status if is_approved else "not_reviewed"
    source["usage_permission_status"] = usage_permission_status if is_approved else "unconfirmed"
    source["reviewed_by"] = reviewer.strip()
    source["review_evidence"] = [str(x).strip() for x in evidence]
    source["approved_record_numbers"] = sorted(approved_set)
    source["reviewed_at_utc"] = now_utc

    if rejection_reasons:
        source["rejection_reasons"] = {str(k): str(v) for k, v in sorted(rejection_reasons.items(), key=lambda x: int(x[0]))}
    if reviewer_notes:
        source["reviewer_notes"] = reviewer_notes.strip()

    source["curation_summary"] = {
        "total_records": total_records,
        "approved_records": len(approved_set),
        "rejected_records": total_records - len(approved_set),
        "checksum_verified": current_sha256,
        "reviewed_at_utc": now_utc,
    }

    target_registry = output_registry_path or registry_path
    _atomic_write_json(target_registry, registry_content)

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        audit_payload = {
            "source_id": source_id,
            "path": source["path"],
            "sha256": current_sha256,
            "reviewed_by": reviewer.strip(),
            "reviewed_at_utc": now_utc,
            "evidence": source["review_evidence"],
            "total_records": total_records,
            "approved_records": len(approved_set),
            "approved_numbers": sorted(approved_set),
            "rejections": source.get("rejection_reasons", {}),
            "reviewer_notes": reviewer_notes,
        }
        _atomic_write_json(log_path, audit_payload)

    return source


def curate_candidate_file(
    input_file: Path,
    output_file: Path,
    approved_numbers: list[int] | set[int],
    reviewer: str,
    evidence: list[str],
    rejection_reasons: dict[int, str] | None = None,
    default_source_id: str = "curated_candidate",
    content_origin_status: str = "verified",
    language_review_status: str = "approved",
    translation_review_status: str = "approved",
    usage_permission_status: str = "confirmed",
    log_path: Path | None = None,
) -> dict:
    """Kiểm duyệt trực tiếp tệp ứng viên (từ data/raw hoặc data/interim) và trích xuất bản ghi đã duyệt.

    Args:
        input_file: Tệp JSONL nguồn đầu vào.
        output_file: Tệp JSONL đầu ra chứa các bản ghi được duyệt.
        approved_numbers: Danh sách số thứ tự bản ghi được duyệt (1-indexed).
        reviewer: Người thẩm định bản ngữ.
        evidence: Bằng chứng thẩm định.
        rejection_reasons: Bảng lý do từ chối.
        default_source_id: ID nguồn mặc định nếu bản ghi chưa có.
        content_origin_status: Trạng thái nguồn gốc ('verified' | 'unverified').
        language_review_status: Trạng thái ngôn ngữ ('approved' | 'not_reviewed').
        translation_review_status: Trạng thái bản dịch ('approved' | 'not_reviewed').
        usage_permission_status: Trạng thái bản quyền ('confirmed' | 'unconfirmed').
        log_path: Tệp ghi log thẩm định.

    Returns:
        dict: Báo cáo kết quả kiểm duyệt tệp ứng viên.
    """
    input_resolved = input_file.resolve()
    output_resolved = output_file.resolve()
    if input_resolved == output_resolved:
        raise ValueError(
            f"output_file ({output_resolved}) không được trùng với input_file: dữ liệu thô nguồn phải bất biến!"
        )
    try:
        raw_root = (ROOT / "data/raw").resolve()
        if output_resolved == raw_root or raw_root in output_resolved.parents:
            raise ValueError(
                f"output_file ({output_resolved}) không được ghi vào thư mục data/raw/: dữ liệu thô phải bất biến!"
            )
    except Exception:
        pass

    current_sha256, rows = validate_source_file(input_file)
    total_records = len(rows)

    if not reviewer or not reviewer.strip():
        raise ValueError("Thiếu reviewed_by (người kiểm duyệt)")
    if not evidence or not all(isinstance(e, str) and e.strip() for e in evidence):
        raise ValueError("Thiếu review_evidence (bằng chứng kiểm duyệt)")

    approved_set = set(int(n) for n in approved_numbers)
    for n in approved_set:
        if n < 1 or n > total_records:
            raise ValueError(f"Số thứ tự {n} nằm ngoài phạm vi 1..{total_records}")

    dimensions_approved = (
        content_origin_status == "verified"
        and language_review_status == "approved"
        and translation_review_status == "approved"
        and usage_permission_status == "confirmed"
    )
    is_training_eligible = bool(dimensions_approved)

    output_rows = []
    now_utc = datetime.now(timezone.utc).isoformat()

    for idx, row in enumerate(rows, 1):
        if idx not in approved_set:
            continue
        tay, vi = text_pair(row)
        if not tay or not vi:
            raise ValueError(f"Bản ghi {idx} thiếu văn bản một phía: tay='{tay}', vi='{vi}'")
        curated_row = copy.deepcopy(row)
        curated_row["tay"] = tay
        curated_row["vi"] = vi
        curated_row["tay_text"] = tay
        curated_row["vi_text"] = vi
        curated_row["training_approved"] = is_training_eligible
        curated_row["content_origin_status"] = content_origin_status
        curated_row["language_review_status"] = language_review_status
        curated_row["translation_review_status"] = translation_review_status
        curated_row["usage_permission_status"] = usage_permission_status
        curated_row["reviewed_by"] = reviewer.strip()
        curated_row["reviewed_at_utc"] = now_utc
        curated_row["review_evidence"] = [e.strip() for e in evidence]
        curated_row["source_record_number"] = idx
        curated_row["source_file_sha256"] = current_sha256

        # Bảo toàn liên kết tài liệu nguồn (Document Grouping)
        file_doc_id = (
            row.get("source_doc_id")
            or row.get("document_id")
            or row.get("source_url")
            or f"{default_source_id}_{input_file.stem}"
        )
        curated_row["source_doc_id"] = file_doc_id
        curated_row["document_id"] = file_doc_id

        output_rows.append(curated_row)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as stream:
        for r in output_rows:
            stream.write(json.dumps(r, ensure_ascii=False) + "\n")

    report = {
        "input_file": str(input_file),
        "output_file": str(output_file),
        "input_sha256": current_sha256,
        "total_records": total_records,
        "approved_records": len(output_rows),
        "rejected_records": total_records - len(output_rows),
        "reviewed_by": reviewer.strip(),
        "reviewed_at_utc": now_utc,
    }

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(log_path, {
            **report,
            "approved_numbers": sorted(approved_set),
            "rejection_reasons": rejection_reasons or {},
        })

    return report


def inspect_candidate_pairs(
    file_path: Path,
    limit: int = 10,
    offset: int = 0,
) -> list[dict]:
    """Xem xét và đánh giá nhanh chất lượng các cặp câu ứng viên kèm cảnh báo chênh lệch độ dài."""
    _, rows = validate_source_file(file_path)
    sliced = rows[offset : offset + limit]
    inspected = []

    for idx, row in enumerate(sliced, offset + 1):
        tay = normalize_text(row.get("tay") or row.get("tay_text") or "")
        vi = normalize_text(row.get("vi") or row.get("vi_text") or "")
        warnings = []

        if not tay:
            warnings.append("empty_tay_text")
        if not vi:
            warnings.append("empty_vi_text")

        if tay and vi:
            len_tay, len_vi = len(tay.split()), len(vi.split())
            ratio = len_tay / max(1, len_vi)
            if ratio > 2.5 or ratio < 0.4:
                warnings.append(f"token_ratio_imbalance: ratio={ratio:.2f} ({len_tay} vs {len_vi} words)")
            if tay.casefold() == vi.casefold():
                warnings.append("identical_source_target_text")

        inspected.append({
            "record_number": idx,
            "tay": tay,
            "vi": vi,
            "doc_id": row.get("source_doc_id") or row.get("document_id") or row.get("source_url") or "",
            "warnings": warnings,
            "raw_row": row,
        })
    return inspected


def check_monolingual_leakage(
    monolingual_rows: list[dict],
    val_rows: list[dict],
    test_rows: list[dict],
    near_dup_threshold: float = 0.85,
) -> dict:
    """Kiểm tra rò rỉ dữ liệu (Q02): đảm bảo câu đơn ngữ không trùng chính xác hoặc gần trùng với tập đánh giá.

    Args:
        monolingual_rows: Danh sách câu đơn ngữ (chuẩn bị đưa vào back-translation).
        val_rows: Tập validation song ngữ đã chốt.
        test_rows: Tập test song ngữ đã chốt.
        near_dup_threshold: Ngưỡng tương đồng Jaccard phát hiện gần trùng.

    Returns:
        dict: Kết quả kiểm tra rò rỉ và danh sách câu vi phạm (nếu có).
    """
    def _extract_norm_texts_and_sigs(rows: list[dict]) -> tuple[set[str], list[tuple[str, set[str], set[str]]]]:
        texts = set()
        sigs = []
        for r in rows:
            for key in ("tay", "tay_text", "vi", "vi_text", "text", "ty"):
                val = r.get(key)
                if isinstance(val, str) and val.strip():
                    norm = normalize_text(val).casefold()
                    if norm not in texts:
                        texts.add(norm)
                        sigs.append(_text_signatures(norm))
        return texts, sigs

    val_texts, val_sigs = _extract_norm_texts_and_sigs(val_rows)
    test_texts, test_sigs = _extract_norm_texts_and_sigs(test_rows)

    leaked = []
    clean_monolingual = []

    for idx, r in enumerate(monolingual_rows, 1):
        target_text = normalize_text(
            r.get("text") or r.get("tay") or r.get("tay_text") or r.get("vi") or r.get("vi_text") or ""
        ).casefold()

        if not target_text:
            continue

        target_sig = _text_signatures(target_text)

        # 1. Trùng chính xác (Exact match)
        if target_text in val_texts:
            leaked.append({
                "record_index": idx,
                "text": target_text,
                "leaked_into": "validation",
                "leak_type": "exact_match",
            })
            continue

        if target_text in test_texts:
            leaked.append({
                "record_index": idx,
                "text": target_text,
                "leaked_into": "test",
                "leak_type": "exact_match",
            })
            continue

        # 2. Gần trùng (Near-duplicate)
        near_match_val = next((s[0] for s in val_sigs if is_near_duplicate(target_sig, s, threshold=near_dup_threshold)), None)
        if near_match_val:
            leaked.append({
                "record_index": idx,
                "text": target_text,
                "leaked_into": "validation",
                "leak_type": "near_duplicate",
                "matched_text": near_match_val,
            })
            continue

        near_match_test = next((s[0] for s in test_sigs if is_near_duplicate(target_sig, s, threshold=near_dup_threshold)), None)
        if near_match_test:
            leaked.append({
                "record_index": idx,
                "text": target_text,
                "leaked_into": "test",
                "leak_type": "near_duplicate",
                "matched_text": near_match_test,
            })
            continue

        clean_monolingual.append(r)

    return {
        "monolingual_total": len(monolingual_rows),
        "val_sentences": len(val_texts),
        "test_sentences": len(test_texts),
        "has_leakage": len(leaked) > 0,
        "leakage_count": len(leaked),
        "leaked_samples": leaked,
        "safe_monolingual_count": len(clean_monolingual),
        "near_duplicate_threshold": near_dup_threshold,
    }


def interactive_curate_cli(
    raw_file_path: Path,
    registry_path: Path | None = None,
    source_id: str | None = None,
    reviewer: str = "",
    evidence: list[str] | None = None,
    output_registry_path: Path | None = None,
    output_curated_file: Path | None = None,
    log_path: Path | None = None,
    input_stream=None,
    output_stream=None,
    project_root: Path = ROOT,
) -> dict:
    """Giao diện dòng lệnh tương tác cho người bản ngữ xem từng cặp câu và phân loại."""
    stream_in = input_stream or sys.stdin
    stream_out = output_stream or sys.stdout

    def _prompt(msg: str) -> str:
        stream_out.write(msg)
        stream_out.flush()
        line = stream_in.readline()
        if not line:
            return ""
        return line.strip()

    stream_out.write("\n=======================================================\n")
    stream_out.write("   HỆ THỐNG KIỂM DUYỆT DỮ LIỆU BẢN NGỮ TÀY - VIỆT\n")
    stream_out.write("=======================================================\n")

    current_sha256, rows = validate_source_file(raw_file_path)
    total = len(rows)

    if not reviewer:
        reviewer = _prompt("Nhập tên người kiểm duyệt bản ngữ: ")
        while not reviewer:
            reviewer = _prompt("Tên không được để trống. Nhập lại tên: ")

    if not evidence:
        ev_str = _prompt("Nhập bằng chứng kiểm định (mặc định: 'Thẩm định bản ngữ trực tiếp'): ")
        evidence = [ev_str.strip() or "Thẩm định bản ngữ trực tiếp"]

    stream_out.write(f"\nTệp kiểm duyệt: {raw_file_path.name} ({total} bản ghi)\n")
    stream_out.write(f"Người duyệt   : {reviewer}\n")
    stream_out.write(f"Mã SHA-256    : {current_sha256}\n")
    stream_out.write("Phím tắt: [A] Chấp thuận | [R] Từ chối (chọn lý do) | [S] Bỏ qua | [Q] Lưu & Thoát\n")
    stream_out.write("-------------------------------------------------------\n")

    approved_numbers: list[int] = []
    rejection_reasons: dict[int, str] = {}
    skipped_numbers: list[int] = []

    for idx, row in enumerate(rows, 1):
        tay = normalize_text(row.get("tay") or row.get("tay_text") or "")
        vi = normalize_text(row.get("vi") or row.get("vi_text") or "")
        doc = row.get("source_doc_id") or row.get("document_id") or row.get("source_url") or "n/a"

        stream_out.write(f"\n[Bản ghi #{idx}/{total}] (Nguồn tài liệu: {doc})\n")
        stream_out.write(f"  Tày : {tay}\n")
        stream_out.write(f"  Việt: {vi}\n")

        choice = ""
        while choice not in ("a", "r", "s", "q"):
            choice = _prompt("Lựa chọn [A/R/S/Q]: ").lower()

        if choice == "a":
            approved_numbers.append(idx)
            stream_out.write("  -> ĐÃ CHẤP THUẬN (Approved)\n")
        elif choice == "r":
            stream_out.write("  Chọn lý do từ chối:\n")
            for k, v in REJECTION_TAXONOMY.items():
                stream_out.write(f"    [{k}] {v}\n")
            reason_key = _prompt("  Nhập mã lý do (1-6) hoặc ghi chú riêng: ").strip()
            reason_text = REJECTION_TAXONOMY.get(reason_key, reason_key or "Từ chối bởi người bản ngữ")
            rejection_reasons[idx] = reason_text
            stream_out.write(f"  -> ĐÃ TỪ CHỐI (Rejected): {reason_text}\n")
        elif choice == "s":
            skipped_numbers.append(idx)
            stream_out.write("  -> ĐÃ BỎ QUA (Skipped)\n")
        elif choice == "q":
            stream_out.write("\nNgười dùng chọn dừng sớm và lưu kết quả...\n")
            break

    stream_out.write("\n=======================================================\n")
    stream_out.write(f"TỔNG KẾT PHIÊN KIỂM DUYỆT:\n")
    stream_out.write(f"  - Số bản ghi đã duyệt   : {len(approved_numbers)}\n")
    stream_out.write(f"  - Số bản ghi bị từ chối : {len(rejection_reasons)}\n")
    stream_out.write(f"  - Số bản ghi bỏ qua     : {len(skipped_numbers)}\n")
    stream_out.write("=======================================================\n")

    summary_result = {
        "reviewer": reviewer,
        "evidence": evidence,
        "total_records": total,
        "approved_records": len(approved_numbers),
        "approved_numbers": approved_numbers,
        "rejection_reasons": rejection_reasons,
        "checksum": current_sha256,
    }

    if registry_path and source_id:
        review_batch(
            registry_path=registry_path,
            source_id=source_id,
            approved_numbers=approved_numbers,
            reviewer=reviewer,
            evidence=evidence,
            output_registry_path=output_registry_path,
            rejection_reasons=rejection_reasons,
            project_root=project_root,
            log_path=log_path,
        )
        stream_out.write(f"Đã cập nhật registry tại: {output_registry_path or registry_path}\n")

    if output_curated_file:
        curate_candidate_file(
            input_file=raw_file_path,
            output_file=output_curated_file,
            approved_numbers=approved_numbers,
            reviewer=reviewer,
            evidence=evidence,
            rejection_reasons=rejection_reasons,
            log_path=log_path,
        )
        stream_out.write(f"Đã xuất dữ liệu đã duyệt tới: {output_curated_file}\n")

    return summary_result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Công cụ kiểm duyệt dữ liệu song ngữ/đơn ngữ Tày - Việt phục vụ người bản ngữ (T03 & T08)."
    )
    parser.add_argument("--registry", type=Path, help="Đường dẫn file source_registry.json")
    parser.add_argument("--source-id", type=str, help="ID nguồn trong registry (vd: vov4)")
    parser.add_argument("--input", type=Path, help="Tệp JSONL cần kiểm duyệt hoặc kiểm tra rò rỉ")
    parser.add_argument("--output", type=Path, help="Tệp JSONL đích chứa các bản ghi được duyệt")
    parser.add_argument("--output-registry", type=Path, help="Đường dẫn ghi registry mới (nếu không ghi đè)")
    parser.add_argument("--reviewer", type=str, default="", help="Họ tên người duyệt bản ngữ")
    parser.add_argument("--evidence", action="append", default=[], help="Bằng chứng kiểm duyệt")
    parser.add_argument("--approve-numbers", type=str, help="Các số thứ tự bản ghi duyệt (vd: 1,2,5-10)")
    parser.add_argument("--reject-numbers", type=str, help="Các số thứ tự bản ghi từ chối")
    parser.add_argument("--rejection-reason", type=str, default="bad_translation", help="Lý do từ chối mặc định")
    parser.add_argument("--approve-all", action="store_true", help="Chấp thuận toàn bộ bản ghi")
    parser.add_argument("--interactive", action="store_true", help="Khởi động chế độ tương tác CLI từng câu")
    parser.add_argument("--inspect", action="store_true", help="Xem trước các cặp câu ứng viên kèm cảnh báo lỗi")
    parser.add_argument("--check-leakage", action="store_true", help="Kiểm tra rò rỉ giữa đơn ngữ và val/test")
    parser.add_argument("--val-file", type=Path, help="Tệp validation JSONL để kiểm tra rò rỉ")
    parser.add_argument("--test-file", type=Path, help="Tệp test JSONL để kiểm tra rò rỉ")
    parser.add_argument("--limit", type=int, default=10, help="Số lượng xem trước trong chế độ inspect")
    parser.add_argument("--offset", type=int, default=0, help="Vị trí bắt đầu trong chế độ inspect")
    parser.add_argument("--log-path", type=Path, help="Đường dẫn xuất file audit log kiểm duyệt")

    args = parser.parse_args()

    # 1. Chế độ kiểm tra rò rỉ đơn ngữ (Q02)
    if args.check_leakage:
        if not args.input or not args.val_file or not args.test_file:
            parser.error("Chế độ --check-leakage cần --input (đơn ngữ), --val-file và --test-file")
        mono = read_jsonl(args.input)
        val = read_jsonl(args.val_file)
        test = read_jsonl(args.test_file)
        report = check_monolingual_leakage(mono, val, test)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["has_leakage"]:
            sys.exit(1)
        return

    # 2. Chế độ xem trước ứng viên (Inspect)
    if args.inspect:
        target = args.input
        if not target and args.registry and args.source_id:
            reg = json.loads(args.registry.read_text(encoding="utf-8"))
            s = next((x for x in reg.get("sources", []) if x.get("source_id") == args.source_id), None)
            if s:
                target = Path(s["path"])
        if not target:
            parser.error("Chế độ --inspect cần --input hoặc --registry và --source-id")
        results = inspect_candidate_pairs(target, limit=args.limit, offset=args.offset)
        print(f"\nXem trước {len(results)} cặp câu từ {target} (offset={args.offset}):\n")
        for item in results:
            warn = f" [CẢNH BÁO: {', '.join(item['warnings'])}]" if item["warnings"] else ""
            print(f"#{item['record_number']} [doc: {item['doc_id']}]{warn}")
            print(f"  Tày : {item['tay']}")
            print(f"  Việt: {item['vi']}")
        return

    # 3. Chế độ tương tác (Interactive CLI)
    if args.interactive:
        target = args.input
        if not target and args.registry and args.source_id:
            reg = json.loads(args.registry.read_text(encoding="utf-8"))
            s = next((x for x in reg.get("sources", []) if x.get("source_id") == args.source_id), None)
            if s:
                target = Path(s["path"])
        if not target:
            parser.error("Chế độ --interactive cần chỉ định file nguồn qua --input hoặc (--registry và --source-id)")

        interactive_curate_cli(
            raw_file_path=target,
            registry_path=args.registry,
            source_id=args.source_id,
            reviewer=args.reviewer,
            evidence=args.evidence or None,
            output_registry_path=args.output_registry,
            output_curated_file=args.output,
            log_path=args.log_path,
        )
        return

    # 4. Chế độ duyệt hàng loạt (Batch curation)
    if args.registry and args.source_id:
        reg = json.loads(args.registry.read_text(encoding="utf-8"))
        s = next((x for x in reg.get("sources", []) if x.get("source_id") == args.source_id), None)
        if not s:
            parser.error(f"Không tìm thấy source_id '{args.source_id}' trong {args.registry}")

        _, rows = validate_source_file(Path(s["path"]), s.get("sha256"))
        total = len(rows)

        if args.approve_all:
            approved = list(range(1, total + 1))
        elif args.approve_numbers:
            approved = parse_number_ranges(args.approve_numbers, total)
        else:
            parser.error("Cần truyền --approve-numbers, --approve-all hoặc bật --interactive")

        rejections = {}
        if args.reject_numbers:
            rejected = parse_number_ranges(args.reject_numbers, total)
            for r in rejected:
                rejections[r] = args.rejection_reason

        if not args.reviewer or not args.reviewer.strip():
            parser.error("Cần cung cấp --reviewer (định danh người thẩm định bản ngữ/chuyên gia cụ thể)")
        if not args.evidence:
            parser.error("Cần cung cấp ít nhất một --evidence (bằng chứng kiểm định đối chiếu cụ thể)")

        res = review_batch(
            registry_path=args.registry,
            source_id=args.source_id,
            approved_numbers=approved,
            reviewer=args.reviewer.strip(),
            evidence=args.evidence,
            output_registry_path=args.output_registry,
            rejection_reasons=rejections,
            log_path=args.log_path,
        )
        print(json.dumps(res.get("curation_summary", {}), ensure_ascii=False, indent=2))
        return

    # 5. Curation tệp độc lập (Curate candidate JSONL directly)
    if args.input and args.output:
        _, rows = validate_source_file(args.input)
        total = len(rows)
        if args.approve_all:
            approved = list(range(1, total + 1))
        elif args.approve_numbers:
            approved = parse_number_ranges(args.approve_numbers, total)
        else:
            parser.error("Cần truyền --approve-numbers, --approve-all hoặc bật --interactive")

        rejections = {}
        if args.reject_numbers:
            rejected = parse_number_ranges(args.reject_numbers, total)
            for r in rejected:
                rejections[r] = args.rejection_reason

        res = curate_candidate_file(
            input_file=args.input,
            output_file=args.output,
            approved_numbers=approved,
            reviewer=args.reviewer or "Người thẩm định bản ngữ",
            evidence=args.evidence or ["Biên bản kiểm duyệt ngữ liệu thực địa"],
            rejection_reasons=rejections,
            log_path=args.log_path,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
