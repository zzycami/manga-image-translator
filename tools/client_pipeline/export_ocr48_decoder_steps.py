#!/usr/bin/env python3
"""Export OCR48 decoder as one ONNX file per autoregressive step (baked step index).

Each file is ~100MB (full decoder weights). Suitable for parity smoke / native
beam; production should use a shared-weight dynamic-step export or LibTorch.

Example:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/export_ocr48_decoder_steps.py \\
      --start 0 --end 24 --out result/ocr_coreml/dec_steps
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
import torch.nn as nn

from manga_translator.ocr.model_48px import OCR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=8, help="exclusive")
    ap.add_argument("--out", type=Path, default=Path("result/ocr_coreml/dec_steps"))
    ap.add_argument("--ckpt", type=Path, default=Path("models/ocr/ocr_ar_48px.ckpt"))
    ap.add_argument(
        "--alphabet", type=Path, default=Path("models/ocr/alphabet-all-v7.txt")
    )
    ap.add_argument("--max-seq-cache", type=int, default=64)
    ap.add_argument("--fw", type=int, default=128)
    args = ap.parse_args()

    with open(args.alphabet) as f:
        dictionary = [line[:-1] for line in f]
    ocr = OCR(dictionary, 768).eval()
    ocr.load_state_dict(torch.load(args.ckpt, map_location="cpu"))

    e = 320
    n_dec = 5
    args.out.mkdir(parents=True, exist_ok=True)

    for step in range(args.start, args.end):
        class FixedStep(nn.Module):
            def __init__(self, model: OCR, s: int):
                super().__init__()
                self.m = model
                self.s = s

            def forward(self, tok, cached, memory, memory_mask_f):
                emb = self.m.embd(tok.long()).unsqueeze(1)
                decoded, cached2 = self.m.decoders(
                    emb, cached, memory, memory_mask_f > 0.5, self.s
                )
                logits = self.m.pred(self.m.pred1(decoded))
                return logits, cached2

        mod = FixedStep(ocr, step).eval()
        tok = torch.ones(1, dtype=torch.long)
        cached = torch.zeros(1, n_dec + 1, args.max_seq_cache, e)
        memory = torch.randn(1, args.fw, e)
        mm = torch.zeros(1, args.fw)
        path = args.out / f"step_{step:03d}.onnx"
        t0 = time.perf_counter()
        torch.onnx.export(
            mod,
            (tok, cached, memory, mm),
            str(path),
            input_names=["tok", "cached", "memory", "memory_mask"],
            output_names=["logits", "cached_out"],
            opset_version=17,
            dynamo=False,
        )
        print(
            f"wrote {path.name} {path.stat().st_size / 1e6:.1f}MB "
            f"in {time.perf_counter() - t0:.1f}s"
        )

    meta = {
        "max_seq_exported": args.end,
        "start": args.start,
        "end_exclusive": args.end,
        "fw": args.fw,
        "max_seq_cache": args.max_seq_cache,
        "beams_k": 5,
        "note": "~100MB per step; prod needs shared-weight dynamic step or LibTorch",
    }
    (args.out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print("meta", meta)


if __name__ == "__main__":
    main()
