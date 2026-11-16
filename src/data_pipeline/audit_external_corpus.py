"""T07: audit offline 2 split nguồn mới và corpus cũ, KHÔNG tạo training corpus.

python3 src/data_pipeline/audit_external_corpus.py \
  --train data/raw/hf_tay_vi/train-<sha>.jsonl \
  --holdout data/quarantine/hf_tay_vi/upstream-test-<sha>.jsonl \
  --existing data/raw/glosbe/dictionary_pairs.jsonl \
  --output data/manifests/t07-corpus-audit-<runid>.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

try:
    from src.data_pipeline.import_hf_tay_vi import extract_pair, normalized
except ModuleNotFoundError:
    from import_hf_tay_vi import extract_pair, normalized


def read_pairs(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    rows = []
    for lineno, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            continue
        try:
            row = json.loads(text)
            a, b = extract_pair(row)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{path}:{lineno}: invalid bilingual record: {exc}") from exc
        rows.append({"tay": normalized(a), "vi": normalized(b),
                     "doc": str(row.get("source_doc_id") or row.get("document_id") or "").casefold(),
                     "approved": row.get("training_approved") is True,
                     "synthetic": row.get("synthetic") is True})
    return rows


def audit_datasets(train: list[dict], holdout: list[dict], existing: list[dict]) -> dict:
    def pairs(rows): return {(r["tay"], r["vi"]) for r in rows}
    def sides(rows, name): return {r[name] for r in rows}
    def docs(rows): return {r["doc"] for r in rows if r["doc"]}
    def dup(rows): return len(rows) - len(pairs(rows))
    overlap = {
        "train_holdout_exact_pair_overlap": len(pairs(train) & pairs(holdout)),
        "train_holdout_tay_overlap": len(sides(train,"tay") & sides(holdout,"tay")),
        "train_holdout_vi_overlap": len(sides(train,"vi") & sides(holdout,"vi")),
        "train_holdout_document_overlap": len(docs(train) & docs(holdout)),
        "train_existing_exact_pair_overlap": len(pairs(train) & pairs(existing)),
        "train_existing_tay_overlap": len(sides(train,"tay") & sides(existing,"tay")),
        "train_existing_vi_overlap": len(sides(train,"vi") & sides(existing,"vi")),
        "holdout_existing_exact_pair_overlap": len(pairs(holdout) & pairs(existing)),
        "holdout_existing_tay_overlap": len(sides(holdout,"tay") & sides(existing,"tay")),
        "holdout_existing_vi_overlap": len(sides(holdout,"vi") & sides(existing,"vi")),
    }
    return {"status": "review_required", "training_approved": False,
            "sizes": {"candidate_train": len(train), "upstream_holdout": len(holdout), "existing": len(existing)},
            "internal_exact_pair_duplicates": {"candidate_train": dup(train), "upstream_holdout": dup(holdout), "existing": dup(existing)},
            "overlap": overlap,
            "candidate_flags": {"premature_approval": sum(r["approved"] for r in train),
                               "synthetic_marked": sum(r["synthetic"] for r in train)},
            "not_performed": ["near_duplicate_detection", "language_identification", "translation_quality_review", "license_independent_verification"],
            "note": "Exact normalized matching and document IDs only; 0 overlap does not establish no semantic leakage."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--existing", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refuse to overwrite output")
    train, holdout = read_pairs(args.train), read_pairs(args.holdout)
    existing = [row for path in args.existing for row in read_pairs(path)]
    report = audit_datasets(train, holdout, existing)
    report["inputs"] = [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                         for path in [args.train, args.holdout, *args.existing]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, ensure_ascii=False, sort_keys=True)
        output.write("\n")
    print(json.dumps({"sizes": report["sizes"], "overlap": report["overlap"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
