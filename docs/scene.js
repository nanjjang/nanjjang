/* ───────────────────────────────────────────────────────────────────────────
   nanjjang · 3D particle universe
   One scene, two uses:
     • live   → docs/index.html          (interactive, real-time)
     • render → scripts/capture_hero.py  (?capture=1, deterministic frames → assets/hero.webp)
   Every animated value is a pure function of time `t`, so frames are reproducible
   and the hero loop (authored as 9 s, shipped re-timed to 8 s) is seamless: it starts and ends on the title card.
   ─────────────────────────────────────────────────────────────────────────── */
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

const Q = new URLSearchParams(location.search);
const CAPTURE = Q.has('capture');
const DEPS = window.__DEPS;
const T_LOOP = 9.0;
const TITLE = (Q.get('text') || 'NANJJANG').toUpperCase().slice(0, 14);
const SUBTITLE = Q.get('sub') || 'BACKEND  ·  WEB  ·  APP  ·  GAME';
const REF_H = 480; // sprite sizes are authored for a 480px tall frame
const REF_DIST = 36;
const FOV = 28;

/* look-dev knobs — override from the URL, e.g. ?expo=0.8&thr=0.9 */
const TUNE = {
  expo: 1.0,    // tone-mapping exposure multiplier
  bloom: 1.0,   // bloom strength multiplier
  thr: 1.0,     // bloom threshold multiplier (HDR)
  rad: 0.4,     // bloom radius
  neb: 0.014,   // nebula backdrop level
  brA: 0.45,    // galaxy brightness
  brB: 0.6,     // title/ring/dust brightness
  glow: 0.25,   // extra energy while particles are in flight
  swirl: 1.6,   // vortex strength during morphs
  dof: 45,      // depth-of-field range (bigger = sharper overall)
  ca: 0.0016,   // chromatic aberration
  vig: 0.5,     // vignette
  szA: 1.0,     // sprite size multiplier (galaxy)
  szB: 1.0,     // sprite size multiplier (title)
  tm: 0,        // tone mapping: 0 ACES, 1 AgX, 2 Neutral, 3 Reinhard, 4 Cineon
  dust: 1.0,    // ambient dust brightness (0 hides it)
  stars: 1.0,   // starfield density (0..1)
  grain: 1.0,   // film-grain / dither amount
  black: 0.03,  // black-point crush (0 = off)
  tshare: 0.70, // share of particles used by the title
  loop: 9.0,    // loop length in seconds (the authored 9 s timeline is re-timed to this)
};
for (const [k, v] of Q) if (k in TUNE && v !== '' && !Number.isNaN(Number(v))) TUNE[k] = Number(v);

/* ───────────────────────────── helpers ───────────────────────────── */
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const gauss = (r) => {
  let u = 0;
  while (u === 0) u = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
};
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const smooth = (x) => x * x * (3 - 2 * x);
const C = (hex) => new THREE.Color(hex);

function ramp(stops, t, out) {
  t = clamp(t);
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (t <= t1) return out.copy(c0).lerp(c1, (t - t0) / (t1 - t0));
  }
  return out.copy(stops[stops.length - 1][1]);
}

/* periodic cubic-Hermite track: [[t, value], …] with keys[0][0] === 0 */
function track(keys, t) {
  const n = keys.length;
  const K = (i) => {
    const k = ((i % n) + n) % n;
    return [keys[k][0] + Math.floor(i / n) * T_LOOP, keys[k][1]];
  };
  let i = 0;
  while (K(i + 1)[0] <= t) i++;
  const [t0, v0] = K(i);
  const [t1, v1] = K(i + 1);
  const [tm, vm] = K(i - 1);
  const [tp, vp] = K(i + 2);
  const h = t1 - t0;
  const s = (t - t0) / h;
  const m0 = ((v1 - vm) / (t1 - tm)) * h;
  const m1 = ((vp - v0) / (tp - t0)) * h;
  const s2 = s * s;
  const s3 = s2 * s;
  return (2 * s3 - 3 * s2 + 1) * v0 + (s3 - 2 * s2 + s) * m0 + (-2 * s3 + 3 * s2) * v1 + (s3 - s2) * m1;
}

