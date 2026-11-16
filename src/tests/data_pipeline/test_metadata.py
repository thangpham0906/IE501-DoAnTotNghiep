"""Unit tests cho kiểm tra metadata/provenance T07; dùng dữ liệu giả định."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.data_pipeline.validate_metadata import validate_manifests


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw_dir = self.root / "data/raw"
        self.raw_file = self.raw_dir / "sample/rows.jsonl"
        self.raw_file.parent.mkdir(parents=True)
        self.raw_file.write_text(json.dumps({"tay_text":"A", "vi_text":"B", "source_url":"https://example.org/a"}) + "\n")
        digest = hashlib.sha256(self.raw_file.read_bytes()).hexdigest()
        self.item = {"source_id": "sample", "path": "data/raw/sample/rows.jsonl",
                     "sha256": digest, "records": 1, "source_url_records": 1,
                     "training_approved": False,
                     "content_origin_status": "unverified", "language_review_status":"pending",
                     "translation_review_status":"pending", "usage_permission_status":"not_confirmed"}
        self.inventory = {"snapshot_id":"test", "summary":{"raw_records":1},
                          "files":[{"path":self.item["path"],"sha256":digest,"records":1}]}
        self.registry = {"snapshot_id":"test", "sources":[self.item]}

    def test_manifest_only_does_not_claim_raw_checked(self):
        out = validate_manifests(self.inventory,self.registry)
        self.assertEqual(out["summary"]["raw_sources_checked"], 0)
        self.assertEqual(out["summary"]["error_count"], 0)
        self.assertEqual(out["sources"][0]["training_approval"], "not_approved")

    def test_raw_verified_with_opt_in(self):
        out = validate_manifests(self.inventory,self.registry,self.raw_dir,self.root)
        self.assertEqual(out["summary"]["raw_sources_checked"], 1)
        self.assertTrue(out["sources"][0]["raw_validation"]["sha256_matches"])

    def test_detects_unverified_record_url_count(self):
        self.item["source_url_records"] = 0
        out = validate_manifests(self.inventory,self.registry,self.raw_dir,self.root)
        codes = {x["code"] for x in out["issues"]}
        self.assertIn("URL_COUNT_NOT_MATCHING_RAW", codes)
        self.assertIn("MISSING_RECORD_SOURCE_URL", codes)

    def test_catches_modified_raw(self):
        self.raw_file.write_text(self.raw_file.read_text() + "\n")
        out = validate_manifests(self.inventory,self.registry,self.raw_dir,self.root)
        self.assertIn("RAW_FILE_HASH_MISMATCH", {x["code"] for x in out["issues"]})

    def test_rejects_path_traversal(self):
        self.item["path"] = "data/raw/../secrets.jsonl"
        out = validate_manifests(self.inventory,self.registry)
        self.assertIn("UNSAFE_RAW_PATH", {x["code"] for x in out["issues"]})

    def test_catches_manifest_hash_mismatch(self):
        self.inventory["files"][0]["sha256"] = "f"*64
        out = validate_manifests(self.inventory,self.registry)
        self.assertIn("SOURCE_SHA256_MISMATCH", {x["code"] for x in out["issues"]})

    def test_detects_duplicate_ids(self):
        extra = self.item.copy()
        extra["path"] = "data/raw/sample/extra.jsonl"
        extra["records"] = 0
        extra["source_url_records"] = 0
        self.registry["sources"].append(extra)
        self.inventory["files"].append({"path":extra["path"], "records":0, "sha256":extra["sha256"]})
        self.inventory["summary"]["raw_records"] = 1
        out = validate_manifests(self.inventory,self.registry)
        self.assertIn("INVALID_OR_DUPLICATE_SOURCE_ID", {x["code"] for x in out["issues"]})


if __name__ == "__main__":
    unittest.main()
