# IE501 — Đồ án tốt nghiệp

**Đề tài:** Nghiên cứu hệ thống dịch máy cho ngôn ngữ ít tài nguyên: Xây dựng bộ dữ liệu và phương pháp tăng cường dữ liệu cho tiếng Tày.

**Research on Machine Translation Systems for Low-Resource Languages: A Dataset and Data Augmentation Methods for the Tay Language.**

Dự án nghiên cứu bộ dữ liệu, phương pháp tăng cường dữ liệu và hệ thống dịch máy **Việt ↔ Tày**, kèm ứng dụng minh họa.

| Vai trò | Họ tên | MSSV |
| --- | --- | --- |
| Sinh viên | Phạm Quốc Thắng | 25410304 |
| Sinh viên | Lê Minh Thiện | 25410313 |
| Giảng viên hướng dẫn | ThS. Nguyễn Thành Luân | — |

Hệ đào tạo: Đào tạo từ xa — Trường Đại học Công nghệ Thông tin, ĐHQG TP.HCM.

**Thời gian thực hiện:** 05/11/2026–17/01/2027. Xem kế hoạch 11 tuần công việc tại [TASKS.md](TASKS.md).

## Tài liệu dự án

| Tài liệu | Nội dung |
| --- | --- |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Bối cảnh, phạm vi và các quyết định cần thống nhất |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Thành phần hệ thống, luồng dữ liệu và cấu trúc mã nguồn dự kiến |
| [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) | Yêu cầu chức năng, chất lượng và tiêu chí nghiệm thu |
| [TASKS.md](TASKS.md) | Trạng thái hiện tại, công việc, phụ thuộc và bằng chứng hoàn thành |
| [.agents/README.md](.agents/README.md) | Quy định báo cáo/review theo nhóm; [phân công 3 nhánh và báo cáo](.agents/BRANCHES.md) |
| [Quy trình xây dựng dữ liệu](docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md) | Từng bước tạo file trong `data/`, lệnh đã chạy, kết quả và nội dung báo cáo tiến độ |
| [AGENTS.md](AGENTS.md) | Hướng dẫn dành cho agent làm việc với repo |

## Bắt đầu

Đã có pipeline dữ liệu dùng thư viện chuẩn Python >= 3.10, kiểm tra trên Python 3.12.3. Chạy từ thư mục gốc:

```bash
python3 -m unittest discover -s src/tests -t . -p 'test_*.py'
```

Đã chạy lại luồng VOV4 106 bài → 97 ứng viên tài liệu → 174 câu đơn ngữ và đối chiếu khớp byte. Các bước xử lý, lệnh chạy lại và điều kiện đưa dữ liệu vào `processed/` nằm trong [hướng dẫn dữ liệu](docs/QUY_TRINH_XAY_DUNG_DU_LIEU.md). Chưa có dữ liệu được duyệt để huấn luyện, mô hình hoặc ứng dụng demo.

Xem [kiểm kê dữ liệu](data/manifests/inventory.json), [danh mục nguồn](data/manifests/source_registry.json) và [kết quả kiểm tra](data/manifests/validation_report.json). Dữ liệu và log hiện lưu cục bộ, được `.gitignore` loại khỏi Git trong khi xác minh nguồn và điều kiện sử dụng; bản clone chỉ có manifest sẽ không tự có corpus. Các số lượng chi tiết và việc còn lại được quản lý tại [TASKS.md](TASKS.md).

## Tài liệu tham khảo

- [Đề cương chi tiết đồ án](docs/DeCuongDATN_25410304_25410313.pdf)
- [Bản Markdown để chỉnh đề cương](docs/DeCuongDATN_25410304_25410313.md)
- [Các mục đã sửa và hướng dẫn xuất PDF](docs/REVIEW_DE_CUONG.md)
- [Danh sách GVHD và thông tin](reference/Danh%20sách%20GVHD%20và%20thông%20tin.md)