/* ───────────────────────── shape A : spiral galaxy ───────────────────────── */
function buildGalaxy(N, rng) {
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const size = new Float32Array(N);
  const R = 15;
  const ARMS = 3;
  const TWIST = 2.2;
  const armAngle = (rr, k) => k * ((Math.PI * 2) / ARMS) + TWIST * Math.log(1 + rr / 1.3);
  // body colour by radius: warm nucleus → violet → indigo → blue → cyan rim
  const stops = [
    [0.0, C('#fff0d0')],
    [0.05, C('#ffb870')],
    [0.15, C('#e08cff')],
    [0.34, C('#8a7bff')],
    [0.6, C('#3f9fff')],
    [1.0, C('#2fe4ff')],
  ];
  const knot = [C('#ff5fb0'), C('#ff8ad0'), C('#6fe6ff'), C('#ffffff'), C('#ffd27a')];
  // star-forming clumps strung along the arms
  const clumps = [];
  for (let c = 0; c < 320; c++) {
    const rr = 1.6 + Math.pow(rng(), 0.85) * (R - 2.2);
    const th = armAngle(rr, (rng() * ARMS) | 0) + gauss(rng) * 0.09;
    clumps.push({ x: rr * Math.cos(th), y: rr * Math.sin(th), z: gauss(rng) * 0.15, k: knot[(rng() * knot.length) | 0] });
  }
  const tmp = new THREE.Color();
  for (let i = 0; i < N; i++) {
    const u = rng();
    let x, y, z, t, b, s;
    if (u < 0.015) {
      // glowing nucleus
      x = gauss(rng) * 0.32; y = gauss(rng) * 0.32; z = gauss(rng) * 0.26;
      t = 0; b = 1.4 + rng() * 1.2; s = 1.4 + rng() * 1.0;
    } else if (u < 0.09) {
      // bulge
      x = gauss(rng) * 1.45; y = gauss(rng) * 1.45; z = gauss(rng) * 0.95;
      t = Math.hypot(x, y) / R * 1.2; b = 0.42 + rng() * 0.5; s = 1.4 + rng() * 1.1;
    } else if (u < 0.21) {
      // star-forming clump
      const k = clumps[(rng() * clumps.length) | 0];
      x = k.x + gauss(rng) * 0.42; y = k.y + gauss(rng) * 0.42; z = k.z + gauss(rng) * 0.2;
      t = Math.hypot(x, y) / R; b = (0.9 + rng() * 1.5) * (1 - 0.9 * smooth(clamp((t - 0.62) / 0.38))); s = 1.3 + rng() * 1.3;
      ramp(stops, t, tmp).lerp(k.k, 0.7);
      pos.set([x, y, z], i * 3);
      col.set([tmp.r * b, tmp.g * b, tmp.b * b], i * 3);
      size[i] = s;
      continue;
    } else if (u < 0.92) {
      // disk with tight spiral arms
      const rr = -Math.log(1 - rng() * (1 - Math.exp(-R / 3.8))) * 3.8;
      t = rr / R;
      const inArm = rng() < 0.88;
      const th = inArm ? armAngle(rr, (rng() * ARMS) | 0) + gauss(rng) * (0.07 + 0.2 * t) : rng() * Math.PI * 2;
      x = rr * Math.cos(th);
      y = rr * Math.sin(th);
      z = gauss(rng) * (0.08 + 0.5 * Math.exp(-rr / 1.8)) + 0.9 * t * t * Math.sin(th - 0.6);
      b = ((inArm ? 0.62 : 0.3) + rng() * 0.5) * (0.35 + 0.65 * smooth(clamp(t / 0.35))) * (1 - 0.92 * smooth(clamp((t - 0.62) / 0.38)));
      s = 1.3 + rng() * 1.1;
    } else {
      // faint halo
      x = gauss(rng) * 7; y = gauss(rng) * 7; z = gauss(rng) * 5;
      t = 0.7 + rng() * 0.3; b = 0.14 + rng() * 0.2; s = 1.3 + rng();
    }
    ramp(stops, t, tmp);
    if (rng() < 0.02) { b *= 3 + rng() * 2.5; s *= 1.6; tmp.lerp(C('#ffffff'), 0.5); }
    pos.set([x, y, z], i * 3);
    col.set([tmp.r * b, tmp.g * b, tmp.b * b], i * 3);
    size[i] = s;
  }
  return { pos, col, size };
}

/* ───────────────────────── shape B : title, subtitle, ring, dust ───────────────────────── */
async function loadFont(family, url, weight) {
  try {
    const ff = new FontFace(family, `url(${url}) format('woff2')`, { weight: String(weight) });
    await ff.load();
    document.fonts.add(ff);
  } catch (err) {
    console.warn(`font ${family} failed to load, using a system fallback`, err);
  }
}

function rasterText(text, font, px) {
  const probe = document.createElement('canvas').getContext('2d');
  probe.font = font;
  const W = Math.ceil(probe.measureText(text).width) + 80;
  const H = Math.ceil(px * 1.6);
  const cv = document.createElement('canvas');
  cv.width = W;
  cv.height = H;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  ctx.font = font;
  ctx.fillStyle = '#fff';
  ctx.textBaseline = 'alphabetic';
  ctx.fillText(text, 40, Math.round(H * 0.72));
  const d = ctx.getImageData(0, 0, W, H).data;
  const mask = new Uint8Array(W * H);
  let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
  for (let i = 0; i < W * H; i++) {
    if (d[i * 4 + 3] > 127) {
      mask[i] = 1;
      const x = i % W;
      const y = (i / W) | 0;
      if (x < x0) x0 = x;
      if (x > x1) x1 = x;
      if (y < y0) y0 = y;
      if (y > y1) y1 = y;
    }
  }
  return { mask, W, H, x0, y0, x1, y1 };
}

/* pick `n` points from a raster mask: a jittered grid fills the glyph evenly (no clumps/holes),
   and `edgeFrac` of the budget hugs the outline so letterforms stay crisp */
function sampleMask(m, n, edgeFrac, rng) {
  const { mask, W, H } = m;
  const edge = [];
  const lit = [];
  for (let y = 1; y < H - 1; y++) {
    for (let x = 1; x < W - 1; x++) {
      const i = y * W + x;
      if (!mask[i]) continue;
      lit.push(i);
      if (!mask[i - 1] || !mask[i + 1] || !mask[i - W] || !mask[i + W]) edge.push(i);
    }
  }
  const nEdge = Math.round(n * edgeFrac);
  const nIn = n - nEdge;
  const cell = Math.sqrt(lit.length / nIn);
  const pts = [];
  for (let y0 = m.y0; y0 <= m.y1; y0 += cell) {
    for (let x0 = m.x0; x0 <= m.x1; x0 += cell) {
      const x = x0 + rng() * cell;
      const y = y0 + rng() * cell;
      if (mask[(y | 0) * W + (x | 0)]) pts.push(x, y);
    }
  }
  while (pts.length / 2 > nIn) {            // too many → drop random ones
    const k = ((rng() * pts.length) / 2) | 0;
    pts[k * 2] = pts[pts.length - 2];
    pts[k * 2 + 1] = pts[pts.length - 1];
    pts.length -= 2;
  }
  while (pts.length / 2 < nIn) {            // too few → top up from random lit pixels
    const i = lit[(rng() * lit.length) | 0];
    pts.push((i % W) + rng(), ((i / W) | 0) + rng());
  }
  for (let k = 0; k < nEdge; k++) {
    const i = edge[(rng() * edge.length) | 0];
    pts.push((i % W) + rng(), ((i / W) | 0) + rng());
  }
  const out = new Float32Array(n * 2);
  const cx = (m.x0 + m.x1) / 2;
  const cy = (m.y0 + m.y1) / 2;
  for (let k = 0; k < n; k++) {
    out[k * 2] = pts[k * 2] - cx;
    out[k * 2 + 1] = -(pts[k * 2 + 1] - cy);
  }
  return { xy: out, width: m.x1 - m.x0, height: m.y1 - m.y0 };
}

