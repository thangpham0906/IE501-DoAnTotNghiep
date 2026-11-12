#!/usr/bin/env python3
"""Kiểm tra provenance/metadata T07, không cấp phép huấn luyện hoặc sửa raw.

Chạy trực tiếp tại root repository:
  python3 src/data_pipeline/validate_metadata.py --output /tmp/t07-metadata-report.json

Đầu vào là manifest đã commit. Dùng --raw-dir để kiểm tra cả corpus cục bộ
nếu raw đã được cung cấp; không có raw thì KHÔNG báo đã xác minh bản ghi.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RAW_PREFIX = "data/raw/"
REQUIRED_STATUSES = (
    "content_origin_status", "language_review_status",
    "translation_review_status", "usage_permission_status",
)


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: cần JSON object")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_repo_path(path: object) -> bool:
    if not isinstance(path, str) or not path.startswith(RAW_PREFIX):
        return False
    p = Path(path)
    return not p.is_absolute() and ".." not in p.parts and p.suffix == ".jsonl"


def _looks_like_url(url: object) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("https", "http") and bool(parsed.hostname) and not any(c.isspace() for c in url)


def validate_manifests(inventory: dict, registry: dict, raw_root: Path | None = None,
                       project_root: Path = ROOT) -> dict:
    """Trả báo cáo có cấu trúc; không biến khai báo thành bằng chứng xác minh.

    raw_root chỉ điều khiển kiểm tra byte/JSONL nếu người dùng cung cấp corpus.
    """
    issues: list[dict] = []

    def issue(code: str, *, source: str = "", message: str = "", severity: str = "warning") -> None:
        issues.append({"severity": severity, "code": code, "source": source, "message": message})

    if not isinstance(inventory.get("files"), list):
        raise ValueError("inventory.files phải là list")
    if not isinstance(registry.get("sources"), list):
        raise ValueError("source_registry.sources phải là list")

    snapshot_a = inventory.get("snapshot_id")
    snapshot_b = registry.get("snapshot_id")
    if snapshot_a != snapshot_b:
        issue("SNAPSHOT_MISMATCH", message="Snapshot ID của inventory và registry khác nhau", severity="error")

    files = {}
    for item in inventory["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            issue("INVALID_INVENTORY_ITEM", severity="error")
            continue
        path = item["path"]
        if path in files:
            issue("DUPLICATE_INVENTORY_PATH", source=path, severity="error")
        files[path] = item

    seen_paths: set[str] = set()
    seen_ids: set[str] = set()
    details = []
    confirmed_bytes = 0
    count_claimed = 0
    count_url = 0

    for source in registry["sources"]:
        if not isinstance(source, dict):
            issue("INVALID_REGISTRY_ITEM", severity="error")
            continue
        path = source.get("path")
        source_id = source.get("source_id")
        if not _safe_repo_path(path):
            issue("UNSAFE_RAW_PATH", source=str(path), severity="error")
            continue
        if path in seen_paths:
            issue("DUPLICATE_SOURCE_PATH", source=path, severity="error")
        seen_paths.add(path)
        if not isinstance(source_id, str) or not source_id.strip() or source_id in seen_ids:
            issue("INVALID_OR_DUPLICATE_SOURCE_ID", source=path, severity="error")
        else:
            seen_ids.add(source_id)

        inv = files.get(path)
        if not inv:
            issue("SOURCE_NOT_IN_INVENTORY", source=path, severity="error")
        else:
            if source.get("sha256") != inv.get("sha256"):
                issue("SOURCE_SHA256_MISMATCH", source=path, severity="error")
            if source.get("records") != inv.get("records"):
                issue("SOURCE_RECORD_COUNT_MISMATCH", source=path, severity="error")
        sha = source.get("sha256")
        if not isinstance(sha, str) or re.fullmatch(r"[a-fA-F0-9]{64}", sha) is None:
            issue("INVALID_SOURCE_SHA256", source=path, severity="error")
        records = source.get("records")
        if type(records) is not int or records < 0:
            issue("INVALID_RECORD_COUNT", source=path, severity="error")
            records = 0
        count_claimed += records
        urls = source.get("source_url_records")
        if type(urls) is not int or not 0 <= urls <= records:
            issue("INVALID_SOURCE_URL_COUNT", source=path, severity="error")
            urls = 0
        count_url += urls
        if urls < records:
            issue("MISSING_RECORD_SOURCE_URL", source=path,
                  message=f"Thiếu URL từng bản ghi: {records - urls}/{records}; có thể thay bằng trích dẫn tài liệu có thể đối chiếu")
        for key in REQUIRED_STATUSES:
            if not isinstance(source.get(key), str) or not source[key].strip():
                issue("MISSING_REVIEW_STATUS", source=path, message=key, severity="error")
        if source.get("training_approved") is not True:
            approval = "not_approved"
        else:
            approval = "claimed_approved_requires_review"
            issue("TRAINING_APPROVAL_REQUIRES_EVIDENCE", source=path,
                  message="Validator không thể xác minh quyết định kiểm duyệt của con người")
        if source.get("content_origin_status") != "verified":
            issue("SOURCE_PROVENANCE_UNVERIFIED", source=path,
                  message="Nhãn nguồn/chủ đề không xác minh xuất xứ của từng bản ghi")
        if source.get("usage_permission_status") != "confirmed":
            issue("USAGE_PERMISSION_UNCONFIRMED", source=path,
                  message="Cần kiểm tra điều kiện sử dụng của nguồn và loại khai thác dự kiến")

        actual = {"checked": False}
        if raw_root is not None:
            raw_path = (project_root / path).resolve()
            raw_base = raw_root.resolve()
            if not raw_path.is_relative_to(raw_base):
                issue("PATH_OUTSIDE_RAW_ROOT", source=path, severity="error")
            elif not raw_path.is_file():
                issue("RAW_FILE_MISSING", source=path, severity="error")
            else:
                computed_sha = _sha256(raw_path)
                hash_match = computed_sha == sha
                if not hash_match:
                    issue("RAW_FILE_HASH_MISMATCH", source=path, severity="error")
                actual_count = 0
                bad_lines = 0
                missing_urls = 0
                for lineno, line in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), 1):
                    if not line.strip():
                        continue
                    actual_count += 1
                    try:
                        item = json.loads(line)
                        if not isinstance(item, dict):
                            raise ValueError("not object")
                        if not _looks_like_url(item.get("source_url")):
                            missing_urls += 1
                    except (ValueError, json.JSONDecodeError):
                        bad_lines += 1
                        issue("RAW_JSONL_INVALID", source=path, message=f"line {lineno}", severity="error")
                if actual_count != records:
                    issue("RAW_RECORD_COUNT_MISMATCH", source=path, severity="error")
                if bad_lines == 0 and actual_count - missing_urls != urls:
                    issue("URL_COUNT_NOT_MATCHING_RAW", source=path, severity="error")
                actual = {"checked": True, "sha256_matches": hash_match,
                          "records": actual_count, "invalid_jsonl_lines": bad_lines,
                          "records_with_valid_source_url": actual_count - missing_urls - bad_lines}
                confirmed_bytes += 1
        details.append({"source_id": source_id, "path": path, "records_claimed": records,
                        "source_url_records_claimed": urls, "training_approval": approval,
                        "raw_validation": actual})

    raw_paths = {p for p in files if p.startswith(RAW_PREFIX)}
    for path in sorted(raw_paths - seen_paths):
        issue("UNREGISTERED_INVENTORY_RAW", source=path, severity="error")
    summary = inventory.get("summary", {})
    if isinstance(summary, dict) and summary.get("raw_records") != count_claimed:
        issue("RAW_TOTAL_MISMATCH", severity="error")
    return {
        "schema_version": 1,
        "scope": "metadata audit; does not approve provenance, language, translations or usage rights",
        "inventory_snapshot_id": snapshot_a,
        "registry_snapshot_id": snapshot_b,
        "summary": {"sources": len(details), "raw_records_claimed": count_claimed,
                    "source_urls_claimed": count_url,
                    "raw_sources_checked": confirmed_bytes,
                    "error_count": sum(i["severity"] == "error" for i in issues),
                    "warning_count": sum(i["severity"] == "warning" for i in issues)},
        "sources": details, "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("data/manifests/inventory.json"))
    parser.add_argument("--registry", type=Path, default=Path("data/manifests/source_registry.json"))
    parser.add_argument("--raw-dir", type=Path, help="Chỉ định data/raw để kiểm tra hash và nội dung JSONL")
    parser.add_argument("--output", type=Path, required=True, help="Đường dẫn báo cáo JSON mới; không ghi đè")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Không ghi đè báo cáo: chọn file output mới")
    report = validate_manifests(_load_json(args.inventory), _load_json(args.registry), args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report["summary"], ensure_ascii=False))
    if report["summary"]["error_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
