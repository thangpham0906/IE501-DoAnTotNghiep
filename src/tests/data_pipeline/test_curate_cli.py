#!/usr/bin/env python3
"""Kiểm thử toàn diện module curate_cli.py và khả năng tương thích với clean_dedup/split_dataset."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.data_pipeline.clean_dedup import process_all_raw_data
from src.data_pipeline.common import ROOT, read_jsonl, sha256, write_json, write_jsonl
from src.data_pipeline.curate_cli import (
    check_monolingual_leakage,
    curate_candidate_file,
    inspect_candidate_pairs,
    interactive_curate_cli,
    parse_number_ranges,
    review_batch,
    validate_source_file,
)
from src.data_pipeline.split_dataset import split_dataset


class TestCurateCli(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

        # Tạo cây thư mục mô phỏng
        self.raw_dir = self.root / "data/raw"
        self.interim_dir = self.root / "data/interim"
        self.manifest_dir = self.root / "data/manifests"
        self.processed_dir = self.root / "data/processed"
        for d in (self.raw_dir, self.interim_dir, self.manifest_dir, self.processed_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.sample_rows = [
            {"tay_text": f"Bản mường Tày {i}", "vi_text": f"Bản làng Việt {i}", "source_doc_id": f"doc_{i // 3}"}
            for i in range(12)
        ]
        self.raw_file = self.raw_dir / "sample.jsonl"
        write_jsonl(self.raw_file, self.sample_rows)
        self.raw_sha256 = sha256(self.raw_file)

        self.registry_file = self.manifest_dir / "source_registry.json"
        self.registry_data = {
            "schema_version": 1,
            "sources": [
                {
                    "source_id": "sample_src",
                    "path": "data/raw/sample.jsonl",
                    "sha256": self.raw_sha256,
                    "records": len(self.sample_rows),
                    "training_approved": False,
                }
            ],
        }
        write_json(self.registry_file, self.registry_data)

    def test_parse_number_ranges(self):
        self.assertEqual(parse_number_ranges("1,2,5-8,10", 12), [1, 2, 5, 6, 7, 8, 10])
        self.assertEqual(parse_number_ranges("  3 , 1 , 2 ", 10), [1, 2, 3])
        self.assertEqual(parse_number_ranges("", 10), [])

        with self.assertRaises(ValueError):
            parse_number_ranges("1,15", 10)  # out of bounds
        with self.assertRaises(ValueError):
            parse_number_ranges("8-3", 10)  # reversed range
        with self.assertRaises(ValueError):
            parse_number_ranges("abc", 10)  # non-numeric

    def test_validate_source_file(self):
        checksum, rows = validate_source_file(self.raw_file, self.raw_sha256)
        self.assertEqual(checksum, self.raw_sha256)
        self.assertEqual(len(rows), 12)

        with self.assertRaises(FileNotFoundError):
            validate_source_file(self.root / "non_existent.jsonl")

        with self.assertRaises(ValueError):
            validate_source_file(self.raw_file, "wrong_hash_1234567890abcdef")

    def test_review_batch_success(self):
        approved = [1, 2, 3, 4, 5]
        rejections = {6: "wrong_language", 7: "bad_translation"}
        log_file = self.manifest_dir / "audit_log.json"

        updated = review_batch(
            registry_path=self.registry_file,
            source_id="sample_src",
            approved_numbers=approved,
            reviewer="Nguyễn Văn A (Người bản ngữ)",
            evidence=["Biên bản họp thẩm định", "Từ điển đối chiếu Tày-Việt"],
            rejection_reasons=rejections,
            project_root=self.root,
            log_path=log_file,
        )

        self.assertTrue(updated["training_approved"])
        self.assertEqual(updated["content_origin_status"], "verified")
        self.assertEqual(updated["language_review_status"], "approved")
        self.assertEqual(updated["translation_review_status"], "approved")
        self.assertEqual(updated["usage_permission_status"], "confirmed")
        self.assertEqual(updated["reviewed_by"], "Nguyễn Văn A (Người bản ngữ)")
        self.assertEqual(updated["approved_record_numbers"], approved)
        self.assertIn("reviewed_at_utc", updated)
        self.assertEqual(updated["rejection_reasons"]["6"], "wrong_language")
        self.assertEqual(updated["curation_summary"]["approved_records"], 5)
        self.assertEqual(updated["curation_summary"]["rejected_records"], 7)

        # Kiểm tra file registry đã được cập nhật
        saved = json.loads(self.registry_file.read_text(encoding="utf-8"))
        saved_source = saved["sources"][0]
        self.assertTrue(saved_source["training_approved"])
        self.assertEqual(saved_source["approved_record_numbers"], approved)

        # Kiểm tra file audit log
        self.assertTrue(log_file.is_file())
        log_data = json.loads(log_file.read_text(encoding="utf-8"))
        self.assertEqual(log_data["source_id"], "sample_src")
        self.assertEqual(log_data["approved_records"], 5)

    def test_review_batch_validation_errors(self):
        # Thiếu reviewed_by
        with self.assertRaisesRegex(ValueError, "reviewed_by"):
            review_batch(
                registry_path=self.registry_file,
                source_id="sample_src",
                approved_numbers=[1, 2],
                reviewer="",
                evidence=["Valid evidence"],
                project_root=self.root,
            )

        # Thiếu review_evidence
        with self.assertRaisesRegex(ValueError, "review_evidence"):
            review_batch(
                registry_path=self.registry_file,
                source_id="sample_src",
                approved_numbers=[1, 2],
                reviewer="Reviewer",
                evidence=[],
                project_root=self.root,
            )

        # Số thứ tự ngoài phạm vi
        with self.assertRaisesRegex(ValueError, "approved_record_numbers"):
            review_batch(
                registry_path=self.registry_file,
                source_id="sample_src",
                approved_numbers=[1, 99],
                reviewer="Reviewer",
                evidence=["Valid evidence"],
                project_root=self.root,
            )

        # Placeholder reviewed_by bị từ chối
        with self.assertRaisesRegex(ValueError, "reviewed_by không được dùng tên placeholder"):
            review_batch(
                registry_path=self.registry_file,
                source_id="sample_src",
                approved_numbers=[1, 2],
                reviewer="admin",
                evidence=["Valid evidence"],
                project_root=self.root,
            )

        # Sai source_id
        with self.assertRaisesRegex(ValueError, "source_id"):
            review_batch(
                registry_path=self.registry_file,
                source_id="unknown_source",
                approved_numbers=[1],
                reviewer="Reviewer",
                evidence=["Valid evidence"],
                project_root=self.root,
            )

    def test_curate_candidate_file_directly(self):
        interim_candidate = self.interim_dir / "candidates.jsonl"
        candidate_rows = [
            {"tay": "Nặm huổi nà pưng", "vi": "Nước suối ruộng bậc thang", "document_id": "doc_01"},
            {"tay": "Tua mu đăm", "vi": "Con lợn đen", "document_id": "doc_02"},
            {"tay": "Rác rưởi", "vi": "Bản dịch sai hoàn toàn", "document_id": "doc_03"},
        ]
        write_jsonl(interim_candidate, candidate_rows)

        output_curated = self.processed_dir / "curated.jsonl"
        log_path = self.manifest_dir / "curate_candidate_log.json"

        report = curate_candidate_file(
            input_file=interim_candidate,
            output_file=output_curated,
            approved_numbers=[1, 2],
            reviewer="Lê Chuyên Gia",
            evidence=["Đối chiếu thực tế"],
            rejection_reasons={3: "bad_translation"},
            log_path=log_path,
        )

        self.assertEqual(report["total_records"], 3)
        self.assertEqual(report["approved_records"], 2)
        curated_rows = read_jsonl(output_curated)
        self.assertEqual(len(curated_rows), 2)
        self.assertEqual(curated_rows[0]["tay_text"], "Nặm huổi nà pưng")
        self.assertTrue(curated_rows[0]["training_approved"])
        self.assertEqual(curated_rows[0]["reviewed_by"], "Lê Chuyên Gia")
        # Bảo toàn liên kết tài liệu gốc (document grouping), không tự bịa doc_0001
        self.assertEqual(curated_rows[0]["document_id"], "doc_01")
        self.assertEqual(curated_rows[1]["document_id"], "doc_02")

        # Kiểm tra bất biến: Cấm ghi đè input_file
        with self.assertRaisesRegex(ValueError, "không được trùng với input_file"):
            curate_candidate_file(
                input_file=interim_candidate,
                output_file=interim_candidate,
                approved_numbers=[1],
                reviewer="Lê Chuyên Gia",
                evidence=["Đối chiếu thực tế"],
            )

        # Kiểm tra 4 chiều: nếu bản quyền chưa xác nhận thì training_approved phải False
        out_unconfirmed = self.processed_dir / "unconfirmed.jsonl"
        curate_candidate_file(
            input_file=interim_candidate,
            output_file=out_unconfirmed,
            approved_numbers=[1],
            reviewer="Lê Chuyên Gia",
            evidence=["Chưa có bản quyền"],
            usage_permission_status="unconfirmed",
        )
        unconfirmed_rows = read_jsonl(out_unconfirmed)
        self.assertFalse(unconfirmed_rows[0]["training_approved"])

    def test_inspect_candidate_pairs(self):
        inspected = inspect_candidate_pairs(self.raw_file, limit=5, offset=0)
        self.assertEqual(len(inspected), 5)
        self.assertEqual(inspected[0]["record_number"], 1)

    def test_check_monolingual_leakage(self):
        mono_rows = [
            {"text": "Câu đơn ngữ độc lập A"},
            {"text": "Câu đơn ngữ độc lập B"},
            {"text": "Câu này trùng với validation"},
        ]
        val_rows = [
            {"tay": "Câu này trùng với validation", "vi": "Bản dịch val"},
            {"tay": "Câu val độc lập", "vi": "Dịch val"},
        ]
        test_rows = [
            {"tay": "Câu test độc lập", "vi": "Dịch test"},
        ]

        leakage = check_monolingual_leakage(mono_rows, val_rows, test_rows)
        self.assertTrue(leakage["has_leakage"])
        self.assertEqual(leakage["leakage_count"], 1)
        self.assertEqual(leakage["leaked_samples"][0]["leaked_into"], "validation")
        self.assertEqual(leakage["safe_monolingual_count"], 2)

        # Kiểm tra trường hợp rò rỉ gần trùng (Near-Duplicate Leakage)
        near_dup_mono = [
            {"text": "Câu val độc lập này nhé"},  # Near duplicate of "Câu val độc lập"
            {"text": "Câu hoàn toàn khác biệt"},
        ]
        near_leakage = check_monolingual_leakage(near_dup_mono, val_rows, test_rows, near_dup_threshold=0.7)
        self.assertTrue(near_leakage["has_leakage"])
        self.assertEqual(near_leakage["leaked_samples"][0]["leak_type"], "near_duplicate")
        self.assertEqual(near_leakage["safe_monolingual_count"], 1)

        # Kiểm tra trường hợp an toàn hoàn toàn (zero leakage)
        safe_mono = [{"text": "Câu an toàn 1"}, {"text": "Câu an toàn 2"}]
        safe_leakage = check_monolingual_leakage(safe_mono, val_rows, test_rows)
        self.assertFalse(safe_leakage["has_leakage"])
        self.assertEqual(safe_leakage["leakage_count"], 0)

    def test_interactive_curate_cli_simulation(self):
        # Mô phỏng tương tác:
        # Nhập Người duyệt, Bằng chứng
        # Record 1: 'a' (chấp thuận)
        # Record 2: 'r' (từ chối), lý do '2' (bad_translation)
        # Record 3: 's' (bỏ qua)
        # Record 4: 'q' (lưu & thoát)
        input_data = "Trần Bản Ngữ\nThẩm định trực tiếp\na\nr\n2\ns\nq\n"
        in_stream = io.StringIO(input_data)
        out_stream = io.StringIO()

        out_reg = self.manifest_dir / "interactive_reg.json"
        shutil.copyfile(self.registry_file, out_reg)

        summary = interactive_curate_cli(
            raw_file_path=self.raw_file,
            registry_path=out_reg,
            source_id="sample_src",
            input_stream=in_stream,
            output_stream=out_stream,
            project_root=self.root,
        )

        self.assertEqual(summary["reviewer"], "Trần Bản Ngữ")
        self.assertEqual(summary["approved_records"], 1)
        self.assertEqual(summary["approved_numbers"], [1])
        self.assertIn(2, summary["rejection_reasons"])

        # Kiểm tra kết quả ghi vào registry
        reg_check = json.loads(out_reg.read_text(encoding="utf-8"))["sources"][0]
        self.assertTrue(reg_check["training_approved"])
        self.assertEqual(reg_check["approved_record_numbers"], [1])
        self.assertEqual(reg_check["reviewed_by"], "Trần Bản Ngữ")

    def test_end_to_end_integration_with_clean_dedup_and_split(self):
        """Kiểm thử luồng tích hợp: Dùng fixtures -> Duyệt qua curate_cli -> Chạy clean_dedup -> Chạy split_dataset."""
        fixture_bilingual = ROOT / "src/tests/fixtures/sample_bilingual.jsonl"
        self.assertTrue(fixture_bilingual.is_file())

        # Tạo thư mục raw riêng cho bài kiểm tra tích hợp để tránh lẫn tệp khác
        integration_raw_dir = self.root / "data/integration_raw"
        integration_raw_dir.mkdir(parents=True, exist_ok=True)
        dest_raw = integration_raw_dir / "sample_bilingual.jsonl"
        shutil.copyfile(fixture_bilingual, dest_raw)
        raw_hash = sha256(dest_raw)
        total_records = len(read_jsonl(dest_raw))
        self.assertGreaterEqual(total_records, 20)

        # Tạo registry trỏ vào dest_raw
        reg_path = self.manifest_dir / "integration_registry.json"
        write_json(
            reg_path,
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_id": "sample_bilingual",
                        "path": "data/integration_raw/sample_bilingual.jsonl",
                        "sha256": raw_hash,
                        "records": total_records,
                        "training_approved": False,
                    }
                ],
            },
        )

        # Bước 1: Trước khi duyệt, clean_dedup trả về 'no_approved_data'
        clean_out = self.processed_dir / "cleaned.jsonl"
        clean_manifest = self.manifest_dir / "clean_manifest.json"
        pre_report = process_all_raw_data(integration_raw_dir, clean_out, reg_path, clean_manifest, self.root)
        self.assertEqual(pre_report["status"], "no_approved_data")
        self.assertFalse(clean_out.exists())

        # Bước 2: Dùng review_batch phê duyệt toàn bộ bản ghi
        approved_all = list(range(1, total_records + 1))
        updated_source = review_batch(
            registry_path=reg_path,
            source_id="sample_bilingual",
            approved_numbers=approved_all,
            reviewer="Hội đồng Thẩm định Ngữ liệu Tày",
            evidence=["Nghiệm thu bản ngữ", "Đối chiếu từ điển"],
            project_root=self.root,
        )
        self.assertTrue(updated_source["training_approved"])

        # Bước 3: Chạy clean_dedup trên registry đã duyệt
        clean_out_real = self.processed_dir / "cleaned_real.jsonl"
        clean_manifest_real = self.manifest_dir / "clean_manifest_real.json"
        clean_report = process_all_raw_data(integration_raw_dir, clean_out_real, reg_path, clean_manifest_real, self.root)

        self.assertEqual(clean_report["status"], "completed")
        self.assertEqual(clean_report["approved_records"], total_records)
        self.assertTrue(clean_out_real.is_file())
        cleaned_rows = read_jsonl(clean_out_real)
        self.assertEqual(len(cleaned_rows), total_records)

        # Bước 4: Chạy split_dataset trên tập dữ liệu đã làm sạch
        split_dir = self.processed_dir / "splits"
        split_manifest = self.manifest_dir / "split_manifest.json"
        split_report = split_dataset(
            input_path=clean_out_real,
            output_dir=split_dir,
            clean_manifest=clean_manifest_real,
            manifest=split_manifest,
            train_ratio=0.7,
            val_ratio=0.15,
            seed=42,
        )

        self.assertEqual(split_report["status"], "completed")
        self.assertTrue((split_dir / "train_e0.jsonl").is_file())
        self.assertTrue((split_dir / "val.jsonl").is_file())
        self.assertTrue((split_dir / "test.jsonl").is_file())

        train_rows = read_jsonl(split_dir / "train_e0.jsonl")
        val_rows = read_jsonl(split_dir / "val.jsonl")
        test_rows = read_jsonl(split_dir / "test.jsonl")

        self.assertGreater(len(train_rows), 0)
        self.assertGreater(len(val_rows), 0)
        self.assertGreater(len(test_rows), 0)
        self.assertEqual(len(train_rows) + len(val_rows) + len(test_rows), total_records)

        # Bước 5: Kiểm tra rò rỉ đơn ngữ với val và test
        mono_fixture = ROOT / "src/tests/fixtures/sample_monolingual.jsonl"
        self.assertTrue(mono_fixture.is_file())
        mono_rows = read_jsonl(mono_fixture)
        leak_check = check_monolingual_leakage(mono_rows, val_rows, test_rows)
        self.assertFalse(leak_check["has_leakage"])
        self.assertEqual(leak_check["leakage_count"], 0)


if __name__ == "__main__":
    unittest.main()