async function buildTargets(N, rng) {
  await Promise.all([
    loadFont('Unbounded', `${DEPS.fonts.unbounded}unbounded-latin-800-normal.woff2`, 800),
    loadFont('JetBrains Mono', `${DEPS.fonts.jbmono}jetbrains-mono-latin-700-normal.woff2`, 700),
  ]);
  await document.fonts.load('800 300px Unbounded');
  await document.fonts.load('700 64px "JetBrains Mono"');

  const nTitle = Math.round(N * TUNE.tshare);
  const nSub = Math.round(N * 0.09);
  const nRing = Math.round(N * 0.1);
  const nRing2 = Math.round(N * 0.07);
  const nDust = N - nTitle - nSub - nRing - nRing2;

  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const size = new Float32Array(N);
  const kind = new Float32Array(N);
  const ringU = new Float32Array(N);
  const tmp = new THREE.Color();
  let o = 0;

  // — title —
  const TITLE_W = 33;
  const titleStops = [
    [0.0, C('#2aa8ff')],
    [0.5, C('#a070ff')],
    [1.0, C('#ff5fc8')],
  ];
  {
    const m = rasterText(TITLE, '800 300px Unbounded, "Arial Black", Impact, sans-serif', 300);
    const s = sampleMask(m, nTitle, 0.4, rng);
    const k = TITLE_W / s.width;
    for (let i = 0; i < nTitle; i++, o++) {
      const x = s.xy[i * 2] * k;
      const y = s.xy[i * 2 + 1] * k + 1.1;
      pos.set([x, y, (rng() - 0.5) * 0.7], o * 3);
      ramp(titleStops, x / TITLE_W + 0.5, tmp).lerp(C('#ffffff'), 0.12);
      const b = 1.2 + rng() * 1.0;
      col.set([tmp.r * b, tmp.g * b, tmp.b * b], o * 3);
      size[o] = 1.25 + rng() * 0.7;
      kind[o] = 0;
    }
  }
  // — subtitle —
  {
    const m = rasterText(SUBTITLE, '700 64px "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace', 64);
    const s = sampleMask(m, nSub, 0.5, rng);
    const SUB_W = Math.min(21, 0.62 * SUBTITLE.length);
    const k = SUB_W / s.width;
    for (let i = 0; i < nSub; i++, o++) {
      pos.set([s.xy[i * 2] * k, s.xy[i * 2 + 1] * k - 2.6, (rng() - 0.5) * 0.3], o * 3);
      tmp.set('#b6e2ff');
      const b = 1.25 + rng() * 0.8;
      col.set([tmp.r * b, tmp.g * b, tmp.b * b], o * 3);
      size[o] = 1.15 + rng() * 0.5;
      kind[o] = 1;
    }
  }
  // — orbit ring (local coords; tilted in the shader) —
  for (let i = 0; i < nRing; i++, o++) {
    const u = rng();
    const r = 17.5 + gauss(rng) * 0.22;
    pos.set([r * Math.cos(u * Math.PI * 2), r * Math.sin(u * Math.PI * 2), gauss(rng) * 0.08], o * 3);
    ringU[o] = u;
    tmp.set('#7fe9ff').lerp(C('#c9a8ff'), rng() * 0.5);
    const b = 0.55 + rng() * 0.5;
    col.set([tmp.r * b, tmp.g * b, tmp.b * b], o * 3);
    size[o] = 1.3 + rng() * 1.3;
    kind[o] = 2;
  }
  // — counter-rotating inner ring —
  for (let i = 0; i < nRing2; i++, o++) {
    const u = rng();
    const r = 12.6 + gauss(rng) * 0.16;
    pos.set([r * Math.cos(u * Math.PI * 2), r * Math.sin(u * Math.PI * 2), gauss(rng) * 0.06], o * 3);
    ringU[o] = u;
    tmp.set('#ff8fe0').lerp(C('#a98bff'), rng() * 0.7);
    const b = 0.42 + rng() * 0.4;
    col.set([tmp.r * b, tmp.g * b, tmp.b * b], o * 3);
    size[o] = 1.2 + rng() * 1.1;
    kind[o] = 4;
  }
  // — ambient dust —
  for (let i = 0; i < nDust; i++, o++) {
    pos.set([(rng() - 0.5) * 46, (rng() - 0.5) * 17, (rng() - 0.5) * 26], o * 3);
    tmp.set('#6f8dff').lerp(C('#ffffff'), rng() * 0.4);
    const b = (0.18 + rng() * 0.5) * TUNE.dust;
    col.set([tmp.r * b, tmp.g * b, tmp.b * b], o * 3);
    size[o] = 1.1 + rng() * 1.6;
    kind[o] = 3;
  }
  return { pos, col, size, kind, ringU };
}

