/**
 * Chạy: node --test scripts/screenshot_png.test.mjs
 * PNG tổng hợp chỉ là fixture kiểm thử decoder trong thư mục tạm, KHÔNG là ảnh UI.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { after, test } from 'node:test';
import { deflateSync } from 'node:zlib';
import { decodeScreenshotPng, validateScreenshot } from './screenshot_png.mjs';

const TEMP_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'screenshot-png-fixtures-'));
after(() => fs.rmSync(TEMP_DIR, { recursive: true, force: true }));
const WIDTH = 256;
const HEIGHT = 64;
const SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

// Encoder fixture dùng phép trừ predictor, CRC tính bit-by-bit độc lập với helper.
function chunk(type, data) {
  const name = Buffer.from(type);
  let crc = 0xffffffff;
  for (const byte of Buffer.concat([name, data])) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  const result = Buffer.alloc(data.length + 12);
  result.writeUInt32BE(data.length, 0);
  name.copy(result, 4);
  data.copy(result, 8);
  result.writeUInt32BE((crc ^ 0xffffffff) >>> 0, result.length - 4);
  return result;
}

function paethForFixture(a, b, c) {
  const p = a + b - c;
  const distances = [Math.abs(p - a), Math.abs(p - b), Math.abs(p - c)];
  return [a, b, c][distances.indexOf(Math.min(...distances))];
}

function fixture({ channels = 3, filter = 0, pixel = (x) => [x, x, x, 255] } = {}) {
  const pixels = Buffer.alloc(WIDTH * HEIGHT * channels);
  for (let y = 0; y < HEIGHT; y++) {
    for (let x = 0; x < WIDTH; x++) {
      const rgba = pixel(x, y);
      for (let c = 0; c < channels; c++) pixels[(y * WIDTH + x) * channels + c] = rgba[c];
    }
  }
  const rowBytes = WIDTH * channels;
  const scanlines = Buffer.alloc((rowBytes + 1) * HEIGHT);
  for (let y = 0; y < HEIGHT; y++) {
    const kind = typeof filter === 'function' ? filter(y) : filter;
    scanlines[y * (rowBytes + 1)] = kind;
    for (let x = 0; x < rowBytes; x++) {
      const index = y * rowBytes + x;
      const left = x >= channels ? pixels[index - channels] : 0;
      const up = y ? pixels[index - rowBytes] : 0;
      const upperLeft = y && x >= channels ? pixels[index - rowBytes - channels] : 0;
      const predictors = [0, left, up, Math.floor((left + up) / 2), paethForFixture(left, up, upperLeft)];
      scanlines[y * (rowBytes + 1) + x + 1] = (pixels[index] - predictors[kind]) & 0xff;
    }
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(WIDTH, 0);
  header.writeUInt32BE(HEIGHT, 4);
  header[8] = 8;
  header[9] = channels === 4 ? 6 : 2;
  return { header, scanlines, pixels };
}

function encode({ header, scanlines }, compressed = deflateSync(scanlines, { level: 0 })) {
  return Buffer.concat([SIGNATURE, chunk('IHDR', header), chunk('IDAT', compressed), chunk('IEND', Buffer.alloc(0))]);
}

function validateFixture(name, png) {
  const file = path.join(TEMP_DIR, name);
  fs.writeFileSync(file, png);
  return validateScreenshot(file);
}

for (const channels of [3, 4]) {
  test(`Cùng gradient ${channels === 3 ? 'RGB' : 'RGBA đục'} được chấp nhận và cùng pixel/màu với filters 0–4`, () => {
    for (let filter = 0; filter <= 4; filter++) {
      const input = fixture({ channels, filter });
      const png = encode(input);
      assert.ok(png.length > 5000);
      const decoded = decodeScreenshotPng(png);
      assert.deepEqual(decoded.pixels, input.pixels, `Pixel phải khớp từng byte (filter=${filter})`);
      assert.equal(decoded.channels, channels);
      const meta = validateFixture(`gradient-${channels}-${filter}.png`, png);
      assert.deepEqual(meta, { width: WIDTH, height: HEIGHT, size: png.length, colorsCount: 64 });
    }
  });
}

test('Hoàn tác filters hỗn hợp trên ảnh 2D có wrap-around và alpha đục', () => {
  for (const channels of [3, 4]) {
    const input = fixture({
      channels,
      filter: (y) => y % 5,
      pixel: (x, y) => [(x * 19 + y * 37) % 256, (x * 3 + y * 53) % 256, (x * 71 + y * 7) % 256, 255],
    });
    assert.deepEqual(decodeScreenshotPng(encode(input)).pixels, input.pixels);
    assert.ok(validateFixture(`mixed-${channels}.png`, encode(input)).colorsCount >= 20);
  }
});

test('PNG đơn sắc >5000 bytes bị từ chối với tất cả filters 0–4', () => {
  for (const channels of [3, 4]) {
    for (let filter = 0; filter <= 4; filter++) {
      const png = encode(fixture({ channels, filter, pixel: () => [248, 250, 252, 255] }));
      assert.ok(png.length > 5000);
      assert.throws(() => validateFixture(`solid-${channels}-${filter}.png`, png), /chỉ có 1 màu pixel/);
    }
  }
});

test('RGB đa dạng nhưng alpha trong suốt/bán trong suốt không được coi là nội dung ảnh', () => {
  for (const alpha of [0, 128]) {
    const png = encode(fixture({ channels: 4, filter: 4, pixel: (x) => [x, x, x, alpha] }));
    assert.throws(() => validateFixture(`transparent-${alpha}.png`, png), /alpha.*trong suốt/);
  }
  const input = fixture({ channels: 4 });
  input.pixels[7] = 0; // Pixel không nằm trên lưới lấy mẫu màu vẫn phải bị từ chối.
  // Với filter None, offset tương ứng trong scanline bằng 1 + offset pixel.
  input.scanlines[8] = 0;
  assert.throws(() => decodeScreenshotPng(encode(input)), /alpha.*trong suốt/);
});

test('Payload scanline thiếu/thừa bị từ chối kể cả zlib và CRC hợp lệ', () => {
  for (const channels of [3, 4]) {
    const input = fixture({ channels, filter: 3 });
    assert.throws(() => decodeScreenshotPng(encode({ ...input, scanlines: input.scanlines.subarray(0, -1) })), /payload scanline/);
    assert.throws(() => decodeScreenshotPng(encode({ ...input, scanlines: Buffer.concat([input.scanlines, Buffer.from([0])]) })), /payload scanline/);
  }
});

test('Dữ liệu zlib hỏng hoặc có byte thừa bị từ chối', () => {
  const input = fixture();
  const compressed = deflateSync(input.scanlines, { level: 0 });
  const corrupt = Buffer.from(compressed);
  corrupt[corrupt.length - 1] ^= 0xff;
  assert.throws(() => decodeScreenshotPng(encode(input, corrupt)), /zlib/);
  assert.throws(() => decodeScreenshotPng(encode(input, Buffer.concat([compressed, Buffer.from([0])]))), /zlib/);
});

test('Signature, CRC, chunk cắt cụt hoặc thiếu IDAT/IEND đều bị từ chối', () => {
  const input = fixture();
  const png = encode(input);
  assert.throws(() => decodeScreenshotPng(Buffer.from('not png')), /signature/);
  assert.throws(() => decodeScreenshotPng(png.subarray(0, 10)), /chunk/);
  assert.throws(() => decodeScreenshotPng(png.subarray(0, -1)), /thiếu header\/CRC/);
  assert.throws(() => decodeScreenshotPng(png.subarray(0, -20)), /cắt cụt/);
  assert.throws(() => decodeScreenshotPng(png.subarray(0, -12)), /thiếu.*IEND/);
  assert.throws(() => decodeScreenshotPng(Buffer.concat([SIGNATURE, chunk('IHDR', input.header), chunk('IEND', Buffer.alloc(0))])), /thiếu.*IDAT/);
  const corrupt = Buffer.from(png);
  corrupt[29] ^= 0xff;
  assert.throws(() => decodeScreenshotPng(corrupt), /CRC/);
  assert.throws(() => decodeScreenshotPng(Buffer.concat([png, Buffer.from([0])])), /dữ liệu thừa/);
});

test('Filter, bit depth, color type và interlace ngoài phạm vi báo lỗi rõ', () => {
  const input = fixture();
  const badFilter = Buffer.from(input.scanlines);
  badFilter[0] = 5;
  assert.throws(() => decodeScreenshotPng(encode({ ...input, scanlines: badFilter })), /filter chưa hỗ trợ: 5/);
  for (const [offset, value, error] of [[8, 16, /8-bit RGB\/RGBA/], [9, 0, /8-bit RGB\/RGBA/], [9, 3, /8-bit RGB\/RGBA/], [12, 1, /không interlace/]]) {
    const header = Buffer.from(input.header);
    header[offset] = value;
    assert.throws(() => decodeScreenshotPng(encode({ ...input, header })), error);
  }
});

test('Kích thước vô nghĩa, quá lớn và RGB tRNS không được hỗ trợ', () => {
  const input = fixture();
  for (const width of [0, 0xffffffff]) {
    const header = Buffer.from(input.header);
    header.writeUInt32BE(width, 0);
    assert.throws(() => decodeScreenshotPng(encode({ ...input, header })), /Kích thước PNG/);
  }
  const png = encode(input);
  const trns = Buffer.concat([png.subarray(0, 33), chunk('tRNS', Buffer.alloc(6)), png.subarray(33)]);
  assert.throws(() => decodeScreenshotPng(trns), /tRNS/);
});

test('Ảnh quá nhỏ bị từ chối trước bước kiểm tra nội dung', () => {
  const file = path.join(TEMP_DIR, 'too-small.png');
  fs.writeFileSync(file, SIGNATURE);
  assert.throws(() => validateScreenshot(file), /kích thước quá nhỏ/);
});

const screenshotDir = fileURLToPath(new URL('../docs/screenshots/', import.meta.url));
const browserScreenshots = [
  '01_e2e_init_page_desktop.png',
  '02_e2e_translate_vi_tay.png',
  '03_e2e_swap_safe.png',
  '04_e2e_translate_tay_vi.png',
  '05_e2e_voice_tab_c21_disabled.png',
  '06_e2e_voice_recorder_auto_stop_and_asr.png',
  '07_e2e_voice_upload_and_translate_result.png',
  '08_e2e_mobile_text_layout.png',
  '09_e2e_mobile_voice_controls_scrolled.png',
];
for (const name of browserScreenshots) {
  test(`Ảnh browser hiện hành hợp lệ: ${name} (không thay thế kiểm tra trực quan)`, () => {
    const meta = validateScreenshot(path.join(screenshotDir, name));
    assert.ok(meta.colorsCount >= 20);
    assert.ok(meta.size >= 5000);
    assert.ok(meta.width > 0 && meta.height > 0);
    if (name.startsWith('08_') || name.startsWith('09_')) {
      assert.equal(meta.width, 390);
      assert.equal(meta.height, 844);
    }
  });
}
