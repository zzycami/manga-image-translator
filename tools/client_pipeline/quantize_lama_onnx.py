#!/usr/bin/env python3
"""
Convert lama_large_*.onnx to FP16 weights (I/O stay float32) and bench vs FP32.

Usage:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/quantize_lama_onnx.py \\
    --onnx result/lama_onnx/lama_large_512.onnx \\
    --image ../manga-translate-native/result/batch_hana_timing/005_005/page_work.jpg \\
    --mask  ../manga-translate-native/result/batch_hana_timing/005_005/mask_final.png
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import onnx
from onnxconverter_common import float16


def _prep(image_path: Path, mask_path: Path, size: int):
    image = cv2.cvtColor(cv2.imread(str(image_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    image = cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR)
    mask = cv2.resize(mask, (size, size), interpolation=cv2.INTER_LINEAR)
    img = (image.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
    m = (mask.astype(np.float32) / 255.0)[None, None]
    m = (m >= 0.5).astype(np.float32)
    return img, m


def _bench(sess, img, mask, runs: int):
    feeds = {"image": img, "mask": mask}
    sess.run(None, feeds)  # warmup
    times = []
    out = None
    for _ in range(runs):
        t0 = time.perf_counter()
        out = sess.run(None, feeds)[0]
        times.append((time.perf_counter() - t0) * 1000)
    return out, times


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onnx", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None, help="default: <stem>_fp16.onnx")
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--image", type=Path, required=True)
    ap.add_argument("--mask", type=Path, required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--skip-convert", action="store_true")
    args = ap.parse_args()

    out = args.out or args.onnx.with_name(args.onnx.stem + "_fp16.onnx")
    report = {"fp32": str(args.onnx), "fp16": str(out), "size": args.size, "runs": args.runs}

    if not args.skip_convert:
        print(f"Loading {args.onnx} ({args.onnx.stat().st_size / 1e6:.1f} MB)…")
        model = onnx.load(str(args.onnx))
        print("Converting float → float16 (keep_io_types=True)…")
        t0 = time.perf_counter()
        model_fp16 = float16.convert_float_to_float16(model, keep_io_types=True)
        print(f"  convert {time.perf_counter() - t0:.1f}s")
        onnx.save(model_fp16, str(out))
        print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")

    import onnxruntime as ort

    img, mask = _prep(args.image, args.mask, args.size)
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    print("Bench FP32…")
    s32 = ort.InferenceSession(str(args.onnx), opts, providers=["CPUExecutionProvider"])
    o32, t32 = _bench(s32, img, mask, args.runs)
    report["fp32_ms"] = [round(x, 2) for x in t32]
    report["fp32_ms_mean"] = round(float(np.mean(t32)), 2)
    report["fp32_mb"] = round(args.onnx.stat().st_size / 1e6, 1)

    print("Bench FP16…")
    s16 = ort.InferenceSession(str(out), opts, providers=["CPUExecutionProvider"])
    o16, t16 = _bench(s16, img, mask, args.runs)
    report["fp16_ms"] = [round(x, 2) for x in t16]
    report["fp16_ms_mean"] = round(float(np.mean(t16)), 2)
    report["fp16_mb"] = round(out.stat().st_size / 1e6, 1)

    diff = np.abs(o32 - o16)
    report["fp16_vs_fp32"] = {
        "max_abs_diff": float(diff.max()),
        "mean_abs_diff": float(diff.mean()),
        "p99_abs_diff": float(np.percentile(diff, 99)),
    }
    # save visual
    erased = (np.clip(o16[0].transpose(1, 2, 0), 0, 1) * 255).astype(np.uint8)
    vis = args.onnx.parent / "smoke_erased_fp16.png"
    cv2.imwrite(str(vis), cv2.cvtColor(erased, cv2.COLOR_RGB2BGR))
    report["vis"] = str(vis)

    meta = args.onnx.parent / "quantize_meta.json"
    meta.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Wrote", meta)


if __name__ == "__main__":
    main()