/* ───────────────────────────── shaders ───────────────────────────── */
const PARTICLE_VERT = /* glsl */ `
  attribute vec3 aA;
  attribute vec3 aB;
  attribute vec3 aColA;
  attribute vec3 aColB;
  attribute vec4 aR;
  attribute vec3 aMisc;   // x arrival delay, y size in A, z size in B
  attribute float aKind;  // B: 0 title, 1 subtitle, 2 ring A, 3 dust, 4 ring B

  uniform float uTime, uPhase, uMorph, uDir, uSpread, uSwirl, uArc, uTurb, uGlow;
  uniform mat3  uRotA, uRingRot, uRingRot2;
  uniform float uRingAng, uSizeScale, uRefDist, uFocus, uFocusRange, uBrA, uBrB;
  uniform float uSweepPos, uSweepInvW;
  uniform vec2  uSweepDir;
  uniform vec3  uMouse;
  uniform float uMouseR, uMouseF;
  uniform vec4  uPulse;

  varying vec3  vColor;
  varying float vCoc;
  varying float vStar;

  mat2 rot(float a){ float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
  vec3 flow(vec3 p, float t){
    return vec3(
      sin(p.y*1.7 + t*1.3) + sin(p.z*2.3 - t*0.7),
      sin(p.z*1.7 + t*1.1) + sin(p.x*2.1 + t*0.9),
      sin(p.x*1.7 + t*1.2) + sin(p.y*2.4 - t*0.8));
  }

  void main(){
    float delay = mix(aMisc.x, 1.0 - aMisc.x, uDir);

    // A · galaxy — differential rotation, then tilt
    vec3 pa = aA;
    float rr = length(pa.xy);
    pa.xy = rot(uTime * (0.22 + 0.75 / (1.0 + 0.8 * rr))) * pa.xy;
    pa = uRotA * pa;

    // B · title / subtitle / ring / dust
    vec3 pb = aB;
    float isRing  = step(1.5, aKind) * (1.0 - step(2.5, aKind));
    float isDust  = step(2.5, aKind) * (1.0 - step(3.5, aKind));
    float isRing2 = step(3.5, aKind);
    float ringHead = 1.0;
    if (isRing > 0.5) {
      pb.xy = rot(uRingAng) * pb.xy;
      pb = uRingRot * pb;
      float u = 6.2831853 * aR.w;                       // brightness is bound to the particle → the comet orbits with the ring
      float c = 0.5 + 0.5 * cos(u);
      float c2 = 0.5 + 0.5 * cos(2.0 * u + 2.1);
      ringHead = 0.22 + 1.9 * pow(c, 6.0) + 0.7 * pow(c2, 10.0);
    } else if (isRing2 > 0.5) {
      pb.xy = rot(-uRingAng) * pb.xy;                   // counter-rotating
      pb = uRingRot2 * pb;
      float u = 6.2831853 * aR.w;
      float c = 0.5 + 0.5 * cos(u + 1.3);
      ringHead = 0.2 + 2.2 * pow(c, 5.0);
    }
    float amp = isDust > 0.5 ? 0.22 : ((isRing + isRing2) > 0.5 ? 0.05 : 0.028);
    pb += amp * vec3(
      sin(2.0 * uPhase + 6.2831853 * aR.x),
      sin(3.0 * uPhase + 6.2831853 * aR.y),
      sin(2.0 * uPhase + 6.2831853 * aR.z));

    float sq = (dot(pb.xy, uSweepDir) - uSweepPos) * uSweepInvW;
    float sweep = exp(-sq * sq) * (1.0 - 0.75 * (isRing + isRing2 + isDust));

    // morph A → B along a swirling quadratic Bézier, staggered per particle
    float s = clamp((uMorph - delay * uSpread) / (1.0 - uSpread), 0.0, 1.0);
    float e = s * s * s * (s * (s * 6.0 - 15.0) + 10.0);
    vec3 d = pb - pa;
    vec3 rv = normalize((vec3(aR.y, aR.z, aR.w) - 0.5) * 2.0 + vec3(0.001));
    vec3 side = normalize(cross(d, rv) + vec3(0.0001));
    vec3 ctrl = 0.5 * (pa + pb) + side * length(d) * (0.12 + 0.55 * aR.x) * uArc;
    vec3 P = mix(mix(pa, ctrl, e), mix(ctrl, pb, e), e);
    float mid = sin(3.14159265 * e);
    P.xy = rot(uSwirl * mid * (0.55 + 0.9 * aR.z)) * P.xy;
    P += flow(P * 0.22, uTime * 0.55) * uTurb * mid;

    // pointer + click shockwave (live mode)
    vec3 dm = P - uMouse;
    float dl = length(dm);
    P += (dm / (dl + 0.001)) * uMouseF * exp(-(dl * dl) / (uMouseR * uMouseR));
    if (uPulse.w >= 0.0) {
      vec3 dp = P - uPulse.xyz;
      float dq = length(dp);
      float q = (dq - uPulse.w * 16.0) / 2.2;
      P += (dp / (dq + 0.001)) * exp(-q * q) * 3.2 * exp(-uPulse.w * 0.8);
    }

    vec4 mv = modelViewMatrix * vec4(P, 1.0);
    gl_Position = projectionMatrix * mv;
    float dist = -mv.z;

    float cm = smoothstep(0.25, 0.75, e);
    vec3 colB = aColB * ringHead;
    colB = mix(colB, vec3(1.7, 1.9, 2.2), clamp(sweep * 0.5, 0.0, 1.0)) * (1.0 + 0.8 * sweep);
    vec3 col = mix(aColA * uBrA, colB * uBrB, cm) * (1.0 + uGlow * mid);
    float tw = max(0.0, sin(3.0 * uPhase + 18.849556 * aR.x + 6.2831853 * aR.z));
    float flare = pow(tw, 20.0) * step(0.975, aR.y);
    col *= 1.0 + 2.2 * flare;
    vStar = flare;

    float coc = clamp(abs(dist - uFocus) / uFocusRange, 0.0, 1.0) * (1.0 - flare);
    float sz = mix(aMisc.y, aMisc.z, cm) * (1.0 + 0.3 * mid) * (1.0 + 3.4 * flare);
    gl_PointSize = sz * (uRefDist / dist) * uSizeScale * (1.0 + 3.2 * coc);
    vColor = col / (1.0 + 4.0 * coc * coc);
    vCoc = coc;
  }
`;

const PARTICLE_FRAG = /* glsl */ `
  varying vec3 vColor;
  varying float vCoc;
  varying float vStar;
  void main(){
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    float d2 = dot(p, p);
    if (d2 > 1.0) discard;
    float g = exp(-d2 * mix(5.0, 34.0, vStar));
    float disc = smoothstep(1.0, 0.55, d2);
    float a = mix(g, disc * 0.8 + 0.2 * g, vCoc);
    float spikes = exp(-abs(p.x) * 26.0 - abs(p.y) * 2.6) + exp(-abs(p.y) * 26.0 - abs(p.x) * 2.6);
    a += vStar * 0.9 * spikes * (1.0 - vCoc);
    gl_FragColor = vec4(vColor * a, 1.0);
  }
`;

const STAR_VERT = /* glsl */ `
  attribute vec3 aCol;
  attribute vec2 aSt;
  uniform float uPhase, uSizeScale;
  varying vec3 vC;
  void main(){
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    float f = floor(aSt.y * 5.0) + 1.0;
    float tw = 0.62 + 0.38 * sin(uPhase * f + aSt.y * 60.0);
    gl_PointSize = aSt.x * uSizeScale;
    vC = aCol * tw;
  }
`;
const STAR_FRAG = /* glsl */ `
  varying vec3 vC;
  void main(){
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    float d2 = dot(p, p);
    if (d2 > 1.0) discard;
    gl_FragColor = vec4(vC * exp(-d2 * 3.0), 1.0);
  }
`;

