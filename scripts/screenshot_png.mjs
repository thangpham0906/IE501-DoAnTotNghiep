/**
 * Kiểm chứng PNG screenshot, không phải decoder PNG tổng quát.
 * Chỉ hỗ trợ 8-bit RGB / RGBA hoàn toàn đục, không interlace, filters 0–4.
 * Chạy hồi quy độc lập: node --test scripts/screenshot_png.test.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { inflateSync } from 'node:zlib';

const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const MAX_SCANLINE_BYTES = 64 * 1024 * 1024;
const CRC_TABLE = Uint32Array.from({ length: 256 }, (_, value) => {
  let crc = value;
  for (let bit = 0; bit < 8; bit++) {
    crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return crc >>> 0;
});

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function paeth(left, up, upperLeft) {
  const prediction = left + up - upperLeft;
  const a = Math.abs(prediction - left);
  const b = Math.abs(prediction - up);
  const c = Math.abs(prediction - upperLeft);
  return a <= b && a <= c ? left : b <= c ? up : upperLeft;
}

export function decodeScreenshotPng(buf) {
  if (!Buffer.isBuffer(buf) || !buf.subarray(0, 8).equals(PNG_SIGNATURE)) {
    throw new Error('Tệp không phải PNG hợp lệ (signature)');
  }
  let header = null;
  let ended = false;
  let idatEnded = false;
  const idatChunks = [];
  for (let offset = 8; offset < buf.length;) {
    if (buf.length - offset < 12) throw new Error('PNG thiếu header/CRC của chunk');
    const length = buf.readUInt32BE(offset);
    const end = offset + 12 + length;
    if (end > buf.length) throw new Error('PNG chunk bị cắt cụt');
    const type = buf.toString('ascii', offset + 4, offset + 8);
    if (crc32(buf.subarray(offset + 4, end - 4)) !== buf.readUInt32BE(end - 4)) {
      throw new Error(`PNG chunk ${type} sai CRC`);
    }
    const data = buf.subarray(offset + 8, end - 4);
    if (!header && type !== 'IHDR') throw new Error('PNG phải bắt đầu bằng IHDR');
    if (type === 'IHDR') {
      if (header || length !== 13) throw new Error('PNG IHDR trùng hoặc sai độ dài');
      const width = data.readUInt32BE(0);
      const height = data.readUInt32BE(4);
      const bitDepth = data[8];
      const colorType = data[9];
      if (bitDepth !== 8 || ![2, 6].includes(colorType)) {
        throw new Error('Chỉ hỗ trợ PNG 8-bit RGB/RGBA (colorType 2/6)');
      }
      if (data[10] !== 0 || data[11] !== 0 || data[12] !== 0) {
        throw new Error('Chỉ hỗ trợ PNG không interlace, compression/filter method 0');
      }
      const channels = colorType === 6 ? 4 : 3;
      const rowBytes = width * channels;
      const scanlineBytes = (rowBytes + 1) * height;
      if (!width || !height || !Number.isSafeInteger(scanlineBytes) || scanlineBytes > MAX_SCANLINE_BYTES) {
        throw new Error('Kích thước PNG không hợp lệ hoặc vượt giới hạn scanline 64 MiB');
      }
      header = { width, height, channels, rowBytes, scanlineBytes };
    } else if (type === 'IDAT') {
      if (idatEnded) throw new Error('PNG IDAT không liên tiếp');
      idatChunks.push(data);
    } else if (type === 'IEND') {
      if (length !== 0 || end !== buf.length) throw new Error('PNG IEND sai độ dài hoặc có dữ liệu thừa');
      ended = true;
      break;
    } else {
      if (type === 'tRNS') throw new Error('Không hỗ trợ PNG trong suốt (tRNS)');
      if ((buf[offset + 4] & 0x20) === 0) throw new Error(`PNG critical chunk chưa hỗ trợ: ${type}`);
      if (idatChunks.length) idatEnded = true;
    }
    offset = end;
  }
  if (!header || !idatChunks.length || !ended) throw new Error('PNG thiếu IHDR, IDAT hoặc IEND');

  const compressed = Buffer.concat(idatChunks);
  let inflated;
  try {
    inflated = inflateSync(compressed, { maxOutputLength: header.scanlineBytes, info: true });
  } catch (err) {
    throw new Error(`PNG zlib/payload scanline không hợp lệ: ${err.message}`);
  }
  const scanlines = inflated.buffer;
  if (scanlines.length !== header.scanlineBytes || inflated.engine.bytesWritten !== compressed.length) {
    throw new Error(`PNG sai độ dài payload scanline/zlib (cần ${header.scanlineBytes}, có ${scanlines.length} byte scanline)`);
  }

  const { width, height, channels, rowBytes } = header;
  const pixels = Buffer.alloc(rowBytes * height);
  let src = 0;
  let dst = 0;
  for (let y = 0; y < height; y++) {
    const filter = scanlines[src++];
    if (filter > 4) throw new Error(`PNG scanline filter chưa hỗ trợ: ${filter}`);
    for (let x = 0; x < rowBytes; x++, dst++) {
      const left = x >= channels ? pixels[dst - channels] : 0;
      const up = y > 0 ? pixels[dst - rowBytes] : 0;
      const upperLeft = y > 0 && x >= channels ? pixels[dst - rowBytes - channels] : 0;
      let predictor = 0;
      if (filter === 1) predictor = left;
      else if (filter === 2) predictor = up;
      else if (filter === 3) predictor = Math.floor((left + up) / 2);
      else if (filter === 4) predictor = paeth(left, up, upperLeft);
      pixels[dst] = (scanlines[src++] + predictor) & 0xff;
    }
  }
  // Không đếm RGB ẩn dưới alpha như nội dung nhìn thấy; screenshot phải đục hoàn toàn.
  if (channels === 4) {
    for (let i = 3; i < pixels.length; i += 4) {
      if (pixels[i] !== 255) throw new Error('Chỉ hỗ trợ RGBA hoàn toàn đục (alpha=255), không hỗ trợ alpha trong suốt/bán trong suốt');
    }
  }
  return { width, height, channels, pixels };
}

/** Kiểm tra rỗng là heuristic trên pixel đã giải mã, không thay thế mở ảnh đối chiếu UI. */
export function validateScreenshot(filePath, minBytes = 5000) {
  const buf = fs.readFileSync(filePath);
  if (buf.length < minBytes) {
    throw new Error(`Ảnh ${path.basename(filePath)} có kích thước quá nhỏ (${buf.length} bytes < ${minBytes} bytes)`);
  }
  const { width, height, channels, pixels } = decodeScreenshotPng(buf);
  const colors = new Set();
  for (let y = 0; y < height; y += 4) {
    for (let x = 0; x < width; x += 4) {
      const idx = (y * width + x) * channels;
      colors.add((pixels[idx] << 16) | (pixels[idx + 1] << 8) | pixels[idx + 2]);
    }
  }
  if (colors.size < 20) {
    throw new Error(`Ảnh ${path.basename(filePath)} chỉ có ${colors.size} màu pixel lấy mẫu, nghi vấn ảnh rỗng/đơn sắc`);
  }
  return { width, height, size: buf.length, colorsCount: colors.size };
}
