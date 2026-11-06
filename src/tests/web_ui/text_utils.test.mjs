/**
 * Unit tests cho text_utils.js sử dụng Node.js test runner tích hợp (node --test).
 * Kiểm tra chuẩn hóa Unicode NFC, cắt tỉa đúng 25 ký tự khoảng trắng, và đếm code point ngoài BMP.
 */

import test, { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  WHITESPACE_CHARS,
  normalizeText,
  codePointLength,
} from '../../web_app/ui/js/text_utils.js';

describe('text_utils - Unicode White_Space và chuẩn hóa NFC', () => {
  it('đúng 25 ký tự khoảng trắng trong tập WHITESPACE_CHARS', () => {
    const chars = Array.from(WHITESPACE_CHARS);
    assert.equal(chars.length, 25);
  });

  it('xử lý chuỗi rỗng và chuỗi không hợp lệ', () => {
    assert.equal(normalizeText(''), '');
    assert.equal(normalizeText(null), '');
    assert.equal(normalizeText(undefined), '');
    assert.equal(normalizeText(123), '');
  });

  it('xử lý chuỗi chỉ chứa khoảng trắng', () => {
    assert.equal(normalizeText('   '), '');
    assert.equal(normalizeText('\t\n\r'), '');
    assert.equal(normalizeText(WHITESPACE_CHARS), '');
  });

  it('chuẩn hóa tổ hợp NFD sang dựng sẵn NFC', () => {
    // Chuỗi decomposed (NFD): 'a' + dấu sắc (U+0301)
    const decomposed = 'á';
    const composed = 'á';
    assert.equal(normalizeText(decomposed), composed);

    // Cụm từ tiếng Việt có dấu tổ hợp
    const textNfd = 'Việt Nam quê hương tôi, đáng sống';
    const expected = 'Việt Nam quê hương tôi, đáng sống';
    assert.equal(normalizeText(textNfd), expected);
  });

  it('cắt tỉa từng ký tự trong 25 ký tự khoảng trắng ở cả 2 đầu', () => {
    const chars = Array.from(WHITESPACE_CHARS);
    for (const ws of chars) {
      const padded = `${ws}Xin chào bà con${ws}`;
      assert.equal(
        normalizeText(padded),
        'Xin chào bà con',
        `Không cắt được khoảng trắng mã 0x${ws.codePointAt(0).toString(16)}`
      );
    }
  });

  it('giữ nguyên khoảng trắng bên trong chuỗi', () => {
    const input = '   Từ thứ nhất\t\ttừ thứ hai   từ thứ ba　từ thứ tư   ';
    const expected = 'Từ thứ nhất\t\ttừ thứ hai   từ thứ ba　từ thứ tư';
    assert.equal(normalizeText(input), expected);
  });

  it('bảo toàn văn bản tiếng Tày và ký tự đặc biệt', () => {
    const tayText = '  Báo Tày vằn nay slắng slương.  ';
    assert.equal(normalizeText(tayText), 'Báo Tày vằn nay slắng slương.');
  });
});

describe('text_utils - Đếm Unicode code point', () => {
  it('đếm ký tự ASCII và chuỗi rỗng', () => {
    assert.equal(codePointLength(''), 0);
    assert.equal(codePointLength(null), 0);
    assert.equal(codePointLength('Hello'), 5);
  });

  it('đếm ký tự tiếng Việt có dấu dựng sẵn', () => {
    // 'Việt' có 4 code point
    assert.equal(codePointLength('Việt'), 4);
  });

  it('đếm ký tự ngoài BMP (astral plane / surrogate pairs / emoji)', () => {
    // Biểu tượng cảm xúc 😀 (U+1F600): String.length là 2, code point length là 1
    const emoji = '😀';
    assert.equal(emoji.length, 2);
    assert.equal(codePointLength(emoji), 1);

    // Ký tự chữ Hán hiếm ngoài BMP: 𠮷 (U+20BB7): String.length là 2, code point length là 1
    const rareChar = '𠮷';
    assert.equal(rareChar.length, 2);
    assert.equal(codePointLength(rareChar), 1);

    // Chuỗi hỗn hợp: 'Chào 🌟 bạn 𠮷!'
    // C(1) h(1) à(1) o(1) ' '(1) 🌟(1) ' '(1) b(1) ạ(1) n(1) ' '(1) 𠮷(1) !(1) = 13 code points
    const mixed = 'Chào 🌟 bạn 𠮷!';
    assert.equal(codePointLength(mixed), 13);
  });

  it('đếm sau chuẩn hóa NFC đồng nhất với backend Python', () => {
    // 'á' (2 code points trước NFC, 1 code point sau NFC)
    const decomposed = 'á';
    assert.equal(codePointLength(decomposed), 2);
    const normalized = normalizeText(decomposed);
    assert.equal(codePointLength(normalized), 1);
  });
});
