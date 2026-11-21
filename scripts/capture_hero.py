#!/usr/bin/env python3
"""Render the 3D particle scene (docs/scene.js) into assets/hero.webp.

The scene is a pure function of time, so every frame is deterministic. Each output frame
is the average (in linear light) of a few sub-frames spread across a virtual shutter —
that is what gives the particles real motion blur instead of a choppy 20 fps look.

Requirements (kept out of the repo on purpose):
    pip install playwright pillow numpy && playwright install chromium
    cwebp + webpmux (brew install webp)

Usage:
    python scripts/capture_hero.py                       # uses jsDelivr for three.js / fonts
    python scripts/capture_hero.py --deps /path/to/node_modules   # fully offline
    python scripts/capture_hero.py --fps 15 --sub 8 --quality 52 --w 1100 --h 412 --loop 8
"""
from __future__ import annotations

import argparse
import concurrent.futures
import functools
import http.server
import io
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


# ───────────────────────────── tiny static server ─────────────────────────────
def start_server(deps: Path | None) -> tuple[socketserver.TCPServer, int]:
    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".woff2": "font/woff2"}

        def translate_path(self, path: str) -> str:
            path = path.split("?", 1)[0].split("#", 1)[0]
            base, rel = (deps, path[len("/_deps/"):]) if deps and path.startswith("/_deps/") else (DOCS, path.lstrip("/"))
            full = os.path.realpath(os.path.join(base, rel))
            return full if full.startswith(os.path.realpath(base)) else str(DOCS / "__forbidden__")

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, *a) -> None:  # noqa: D401
            pass

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


# ───────────────────────────── frame rendering ─────────────────────────────
def render_slice(job: dict) -> int:
    """Render frames job['indices'] to PNGs in job['dir'] (one headless Chromium, software WebGL)."""
    from playwright.sync_api import sync_playwright

    a = job["args"]
    rng = np.random.default_rng(1234)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"])
        page = browser.new_page(viewport={"width": a["w"], "height": a["h"]}, device_scale_factor=1)
        page.on("pageerror", lambda e: print("page error:", e, file=sys.stderr))
        page.goto(f"http://127.0.0.1:{job['port']}/index.html?capture=1&w={a['w']}&h={a['h']}{'' if job['local'] else '&cdn=1'}{a['query']}")
        page.wait_for_function("window.__ready === true", timeout=180_000)
        canvas = page.locator("#gl")
        for i in job["indices"]:
            t0 = i / a["fps"]
            acc = None
            for k in range(a["sub"]):
                # centred virtual shutter: [-shutter/2, +shutter/2] of one frame interval
                off = (((k + 0.5) / a["sub"]) - 0.5) * (a["shutter"] / a["fps"]) if a["sub"] > 1 else 0.0
                page.evaluate("t => window.renderAt(t)", t0 + off)
                im = np.asarray(Image.open(io.BytesIO(canvas.screenshot(type="png"))).convert("RGB"), dtype=np.float32) / 255.0
                lin = np.power(im, 2.2)
                acc = lin if acc is None else acc + lin
            out = np.power(acc / a["sub"], 1 / 2.2) * 255.0
            if a["dither"]:
                out += rng.uniform(-0.5, 0.5, size=out.shape[:2])[..., None]  # kill banding after 8-bit quantisation
            Image.fromarray(np.clip(np.rint(out), 0, 255).astype(np.uint8)).save(Path(job["dir"]) / f"f{i:04d}.png", compress_level=1)
        browser.close()
    return len(job["indices"])


# ───────────────────────────── encoding ─────────────────────────────
def _cwebp(args: tuple[Path, Path, int]) -> None:
    src, dst, quality = args
    r = subprocess.run(
        ["cwebp", "-quiet", "-q", str(quality), "-m", "6", "-sns", "100", "-f", "30", "-sharpness", "0", "-segments", "4", str(src), "-o", str(dst)],
        capture_output=True, text=True,
    )
    if r.returncode:
        sys.exit(f"cwebp failed on {src.name}: {r.stderr[-400:]}")


