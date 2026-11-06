"""Kiểm tra và chuẩn hóa tệp âm thanh WAV PCM theo đặc tả mục 5.3."""

import struct
from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import (
    AudioInvalidError,
    AudioTooLargeError,
    AudioTooLongError,
    AudioUnsupportedFormatError,
)
from src.web_app.services.asr.base import AudioInput


def validate_wav(data: bytes, settings: WebSettings) -> AudioInput:
    """Kiểm tra tính hợp lệ của dữ liệu tệp WAV và trích xuất AudioInput chuẩn hóa.

    Yêu cầu định dạng:
    - Container: RIFF/WAVE hợp lệ
    - Định dạng âm thanh: Format tag 1 (WAVE_FORMAT_PCM không nén)
    - Kênh: 1 (mono)
    - Tần số lấy mẫu: 16.000 Hz
    - Độ sâu mẫu: signed 16-bit little-endian
    - Dữ liệu: Chứa đúng 1 chunk fmt và 1 chunk data, không rỗng, frame count chẵn và nguyên vẹn.

    Các lỗi được phân loại chính xác:
    - AudioTooLargeError: vượt giới hạn dung lượng tệp MAX_AUDIO_FILE_BYTES
    - AudioTooLongError: thời lượng PCM vượt quá MAX_AUDIO_DURATION_SEC
    - AudioUnsupportedFormatError: không phải RIFF/WAVE hoặc sai tag/rate/kênh/bit depth
    - AudioInvalidError: tệp hỏng, cắt cụt, header không khớp, thiếu frame hoặc 0 frames.
    """
    data_len = len(data)

    # 1. Kiểm tra dung lượng tệp trước khi xử lý
    if data_len > settings.MAX_AUDIO_FILE_BYTES:
        raise AudioTooLargeError(
            f"Dung lượng tệp âm thanh ({data_len} bytes) vượt quá giới hạn cho phép ({settings.MAX_AUDIO_FILE_BYTES} bytes)."
        )

    # 2. Kiểm tra độ dài tối thiểu của header WAV (RIFF: 12 bytes + fmt: 24 bytes + data header: 8 bytes = 44 bytes)
    if data_len < 44:
        raise AudioInvalidError(
            f"Dữ liệu âm thanh quá ngắn ({data_len} bytes), không đủ cấu trúc header WAV tối thiểu."
        )

    # 3. Kiểm tra container RIFF
    riff_tag = data[:4]
    if riff_tag != b"RIFF":
        raise AudioUnsupportedFormatError(
            f"Tệp không phải định dạng RIFF/WAVE (header bắt đầu bằng {riff_tag!r})."
        )

    riff_size = struct.unpack_from("<I", data, 4)[0]
    expected_file_size = riff_size + 8
    if expected_file_size != data_len:
        raise AudioInvalidError(
            f"Khai báo kích thước RIFF ({expected_file_size} bytes) không khớp với kích thước tệp thực tế ({data_len} bytes)."
        )

    wave_tag = data[8:12]
    if wave_tag != b"WAVE":
        raise AudioUnsupportedFormatError(
            f"Container RIFF không phải định dạng WAVE (nhận được {wave_tag!r})."
        )

    # 4. Duyệt các chunk bên trong container RIFF
    offset = 12
    end_offset = data_len

    fmt_seen = False
    data_seen = False

    audio_format: int | None = None
    num_channels: int | None = None
    sample_rate: int | None = None
    byte_rate: int | None = None
    block_align: int | None = None
    bits_per_sample: int | None = None

    data_chunk_offset: int | None = None
    data_chunk_size: int | None = None

    while offset < end_offset:
        # Kiểm tra đủ 8 bytes cho chunk header (ID 4 bytes + Size 4 bytes)
        if offset + 8 > end_offset:
            raise AudioInvalidError(
                f"Chunk header bị cắt cụt tại vị trí {offset} (còn lại {end_offset - offset} bytes)."
            )

        chunk_id = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        chunk_data_offset = offset + 8

        # Kiểm tra chunk data có nằm gọn trong file không
        if chunk_data_offset + chunk_size > end_offset:
            raise AudioInvalidError(
                f"Chunk {chunk_id!r} khai báo kích thước {chunk_size} bytes vượt quá kích thước tệp."
            )

        pad_byte = chunk_size % 2
        chunk_total_advance = 8 + chunk_size + pad_byte

        # Kiểm tra byte đệm chẵn nếu chunk có kích thước lẻ
        if chunk_data_offset + chunk_size + pad_byte > end_offset:
            raise AudioInvalidError(
                f"Thiếu byte đệm (padding byte) cho chunk {chunk_id!r} có kích thước lẻ ({chunk_size} bytes)."
            )

        if chunk_id == b"fmt ":
            if fmt_seen:
                raise AudioInvalidError("Phát hiện nhiều hơn một chunk 'fmt ' trong tệp WAV.")
            fmt_seen = True

            if chunk_size < 16:
                raise AudioInvalidError(
                    f"Kích thước chunk 'fmt ' quá nhỏ ({chunk_size} bytes, tối thiểu 16 bytes)."
                )

            (
                audio_format,
                num_channels,
                sample_rate,
                byte_rate,
                block_align,
                bits_per_sample,
            ) = struct.unpack_from("<HHIIHH", data, chunk_data_offset)

            # Kiểm tra định dạng PCM tag 1
            if audio_format != 1:
                raise AudioUnsupportedFormatError(
                    f"Chỉ hỗ trợ format tag 1 (PCM không nén), nhận được format tag {audio_format}."
                )

            # Kiểm tra số kênh mono (1)
            if num_channels != 1:
                raise AudioUnsupportedFormatError(
                    f"Chỉ hỗ trợ âm thanh 1 kênh (mono), nhận được {num_channels} kênh."
                )

            # Kiểm tra tần số lấy mẫu 16.000 Hz
            if sample_rate != 16000:
                raise AudioUnsupportedFormatError(
                    f"Chỉ hỗ trợ tần số lấy mẫu 16.000 Hz, nhận được {sample_rate} Hz."
                )

            # Kiểm tra độ sâu mẫu 16-bit
            if bits_per_sample != 16:
                raise AudioUnsupportedFormatError(
                    f"Chỉ hỗ trợ độ sâu mẫu 16-bit, nhận được {bits_per_sample}-bit."
                )

            # Kiểm tra block align cho 16-bit mono: channels * (bits / 8) = 1 * 2 = 2
            expected_block_align = num_channels * (bits_per_sample // 8)
            if block_align != 2 or block_align != expected_block_align:
                raise AudioInvalidError(
                    f"Block align không hợp lệ: khai báo {block_align}, kỳ vọng {expected_block_align}."
                )

            # Kiểm tra byte rate: sample_rate * block_align = 16000 * 2 = 32000
            expected_byte_rate = sample_rate * block_align
            if byte_rate != 32000 or byte_rate != expected_byte_rate:
                raise AudioInvalidError(
                    f"Byte rate không hợp lệ: khai báo {byte_rate}, kỳ vọng {expected_byte_rate}."
                )

        elif chunk_id == b"data":
            if not fmt_seen:
                raise AudioInvalidError("Chunk 'data' xuất hiện trước chunk 'fmt ' trong tệp WAV.")
            if data_seen:
                raise AudioInvalidError("Phát hiện nhiều hơn một chunk 'data' trong tệp WAV.")
            data_seen = True
            data_chunk_offset = chunk_data_offset
            data_chunk_size = chunk_size

        # Chuyển sang chunk tiếp theo
        offset += chunk_total_advance

    # 5. Xác nhận đã tìm thấy cả fmt và data chunk
    if not fmt_seen:
        raise AudioInvalidError("Không tìm thấy chunk 'fmt ' trong tệp WAV.")

    if not data_seen or data_chunk_offset is None or data_chunk_size is None:
        raise AudioInvalidError("Không tìm thấy chunk 'data' trong tệp WAV.")

    # 6. Kiểm tra tính toàn vẹn dữ liệu PCM và số frame
    # Mỗi frame là block_align = 2 bytes
    if data_chunk_size % 2 != 0:
        raise AudioInvalidError(
            f"Kích thước dữ liệu PCM ({data_chunk_size} bytes) không chia hết cho kích thước frame (2 bytes)."
        )

    frame_count = data_chunk_size // 2
    if frame_count == 0:
        raise AudioInvalidError("Tệp âm thanh không chứa frame nào (0 frames).")

    # 7. Kiểm tra thời lượng PCM thực tế
    duration_sec = frame_count / 16000.0
    if duration_sec > settings.MAX_AUDIO_DURATION_SEC:
        raise AudioTooLongError(
            f"Thời lượng âm thanh ({duration_sec:.2f}s) vượt quá giới hạn cho phép ({settings.MAX_AUDIO_DURATION_SEC}s)."
        )

    # 8. Cấp phát và trích xuất sau khi tất cả điều kiện và giới hạn đã được thỏa mãn
    pcm_bytes = data[data_chunk_offset : data_chunk_offset + data_chunk_size]

    return AudioInput(
        pcm_bytes=pcm_bytes,
        sample_rate_hz=16000,
        channels=1,
        frame_count=frame_count,
        duration_sec=duration_sec,
    )
