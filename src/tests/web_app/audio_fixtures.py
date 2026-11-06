"""Hàm tiện ích sinh dữ liệu tệp WAV trong bộ nhớ phục vụ kiểm thử."""

import struct


def build_wav_bytes(
    num_channels: int = 1,
    sample_rate: int = 16000,
    bits_per_sample: int = 16,
    audio_format: int = 1,
    pcm_bytes: bytes | None = None,
    duration_sec: float | None = None,
    override_riff_size: int | None = None,
    override_fmt_size: int | None = None,
    override_data_size: int | None = None,
    override_byte_rate: int | None = None,
    override_block_align: int | None = None,
    riff_tag: bytes = b"RIFF",
    wave_tag: bytes = b"WAVE",
    omit_fmt: bool = False,
    omit_data: bool = False,
    duplicate_fmt: bool = False,
    duplicate_data: bool = False,
    data_before_fmt: bool = False,
    extra_chunk: tuple[bytes, bytes] | None = None,
    include_odd_pad_byte: bool = True,
) -> bytes:
    """Tạo byte stream WAV hợp lệ hoặc tùy biến lỗi phục vụ kiểm thử."""
    block_align = (
        override_block_align
        if override_block_align is not None
        else num_channels * (bits_per_sample // 8)
    )
    byte_rate = (
        override_byte_rate
        if override_byte_rate is not None
        else sample_rate * block_align
    )

    # Nếu không truyền pcm_bytes, tự sinh từ duration_sec
    if pcm_bytes is None:
        dur = duration_sec if duration_sec is not None else 1.0
        frame_count = int(sample_rate * dur)
        pcm_bytes = b"\x00" * (frame_count * block_align)

    # Xây dựng fmt chunk
    fmt_data = struct.pack(
        "<HHIIHH",
        audio_format,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
    )
    fmt_chunk_size = (
        override_fmt_size if override_fmt_size is not None else len(fmt_data)
    )
    fmt_chunk = b"fmt " + struct.pack("<I", fmt_chunk_size) + fmt_data

    # Xây dựng data chunk
    data_chunk_size = (
        override_data_size if override_data_size is not None else len(pcm_bytes)
    )
    data_chunk = b"data" + struct.pack("<I", data_chunk_size) + pcm_bytes
    if data_chunk_size % 2 == 1 and include_odd_pad_byte:
        data_chunk += b"\x00"

    # Tổ chức các chunk
    chunks: list[bytes] = []

    if data_before_fmt:
        if not omit_data:
            chunks.append(data_chunk)
            if duplicate_data:
                chunks.append(data_chunk)
        if not omit_fmt:
            chunks.append(fmt_chunk)
            if duplicate_fmt:
                chunks.append(fmt_chunk)
    else:
        if not omit_fmt:
            chunks.append(fmt_chunk)
            if duplicate_fmt:
                chunks.append(fmt_chunk)
        if extra_chunk:
            c_tag, c_data = extra_chunk
            chunk_bytes = c_tag + struct.pack("<I", len(c_data)) + c_data
            if len(c_data) % 2 == 1 and include_odd_pad_byte:
                chunk_bytes += b"\x00"
            chunks.append(chunk_bytes)
        if not omit_data:
            chunks.append(data_chunk)
            if duplicate_data:
                chunks.append(data_chunk)

    body = wave_tag + b"".join(chunks)
    riff_size = (
        override_riff_size if override_riff_size is not None else len(body)
    )

    return riff_tag + struct.pack("<I", riff_size) + body