const NEBULA_VERT = /* glsl */ `
  varying vec2 vUv;
  void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.9999, 1.0); }
`;
const NEBULA_FRAG = /* glsl */ `
  uniform float uAspect, uLevel;
  uniform vec2 uOff;
  varying vec2 vUv;
  float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float n(vec2 p){
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(h(i), h(i + vec2(1.0, 0.0)), f.x), mix(h(i + vec2(0.0, 1.0)), h(i + vec2(1.0, 1.0)), f.x), f.y);
  }
  float fbm(vec2 p){
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++){ v += a * n(p); p = p * 2.03 + vec2(17.0, 9.0); a *= 0.5; }
    return v;
  }
  void main(){
    vec2 q = (vUv - 0.5) * vec2(uAspect, 1.0);
    vec2 p = q * 1.7 + uOff;
    float f1 = fbm(p * 1.1);
    float f2 = fbm(p * 2.3 + 11.0 + f1 * 1.5);
    float f3 = fbm(p * 0.8 + 40.0);
    vec3 c = vec3(0.10, 0.13, 0.50) * smoothstep(0.38, 0.88, f1);
    c += vec3(0.46, 0.10, 0.42) * smoothstep(0.48, 0.95, f2) * 0.75;
    c += vec3(0.04, 0.30, 0.46) * smoothstep(0.5, 0.9, f3) * 0.55;
    float vg = 1.0 - smoothstep(0.15, 1.15, length(q));
    c *= (0.2 + 0.8 * vg) * uLevel;
    c += vec3(0.0035, 0.005, 0.015);
    gl_FragColor = vec4(c, 1.0);
  }
`;

const FINAL_SHADER = {
  uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uCA: { value: 0.0016 }, uVig: { value: 0.5 }, uGrain: { value: 1.0 }, uShock: { value: 0 }, uShockR: { value: 0 }, uAspect: { value: 2.667 }, uBlack: { value: 0.03 } },
  vertexShader: /* glsl */ `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float uTime, uCA, uVig, uGrain, uShock, uShockR, uAspect, uBlack;
    varying vec2 vUv;
    float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
    void main(){
      vec2 c = vUv - 0.5;
      vec2 ca = c * vec2(uAspect, 1.0);
      float r2 = dot(ca, ca);
      vec2 off = c * uCA * (0.35 + r2 * 2.2);
      vec3 col = vec3(texture2D(tDiffuse, vUv + off).r, texture2D(tDiffuse, vUv).g, texture2D(tDiffuse, vUv - off).b);
      float rd = length(ca) - uShockR;
      float ring = (exp(-pow(rd / 0.014, 2.0)) + 0.35 * exp(-pow((rd + 0.05) / 0.04, 2.0))) * uShock;
      col += vec3(0.45, 0.65, 1.0) * ring * 0.75;
      col *= 1.0 - uVig * smoothstep(0.3, 1.05, length(ca));
      col = max(col - uBlack, 0.0) / (1.0 - uBlack);   // crush the toe: flat black compresses cleanly
      col += (hash(gl_FragCoord.xy + fract(uTime) * 97.0) - 0.5) * (1.6 / 255.0) * uGrain;
      gl_FragColor = vec4(col, 1.0);
    }`,
};

/* ───────────────────────── timeline (pure function of t) ───────────────────────── */
const TR = {
  D:     [[0, 36], [0.7, 36], [1.4, 36], [3.0, 32], [4.2, 28], [5.4, 25], [7.2, 35], [8.2, 36]],
  yaw:   [[0, 0], [1.4, 0], [3.0, 0.22], [5.4, -0.16], [7.2, 0], [8.2, 0]],
  pitch: [[0, 0], [1.4, 0], [3.0, -0.1], [5.4, 0.08], [7.2, 0], [8.2, 0]],
  gx:    [[0, -1.15], [1.4, -1.15], [3.0, -1.08], [5.4, -0.98], [7.2, -1.1], [8.2, -1.15]],
  gz:    [[0, -0.3], [1.4, -0.3], [3.0, -0.2], [5.4, -0.05], [7.2, -0.3], [8.2, -0.3]],
  expo:  [[0, 1.0], [1.4, 1.0], [3.0, 0.95], [5.4, 1.0], [7.2, 1.0], [8.2, 1.0]],
  bloom: [[0, 0.5], [1.4, 0.5], [3.0, 1.0], [5.4, 1.0], [7.2, 0.62], [8.2, 0.5]],
  thr:   [[0, 0.62], [1.4, 0.62], [3.0, 0.85], [5.4, 0.85], [7.2, 0.62], [8.2, 0.62]],
};
const SEG = { dissolve: [1.4, 3.0], collapse: [5.4, 7.2] };

function heroState(tIn) {
  const t = ((((tIn * T_LOOP) / TUNE.loop) % T_LOOP) + T_LOOP) % T_LOOP;
  let morph = 1;
  let dir = 0;
  if (t >= SEG.dissolve[0] && t < SEG.dissolve[1]) {
    morph = 1 - (t - SEG.dissolve[0]) / (SEG.dissolve[1] - SEG.dissolve[0]);
    dir = 1;
  } else if (t >= SEG.dissolve[1] && t < SEG.collapse[0]) {
    morph = 0;
  } else if (t >= SEG.collapse[0] && t < SEG.collapse[1]) {
    morph = (t - SEG.collapse[0]) / (SEG.collapse[1] - SEG.collapse[0]);
  }
  const phase = (2 * Math.PI * t) / T_LOOP;
  const shockAge = t - 7.12;
  const inShock = shockAge >= 0 && shockAge < 1.2;
  const flash = smooth(clamp((t - 7.02) / 0.1)) * Math.exp(-Math.max(0, shockAge) * 5.5);
  const sweepT = (t - 7.6) / 1.2;
  return {
    t, morph, dir, phase,
    D: track(TR.D, t),
    yaw: track(TR.yaw, t) + 0.035 * Math.sin(phase) * morph,
    pitch: track(TR.pitch, t) + 0.012 * Math.sin(phase + 1.0) * morph,
    gx: track(TR.gx, t),
    gz: track(TR.gz, t),
    expo: track(TR.expo, t) + 0.16 * flash,
    bloom: track(TR.bloom, t) + 0.6 * flash,
    thr: track(TR.thr, t),
    swirl: TUNE.swirl,
    glow: TUNE.glow,
    sweep: sweepT >= 0 && sweepT <= 1 ? -22 + 44 * sweepT : -999,
    shock: inShock ? Math.exp(-shockAge * 2.4) * (1 - smooth(clamp((shockAge - 0.8) / 0.4))) : 0,
    shockR: inShock ? shockAge * 0.62 : 0,
  };
}

