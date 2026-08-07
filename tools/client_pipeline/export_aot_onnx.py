#!/usr/bin/env python3
"""
Export MIT AOT inpainter (inpainting.ckpt, ~22MB) to ONNX.

I/O match lama export for client reuse:
  image/mask float32 [0,1] → erased float32 [0,1]

Usage:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/export_aot_onnx.py \\
    --size 384 --smoke \\
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
import torch
import torch.nn as nn


class AotEraseOnnx(nn.Module):
    def __init__(self, generator: nn.Module):
        super().__init__()
        self.generator = generator

    def forward(self, img: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        # img in [0,1] → AOT expects [-1,1]
        x = img * 2.0 - 1.0
        x = x * (1.0 - mask)
        pred = self.generator(x, mask)
        out = pred * mask + (1.0 - mask) * x
        return (out + 1.0) * 0.5


def _load(image_path: Path, mask_path: Path, size: int):
    image = cv2.cvtColor(cv2.imread(str(image_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    h0, w0 = image.shape[:2]
    image = cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR)
    mask = cv2.resize(mask, (size, size), interpolation=cv2.INTER_LINEAR)
    img_t = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    mask_t = (torch.from_numpy(mask).unsqueeze(0).unsqueeze(0).float() / 255.0 >= 0.5).float()
    return img_t, mask_t, (h0, w0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, default=Path("models/inpainting/inpainting.ckpt"))
    ap.add_argument("--size", type=int, default=384)
    ap.add_argument("--out-dir", type=Path, default=Path("result/lama_onnx"))
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--image", type=Path, default=None)
    ap.add_argument("--mask", type=Path, default=None)
    args = ap.parse_args()
    if args.size % 8 != 0:
        raise SystemExit("--size must be multiple of 8")

    from manga_translator.inpainting.inpainting_aot import AOTGenerator

    args.out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = args.out_dir / f"aot_{args.size}.onnx"

    print(f"Loading {args.ckpt}…")
    gen = AOTGenerator()
    sd = torch.load(str(args.ckpt), map_location="cpu")
    gen.load_state_dict(sd["model"] if "model" in sd else sd)
    gen.eval()
    wrapper = AotEraseOnnx(gen).eval()

    dummy_img = torch.rand(1, 3, args.size, args.size)
    dummy_mask = (torch.rand(1, 1, args.size, args.size) > 0.7).float()

    print(f"Exporting → {onnx_path} …")
    t0 = time.perf_counter()
    with torch.no_grad():
        torch.onnx.export(
            wrapper,
            (dummy_img, dummy_mask),
            str(onnx_path),
            input_names=["image", "mask"],
            output_names=["erased"],
            opset_version=args.opset,
            dynamo=False,
            do_constant_folding=True,
        )
    print(f"  export {time.perf_counter() - t0:.2f}s  size={onnx_path.stat().st_size / 1e6:.1f} MB")

    meta = {
        "kind": "aot",
        "ckpt": str(args.ckpt),
        "size": args.size,
        "onnx": str(onnx_path),
        "inputs": {"image": "float32 NCHW [0,1]", "mask": "float32 NCHW {0,1}"},
    }

    if args.smoke:
        import onnxruntime as ort

        img_t, mask_t, orig_hw = _load(args.image, args.mask, args.size)
        with torch.no_grad():
            t0 = time.perf_counter()
            pt = wrapper(img_t, mask_t).numpy()
            pt_ms = (time.perf_counter() - t0) * 1000
        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        feeds = {"image": img_t.numpy(), "mask": mask_t.numpy()}
        sess.run(None, feeds)
        t0 = time.perf_counter()
        ort_out = sess.run(None, feeds)[0]
        ort_ms = (time.perf_counter() - t0) * 1000
        diff = np.abs(pt - ort_out)
        meta["smoke"] = {
            "pytorch_ms": round(pt_ms, 2),
            "ort_cpu_ms": round(ort_ms, 2),
            "max_abs_diff": float(diff.max()),
            "mean_abs_diff": float(diff.mean()),
            "orig_hw": list(orig_hw),
        }
        erased = (np.clip(ort_out[0].transpose(1, 2, 0), 0, 1) * 255).astype(np.uint8)
        erased_full = cv2.resize(erased, (orig_hw[1], orig_hw[0]))
        mask_full = cv2.imread(str(args.mask), 0)
        mask_bin = (mask_full >= 127).astype(np.uint8)[:, :, None]
        orig = cv2.cvtColor(cv2.imread(str(args.image)), cv2.COLOR_BGR2RGB)
        comp = erased_full * mask_bin + orig * (1 - mask_bin)
        out_png = args.out_dir / f"smoke_aot_{args.size}.png"
        cv2.imwrite(str(out_png), cv2.cvtColor(comp.astype(np.uint8), cv2.COLOR_RGB2BGR))
        print("Smoke:", json.dumps(meta["smoke"], indent=2))
        print("Wrote", out_png)

    (args.out_dir / f"export_aot_{args.size}_meta.json").write_text(json.dumps(meta, indent=2))
    print("Wrote", args.out_dir / f"export_aot_{args.size}_meta.json")


if __name__ == "__main__":
    main()
