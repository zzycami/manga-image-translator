#!/usr/bin/env python3
"""
Export MIT ocr_ar_48px pieces to Core ML (iOS16+ mlprogram).

The production path uses beam search (Python loops) — that does not map cleanly
to a single Core ML graph. This spike exports:

  1) encoder: backbone + transformer encoders → memory [1, W/4, 320]
  2) decoder_step0: one decode step with step==0 baked (proof that logits+cache export)

Greedy / beam decoding on device should call decoder repeatedly from Swift
(with either a step-aware graph later, or LibTorch/ORT for the decoder).

Usage:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/export_ocr48_coreml.py --smoke
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import einops
import numpy as np
import torch
import torch.nn as nn

H = 48
E = 320
N_DEC = 5
START, END = 1, 2


class OCREncoderF(nn.Module):
    def __init__(self, ocr: nn.Module):
        super().__init__()
        self.ocr = ocr

    def forward(self, img: torch.Tensor, encoder_mask_f: torch.Tensor) -> torch.Tensor:
        encoder_mask = encoder_mask_f > 0.5
        memory = self.ocr.backbone(img)
        memory = einops.rearrange(memory, "N C 1 W -> N W C")
        return self.ocr.encoders(memory, encoder_mask)


class OCRDecoderStep0(nn.Module):
    """Decoder step with step index fixed at 0 (for Core ML convert proof)."""

    def __init__(self, ocr: nn.Module, max_seq: int):
        super().__init__()
        self.ocr = ocr
        self.max_seq = max_seq

    def forward(
        self,
        tok: torch.Tensor,
        cached: torch.Tensor,
        memory: torch.Tensor,
        memory_mask_f: torch.Tensor,
    ):
        emb = self.ocr.embd(tok.long()).unsqueeze(1)
        decoded, cached2 = self.ocr.decoders(
            emb, cached, memory, memory_mask_f > 0.5, 0
        )
        logits = self.ocr.pred(self.ocr.pred1(decoded))
        return logits, cached2


def load_ocr(ckpt: Path, alphabet: Path):
    from manga_translator.ocr.model_48px import OCR

    with open(alphabet, encoding="utf-8") as fp:
        dictionary = [s[:-1] for s in fp.readlines()]
    model = OCR(dictionary, 768)
    sd = torch.load(str(ckpt), map_location="cpu")
    model.load_state_dict(sd)
    model.eval()
    return model, dictionary


def export_encoder(model, w_max: int, out: Path, ios_target) -> Path:
    import coremltools as ct

    fw = w_max // 4
    enc = OCREncoderF(model).eval()
    dummy_img = torch.rand(1, 3, H, w_max)
    dummy_mask = torch.zeros(1, fw)
    with torch.no_grad():
        traced = torch.jit.trace(enc, (dummy_img, dummy_mask))
    ml = ct.convert(
        traced,
        inputs=[
            ct.TensorType(name="image", shape=(1, 3, H, w_max), dtype=np.float32),
            ct.TensorType(name="encoder_mask", shape=(1, fw), dtype=np.float32),
        ],
        outputs=[ct.TensorType(name="memory", dtype=np.float32)],
        convert_to="mlprogram",
        minimum_deployment_target=ios_target,
        compute_precision=ct.precision.FLOAT32,
    )
    path = out / f"ocr48_encoder_w{w_max}.mlpackage"
    ml.save(str(path))
    return path


def export_decoder_step0(model, w_max: int, max_seq: int, out: Path, ios_target) -> Path:
    import coremltools as ct

    fw = w_max // 4
    dec = OCRDecoderStep0(model, max_seq).eval()
    tok = torch.ones(1, dtype=torch.long)
    cached = torch.zeros(1, N_DEC + 1, max_seq, E)
    memory = torch.randn(1, fw, E)
    mmask = torch.zeros(1, fw)
    with torch.no_grad():
        traced = torch.jit.trace(dec, (tok, cached, memory, mmask))
    ml = ct.convert(
        traced,
        inputs=[
            ct.TensorType(name="tok", shape=(1,), dtype=np.int32),
            ct.TensorType(
                name="cached",
                shape=(1, N_DEC + 1, max_seq, E),
                dtype=np.float32,
            ),
            ct.TensorType(name="memory", shape=(1, fw, E), dtype=np.float32),
            ct.TensorType(name="memory_mask", shape=(1, fw), dtype=np.float32),
        ],
        outputs=[
            ct.TensorType(name="logits", dtype=np.float32),
            ct.TensorType(name="cached_out", dtype=np.float32),
        ],
        convert_to="mlprogram",
        minimum_deployment_target=ios_target,
        compute_precision=ct.precision.FLOAT32,
    )
    path = out / f"ocr48_decoder_step0_w{w_max}.mlpackage"
    ml.save(str(path))
    return path


def _package_mb(path: Path) -> float:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / 1e6


def strip_from_region(img_rgb: np.ndarray, region: dict) -> Optional[np.ndarray]:
    """MIT-style perspective crop to height=48 (honours vertical flag)."""
    from manga_translator.utils import Quadrilateral

    polys = region.get("polygons") or []
    if not polys:
        return None
    pts = np.array(polys[0], dtype=np.int32)
    q = Quadrilateral(pts, "", 1.0)
    direction = "v" if region.get("vertical") else "h"
    return q.get_transformed_region(img_rgb, direction, H)


def pad_strip(strip: np.ndarray, w_max: int) -> Tuple[np.ndarray, int]:
    canvas = np.zeros((H, w_max, 3), np.uint8)
    ww = min(strip.shape[1], w_max)
    canvas[:, :ww] = strip[:, :ww]
    return canvas, ww


def to_nchw(strip_u8: np.ndarray) -> torch.Tensor:
    # Match Model48pxOCR: (x - 127.5) / 127.5
    t = (torch.from_numpy(strip_u8).float() - 127.5) / 127.5
    return einops.rearrange(t, "h w c -> 1 c h w")


def idxs_to_text(dictionary: List[str], idxs: List[int]) -> str:
    seq: List[str] = []
    for i in idxs:
        if i == END:
            break
        if i == START:
            continue
        ch = dictionary[i]
        if ch.startswith("<") and ch.endswith(">"):
            if ch == "<SP>":
                seq.append(" ")
            continue
        seq.append(ch)
    return "".join(seq)


def beam_decode(model, img_nchw: torch.Tensor, width: int, max_seq: int = 128) -> str:
    with torch.no_grad():
        ret = model.infer_beam_batch_tensor(
            img_nchw, [width], beams_k=5, max_seq_length=max_seq
        )
    idxs = ret[0][0].tolist()
    return idxs_to_text(model.dictionary, idxs)


def smoke(
    model,
    dictionary: List[str],
    enc_ml_path: Path,
    w_max: int,
    image: Path,
    stages: Path,
    out_dir: Path,
):
    import coremltools as ct

    stages_j = json.loads(stages.read_text(encoding="utf-8"))
    img_bgr = cv2.imread(str(image))
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    ml_enc = ct.models.MLModel(str(enc_ml_path))

    rows = []
    fw = w_max // 4
    for i, region in enumerate(stages_j.get("regions") or []):
        strip = strip_from_region(img_rgb, region)
        if strip is None:
            continue
        # Beam path uses tight width (MIT); Core ML encoder needs fixed w_max pad.
        width = strip.shape[1]
        max_w = 4 * ((width + 7) // 4)
        region_u8 = np.zeros((H, max_w, 3), np.uint8)
        region_u8[:, :width] = strip
        nchw_beam = to_nchw(region_u8)

        padded, _ = pad_strip(strip, w_max)
        nchw = to_nchw(padded)
        mask_f = np.zeros((1, fw), np.float32)
        valid = (width + 3) // 4 + 2
        if valid < fw:
            mask_f[0, valid:] = 1.0

        t0 = time.perf_counter()
        with torch.no_grad():
            mem_pt = OCREncoderF(model)(nchw, torch.from_numpy(mask_f)).numpy()
        pt_enc_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        out = ml_enc.predict(
            {"image": nchw.numpy().astype(np.float32), "encoder_mask": mask_f}
        )
        mem_key = "memory" if "memory" in out else list(out.keys())[0]
        mem_ml = np.asarray(out[mem_key])
        ml_enc_ms = (time.perf_counter() - t0) * 1000
        max_abs = float(np.max(np.abs(mem_pt - mem_ml)))

        t0 = time.perf_counter()
        text_beam = beam_decode(model, nchw_beam, width)
        beam_ms = (time.perf_counter() - t0) * 1000

        mit_text = region.get("sourceText") or ""
        # Merged regions may contain multiple OCR lines; beam on one poly ≈ first line.
        prefix = mit_text.startswith(text_beam) if text_beam else False
        rows.append(
            {
                "i": i,
                "mit": mit_text,
                "beam_pt": text_beam,
                "exact": text_beam == mit_text,
                "prefix_of_mit": prefix,
                "encoder_max_abs": max_abs,
                "pt_enc_ms": round(pt_enc_ms, 1),
                "ml_enc_ms": round(ml_enc_ms, 1),
                "beam_ms": round(beam_ms, 1),
                "strip_w": width,
                "vertical": bool(region.get("vertical")),
            }
        )
        print(
            f"r{i}: encΔ={max_abs:.3e} ml_enc={ml_enc_ms:.0f}ms "
            f"beam={text_beam!r} mit={mit_text!r}"
        )

    summary = {
        "encoder": str(enc_ml_path),
        "w_max": w_max,
        "regions": rows,
        "exact_rate": (
            sum(1 for r in rows if r["exact"]) / len(rows) if rows else 0.0
        ),
        "prefix_rate": (
            sum(1 for r in rows if r["prefix_of_mit"]) / len(rows) if rows else 0.0
        ),
        "note": (
            "Core ML encoder vs PT; beam still PyTorch. "
            "stages.regions are often merged multi-line → beam on one polygon may be prefix only."
        ),
    }
    out_json = out_dir / "smoke_005.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out_json} exact_rate={summary['exact_rate']}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ckpt", type=Path, default=Path("models/ocr/ocr_ar_48px.ckpt"))
    ap.add_argument(
        "--alphabet", type=Path, default=Path("models/ocr/alphabet-all-v7.txt")
    )
    ap.add_argument("--w-max", type=int, default=512, help="Padded strip width")
    ap.add_argument("--max-seq", type=int, default=64)
    ap.add_argument("--out-dir", type=Path, default=Path("result/ocr_coreml"))
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument(
        "--image",
        type=Path,
        default=Path(
            "../manga-translate-native/result/batch_hana_timing/005_005/page_work.jpg"
        ),
    )
    ap.add_argument(
        "--stages",
        type=Path,
        default=Path(
            "result/bench_mit_stages_ab/simple_sort_20260808_205647/baseline/005_005.stages.json"
        ),
    )
    ap.add_argument(
        "--ios-target",
        default="iOS16",
        choices=("iOS15", "iOS16", "iOS17"),
    )
    args = ap.parse_args()
    if args.w_max % 4 != 0:
        raise SystemExit("--w-max must be multiple of 4")

    import coremltools as ct

    target = {
        "iOS15": ct.target.iOS15,
        "iOS16": ct.target.iOS16,
        "iOS17": ct.target.iOS17,
    }[args.ios_target]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Loading {args.ckpt}…")
    model, dictionary = load_ocr(args.ckpt, args.alphabet)

    t0 = time.perf_counter()
    enc_path = export_encoder(model, args.w_max, args.out_dir, target)
    print(f"encoder {enc_path} ({_package_mb(enc_path):.1f} MB) in {time.perf_counter()-t0:.1f}s")

    t0 = time.perf_counter()
    dec_path = export_decoder_step0(
        model, args.w_max, args.max_seq, args.out_dir, target
    )
    print(f"decoder_step0 {dec_path} ({_package_mb(dec_path):.1f} MB) in {time.perf_counter()-t0:.1f}s")

    meta = {
        "ckpt": str(args.ckpt),
        "alphabet": str(args.alphabet),
        "dict_size": len(dictionary),
        "w_max": args.w_max,
        "max_seq": args.max_seq,
        "encoder": str(enc_path),
        "decoder_step0": str(dec_path),
        "encoder_mb": round(_package_mb(enc_path), 1),
        "decoder_step0_mb": round(_package_mb(dec_path), 1),
        "ios_target": args.ios_target,
        "limitations": [
            "Beam search not in Core ML; device should greedy-loop or use ORT/LibTorch decoder",
            "decoder_step0 has step baked to 0 — only proves convert; full loop needs step-aware export or N step packages",
            "Axis-aligned bbox crops ≠ MIT quadrilateral warp — smoke texts may drift",
        ],
    }
    (args.out_dir / "export_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.smoke:
        if not args.image.is_file() or not args.stages.is_file():
            raise SystemExit(f"smoke needs --image and --stages (got {args.image}, {args.stages})")
        smoke(model, dictionary, enc_path, args.w_max, args.image, args.stages, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
