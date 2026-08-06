#!/usr/bin/env python3
"""
End-to-end client path (desktop spike, before mobile ONNX):

  original page + refined mask
    → lama_large erase
    → inject as inpaintedJpegBase64 into stages
    → manga-translate-native render_page (CoreText glyphs)

Does not require a live MIT server if local stages + mask_final.png exist.

Example:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/run_e2e_client_pipeline.py \\
    --pages-dir ../manga-translate-native/result/batch_hana_timing \\
    --render-bin ../manga-translate-native/build/render_page \\
    --out-dir result/e2e_client_pipeline
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _decode_mask_b64(b64: str) -> np.ndarray:
    arr = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
    mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError("bad maskPngBase64")
    return mask


def _jpeg_b64(rgb: np.ndarray, quality: int = 90) -> str:
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _load_stages_and_mask(
    page_dir: Path,
    rgb: np.ndarray,
) -> Tuple[Dict[str, Any], np.ndarray, str]:
    h, w = rgb.shape[:2]
    candidates = [
        page_dir / "stages_with_mask.json",
        page_dir / "stages.json",
        page_dir.parent.parent
        / "batch_hana_client_erase"
        / page_dir.name
        / "stages_slim.json",
    ]
    stages: Optional[Dict[str, Any]] = None
    for p in candidates:
        if p.exists():
            stages = json.loads(p.read_text(encoding="utf-8"))
            break
    if stages is None:
        raise FileNotFoundError(f"no stages json under {page_dir}")

    mask = None
    source = "none"
    local_mask = page_dir / "mask_final.png"
    if local_mask.exists():
        mask = cv2.imread(str(local_mask), cv2.IMREAD_GRAYSCALE)
        source = "mask_final.png"
    elif stages.get("maskPngBase64"):
        mask = _decode_mask_b64(stages["maskPngBase64"])
        source = "stages_maskPngBase64"
    if mask is None:
        raise RuntimeError("no mask (need mask_final.png or stages.maskPngBase64)")
    if mask.shape[0] != h or mask.shape[1] != w:
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
    return stages, mask, source


async def _lama_erase(rgb: np.ndarray, mask: np.ndarray, device: str, size: int) -> np.ndarray:
    from manga_translator.config import Inpainter, InpainterConfig
    from manga_translator.inpainting import prepare, dispatch

    await prepare(Inpainter.lama_large, device)
    cfg = InpainterConfig(inpainter=Inpainter.lama_large)
    return await dispatch(Inpainter.lama_large, rgb, mask, cfg, size, device, False)


def _pick_device(name: str) -> str:
    import torch

    if name == "cpu":
        return "cpu"
    if name == "mps":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    if name == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


async def _run_one(
    page_dir: Path,
    out_dir: Path,
    render_bin: Path,
    device: str,
    inpainting_size: int,
) -> Dict[str, Any]:
    work = page_dir / "page_work.jpg"
    orig = page_dir / "page_orig.jpg"
    img_path = work if work.exists() else orig
    rgb = _load_rgb(img_path)
    # Prefer work-sized mask next to page; also accept bench_lama_client copy
    if not (page_dir / "mask_final.png").exists():
        alt = ROOT / "result" / "bench_lama_client" / page_dir.name / "mask.png"
        if alt.exists():
            import shutil

            shutil.copy2(alt, page_dir / "mask_final.png")
    stages, mask, mask_source = _load_stages_and_mask(page_dir, rgb)

    t0 = time.perf_counter()
    erased = await _lama_erase(rgb, mask, device, inpainting_size)
    lama_ms = (time.perf_counter() - t0) * 1000

    page_out = out_dir / page_dir.name
    page_out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(page_out / "mask.png"), mask)
    cv2.imwrite(str(page_out / "01_erased.png"), cv2.cvtColor(erased, cv2.COLOR_RGB2BGR))

    # Feed lama output as server-style inpainted base so native skips geometry wipe.
    stages_out = dict(stages)
    stages_out["inpaintedJpegBase64"] = _jpeg_b64(erased, quality=92)
    stages_out["skipRegionFill"] = True
    stages_out["imageWidth"] = int(rgb.shape[1])
    stages_out["imageHeight"] = int(rgb.shape[0])
    # Keep mask for inspection / future native lama; not required by render_page today.
    if not stages_out.get("maskPngBase64"):
        ok, buf = cv2.imencode(".png", mask)
        if ok:
            stages_out["maskPngBase64"] = base64.b64encode(buf.tobytes()).decode("ascii")

    stages_path = page_out / "stages_for_render.json"
    # Compact write without pretty indent (smaller)
    stages_path.write_text(json.dumps(stages_out, ensure_ascii=False), encoding="utf-8")

    # Work-size final
    out_work = page_out / "02_final_work.png"
    t1 = time.perf_counter()
    subprocess.run(
        [str(render_bin), str(img_path), str(stages_path), str(out_work)],
        check=True,
        capture_output=True,
        text=True,
    )
    render_work_ms = (time.perf_counter() - t1) * 1000

    render_full_ms = None
    out_full = None
    if orig.exists() and work.exists():
        out_full = page_out / "03_final_full.png"
        t2 = time.perf_counter()
        subprocess.run(
            [str(render_bin), str(orig), str(stages_path), str(out_full)],
            check=True,
            capture_output=True,
            text=True,
        )
        render_full_ms = (time.perf_counter() - t2) * 1000

    return {
        "page": page_dir.name,
        "size": f"{rgb.shape[1]}x{rgb.shape[0]}",
        "mask_source": mask_source,
        "lama_ms": round(lama_ms, 1),
        "render_work_ms": round(render_work_ms, 1),
        "render_full_ms": None if render_full_ms is None else round(render_full_ms, 1),
        "final_work": str(out_work),
        "final_full": None if out_full is None else str(out_full),
    }


async def _main_async(args: argparse.Namespace) -> None:
    device = _pick_device(args.device)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    render_bin = Path(args.render_bin)
    if not render_bin.is_file():
        raise SystemExit(f"render_page not found: {render_bin}")

    pages_dir = Path(args.pages_dir)
    report = {"device": device, "inpainting_size": args.inpainting_size, "pages": []}
    for stem in args.stems.split(","):
        stem = stem.strip()
        d = pages_dir / stem
        if not d.is_dir():
            print(f"skip missing {d}")
            continue
        print(f"== {stem} device={device}")
        row = await _run_one(d, out_dir, render_bin, device, args.inpainting_size)
        report["pages"].append(row)
        print(
            f"   lama={row['lama_ms']}ms render_work={row['render_work_ms']}ms "
            f"full={row['render_full_ms']} → {row['final_work']}"
        )

    (out_dir / "e2e_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--pages-dir",
        default=str(ROOT.parent / "manga-translate-native" / "result" / "batch_hana_timing"),
    )
    ap.add_argument("--stems", default="005_005,007_007,033_033")
    ap.add_argument(
        "--render-bin",
        default=str(ROOT.parent / "manga-translate-native" / "build" / "render_page"),
    )
    ap.add_argument("--device", default="auto", choices=["auto", "mps", "cuda", "cpu"])
    ap.add_argument("--inpainting-size", type=int, default=1024)
    ap.add_argument("--out-dir", default=str(ROOT / "result" / "e2e_client_pipeline"))
    args = ap.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
