#!/usr/bin/env python3
"""
Benchmark server-identical lama_large on the client machine (Mac MPS/CPU).

Product path under test:
  original page (local) + refined mask (from stages JSON) → lama_large → erased RGB

Does not change the default App render path; geometry erase remains the fallback.

Examples:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/bench_client_lama.py \\
    --pages-dir ../manga-translate-native/result/batch_hana_timing \\
    --fetch-stages http://127.0.0.1:8010 \\
    --runs 3

  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/bench_client_lama.py \\
    --image page.jpg --mask mask.png --out-dir result/bench_lama_client
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Repo root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _rss_mb() -> float:
    # macOS: ru_maxrss is bytes; Linux: kilobytes
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return rss / (1024 * 1024)
    return rss / 1024


def _pick_device(preferred: str) -> str:
    import torch

    if preferred == "cpu":
        return "cpu"
    if preferred == "mps":
        return "mps" if torch.backends.mps.is_available() else "cpu"
    if preferred == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"
    # auto
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _decode_mask_b64(b64: str) -> np.ndarray:
    raw = base64.b64decode(b64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError("Failed to decode maskPngBase64")
    return mask


def _synthesize_mask_from_stages(stages: Dict[str, Any], h: int, w: int) -> np.ndarray:
    """Fallback when no server mask: dilated polygons (not fit_text quality)."""
    mask = np.zeros((h, w), dtype=np.uint8)
    for r in stages.get("regions") or []:
        for poly in r.get("polygons") or []:
            pts = np.array(poly, dtype=np.int32)
            if pts.ndim == 2 and len(pts) >= 3:
                cv2.fillPoly(mask, [pts], 255)
        bb = r.get("boundingBox") or {}
        x, y, bw, bh = int(bb.get("x", 0)), int(bb.get("y", 0)), int(bb.get("w", 0)), int(bb.get("h", 0))
        if bw > 0 and bh > 0:
            cv2.rectangle(mask, (x, y), (x + bw, y + bh), 255, -1)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
    return cv2.dilate(mask, k, iterations=1)


def _textblocks_from_stages(stages: Dict[str, Any]):
    from manga_translator.utils import TextBlock

    blocks = []
    for r in stages.get("regions") or []:
        polys = r.get("polygons") or []
        if not polys:
            bb = r.get("boundingBox") or {}
            x, y, bw, bh = int(bb.get("x", 0)), int(bb.get("y", 0)), int(bb.get("w", 0)), int(bb.get("h", 0))
            polys = [[[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh]]]
        blk = TextBlock(
            lines=polys,
            texts=[r.get("sourceText") or ""],
            translation=r.get("translatedText") or "",
            fg_color=(0, 0, 0),
            bg_color=(255, 255, 255),
            angle=float(r.get("angleDeg") or 0),
            direction="v" if r.get("vertical") else "h",
        )
        blocks.append(blk)
    return blocks


async def _refine_mask_local(rgb: np.ndarray, stages: Dict[str, Any]) -> np.ndarray:
    """Run the same fit_text refinement the server uses (raw mask ≈ region fill)."""
    from manga_translator.mask_refinement import dispatch as dispatch_mask_refinement

    h, w = rgb.shape[:2]
    raw = _synthesize_mask_from_stages(stages, h, w)
    regions = _textblocks_from_stages(stages)
    return await dispatch_mask_refinement(
        regions, rgb, raw, "fit_text", dilation_offset=20, ignore_bubble=0, verbose=False, kernel_size=3
    )


def _load_rgb(path: Path) -> np.ndarray:
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _fetch_stages(host: str, image_path: Path, timeout: float = 180.0) -> Dict[str, Any]:
    import urllib.request

    boundary = "----BenchLamaBoundary7MA4YWxkTrZu0gW"
    img_bytes = image_path.read_bytes()
    config = json.dumps(
        {
            "pipeline_mode": "json_stages",
            "stages_include_mask": True,
            "stages_include_inpainted": False,
            "translator": {"translator": "custom_openai", "target_lang": "CHS"},
        }
    ).encode("utf-8")
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="image"; filename="page.jpg"\r\n',
            b"Content-Type: image/jpeg\r\n\r\n",
            img_bytes,
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="config"\r\n\r\n',
            config,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    url = host.rstrip("/") + "/translate/with-form/stages"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def _resolve_page_inputs(
    page_dir: Path,
    fetch_host: Optional[str],
) -> Tuple[np.ndarray, np.ndarray, str, Dict[str, Any]]:
    """
    Returns rgb (prefer work size matching stages), mask, mask_source, stages dict.
    """
    work = page_dir / "page_work.jpg"
    orig = page_dir / "page_orig.jpg"
    stages_path = page_dir / "stages.json"
    stages_slim = (
        page_dir.parent.parent / "batch_hana_client_erase" / page_dir.name / "stages_slim.json"
    )
    # Prefer work image for speed parity with cloud working resolution
    img_path = work if work.exists() else orig
    if not img_path.exists():
        raise FileNotFoundError(f"No page image in {page_dir}")

    stages: Dict[str, Any] = {}

    if fetch_host:
        try:
            stages = _fetch_stages(fetch_host, img_path)
            (page_dir / "stages_with_mask.json").write_text(
                json.dumps(stages, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            print(f"WARN fetch-stages failed ({e}); falling back to local stages")
            stages = {}
    if not stages and stages_path.exists():
        stages = json.loads(stages_path.read_text(encoding="utf-8"))
    if not stages and stages_slim.exists():
        stages = json.loads(stages_slim.read_text(encoding="utf-8"))

    rgb = _load_rgb(img_path)
    h, w = rgb.shape[:2]

    mask = None
    mask_source = "none"
    local_mask = page_dir / "mask_final.png"
    if local_mask.exists():
        mask = cv2.imread(str(local_mask), cv2.IMREAD_GRAYSCALE)
        mask_source = "local_mask_final.png"
    elif stages.get("maskPngBase64"):
        mask = _decode_mask_b64(stages["maskPngBase64"])
        mask_source = "stages_maskPngBase64"
    elif stages:
        mask = await _refine_mask_local(rgb, stages)
        mask_source = "local_fit_text_refine"
        # Persist for size reporting / reuse
        ok, buf = cv2.imencode(".png", mask)
        if ok:
            stages = dict(stages)
            stages["maskPngBase64"] = base64.b64encode(buf.tobytes()).decode("ascii")
            (page_dir / "mask_final.png").write_bytes(buf.tobytes())

    if mask is None:
        raise RuntimeError(f"No mask/stages for {page_dir}")

    if mask.shape[0] != h or mask.shape[1] != w:
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

    return rgb, mask, mask_source, stages


async def _run_bench(args: argparse.Namespace) -> Dict[str, Any]:
    from manga_translator.config import Inpainter, InpainterConfig
    from manga_translator.inpainting import prepare, dispatch

    device = _pick_device(args.device)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "device": device,
        "inpainter": "lama_large",
        "inpainting_size": args.inpainting_size,
        "runs": args.runs,
        "pages": [],
        "peak_rss_mb_end": None,
        "model_load_ms": None,
        "verdict": None,
    }

    t0 = time.perf_counter()
    await prepare(Inpainter.lama_large, device)
    report["model_load_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    report["rss_mb_after_load"] = round(_rss_mb(), 1)

    cfg = InpainterConfig(inpainter=Inpainter.lama_large)

    page_jobs: List[Tuple[str, Path]] = []
    if args.image:
        page_jobs.append(("single", Path(args.image)))
    else:
        pages_dir = Path(args.pages_dir)
        for stem in args.stems.split(","):
            stem = stem.strip()
            d = pages_dir / stem
            if d.is_dir():
                page_jobs.append((stem, d))

    for name, path in page_jobs:
        if path.is_file():
            rgb = _load_rgb(path)
            if not args.mask:
                raise SystemExit("--mask required with --image")
            mask = cv2.imread(args.mask, cv2.IMREAD_GRAYSCALE)
            if mask is None:
                raise FileNotFoundError(args.mask)
            if mask.shape[:2] != rgb.shape[:2]:
                mask = cv2.resize(mask, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
            mask_source = "cli_mask"
            stages = {}
        else:
            rgb, mask, mask_source, stages = await _resolve_page_inputs(path, args.fetch_stages)

        # Warmup
        _ = await dispatch(
            Inpainter.lama_large,
            rgb,
            mask,
            cfg,
            args.inpainting_size,
            device,
            False,
        )

        times_ms: List[float] = []
        last = None
        for _i in range(args.runs):
            t1 = time.perf_counter()
            last = await dispatch(
                Inpainter.lama_large,
                rgb,
                mask,
                cfg,
                args.inpainting_size,
                device,
                False,
            )
            times_ms.append((time.perf_counter() - t1) * 1000)

        page_out = out_dir / name
        page_out.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(page_out / "mask.png"), mask)
        cv2.imwrite(str(page_out / "erased.png"), cv2.cvtColor(last, cv2.COLOR_RGB2BGR))
        if stages:
            # Strip huge fields for side dump size check
            slim = {k: v for k, v in stages.items() if k != "inpaintedJpegBase64"}
            mb = slim.get("maskPngBase64") or ""
            (page_out / "stages_meta.json").write_text(
                json.dumps(
                    {
                        "regions": len(stages.get("regions") or []),
                        "mask_b64_chars": len(mb),
                        "mask_png_bytes_est": int(len(mb) * 3 / 4) if mb else 0,
                        "imageWidth": stages.get("imageWidth"),
                        "imageHeight": stages.get("imageHeight"),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        avg = sum(times_ms) / len(times_ms)
        page_report = {
            "page": name,
            "size": f"{rgb.shape[1]}x{rgb.shape[0]}",
            "mask_source": mask_source,
            "mask_nonzero_pct": round(100.0 * float(np.count_nonzero(mask)) / mask.size, 2),
            "warmup_done": True,
            "runs_ms": [round(x, 1) for x in times_ms],
            "avg_ms": round(avg, 1),
            "min_ms": round(min(times_ms), 1),
            "max_ms": round(max(times_ms), 1),
            "rss_mb": round(_rss_mb(), 1),
            "erased_png": str(page_out / "erased.png"),
        }
        report["pages"].append(page_report)
        print(
            f"[{name}] {page_report['size']} mask={mask_source} "
            f"avg={page_report['avg_ms']}ms min={page_report['min_ms']} "
            f"rss={page_report['rss_mb']}MB"
        )

    report["peak_rss_mb_end"] = round(_rss_mb(), 1)
    if report["pages"]:
        mean_avg = sum(p["avg_ms"] for p in report["pages"]) / len(report["pages"])
        report["mean_page_avg_ms"] = round(mean_avg, 1)
        # Rough product guidance for phone later; Mac numbers are an upper/lower bound depending on GPU.
        if mean_avg <= 800 and report["peak_rss_mb_end"] <= 2500:
            report["verdict"] = "promising_for_high_end_client_after_mobile_port"
        elif mean_avg <= 2500:
            report["verdict"] = "usable_on_desktop_need_quantize_or_size_cap_for_phone"
        else:
            report["verdict"] = "too_heavy_quantize_or_keep_geometry_fallback"
        report["verdict_notes"] = (
            "Thresholds are heuristic for Mac MPS/CPU spike only; "
            "Android/iOS needs a separate device bench before shipping."
        )

    (out_dir / "bench_lama_client.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: report[k] for k in ("device", "model_load_ms", "mean_page_avg_ms", "peak_rss_mb_end", "verdict")}, indent=2))
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--pages-dir",
        default=str(
            ROOT.parent / "manga-translate-native" / "result" / "batch_hana_timing"
        ),
        help="Directory containing per-page folders (005_005, ...)",
    )
    ap.add_argument("--stems", default="005_005,007_007,033_033")
    ap.add_argument("--image", default=None, help="Single image path (with --mask)")
    ap.add_argument("--mask", default=None, help="Single mask PNG path")
    ap.add_argument(
        "--fetch-stages",
        default=None,
        help="MIT base URL to POST /translate/with-form/stages (gets real mask)",
    )
    ap.add_argument("--device", default="auto", choices=["auto", "mps", "cuda", "cpu"])
    ap.add_argument("--inpainting-size", type=int, default=1024)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument(
        "--out-dir",
        default=str(ROOT / "result" / "bench_lama_client"),
    )
    args = ap.parse_args()
    asyncio.run(_run_bench(args))


if __name__ == "__main__":
    main()
