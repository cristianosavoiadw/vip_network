/**
 * Minimal QR Code encoder (byte mode, error correction level M, versions 1–10), enough for
 * check-in tokens. Follows ISO/IEC 18004 (same structure as Nayuki's reference implementation).
 * No runtime dependency and no external service: the token never leaves the browser.
 */

const ECC_PER_BLOCK_M = [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26];
const BLOCKS_M = [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5];
const FORMAT_M = 0; // L=1, M=0, Q=3, H=2

function rawModules(ver: number): number {
  let r = (16 * ver + 128) * ver + 64;
  if (ver >= 2) {
    const n = Math.floor(ver / 7) + 2;
    r -= (25 * n - 10) * n - 55;
    if (ver >= 7) r -= 36;
  }
  return r;
}

function dataCodewords(ver: number): number {
  return Math.floor(rawModules(ver) / 8) - ECC_PER_BLOCK_M[ver] * BLOCKS_M[ver];
}

function gfMul(x: number, y: number): number {
  let z = 0;
  for (let i = 7; i >= 0; i--) {
    z = (z << 1) ^ ((z >>> 7) * 0x11d);
    z ^= ((y >>> i) & 1) * x;
  }
  return z;
}

function rsDivisor(degree: number): number[] {
  const out: number[] = new Array(degree - 1).fill(0);
  out.push(1);
  let root = 1;
  for (let i = 0; i < degree; i++) {
    for (let j = 0; j < out.length; j++) {
      out[j] = gfMul(out[j], root);
      if (j + 1 < out.length) out[j] ^= out[j + 1];
    }
    root = gfMul(root, 0x02);
  }
  return out;
}

function rsRemainder(data: number[], divisor: number[]): number[] {
  const out = divisor.map(() => 0);
  for (const b of data) {
    const factor = b ^ (out.shift() as number);
    out.push(0);
    divisor.forEach((coef, i) => (out[i] ^= gfMul(coef, factor)));
  }
  return out;
}

function interleave(ver: number, data: number[]): number[] {
  const numBlocks = BLOCKS_M[ver];
  const eccLen = ECC_PER_BLOCK_M[ver];
  const raw = Math.floor(rawModules(ver) / 8);
  const numShort = numBlocks - (raw % numBlocks);
  const shortLen = Math.floor(raw / numBlocks);
  const div = rsDivisor(eccLen);
  const blocks: number[][] = [];
  for (let i = 0, k = 0; i < numBlocks; i++) {
    const dat = data.slice(k, k + shortLen - eccLen + (i < numShort ? 0 : 1));
    k += dat.length;
    const ecc = rsRemainder(dat, div);
    if (i < numShort) dat.push(0);
    blocks.push(dat.concat(ecc));
  }
  const out: number[] = [];
  for (let i = 0; i < blocks[0].length; i++) {
    blocks.forEach((block, j) => {
      if (i !== shortLen - eccLen || j >= numShort) out.push(block[i]);
    });
  }
  return out;
}

function alignPositions(ver: number, size: number): number[] {
  if (ver === 1) return [];
  const n = Math.floor(ver / 7) + 2;
  const step = Math.ceil((ver * 4 + 4) / (n * 2 - 2)) * 2;
  const out = [6];
  for (let pos = size - 7; out.length < n; pos -= step) out.splice(1, 0, pos);
  return out;
}

const bit = (x: number, i: number) => ((x >>> i) & 1) !== 0;