/* ───────────────────────────── scene setup ───────────────────────────── */
const canvas = document.getElementById('gl');
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: 'high-performance', preserveDrawingBuffer: CAPTURE });
} catch (err) {
  document.getElementById('nogl').style.display = 'grid';
  throw err;
}
renderer.setClearColor(0x020309, 1);
renderer.toneMapping = [THREE.ACESFilmicToneMapping, THREE.AgXToneMapping, THREE.NeutralToneMapping, THREE.ReinhardToneMapping, THREE.CineonToneMapping][TUNE.tm] ?? THREE.ACESFilmicToneMapping;

const isSmall = Math.min(innerWidth, innerHeight) < 700;
const N = CAPTURE ? 90000 : isSmall ? 45000 : 90000;
const W0 = CAPTURE ? Number(Q.get('w') || 1280) : innerWidth;
const H0 = CAPTURE ? Number(Q.get('h') || 480) : innerHeight;
const DPR = CAPTURE ? 1 : Math.min(devicePixelRatio || 1, isSmall ? 1.5 : 2);
renderer.setPixelRatio(DPR);
renderer.setSize(W0, H0, false);
if (CAPTURE) {
  canvas.style.width = W0 + 'px';
  canvas.style.height = H0 + 'px';
}

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(FOV, W0 / H0, 0.5, 600);

const rng = mulberry32(20260421);
const galaxy = buildGalaxy(N, rng);
const targets = await buildTargets(N, rng);

/* pair galaxy ↔ title particles by screen-x rank so the morph flows left → right */
const keyG = new Float32Array(N);
const keyB = new Float32Array(N);
const cz = Math.cos(-0.3), sz = Math.sin(-0.3);
for (let i = 0; i < N; i++) {
  keyG[i] = galaxy.pos[i * 3] * cz - galaxy.pos[i * 3 + 1] * sz + gauss(rng) * 2.4;
  const k = targets.kind[i];
  keyB[i] = k === 2 ? targets.pos[i * 3] * 0.75 : k === 4 ? targets.pos[i * 3] * 0.5 : targets.pos[i * 3];
}
const orderG = Array.from({ length: N }, (_, i) => i).sort((a, b) => keyG[a] - keyG[b]);
const orderB = Array.from({ length: N }, (_, i) => i).sort((a, b) => keyB[a] - keyB[b]);

const aA = galaxy.pos;
const aB = new Float32Array(N * 3);
const aColA = galaxy.col;
const aColB = new Float32Array(N * 3);
const aR = new Float32Array(N * 4);
const aMisc = new Float32Array(N * 3);
const aKind = new Float32Array(N);
for (let k = 0; k < N; k++) {
  const gi = orderG[k];
  const bj = orderB[k];
  aB.set(targets.pos.subarray(bj * 3, bj * 3 + 3), gi * 3);
  aColB.set(targets.col.subarray(bj * 3, bj * 3 + 3), gi * 3);
  aKind[gi] = targets.kind[bj];
  aR[gi * 4] = rng();
  aR[gi * 4 + 1] = rng();
  aR[gi * 4 + 2] = rng();
  aR[gi * 4 + 3] = targets.kind[bj] === 2 || targets.kind[bj] === 4 ? targets.ringU[bj] : rng();
  aMisc[gi * 3] = clamp((k / N) * 0.86 + rng() * 0.14);
  aMisc[gi * 3 + 1] = galaxy.size[gi] * TUNE.szA;
  aMisc[gi * 3 + 2] = targets.size[bj] * TUNE.szB;
}

const geo = new THREE.BufferGeometry();
geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3)); // unused, required for draw count
geo.setAttribute('aA', new THREE.BufferAttribute(aA, 3));
geo.setAttribute('aB', new THREE.BufferAttribute(aB, 3));
geo.setAttribute('aColA', new THREE.BufferAttribute(aColA, 3));
geo.setAttribute('aColB', new THREE.BufferAttribute(aColB, 3));
geo.setAttribute('aR', new THREE.BufferAttribute(aR, 4));
geo.setAttribute('aMisc', new THREE.BufferAttribute(aMisc, 3));
geo.setAttribute('aKind', new THREE.BufferAttribute(aKind, 1));

const U = {
  uTime: { value: 0 }, uPhase: { value: 0 }, uMorph: { value: 1 }, uDir: { value: 0 },
  uSpread: { value: 0.5 }, uSwirl: { value: TUNE.swirl }, uArc: { value: 1.0 }, uTurb: { value: 1.2 }, uGlow: { value: TUNE.glow },
  uRotA: { value: new THREE.Matrix3() }, uRingRot: { value: new THREE.Matrix3() }, uRingRot2: { value: new THREE.Matrix3() }, uRingAng: { value: 0 },
  uSizeScale: { value: (H0 * DPR) / REF_H }, uRefDist: { value: REF_DIST }, uFocus: { value: REF_DIST }, uFocusRange: { value: TUNE.dof },
  uBrA: { value: TUNE.brA }, uBrB: { value: TUNE.brB },
  uSweepPos: { value: -999 }, uSweepInvW: { value: 0.62 }, uSweepDir: { value: new THREE.Vector2(0.94, 0.34) },
  uMouse: { value: new THREE.Vector3(0, 0, 9999) }, uMouseR: { value: 3.2 }, uMouseF: { value: 0 }, uPulse: { value: new THREE.Vector4(0, 0, 0, -1) },
};
const points = new THREE.Points(
  geo,
  new THREE.ShaderMaterial({ uniforms: U, vertexShader: PARTICLE_VERT, fragmentShader: PARTICLE_FRAG, transparent: true, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending })
);
points.frustumCulled = false;
points.renderOrder = 1;
scene.add(points);

