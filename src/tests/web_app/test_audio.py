"""Unit tests cho module validate_wav và các ca biên âm thanh."""

import pytest

from src.web_app.core.config import WebSettings
from src.web_app.core.exceptions import (
    AudioInvalidError,
    AudioTooLargeError,
    AudioTooLongError,
    AudioUnsupportedFormatError,
)
from src.web_app.services.asr.audio import validate_wav
from src.tests.web_app.audio_fixtures import build_wav_bytes


@pytest.fixture
def default_settings() -> WebSettings:
    return WebSettings()


class TestWAVValidationSuccess:
    """Các trường hợp tệp WAV hợp lệ."""

    def test_valid_wav_standard(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(duration_sec=1.0)
        audio = validate_wav(data, default_settings)
        assert audio.sample_rate_hz == 16000
        assert audio.channels == 1
        assert audio.frame_count == 16000
        assert audio.duration_sec == 1.0
        assert len(audio.pcm_bytes) == 32000

    def test_valid_wav_half_second(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(duration_sec=0.5)
        audio = validate_wav(data, default_settings)
        assert audio.frame_count == 8000
        assert audio.duration_sec == 0.5
        assert len(audio.pcm_bytes) == 16000

    def test_valid_wav_exact_max_duration_boundary(
        self, default_settings: WebSettings
    ) -> None:
        # Chính xác 30 giây (30 * 16000 = 480000 frames)
        data = build_wav_bytes(duration_sec=30.0)
        audio = validate_wav(data, default_settings)
        assert audio.frame_count == 480000
        assert audio.duration_sec == 30.0

    def test_valid_wav_with_extra_chunk(self, default_settings: WebSettings) -> None:
        # Thêm chunk JUNK hợp lệ giữa fmt và data
        extra = (b"JUNK", b"padding info")
        data = build_wav_bytes(duration_sec=0.5, extra_chunk=extra)
        audio = validate_wav(data, default_settings)
        assert audio.duration_sec == 0.5


class TestWAVValidationLimits:
    """Kiểm tra các ngưỡng giới hạn dung lượng và thời lượng."""

    def test_audio_too_large(self) -> None:
        # Đặt giới hạn nhỏ để kiểm thử
        settings = WebSettings(MAX_AUDIO_FILE_BYTES=500, MAX_MULTIPART_BODY_BYTES=1000)
        data = build_wav_bytes(duration_sec=1.0)  # > 32000 bytes
        with pytest.raises(AudioTooLargeError) as exc_info:
            validate_wav(data, settings)
        assert exc_info.value.status_code == 413
        assert exc_info.value.error_code == "AUDIO_TOO_LARGE"

    def test_audio_too_long(self, default_settings: WebSettings) -> None:
        # Thời lượng 30.1 giây (vượt quá 30 giây)
        data = build_wav_bytes(duration_sec=30.1)
        with pytest.raises(AudioTooLongError) as exc_info:
            validate_wav(data, default_settings)
        assert exc_info.value.status_code == 400
        assert exc_info.value.error_code == "AUDIO_TOO_LONG"


class TestWAVValidationUnsupportedFormat:
    """Các trường hợp không đúng định dạng WAV PCM 16kHz mono 16-bit."""

    def test_non_riff_header(self, default_settings: WebSettings) -> None:
        # Header MP3 ID3 hoặc plain text
        data = b"ID3\x03\x00\x00\x00" + b"\x00" * 50
        with pytest.raises(AudioUnsupportedFormatError) as exc:
            validate_wav(data, default_settings)
        assert exc.value.error_code == "AUDIO_UNSUPPORTED_FORMAT"

    def test_non_wave_container(self, default_settings: WebSettings) -> None:
        # Container RIFF nhưng tag là AVI
        data = build_wav_bytes(wave_tag=b"AVI ")
        with pytest.raises(AudioUnsupportedFormatError) as exc:
            validate_wav(data, default_settings)
        assert exc.value.error_code == "AUDIO_UNSUPPORTED_FORMAT"

    @pytest.mark.parametrize("fmt_tag", [3, 6, 7])
    def test_non_pcm_format_tag(
        self, default_settings: WebSettings, fmt_tag: int
    ) -> None:
        # Format tag 3 (IEEE float), 6 (ALAW), 7 (MULAW)
        data = build_wav_bytes(audio_format=fmt_tag)
        with pytest.raises(AudioUnsupportedFormatError) as exc:
            validate_wav(data, default_settings)
        assert exc.value.error_code == "AUDIO_UNSUPPORTED_FORMAT"

    @pytest.mark.parametrize("rate", [8000, 22050, 44100, 48000])
    def test_unsupported_sample_rates(
        self, default_settings: WebSettings, rate: int
    ) -> None:
        data = build_wav_bytes(sample_rate=rate)
        with pytest.raises(AudioUnsupportedFormatError) as exc:
            validate_wav(data, default_settings)
        assert exc.value.error_code == "AUDIO_UNSUPPORTED_FORMAT"

    def test_unsupported_channels_stereo(
        self, default_settings: WebSettings
    ) -> None:
        data = build_wav_bytes(num_channels=2)
        with pytest.raises(AudioUnsupportedFormatError) as exc:
            validate_wav(data, default_settings)
        assert exc.value.error_code == "AUDIO_UNSUPPORTED_FORMAT"

    @pytest.mark.parametrize("bits", [8, 24, 32])
    def test_unsupported_bits_per_sample(
        self, default_settings: WebSettings, bits: int
    ) -> None:
        data = build_wav_bytes(bits_per_sample=bits)
        with pytest.raises(AudioUnsupportedFormatError) as exc:
            validate_wav(data, default_settings)
        assert exc.value.error_code == "AUDIO_UNSUPPORTED_FORMAT"


class TestWAVValidationInvalidData:
    """Các trường hợp tệp WAV bị hỏng hoặc dữ liệu không nhất quán."""

    def test_empty_and_short_data(self, default_settings: WebSettings) -> None:
        with pytest.raises(AudioInvalidError):
            validate_wav(b"", default_settings)
        with pytest.raises(AudioInvalidError):
            validate_wav(b"RIFF\x10\x00\x00\x00WAVE", default_settings)

    def test_riff_size_declared_mismatch(
        self, default_settings: WebSettings
    ) -> None:
        # Khai báo kích thước lớn hơn thực tế
        data = build_wav_bytes(override_riff_size=999999)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

        # Khai báo kích thước nhỏ hơn thực tế
        data_short = build_wav_bytes(override_riff_size=20)
        with pytest.raises(AudioInvalidError):
            validate_wav(data_short, default_settings)

    def test_truncated_chunk_header(self, default_settings: WebSettings) -> None:
        valid = build_wav_bytes()
        # Cắt bớt 4 byte cuối của file
        truncated = valid[:-4]
        with pytest.raises(AudioInvalidError):
            validate_wav(truncated, default_settings)

    def test_chunk_size_exceeds_file(self, default_settings: WebSettings) -> None:
        # fmt_size khai báo quá lớn
        data = build_wav_bytes(override_fmt_size=2000)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_missing_fmt_chunk(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(omit_fmt=True)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_missing_data_chunk(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(omit_data=True)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_fmt_chunk_size_too_small(self, default_settings: WebSettings) -> None:
        # fmt chunk size < 16
        valid = build_wav_bytes()
        # Sửa fmt chunk size (byte 16..20) thành 10
        corrupt = valid[:16] + b"\x0a\x00\x00\x00" + valid[20:]
        with pytest.raises(AudioInvalidError):
            validate_wav(corrupt, default_settings)

    def test_duplicate_fmt_chunk(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(duplicate_fmt=True)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_duplicate_data_chunk(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(duplicate_data=True)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_data_before_fmt_chunk(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(data_before_fmt=True)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_inconsistent_block_align(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(override_block_align=4)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_inconsistent_byte_rate(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(override_byte_rate=16000)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_pcm_data_odd_bytes(self, default_settings: WebSettings) -> None:
        # PCM 16-bit mono yêu cầu số byte chẵn (mỗi sample 2 byte)
        data = build_wav_bytes(pcm_bytes=b"\x00" * 31)
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)

    def test_zero_frames(self, default_settings: WebSettings) -> None:
        data = build_wav_bytes(pcm_bytes=b"")
        with pytest.raises(AudioInvalidError):
            validate_wav(data, default_settings)
