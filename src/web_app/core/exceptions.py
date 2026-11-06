"""Các ngoại lệ nghiệp vụ (Domain Exceptions) của Web Demo."""

from typing import Any


class AppError(Exception):
    """Lớp cơ sở cho các lỗi nghiệp vụ có thể kiểm soát."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    default_message: str = "Đã xảy ra lỗi hệ thống."

    def __init__(
        self,
        message: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.default_message)
        self.message = message or self.default_message
        self.detail = detail


class InvalidInputError(AppError):
    status_code = 400
    error_code = "INVALID_INPUT"
    default_message = "Dữ liệu đầu vào không hợp lệ hoặc thiếu trường bắt buộc."


class UnsupportedDirectionError(AppError):
    status_code = 400
    error_code = "UNSUPPORTED_DIRECTION"
    default_message = "Chiều dịch không được hỗ trợ bởi bundle hiện tại."


class InputTooLongError(AppError):
    status_code = 400
    error_code = "INPUT_TOO_LONG"
    default_message = "Văn bản vượt quá giới hạn cho phép."


class RequestTooLargeError(AppError):
    status_code = 413
    error_code = "REQUEST_TOO_LARGE"
    default_message = "Kích thước yêu cầu vượt quá giới hạn cho phép."


class AudioTooLargeError(AppError):
    status_code = 413
    error_code = "AUDIO_TOO_LARGE"
    default_message = "Dung lượng tệp âm thanh vượt quá giới hạn cho phép."


class AudioTooLongError(AppError):
    status_code = 400
    error_code = "AUDIO_TOO_LONG"
    default_message = "Thời lượng âm thanh vượt quá giới hạn cho phép."


class AudioUnsupportedFormatError(AppError):
    status_code = 400
    error_code = "AUDIO_UNSUPPORTED_FORMAT"
    default_message = (
        "Định dạng âm thanh không được hỗ trợ. Yêu cầu WAV PCM signed 16-bit 16kHz mono."
    )


class AudioInvalidError(AppError):
    status_code = 400
    error_code = "AUDIO_INVALID"
    default_message = "Tệp WAV bị hỏng hoặc dữ liệu không khớp header."


class UnsupportedASRLanguageError(AppError):
    status_code = 400
    error_code = "UNSUPPORTED_ASR_LANGUAGE"
    default_message = "Ngôn ngữ nhận dạng âm thanh không được hỗ trợ. Chỉ hỗ trợ tiếng Việt ('vi')."


class NoSpeechDetectedError(AppError):
    status_code = 400
    error_code = "NO_SPEECH_DETECTED"
    default_message = "Không phát hiện lời nói có nội dung trong tệp âm thanh."


class ModelNotFoundError(AppError):
    status_code = 404
    error_code = "MODEL_NOT_FOUND"
    default_message = "Không tìm thấy mô hình được yêu cầu."


class ModelNotReadyError(AppError):
    status_code = 503
    error_code = "MODEL_NOT_READY"
    default_message = "Mô hình hoặc engine chưa sẵn sàng để phục vụ yêu cầu."


class ServiceOverloadedError(AppError):
    status_code = 503
    error_code = "SERVICE_OVERLOADED"
    default_message = "Hệ thống đang bận. Hàng đợi suy luận đã đầy."


class InferenceTimeoutError(AppError):
    status_code = 504
    error_code = "INFERENCE_TIMEOUT"
    default_message = "Thời gian xử lý suy luận đã vượt quá giới hạn cho phép."

    def __init__(self, phase: str, message: str | None = None) -> None:
        self.phase = phase
        detail = {"phase": phase}
        msg = message or f"Quá thời hạn xử lý ở giai đoạn: {phase}."
        super().__init__(message=msg, detail=detail)



class OutputTooLongError(AppError):
    status_code = 500
    error_code = "OUTPUT_TOO_LONG"
    default_message = "Mô hình chạm giới hạn độ dài đầu ra trước khi hoàn tất bản dịch."


class InferenceFailedError(AppError):
    status_code = 500
    error_code = "INFERENCE_FAILED"
    default_message = "Suy luận dịch thất bại trong quá trình xử lý."


class ASRFailureError(AppError):
    status_code = 500
    error_code = "ASR_FAILURE"
    default_message = "Nhận dạng giọng nói thất bại trong quá trình xử lý."


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"
    default_message = "Tài nguyên hoặc đường dẫn API không tồn tại."


class MethodNotAllowedError(AppError):
    status_code = 405
    error_code = "METHOD_NOT_ALLOWED"
    default_message = "Phương thức HTTP không được phép cho endpoint này."


class InternalError(AppError):
    status_code = 500
    error_code = "INTERNAL_ERROR"
    default_message = "Đã xảy ra lỗi nội bộ không mong muốn."