/* distant starfield */
const SN = Math.round(2600 * TUNE.stars);
const sPos = new Float32Array(SN * 3);
const sCol = new Float32Array(SN * 3);
const sSt = new Float32Array(SN * 2);
for (let i = 0; i < SN; i++) {
  const th = rng() * Math.PI * 2;
  const ph = Math.acos(2 * rng() - 1);
  const r = 140 + rng() * 120;
  sPos.set([r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph) * 0.7, r * Math.sin(ph) * Math.sin(th)], i * 3);
  const c = C('#9db8ff').lerp(C('#ffe2c0'), rng()).lerp(C('#ffffff'), 0.3);
  const b = 0.25 + Math.pow(rng(), 4) * 1.6;
  sCol.set([c.r * b, c.g * b, c.b * b], i * 3);
  sSt[i * 2] = 1.2 + Math.pow(rng(), 5) * 3.2;
  sSt[i * 2 + 1] = rng();
}
const starGeo = new THREE.BufferGeometry();
starGeo.setAttribute('position', new THREE.BufferAttribute(sPos, 3));
starGeo.setAttribute('aCol', new THREE.BufferAttribute(sCol, 3));
starGeo.setAttribute('aSt', new THREE.BufferAttribute(sSt, 2));
const stars = new THREE.Points(
  starGeo,
  new THREE.ShaderMaterial({ uniforms: { uPhase: U.uPhase, uSizeScale: U.uSizeScale }, vertexShader: STAR_VERT, fragmentShader: STAR_FRAG, transparent: true, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending })
);
stars.frustumCulled = false;
stars.renderOrder = 0;
scene.add(stars);

/* nebula backdrop */
const NU = { uAspect: { value: W0 / H0 }, uLevel: { value: TUNE.neb }, uOff: { value: new THREE.Vector2() } };
const nebula = new THREE.Mesh(
  new THREE.PlaneGeometry(2, 2),
  new THREE.ShaderMaterial({ uniforms: NU, vertexShader: NEBULA_VERT, fragmentShader: NEBULA_FRAG, depthTest: false, depthWrite: false })
);
nebula.frustumCulled = false;
nebula.renderOrder = -10;
scene.add(nebula);

/* post */
const composer = new EffectComposer(renderer);
composer.setPixelRatio(DPR);
composer.setSize(W0, H0);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(W0, H0), 0.85, TUNE.rad, TUNE.thr);
composer.addPass(bloom);
composer.addPass(new OutputPass());
const finalPass = new ShaderPass(FINAL_SHADER);
composer.addPass(finalPass);

/* ───────────────────────────── per-frame state ───────────────────────────── */
const _m4 = new THREE.Matrix4();
const _eul = new THREE.Euler();
const RING_TILT = new THREE.Matrix3().setFromMatrix4(_m4.makeRotationFromEuler(_eul.set(-1.34, 0, -0.1, 'ZYX')));
U.uRingRot.value.copy(RING_TILT);
U.uRingRot2.value.setFromMatrix4(_m4.makeRotationFromEuler(_eul.set(-1.18, 0, 0.3, 'ZYX')));

/* the authored composition is 2.67:1; on narrower screens pull the camera back so the title always fits */
const fitK = (aspect) => Math.max(1, 2.23 / aspect);

function apply(S, extra = {}) {
  U.uTime.value = S.t;
  U.uPhase.value = S.phase;
  U.uMorph.value = S.morph;
  U.uDir.value = S.dir;
  U.uSwirl.value = S.swirl;
  U.uGlow.value = S.glow;
  U.uRingAng.value = S.phase;
  U.uSweepPos.value = S.sweep;
  U.uRotA.value.setFromMatrix4(_m4.makeRotationFromEuler(_eul.set(S.gx, 0, S.gz, 'ZYX')));

  const yaw = S.yaw + (extra.yaw || 0);
  const pitch = S.pitch + (extra.pitch || 0);
  const D = S.D * fitK(camera.aspect);
  camera.position.set(D * Math.sin(yaw) * Math.cos(pitch), D * Math.sin(pitch), D * Math.cos(yaw) * Math.cos(pitch));
  camera.lookAt(0, 0, 0);
  U.uFocus.value = D;

  NU.uOff.value.set(yaw * 0.35, pitch * 0.35);
  renderer.toneMappingExposure = S.expo * TUNE.expo;
  bloom.strength = S.bloom * TUNE.bloom;
  bloom.threshold = S.thr * TUNE.thr;
  finalPass.uniforms.uTime.value = S.t;
  finalPass.uniforms.uShock.value = S.shock;
  finalPass.uniforms.uShockR.value = S.shockR;
  finalPass.uniforms.uCA.value = TUNE.ca + 0.005 * S.shock;
  finalPass.uniforms.uVig.value = TUNE.vig;
  finalPass.uniforms.uGrain.value = TUNE.grain;
  finalPass.uniforms.uBlack.value = TUNE.black;
  finalPass.uniforms.uAspect.value = camera.aspect;
}

/* ───────────────────────────── capture API ───────────────────────────── */
if (CAPTURE) {
  document.documentElement.classList.add('capture');
  window.renderAt = (t) => {
    apply(heroState(t));
    composer.render();
    return true;
  };
  window.__loop = TUNE.loop;
  window.__ready = true;
} else {
  startLive();
}

