"""Đọc dữ liệu, bảo vệ đầu ra và ghi bằng chứng cho mỗi lần chạy."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def text_pair(row: dict) -> tuple[str, str]:
    values = (row.get("tay") or row.get("tay_text") or "",
              row.get("vi") or row.get("vi_text") or "")
    if not all(isinstance(value, str) for value in values):
        raise ValueError("Các trường văn bản phải là chuỗi")
    return tuple(normalize_text(value) for value in values)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: JSON không hợp lệ") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{number}: bản ghi phải là object")
        rows.append(row)
    return rows


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_path(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def describe(path: Path) -> dict:
    return {"path": display_path(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def ensure_new(*paths: Path) -> None:
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Các đầu ra phải có đường dẫn khác nhau")
    for path in paths:
        if path.exists():
            raise FileExistsError(f"Không ghi đè {path}; chọn đường dẫn cho lần chạy mới")


def write_json(path: Path, value: dict) -> None:
    ensure_new(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    ensure_new(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def run_report(stage: str, inputs: list[Path], outputs: list[Path], **details) -> dict:
    return {
        "stage": stage,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "argv": sys.argv,
        "code": [describe(path) for path in sorted(Path(__file__).parent.glob("*.py"))],
        "inputs": [describe(path) for path in inputs],
        "outputs": [describe(path) for path in outputs],
        **details,
    }


def comparison(output: Path, expected: Path | None) -> dict:
    if expected is None:
        return {"performed": False}
    return {"performed": True, "expected": describe(expected),
            "byte_identical": output.read_bytes() == expected.read_bytes()}