/** QR modules (true = dark), row by row, without quiet zone. */
export function qrMatrix(text: string, forceMask?: number): boolean[][] {
  const bytes = Array.from(new TextEncoder().encode(text));
  let ver = 1;
  while (ver <= 10 && 4 + (ver < 10 ? 8 : 16) + bytes.length * 8 > dataCodewords(ver) * 8) ver++;
  if (ver > 10) throw new Error("QR payload too long");

  const bits: number[] = [];
  const push = (val: number, len: number) => {
    for (let i = len - 1; i >= 0; i--) bits.push((val >>> i) & 1);
  };
  push(0b0100, 4);
  push(bytes.length, ver < 10 ? 8 : 16);
  bytes.forEach((b) => push(b, 8));
  const capBits = dataCodewords(ver) * 8;
  push(0, Math.min(4, capBits - bits.length));
  push(0, (8 - (bits.length % 8)) % 8);
  for (let pad = 0xec; bits.length < capBits; pad ^= 0xec ^ 0x11) push(pad, 8);
  const codewords: number[] = [];
  for (let i = 0; i < bits.length; i += 8) codewords.push(parseInt(bits.slice(i, i + 8).join(""), 2));
  const all = interleave(ver, codewords);

  const size = ver * 4 + 17;
  const m: boolean[][] = Array.from({ length: size }, () => new Array<boolean>(size).fill(false));
  const fn: boolean[][] = Array.from({ length: size }, () => new Array<boolean>(size).fill(false));
  const setF = (x: number, y: number, dark: boolean) => {
    m[y][x] = dark;
    fn[y][x] = true;
  };

  for (let i = 0; i < size; i++) {
    setF(6, i, i % 2 === 0);
    setF(i, 6, i % 2 === 0);
  }
  for (const [cx, cy] of [[3, 3], [size - 4, 3], [3, size - 4]]) {
    for (let dy = -4; dy <= 4; dy++) {
      for (let dx = -4; dx <= 4; dx++) {
        const d = Math.max(Math.abs(dx), Math.abs(dy));
        const x = cx + dx;
        const y = cy + dy;
        if (x >= 0 && x < size && y >= 0 && y < size) setF(x, y, d !== 2 && d !== 4);
      }
    }
  }
  const al = alignPositions(ver, size);
  for (let i = 0; i < al.length; i++) {
    for (let j = 0; j < al.length; j++) {
      if ((i === 0 && j === 0) || (i === 0 && j === al.length - 1) || (i === al.length - 1 && j === 0)) continue;
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) setF(al[i] + dx, al[j] + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }
  }
  const drawFormat = (mask: number) => {
    const data = (FORMAT_M << 3) | mask;
    let rem = data;
    for (let i = 0; i < 10; i++) rem = (rem << 1) ^ ((rem >>> 9) * 0x537);
    const b = ((data << 10) | rem) ^ 0x5412;
    for (let i = 0; i <= 5; i++) setF(8, i, bit(b, i));
    setF(8, 7, bit(b, 6));
    setF(8, 8, bit(b, 7));
    setF(7, 8, bit(b, 8));
    for (let i = 9; i < 15; i++) setF(14 - i, 8, bit(b, i));
    for (let i = 0; i < 8; i++) setF(size - 1 - i, 8, bit(b, i));
    for (let i = 8; i < 15; i++) setF(8, size - 15 + i, bit(b, i));
    setF(8, size - 8, true);
  };
  drawFormat(0);
  if (ver >= 7) {
    let rem = ver;
    for (let i = 0; i < 12; i++) rem = (rem << 1) ^ ((rem >>> 11) * 0x1f25);
    const b = (ver << 12) | rem;
    for (let i = 0; i < 18; i++) {
      const a = size - 11 + (i % 3);
      const c = Math.floor(i / 3);
      setF(a, c, bit(b, i));
      setF(c, a, bit(b, i));
    }
  }

  let k = 0;
  for (let right = size - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    for (let vert = 0; vert < size; vert++) {
      for (let j = 0; j < 2; j++) {
        const x = right - j;
        const up = ((right + 1) & 2) === 0;
        const y = up ? size - 1 - vert : vert;
        if (!fn[y][x] && k < all.length * 8) {
          m[y][x] = bit(all[k >>> 3], 7 - (k & 7));
          k++;
        }
      }
    }
  }

  const masked = (mask: number, x: number, y: number): boolean => {
    switch (mask) {
      case 0: return (x + y) % 2 === 0;
      case 1: return y % 2 === 0;
      case 2: return x % 3 === 0;
      case 3: return (x + y) % 3 === 0;
      case 4: return (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0;
      case 5: return ((x * y) % 2) + ((x * y) % 3) === 0;
      case 6: return (((x * y) % 2) + ((x * y) % 3)) % 2 === 0;
      default: return (((x + y) % 2) + ((x * y) % 3)) % 2 === 0;
    }
  };
  const apply = (mask: number) => {
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) if (!fn[y][x] && masked(mask, x, y)) m[y][x] = !m[y][x];
  };
  // simplified penalty (runs, 2x2 blocks, balance): any mask is valid, this only helps scanners
  const penalty = (): number => {
    let p = 0;
    let dark = 0;
    for (let a = 0; a < size; a++) {
      let runR = 1;
      let runC = 1;
      for (let b = 0; b < size; b++) {
        if (m[a][b]) dark++;
        if (b > 0) {
          runR = m[a][b] === m[a][b - 1] ? runR + 1 : 1;
          runC = m[b][a] === m[b - 1][a] ? runC + 1 : 1;
          if (runR === 5) p += 3;
          else if (runR > 5) p += 1;
          if (runC === 5) p += 3;
          else if (runC > 5) p += 1;
        }
        if (a > 0 && b > 0 && m[a][b] === m[a - 1][b] && m[a][b] === m[a][b - 1] && m[a][b] === m[a - 1][b - 1]) p += 3;
      }
    }
    const total = size * size;
    p += (Math.ceil(Math.abs(dark * 20 - total * 10) / total) - 1) * 10;
    return p;
  };
  let best = forceMask ?? 0;
  let min = Infinity;
  for (let mask = 0; mask < 8 && forceMask === undefined; mask++) {
    apply(mask);
    drawFormat(mask);
    const p = penalty();
    if (p < min) {
      min = p;
      best = mask;
    }
    apply(mask);
  }
  apply(best);
  drawFormat(best);
  return m;
}

/** QR Code as an inline SVG (white background, 4-module quiet zone). */
export function QrCode({ value, size = 112, label = "QR Code de check-in" }: { value: string; size?: number; label?: string }) {
  let matrix: boolean[][];
  try {
    matrix = qrMatrix(value);
  } catch {
    return null;
  }
  const n = matrix.length + 8;
  let d = "";
  matrix.forEach((row, y) => row.forEach((on, x) => on && (d += `M${x + 4} ${y + 4}h1v1h-1z`)));
  return (
    <svg role="img" aria-label={label} viewBox={`0 0 ${n} ${n}`} width={size} height={size} shapeRendering="crispEdges" className="flex-none rounded-lg border border-line bg-white">
      <rect width={n} height={n} fill="#fff" />
      <path d={d} fill="#0E1930" />
    </svg>
  );
}