def encode(frames: list[Path], out: Path, fps: int, quality: int, method: int) -> None:
    """Encode every frame as an independent, opaque lossy WebP and mux them into one animation.

    img2webp's animation encoder re-uses 'nearly unchanged' pixels from the previous frame (via a
    hidden alpha mask). On dark, smooth glows that freezes old quantisation blocks in place and you
    get a mosaic. Our frames change everywhere anyway, so independent frames cost nothing extra.
    """
    if not (shutil.which("cwebp") and shutil.which("webpmux")):
        sys.exit("need cwebp + webpmux (brew install webp)")
    dur = round(1000 / fps)
    tmp = Path(tempfile.mkdtemp(prefix="webp_"))
    try:
        parts = [tmp / f"{f.stem}.webp" for f in frames]
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
            list(ex.map(_cwebp, [(f, d, quality) for f, d in zip(frames, parts)]))
        cmd = ["webpmux"]
        for d in parts:
            cmd += ["-frame", str(d), f"+{dur}+0+0+0-b"]
        cmd += ["-loop", "0", "-o", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"webpmux failed: {(r.stderr or r.stdout)[-600:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--w", type=int, default=1100)
    ap.add_argument("--h", type=int, default=412)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--loop", type=float, default=8.0, help="loop length in seconds (scene timeline is re-timed to it)")
    ap.add_argument("--sub", type=int, default=8, help="sub-frames per frame (motion blur samples)")
    ap.add_argument("--shutter", type=float, default=0.65, help="shutter open fraction of a frame interval")
    ap.add_argument("--quality", type=int, default=52, help="WebP quality 0-100")
    ap.add_argument("--method", type=int, default=6, help="WebP effort 0-6")
    ap.add_argument("--deps", type=Path, help="node_modules dir with three, @fontsource/* (default: jsDelivr)")
    ap.add_argument("--frames", type=Path, help="keep PNG frames in this dir (default: temp)")
    ap.add_argument("--out", type=Path, default=ROOT / "assets" / "hero.webp")
    ap.add_argument("--query", default="", help="extra URL params, e.g. '&expo=0.9'")
    ap.add_argument("--dither", action="store_true", help="add ±0.5 LSB noise before 8-bit quantisation (bigger files)")
    ap.add_argument("--only", help="render just these frame indices (comma list) and skip encoding — for look-dev")
    ap.add_argument("--encode-only", action="store_true", help="skip rendering; encode existing frames in --frames")
    a = ap.parse_args()

    n = round(a.loop * a.fps)
    work = a.frames or Path(tempfile.mkdtemp(prefix="hero_"))
    work.mkdir(parents=True, exist_ok=True)

    if not a.encode_only:
        srv, port = start_server(a.deps)
        t0 = time.time()
        cfg = {k: getattr(a, k) for k in ("w", "h", "fps", "sub", "shutter", "dither")}
        cfg["query"] = f"&loop={a.loop}{a.query}"
        idx = [int(x) for x in a.only.split(",")] if a.only else list(range(n))
        render_slice({"args": cfg, "indices": idx, "dir": str(work), "port": port, "local": a.deps is not None})
        srv.shutdown()
        if a.only:
            print(f"rendered frames {idx} → {work}")
            return
        print(f"rendered {n} frames × {a.sub} sub-frames in {time.time() - t0:.0f}s → {work}")

    frames = sorted(work.glob("f*.png"))
    assert len(frames) == n, f"expected {n} frames, found {len(frames)}"
    a.out.parent.mkdir(parents=True, exist_ok=True)
    encode(frames, a.out, a.fps, a.quality, a.method)
    print(f"{a.out}  {a.out.stat().st_size / 1e6:.2f} MB  ({n} frames @ {a.fps} fps, {a.w}×{a.h})")
    if not a.frames:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
