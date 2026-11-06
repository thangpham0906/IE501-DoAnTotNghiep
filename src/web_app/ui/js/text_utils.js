/**
 * Tiện ích xử lý văn bản và đếm Unicode code point theo đặc tả §4.3 và §6.2.
 * Đảm bảo tính toán đồng nhất giữa frontend và backend Python.
 */

/**
 * Danh sách 25 ký tự khoảng trắng chuẩn Unicode White_Space theo mục 4.3 của đặc tả:
 * U+0009–000D, U+0020, U+0085, U+00A0, U+1680, U+2000–200A, U+2028–2029, U+202F, U+205F, U+3000.
 */
export const WHITESPACE_CHARS =
  '\t\n\x0b\x0c\r' + // U+0009-000D
  ' ' + // U+0020
  '\x85' + // U+0085
  '\xa0' + // U+00A0
  ' ' + // U+1680
  '           ' + // U+2000-200A
  '  ' + // U+2028-2029
  ' ' + // U+202F
  ' ' + // U+205F
  '　'; // U+3000

// Tập tra cứu nhanh cho các ký tự khoảng trắng
const WHITESPACE_SET = new Set(Array.from(WHITESPACE_CHARS));

/**
 * Chuẩn hóa văn bản sang Unicode NFC và cắt bỏ các ký tự khoảng trắng ở hai đầu
 * theo đúng tập 25 ký tự WHITESPACE_CHARS.
 * Khoảng trắng bên trong văn bản được bảo toàn nguyên vẹn.
 *
 * @param {string} text - Chuỗi văn bản đầu vào
 * @returns {string} - Chuỗi sau chuẩn hóa NFC và cắt tỉa
 */
export function normalizeText(text) {
  if (typeof text !== 'string' || text.length === 0) {
    return '';
  }

  // Bước 1: Chuẩn hóa NFC
  const normalized = text.normalize('NFC');
  if (normalized.length === 0) {
    return '';
  }

  // Bước 2: Tách thành mảng các code point để duyệt ranh giới chính xác
  const chars = Array.from(normalized);

  let start = 0;
  while (start < chars.length && WHITESPACE_SET.has(chars[start])) {
    start++;
  }

  // Nếu toàn bộ chuỗi là khoảng trắng
  if (start === chars.length) {
    return '';
  }

  let end = chars.length - 1;
  while (end >= start && WHITESPACE_SET.has(chars[end])) {
    end--;
  }

  return chars.slice(start, end + 1).join('');
}

/**
 * Đếm số lượng Unicode code point của chuỗi văn bản.
 * Xử lý chính xác các ký tự nằm ngoài Basic Multilingual Plane (BMP)
 * như surrogate pairs, biểu tượng cảm xúc (emoji) hoặc chữ Tày cổ/Hán Nôm.
 *
 * @param {string} text - Chuỗi cần đếm code point
 * @returns {number} - Số lượng code point
 */
export function codePointLength(text) {
  if (typeof text !== 'string' || text.length === 0) {
    return 0;
  }
  return Array.from(text).length;
}
