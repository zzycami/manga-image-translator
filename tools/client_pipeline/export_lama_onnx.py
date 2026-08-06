#!/usr/bin/env python3
"""
Export MIT lama_large (lama_large_512px.ckpt) to ONNX for on-device erase.

torch.onnx.export cannot emit aten::fft_rfftn (opset 17). This script patches
FourierUnit.forward with an ONNX-friendly matmul DFT (FourierUnitJIT pattern).

Usage:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/export_lama_onnx.py \\
    --size 512 --out-dir result/lama_onnx --smoke \\
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
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Matmul DFT (ortho), fixed to 2D real FFT used by FourierUnit
# ---------------------------------------------------------------------------

def rfft_ortho(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """RFFT along last dim, ortho norm. x: (..., N) -> (..., N//2+1) real/imag."""
    n = x.shape[-1]
    device, dtype = x.device, torch.float32
    n_idx = torch.arange(n, device=device, dtype=dtype)
    k_idx = torch.arange(n // 2 + 1, device=device, dtype=dtype)
    angle = -2 * torch.pi * n_idx[:, None] * k_idx / float(n)
    cos_m = torch.cos(angle)
    sin_m = torch.sin(angle)
    xf = x.to(dtype)
    real = torch.matmul(xf, cos_m)
    imag = torch.matmul(xf, sin_m)
    scale = float(n) ** 0.5
    return real / scale, imag / scale


def fft_ortho(real: torch.Tensor, imag: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Complex FFT along last dim, ortho norm."""
    n = real.shape[-1]
    device, dtype = real.device, torch.float32
    n_idx = torch.arange(n, device=device, dtype=dtype)
    k = n_idx.unsqueeze(1)
    angle = -2 * torch.pi * k * n_idx / float(n)
    cos_m = torch.cos(angle)
    sin_m = torch.sin(angle)
    r = real.to(dtype).unsqueeze(-1)
    i = imag.to(dtype).unsqueeze(-1)
    out_r = torch.matmul(cos_m, r) - torch.matmul(sin_m, i)
    out_i = torch.matmul(sin_m, r) + torch.matmul(cos_m, i)
    scale = float(n) ** 0.5
    return out_r.squeeze(-1) / scale, out_i.squeeze(-1) / scale


def ifft_ortho(real: torch.Tensor, imag: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Complex IFFT along last dim, ortho norm."""
    n = real.shape[-1]
    device, dtype = real.device, torch.float32
    n_idx = torch.arange(n, device=device, dtype=dtype)
    k = n_idx.unsqueeze(1)
    angle = 2 * torch.pi * k * n_idx / float(n)
    cos_m = torch.cos(angle)
    sin_m = torch.sin(angle)
    r = real.to(dtype).unsqueeze(-1)
    i = imag.to(dtype).unsqueeze(-1)
    out_r = torch.matmul(cos_m, r) - torch.matmul(sin_m, i)
    out_i = torch.matmul(sin_m, r) + torch.matmul(cos_m, i)
    scale = float(n) ** 0.5
    return out_r.squeeze(-1) / scale, out_i.squeeze(-1) / scale


def rfft2_ortho(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """2D RFFT over last two dims (H, W)."""
    # FFT along W (last)
    real, imag = rfft_ortho(x)
    # FFT along H: move H to last
    real = real.transpose(-2, -1)
    imag = imag.transpose(-2, -1)
    real, imag = fft_ortho(real, imag)
    real = real.transpose(-2, -1)
    imag = imag.transpose(-2, -1)
    return real, imag


def irfft2_ortho(real: torch.Tensor, imag: torch.Tensor, h: int, w: int) -> torch.Tensor:
    """2D IRFFT; real/imag are rfft2 half-spectrum (…, H, W//2+1)."""
    # IFFT along H
    real = real.transpose(-2, -1)
    imag = imag.transpose(-2, -1)
    real, imag = ifft_ortho(real, imag)
    real = real.transpose(-2, -1)
    imag = imag.transpose(-2, -1)
    # Hermitian expand along W then IFFT
    # spectrum length along W is w//2+1
    # For even w: indices 1 .. w//2-1 flipped (exclude Nyquist at w//2)
    # rfft length = w//2+1; full = [0 .. w//2] + conj(flip(1 .. w//2-1))
    if w % 2 == 0:
        real_ext = torch.cat([real, torch.flip(real[..., 1:-1], dims=[-1])], dim=-1)
        imag_ext = torch.cat([imag, -torch.flip(imag[..., 1:-1], dims=[-1])], dim=-1)
    else:
        real_ext = torch.cat([real, torch.flip(real[..., 1:], dims=[-1])], dim=-1)
        imag_ext = torch.cat([imag, -torch.flip(imag[..., 1:], dims=[-1])], dim=-1)
    out_r, _ = ifft_ortho(real_ext, imag_ext)
    return out_r


def patch_fourier_unit_for_onnx() -> None:
    from manga_translator.inpainting import inpainting_lama_mpe as m

    def forward_exportable(self, x: torch.Tensor) -> torch.Tensor:
        batch = x.shape[0]
        if getattr(self, "spatial_scale_factor", None) is not None:
            orig_size = x.shape[-2:]
            x = F.interpolate(
                x,
                scale_factor=self.spatial_scale_factor,
                mode=self.spatial_scale_mode,
                align_corners=False,
            )
        else:
            orig_size = None

        h, w = x.shape[-2:]
        ffted_real, ffted_imag = rfft2_ortho(x)
        ffted = torch.stack((ffted_real, ffted_imag), dim=-1)
        ffted = ffted.permute(0, 1, 4, 2, 3).contiguous()
        ffted = ffted.view(batch, -1, ffted.size(-2), ffted.size(-1))

        if getattr(self, "spectral_pos_encoding", False):
            height, width = ffted.shape[-2:]
            coords_vert = torch.linspace(0, 1, height, device=ffted.device)[None, None, :, None].expand(
                batch, 1, height, width
            )
            coords_hor = torch.linspace(0, 1, width, device=ffted.device)[None, None, None, :].expand(
                batch, 1, height, width
            )
            ffted = torch.cat((coords_vert, coords_hor, ffted), dim=1)

        ffted = self.conv_layer(ffted)
        ffted = self.relu(self.bn(ffted))
        ffted = ffted.view(batch, -1, 2, ffted.size(-2), ffted.size(-1)).permute(0, 1, 3, 4, 2).contiguous()
        out = irfft2_ortho(ffted[..., 0], ffted[..., 1], h, w)
        if orig_size is not None:
            out = F.interpolate(out, size=orig_size, mode=self.spatial_scale_mode, align_corners=False)
        return out

    m.FourierUnit.forward = forward_exportable


class LamaEraseOnnx(nn.Module):
    def __init__(self, generator: nn.Module):
        super().__init__()
        self.generator = generator

    def forward(self, img: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        img_m = img * (1.0 - mask)
        pred = self.generator(img_m, mask)
        return pred * mask + (1.0 - mask) * img_m


def _load_rgb_mask(image_path: Path, mask_path: Path, size: int):
    image = cv2.cvtColor(cv2.imread(str(image_path), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if image is None or mask is None:
        raise FileNotFoundError(f"image/mask missing: {image_path} {mask_path}")
    h0, w0 = image.shape[:2]
    image_r = cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR)
    mask_r = cv2.resize(mask, (size, size), interpolation=cv2.INTER_LINEAR)
    img_t = torch.from_numpy(image_r).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    mask_t = torch.from_numpy(mask_r).unsqueeze(0).unsqueeze(0).float() / 255.0
    mask_t = (mask_t >= 0.5).float()
    return img_t, mask_t, (h0, w0)


def _verify_dft_vs_torch():
    x = torch.randn(1, 8, 64, 64)
    ref = torch.fft.rfftn(x, dim=(-2, -1), norm="ortho")
    r, i = rfft2_ortho(x)
    got = torch.complex(r, i)
    err = (ref - got).abs().max().item()
    back = irfft2_ortho(r, i, 64, 64)
    # torch irfftn
    ref_back = torch.fft.irfftn(ref, s=(64, 64), dim=(-2, -1), norm="ortho")
    err2 = (back - ref_back).abs().max().item()
    print(f"DFT self-check: rfft max_err={err:.3e}  irfft max_err={err2:.3e}")
    if err > 1e-4 or err2 > 1e-4:
        raise RuntimeError("matmul DFT does not match torch.fft")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, default=Path("models/inpainting/lama_large_512px.ckpt"))
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--out-dir", type=Path, default=Path("result/lama_onnx"))
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--image", type=Path, default=None)
    ap.add_argument("--mask", type=Path, default=None)
    ap.add_argument("--skip-export", action="store_true")
    ap.add_argument("--compare-native-fft", action="store_true",
                    help="Before patch: run native model; after patch compare on same inputs")
    args = ap.parse_args()
    if args.size % 8 != 0:
        raise SystemExit("--size must be multiple of 8")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = args.out_dir / f"lama_large_{args.size}.onnx"

    _verify_dft_vs_torch()

    native_out = None
    if args.compare_native_fft and args.image and args.mask:
        from manga_translator.inpainting.inpainting_lama_mpe import load_lama_mpe

        print("Native-FFT reference forward…")
        lama_ref = load_lama_mpe(str(args.ckpt), device="cpu", use_mpe=False, large_arch=True)
        wrap_ref = LamaEraseOnnx(lama_ref.generator).eval()
        img_t, mask_t, _ = _load_rgb_mask(args.image, args.mask, args.size)
        with torch.no_grad():
            native_out = wrap_ref(img_t, mask_t).numpy()
        del lama_ref, wrap_ref

    patch_fourier_unit_for_onnx()
    from manga_translator.inpainting.inpainting_lama_mpe import load_lama_mpe

    print(f"Loading {args.ckpt} (patched FourierUnit)…")
    t0 = time.perf_counter()
    lama = load_lama_mpe(str(args.ckpt), device="cpu", use_mpe=False, large_arch=True)
    print(f"  load {time.perf_counter() - t0:.2f}s")
    wrapper = LamaEraseOnnx(lama.generator).eval()

    dummy_img = torch.rand(1, 3, args.size, args.size)
    dummy_mask = (torch.rand(1, 1, args.size, args.size) > 0.7).float()

    if not args.skip_export:
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
        mb = onnx_path.stat().st_size / 1e6
        print(f"  export {time.perf_counter() - t0:.2f}s  size={mb:.1f} MB")

    meta = {
        "ckpt": str(args.ckpt),
        "size": args.size,
        "opset": args.opset,
        "onnx": str(onnx_path),
        "inputs": {"image": "float32 NCHW [0,1]", "mask": "float32 NCHW {0,1}"},
        "output": "erased float32 NCHW [0,1]",
        "fft": "matmul DFT ortho (FourierUnitJIT-style)",
    }

    if args.smoke:
        if args.image is None or args.mask is None:
            raise SystemExit("--smoke requires --image and --mask")
        img_t, mask_t, orig_hw = _load_rgb_mask(args.image, args.mask, args.size)
        with torch.no_grad():
            t0 = time.perf_counter()
            pt_out = wrapper(img_t, mask_t)
            pt_ms = (time.perf_counter() - t0) * 1000
        pt_np = pt_out.numpy()

        if native_out is not None:
            d = np.abs(pt_np - native_out)
            meta["patch_vs_native_fft"] = {
                "max_abs_diff": float(d.max()),
                "mean_abs_diff": float(d.mean()),
            }
            print("patch vs native FFT:", meta["patch_vs_native_fft"])

        import onnxruntime as ort

        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        feeds = {"image": img_t.numpy(), "mask": mask_t.numpy()}
        sess.run(None, feeds)  # warmup
        t0 = time.perf_counter()
        ort_out = sess.run(None, feeds)[0]
        ort_ms = (time.perf_counter() - t0) * 1000
        diff = np.abs(pt_np - ort_out)
        meta["smoke"] = {
            "image": str(args.image),
            "mask": str(args.mask),
            "orig_hw": list(orig_hw),
            "pytorch_patched_ms": round(pt_ms, 2),
            "ort_cpu_ms": round(ort_ms, 2),
            "max_abs_diff": float(diff.max()),
            "mean_abs_diff": float(diff.mean()),
        }
        print("Smoke:", json.dumps(meta["smoke"], indent=2))

        erased = (np.clip(ort_out[0].transpose(1, 2, 0), 0, 1) * 255).astype(np.uint8)
        erased_full = cv2.resize(erased, (orig_hw[1], orig_hw[0]), interpolation=cv2.INTER_LINEAR)
        mask_full = cv2.imread(str(args.mask), cv2.IMREAD_GRAYSCALE)
        mask_bin = (mask_full >= 127).astype(np.uint8)[:, :, None]
        orig = cv2.cvtColor(cv2.imread(str(args.image), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        composited = erased_full * mask_bin + orig * (1 - mask_bin)
        out_png = args.out_dir / "smoke_erased.png"
        cv2.imwrite(str(out_png), cv2.cvtColor(composited.astype(np.uint8), cv2.COLOR_RGB2BGR))
        print(f"Wrote {out_png}")

    (args.out_dir / "export_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("Wrote", args.out_dir / "export_meta.json")


if __name__ == "__main__":
    main()
