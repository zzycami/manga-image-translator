#!/usr/bin/env python3
"""
Export MIT AOT inpainter to Core ML (runs on Apple Neural Engine / Metal GPU).

Full-precision FP32 first (same as Android ONNX「全量转」); quantize later if needed.

I/O match ONNX / Android ORT:
  image/mask float32 NCHW [0,1] → erased float32 NCHW [0,1]

Usage:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/export_aot_coreml.py \\
    --size 384 --smoke \\
    --image ../manga-translate-native/result/batch_hana_timing/005_005/page_work.jpg \\
    --mask  ../manga-translate-native/result/batch_hana_timing/005_005/mask_final.png

Note: coremltools 9+ no longer imports ONNX; we convert from Torch after
baking ScaledWS* weights (var_mean is unsupported in the PyTorch→MIL path).
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
        x = img * 2.0 - 1.0
        x = x * (1.0 - mask)
        pred = self.generator(x, mask)
        out = pred * mask + (1.0 - mask) * x
        return (out + 1.0) * 0.5


def bake_weight_standardization(module: nn.Module) -> nn.Module:
    """
    Fold ScaledWS* runtime var_mean into fixed Conv2d / ConvTranspose2d weights.

    coremltools cannot convert torch.var_mean (used by ScaledWSConv2d.get_weight).
    At eval time weights are constant, so baking is numerically equivalent.
    """
    from manga_translator.inpainting.inpainting_aot import ScaledWSConv2d, ScaledWSTransposeConv2d

    for name, child in list(module.named_children()):
        if isinstance(child, ScaledWSConv2d):
            baked = nn.Conv2d(
                child.in_channels,
                child.out_channels,
                child.kernel_size,
                stride=child.stride,
                padding=child.padding,
                dilation=child.dilation,
                groups=child.groups,
                bias=child.bias is not None,
            )
            with torch.no_grad():
                baked.weight.copy_(child.get_weight())
                if child.bias is not None:
                    baked.bias.copy_(child.bias)
            setattr(module, name, baked)
        elif isinstance(child, ScaledWSTransposeConv2d):
            baked = nn.ConvTranspose2d(
                child.in_channels,
                child.out_channels,
                child.kernel_size,
                stride=child.stride,
                padding=child.padding,
                output_padding=child.output_padding,
                groups=child.groups,
                bias=child.bias is not None,
                dilation=child.dilation,
            )
            with torch.no_grad():
                baked.weight.copy_(child.get_weight())
                if child.bias is not None:
                    baked.bias.copy_(child.bias)
            setattr(module, name, baked)
        else:
            bake_weight_standardization(child)
    return module


def _load(image_path: Path, mask_path: Path, size: int):
    image = cv2.cvtColor(cv2.imread(str(image_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    h0, w0 = image.shape[:2]
    image = cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR)
    mask = cv2.resize(mask, (size, size), interpolation=cv2.INTER_LINEAR)
    img_t = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    mask_t = (torch.from_numpy(mask).unsqueeze(0).unsqueeze(0).float() / 255.0 >= 0.5).float()
    return img_t, mask_t, (h0, w0)


def _compose_full(erased_nchw: np.ndarray, image_path: Path, mask_path: Path, orig_hw):
    erased = (np.clip(erased_nchw[0].transpose(1, 2, 0), 0, 1) * 255).astype(np.uint8)
    erased_full = cv2.resize(erased, (orig_hw[1], orig_hw[0]))
    mask_full = cv2.imread(str(mask_path), 0)
    mask_bin = (mask_full >= 127).astype(np.uint8)[:, :, None]
    orig = cv2.cvtColor(cv2.imread(str(image_path)), cv2.COLOR_BGR2RGB)
    return erased_full * mask_bin + orig * (1 - mask_bin)


def _export_from_torch(wrapper: nn.Module, size: int, ml_path: Path, minimum_deployment_target):
    import coremltools as ct

    dummy_img = torch.rand(1, 3, size, size)
    dummy_mask = (torch.rand(1, 1, size, size) > 0.7).float()
    wrapper.eval()
    with torch.no_grad():
        traced = torch.jit.trace(wrapper, (dummy_img, dummy_mask))

    print(f"Converting traced Torch → {ml_path} …")
    t0 = time.perf_counter()
    mlmodel = ct.convert(
        traced,
        inputs=[
            ct.TensorType(name="image", shape=(1, 3, size, size), dtype=np.float32),
            ct.TensorType(name="mask", shape=(1, 1, size, size), dtype=np.float32),
        ],
        outputs=[ct.TensorType(name="erased", dtype=np.float32)],
        convert_to="mlprogram",
        minimum_deployment_target=minimum_deployment_target,
        compute_precision=ct.precision.FLOAT32,
    )
    print(f"  convert {time.perf_counter() - t0:.2f}s")
    mlmodel.save(str(ml_path))
    return mlmodel


def _predict(mlmodel, img_np: np.ndarray, mask_np: np.ndarray):
    # coremltools returns dict keyed by output name
    out = mlmodel.predict({"image": img_np, "mask": mask_np})
    # Prefer known name; otherwise first array-like value
    if "erased" in out:
        return np.asarray(out["erased"])
    for v in out.values():
        arr = np.asarray(v)
        if arr.ndim >= 3:
            return arr
    raise RuntimeError(f"Unexpected Core ML outputs: {list(out.keys())}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, default=Path("models/inpainting/inpainting.ckpt"))
    ap.add_argument("--size", type=int, default=384)
    ap.add_argument("--out-dir", type=Path, default=Path("result/lama_coreml"))
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--image", type=Path, default=None)
    ap.add_argument("--mask", type=Path, default=None)
    ap.add_argument(
        "--ios-target",
        type=str,
        default="iOS16",
        choices=("iOS15", "iOS16", "iOS17"),
        help="Minimum Core ML deployment target (mlprogram).",
    )
    args = ap.parse_args()
    if args.size % 8 != 0:
        raise SystemExit("--size must be multiple of 8")

    import coremltools as ct

    target_map = {
        "iOS15": ct.target.iOS15,
        "iOS16": ct.target.iOS16,
        "iOS17": ct.target.iOS17,
    }
    minimum_deployment_target = target_map[args.ios_target]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    ml_path = args.out_dir / f"aot_{args.size}.mlpackage"

    from manga_translator.inpainting.inpainting_aot import AOTGenerator

    print(f"Loading {args.ckpt}…")
    gen = AOTGenerator()
    sd = torch.load(str(args.ckpt), map_location="cpu")
    gen.load_state_dict(sd["model"] if "model" in sd else sd)
    gen.eval()
    print("Baking ScaledWS* → Conv2d/ConvTranspose2d (Core ML has no var_mean)…")
    bake_weight_standardization(gen)
    wrapper = AotEraseOnnx(gen).eval()
    mlmodel = _export_from_torch(wrapper, args.size, ml_path, minimum_deployment_target)
    source = f"torch_baked:{args.ckpt}"

    size_mb = sum(p.stat().st_size for p in ml_path.rglob("*") if p.is_file()) / 1e6
    print(f"Wrote {ml_path} ({size_mb:.1f} MB files)")

    meta = {
        "kind": "aot",
        "source": source,
        "size": args.size,
        "coreml": str(ml_path),
        "compute_precision": "FLOAT32",
        "minimum_deployment_target": args.ios_target,
        "inputs": {"image": "float32 NCHW [0,1]", "mask": "float32 NCHW {0,1}"},
        "note": "Core ML mlprogram; Apple runtime uses Neural Engine / Metal GPU (ComputeUnits.ALL).",
    }

    if args.smoke:
        if args.image is None or args.mask is None:
            raise SystemExit("--smoke requires --image and --mask")
        img_t, mask_t, orig_hw = _load(args.image, args.mask, args.size)
        img_np = img_t.numpy()
        mask_np = mask_t.numpy()

        with torch.no_grad():
            t0 = time.perf_counter()
            pt = wrapper(img_t, mask_t).numpy()
            pt_ms = (time.perf_counter() - t0) * 1000

        # Warmup + timed Core ML predict (ALL = CPU+GPU+ANE / Metal path)
        _predict(mlmodel, img_np, mask_np)
        t0 = time.perf_counter()
        cml_out = _predict(mlmodel, img_np, mask_np)
        cml_ms = (time.perf_counter() - t0) * 1000

        # Normalize shape to NCHW
        if cml_out.ndim == 3:
            cml_out = cml_out[None, ...]
        # Some converters emit NHWC
        if cml_out.shape[1] not in (1, 3) and cml_out.shape[-1] == 3:
            cml_out = cml_out.transpose(0, 3, 1, 2)

        diff = np.abs(pt - cml_out)
        meta["smoke"] = {
            "ref_ms": round(pt_ms, 2) if pt_ms is not None else None,
            "coreml_ms": round(cml_ms, 2),
            "max_abs_diff": float(diff.max()),
            "mean_abs_diff": float(diff.mean()),
            "orig_hw": list(orig_hw),
            "coreml_out_shape": list(cml_out.shape),
        }
        comp = _compose_full(cml_out, args.image, args.mask, orig_hw)
        out_png = args.out_dir / f"smoke_aot_coreml_{args.size}.png"
        cv2.imwrite(str(out_png), cv2.cvtColor(comp.astype(np.uint8), cv2.COLOR_RGB2BGR))
        print("Smoke:", json.dumps(meta["smoke"], indent=2))
        print("Wrote", out_png)

    (args.out_dir / f"export_aot_coreml_{args.size}_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n"
    )
    print("Wrote", args.out_dir / f"export_aot_coreml_{args.size}_meta.json")


if __name__ == "__main__":
    main()