/* ───────────────────────────── live mode ───────────────────────────── */
function startLive() {
  const ui = { dock: document.getElementById('dock'), fps: document.getElementById('fps') };
  let mode = 'auto';
  let tAuto = 0;
  let morph = 1;
  const cam = { D: 36, yaw: 0, pitch: 0, gx: -1.4, gz: -0.3, expo: 1, bloom: 0.85 };
  const ptr = { x: 0, y: 0, nx: 0, ny: 0, down: false, dx: 0, dy: 0, orbitYaw: 0, orbitPitch: 0, inside: false };
  const ray = new THREE.Raycaster();
  let pulseAge = -1;
  let last = performance.now();
  let frames = 0;
  let fpsT = last;
  let dpr = DPR;            // adaptive resolution: drops when the GPU can't hold ~30 fps
  let perfN = 0;            // frames counted in the current window …
  let perfSum = 0;          // … and their summed frame time (ms)
  let perfBad = 0;          // consecutive slow windows

  const resize = () => {
    const w = innerWidth;
    const h = innerHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    U.uSizeScale.value = (h * dpr) / REF_H;
    NU.uAspect.value = w / h;
  };
  addEventListener('resize', resize);
  resize();

  canvas.addEventListener('pointermove', (e) => {
    ptr.inside = true;
    const nx = (e.clientX / innerWidth) * 2 - 1;
    const ny = -(e.clientY / innerHeight) * 2 + 1;
    if (ptr.down) {
      ptr.orbitYaw -= (nx - ptr.nx) * 1.6;
      ptr.orbitPitch += (ny - ptr.ny) * 1.0;
    }
    ptr.nx = nx;
    ptr.ny = ny;
  });
  canvas.addEventListener('pointerleave', () => { ptr.inside = false; });
  canvas.addEventListener('pointerdown', (e) => {
    ptr.down = true;
    ptr.inside = true;
    ptr.nx = (e.clientX / innerWidth) * 2 - 1;
    ptr.ny = -(e.clientY / innerHeight) * 2 + 1;
    canvas.setPointerCapture(e.pointerId);
    pulseAge = 0;
    ray.setFromCamera(new THREE.Vector2(ptr.nx, ptr.ny), camera);
    const p = ray.ray.at(camera.position.length(), new THREE.Vector3());
    U.uPulse.value.set(p.x, p.y, p.z, 0);
  });
  canvas.addEventListener('pointerup', () => { ptr.down = false; });

  ui.dock.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    const next = b.dataset.mode;
    if (next === 'auto') tAuto = mode === 'galaxy' ? 3.0 : 0.0;
    mode = next;
    ui.dock.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
  });
  addEventListener('keydown', (e) => {
    const map = { 1: 'auto', 2: 'title', 3: 'galaxy' };
    if (map[e.key]) ui.dock.querySelector(`[data-mode="${map[e.key]}"]`).click();
  });

  const lerpTo = (cur, target, k) => cur + (target - cur) * k;

  // start state: ?mode=title|galaxy, or a calm title card when the OS asks for reduced motion
  const wanted = Q.get('mode') || (matchMedia('(prefers-reduced-motion: reduce)').matches ? 'title' : 'auto');
  const wantedBtn = ui.dock.querySelector(`[data-mode="${wanted}"]`);
  if (wantedBtn && wanted !== 'auto') wantedBtn.click();

  function tick(now) {
    const raw = now - last;
    const dt = Math.min(0.05, raw / 1000);
    last = now;
    if (!innerWidth || !innerHeight) return;

    let S;
    if (mode === 'auto') {
      tAuto += dt;
      S = heroState(tAuto);
    } else {
      // hold a pose: damped morph toward the chosen state
      const target = mode === 'title' ? 1 : 0;
      const prev = morph;
      morph = lerpTo(morph, target, 1 - Math.exp(-dt * 1.25));
      const tRef = mode === 'title' ? 0.7 : 4.2 + 0.9 * Math.sin(now / 1000 * 0.35);
      S = heroState(tRef);
      S.t = now / 1000;
      S.phase = (2 * Math.PI * S.t) / T_LOOP;
      S.morph = morph;
      S.dir = morph < prev ? 1 : 0;
      S.sweep = -999;
      S.shock = 0;
    }
    // damped camera so mode switches never jump
    const k = 1 - Math.exp(-dt * 7);
    for (const key of ['D', 'yaw', 'pitch', 'gx', 'gz', 'expo', 'bloom']) cam[key] = lerpTo(cam[key], S[key], k);
    S.D = cam.D; S.yaw = cam.yaw; S.pitch = cam.pitch; S.gx = cam.gx; S.gz = cam.gz; S.expo = cam.expo; S.bloom = cam.bloom;

    // pointer parallax + drag-orbit (relaxes back slowly)
    if (!ptr.down) { ptr.orbitYaw *= Math.exp(-dt * 0.5); ptr.orbitPitch *= Math.exp(-dt * 0.5); }
    apply(S, { yaw: ptr.nx * 0.07 + ptr.orbitYaw, pitch: ptr.ny * 0.04 + ptr.orbitPitch });

    // pointer repulsion field
    if (ptr.inside) {
      ray.setFromCamera(new THREE.Vector2(ptr.nx, ptr.ny), camera);
      ray.ray.at(camera.position.length(), U.uMouse.value);
      U.uMouseF.value = lerpTo(U.uMouseF.value, 2.4, 1 - Math.exp(-dt * 8));
    } else {
      U.uMouseF.value = lerpTo(U.uMouseF.value, 0, 1 - Math.exp(-dt * 4));
    }
    if (pulseAge >= 0) {
      pulseAge += dt;
      U.uPulse.value.w = pulseAge;
      if (pulseAge > 4) { pulseAge = -1; U.uPulse.value.w = -1; }
    }

    composer.render();

    // adaptive resolution — only trust frames that look GPU-bound. A hidden / occluded / backgrounded
    // tab gets throttled to ~1 fps by the browser (raw ≥ 250 ms); that is not a reason to lower quality.
    if (raw < 250 && now > 3000) {
      perfN++;
      perfSum += raw;
      if (perfN >= 45) {
        perfBad = perfSum / perfN > 36 ? perfBad + 1 : 0;   // avg frame time > 36 ms ≈ under 28 fps
        perfN = 0;
        perfSum = 0;
        if (perfBad >= 2 && dpr > 0.85) {
          dpr = Math.max(0.85, dpr * 0.8);
          perfBad = 0;
          renderer.setPixelRatio(dpr);
          composer.setPixelRatio(dpr);
          resize();
        }
      }
    }

    frames++;
    if (now - fpsT > 500 && Q.has('fps')) {
      ui.fps.textContent = `${Math.round((frames * 1000) / (now - fpsT))} fps · ${N.toLocaleString()} particles`;
      frames = 0;
      fpsT = now;
    }
  }
  renderer.setAnimationLoop(tick);
}
