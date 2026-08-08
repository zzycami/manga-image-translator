#!/usr/bin/env python3
"""
On-device OCR quality path: ONNX encoder + PyTorch beam decode (beams_k=5).

Matches MIT `OCR.infer_beam_batch_tensor` after the encoder, so App can later
swap the PT decoder for ORT/C++ while keeping this beam algorithm.

Usage:
  PYTHONPATH=. ./venv/bin/python tools/client_pipeline/ocr48_beam_runtime.py \\
    --smoke-stages \\
    --image ../manga-translate-native/result/batch_hana_timing/005_005/page_work.jpg \\
    --stages result/bench_mit_stages_ab/simple_sort_20260808_205647/baseline/005_005.stages.json
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import einops
import numpy as np
import torch

H = 48
E = 320
START, END, PAD = 1, 2, 0


def idxs_to_text(dictionary: Sequence[str], idxs: Sequence[int]) -> str:
    seq: List[str] = []
    for i in idxs:
        if int(i) == END:
            break
        if int(i) == START:
            continue
        ch = dictionary[int(i)]
        if ch.startswith("<") and ch.endswith(">"):
            if ch == "<SP>":
                seq.append(" ")
            continue
        seq.append(ch)
    return "".join(seq)


def load_ocr_pt(ckpt: Path, alphabet: Path):
    from manga_translator.ocr.model_48px import OCR

    with open(alphabet, encoding="utf-8") as fp:
        dictionary = [s[:-1] for s in fp.readlines()]
    model = OCR(dictionary, 768)
    model.load_state_dict(torch.load(str(ckpt), map_location="cpu"))
    model.eval()
    return model, dictionary


class OrtEncoder:
    def __init__(self, onnx_path: Path, w_max: int = 512):
        import onnxruntime as ort

        self.w_max = w_max
        self.fw = w_max // 4
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(
            str(onnx_path), opts, providers=["CPUExecutionProvider"]
        )

    def encode(self, strip_u8: np.ndarray) -> Tuple[torch.Tensor, torch.Tensor, int]:
        """strip HxW×3 uint8 RGB → memory [1,fw,E], mask bool [1,fw], width."""
        assert strip_u8.shape[0] == H
        width = int(strip_u8.shape[1])
        if width > self.w_max:
            # Keep aspect: shrink to w_max (rare for bubble lines)
            strip_u8 = cv2.resize(strip_u8, (self.w_max, H), interpolation=cv2.INTER_AREA)
            width = self.w_max
        canvas = np.zeros((H, self.w_max, 3), np.uint8)
        canvas[:, :width] = strip_u8
        nchw = (canvas.astype(np.float32) - 127.5) / 127.5
        nchw = einops.rearrange(nchw, "h w c -> 1 c h w")
        mask_f = np.zeros((1, self.fw), np.float32)
        valid = (width + 3) // 4 + 2
        if valid < self.fw:
            mask_f[0, valid:] = 1.0
        out = self.sess.run(
            None, {"image": nchw.astype(np.float32), "encoder_mask": mask_f}
        )[0]
        memory = torch.from_numpy(np.asarray(out))
        input_mask = torch.from_numpy(mask_f > 0.5)
        return memory, input_mask, width


def beam_from_memory(
    model,
    memory: torch.Tensor,
    input_mask: torch.Tensor,
    beams_k: int = 5,
    max_finished_hypos: int = 2,
    max_seq_length: int = 255,
) -> Tuple[torch.Tensor, float, torch.Tensor]:
    """
    Copy of OCR.infer_beam_batch_tensor from after encoder (N=1).
    Returns (token_idxs_without_start, prob, last_cached_row).
    """
    N = memory.size(0)
    assert N == 1, "runtime smoke uses N=1; batch later"

    out_idx = torch.full((N, 1), START, dtype=torch.long)
    cached_activations = torch.zeros(N, len(model.decoders) + 1, max_seq_length, E)
    log_probs = torch.zeros(N, 1)
    idx_embedded = model.embd(out_idx[:, -1:])

    decoded, cached_activations = model.decoders(
        idx_embedded, cached_activations, memory, input_mask, 0
    )
    pred_char_logprob = model.pred(model.pred1(decoded)).log_softmax(-1)
    pred_chars_values, pred_chars_index = torch.topk(pred_char_logprob, beams_k, dim=1)

    out_idx = torch.cat(
        [
            out_idx.unsqueeze(1).expand(-1, beams_k, -1),
            pred_chars_index.unsqueeze(-1),
        ],
        dim=-1,
    ).reshape(-1, 2)
    log_probs = pred_chars_values.view(-1, 1)
    memory = memory.repeat_interleave(beams_k, dim=0)
    input_mask = input_mask.repeat_interleave(beams_k, dim=0)
    cached_activations = cached_activations.repeat_interleave(beams_k, dim=0)
    batch_index = torch.arange(N).repeat_interleave(beams_k, dim=0)

    finished_hypos: Dict[int, Tuple] = {}
    N_remaining = N

    for step in range(1, max_seq_length):
        idx_embedded = model.embd(out_idx[:, -1:])
        decoded, cached_activations = model.decoders(
            idx_embedded, cached_activations, memory, input_mask, step
        )
        pred_char_logprob = model.pred(model.pred1(decoded)).log_softmax(-1)
        pred_chars_values, pred_chars_index = torch.topk(
            pred_char_logprob, beams_k, dim=1
        )

        finished = out_idx[:, -1] == END
        pred_chars_values = pred_chars_values.clone()
        pred_chars_index = pred_chars_index.clone()
        pred_chars_values[finished] = 0
        pred_chars_index[finished] = END

        new_out_idx = out_idx.unsqueeze(1).expand(-1, beams_k, -1)
        new_out_idx = torch.cat(
            [new_out_idx, pred_chars_index.unsqueeze(-1)], dim=-1
        )
        new_out_idx = new_out_idx.view(-1, step + 2)
        new_log_probs = (
            log_probs.unsqueeze(1).expand(-1, beams_k, -1)
            + pred_chars_values.unsqueeze(-1)
        ).view(-1, 1)

        new_out_idx = new_out_idx.view(N_remaining, -1, step + 2)
        new_log_probs = new_log_probs.view(N_remaining, -1)
        batch_topk_log_probs, batch_topk_indices = new_log_probs.topk(beams_k, dim=1)

        expanded_topk_indices = batch_topk_indices.unsqueeze(-1).expand(
            -1, -1, new_out_idx.shape[-1]
        )
        out_idx = torch.gather(new_out_idx, 1, expanded_topk_indices).reshape(
            -1, step + 2
        )
        log_probs = batch_topk_log_probs.view(-1, 1)

        finished = (out_idx[:, -1] == END).view(N_remaining, beams_k)
        finished_counts = finished.sum(dim=1)
        finished_batch_indices = (
            finished_counts >= max_finished_hypos
        ).nonzero(as_tuple=False).squeeze()

        if finished_batch_indices.numel() == 0:
            continue
        if finished_batch_indices.dim() == 0:
            finished_batch_indices = finished_batch_indices.unsqueeze(0)

        for idx in finished_batch_indices:
            batch_log_probs = batch_topk_log_probs[idx]
            best_beam_idx = batch_log_probs.argmax()
            finished_hypos[int(batch_index[beams_k * idx].item())] = (
                out_idx[idx * beams_k + best_beam_idx],
                float(torch.exp(batch_log_probs[best_beam_idx]).item()),
                cached_activations[idx * beams_k + best_beam_idx],
            )

        remaining_indexs = []
        finished_set = set(int(x) for x in finished_batch_indices.view(-1).tolist())
        for i in range(N_remaining):
            if i not in finished_set:
                for j in range(beams_k):
                    remaining_indexs.append(i * beams_k + j)

        if not remaining_indexs:
            break

        N_remaining = int(len(remaining_indexs) / beams_k)
        sel = torch.tensor(remaining_indexs, dtype=torch.long)
        out_idx = out_idx.index_select(0, sel)
        log_probs = log_probs.index_select(0, sel)
        memory = memory.index_select(0, sel)
        cached_activations = cached_activations.index_select(0, sel)
        input_mask = input_mask.index_select(0, sel)
        batch_index = batch_index.index_select(0, sel)

    if len(finished_hypos) < N:
        for i in range(N):
            if i not in finished_hypos:
                sample_indices = (batch_index == i).nonzero(as_tuple=True)[0]
                if sample_indices.numel() > 0:
                    best_hypo_index = sample_indices[0]
                    finished_hypos[i] = (
                        out_idx[best_hypo_index],
                        float(torch.exp(log_probs[best_hypo_index]).item()),
                        cached_activations[best_hypo_index],
                    )
                else:
                    finished_hypos[i] = (
                        torch.tensor([END]),
                        0.0,
                        torch.zeros(cached_activations.shape[1:]),
                    )

    final_idx, prob, decoded = finished_hypos[0]
    return final_idx[1:], prob, decoded


class Ocr48BeamRuntime:
    def __init__(
        self,
        ckpt: Path,
        alphabet: Path,
        encoder_onnx: Path,
        w_max: int = 512,
        beams_k: int = 5,
    ):
        self.model, self.dictionary = load_ocr_pt(ckpt, alphabet)
        self.encoder = OrtEncoder(encoder_onnx, w_max=w_max)
        self.beams_k = beams_k

    @torch.no_grad()
    def ocr_strip(self, strip_u8: np.ndarray) -> Tuple[str, float, dict]:
        t0 = time.perf_counter()
        memory, input_mask, width = self.encoder.encode(strip_u8)
        enc_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        idxs, prob, _ = beam_from_memory(
            self.model, memory, input_mask, beams_k=self.beams_k
        )
        beam_ms = (time.perf_counter() - t0) * 1000
        text = idxs_to_text(self.dictionary, idxs.tolist())
        return text, prob, {"enc_ms": enc_ms, "beam_ms": beam_ms, "width": width}

    @torch.no_grad()
    def ocr_strip_pt_full(self, strip_u8: np.ndarray) -> str:
        """Reference: full PyTorch encoder+beam (same pad as ORT w_max path)."""
        width = strip_u8.shape[1]
        w_max = self.encoder.w_max
        if width > w_max:
            strip_u8 = cv2.resize(strip_u8, (w_max, H), interpolation=cv2.INTER_AREA)
            width = w_max
        max_w = 4 * ((width + 7) // 4)
        region = np.zeros((1, H, max_w, 3), np.uint8)
        region[0, :, :width] = strip_u8
        t = (torch.from_numpy(region).float() - 127.5) / 127.5
        t = einops.rearrange(t, "n h w c -> n c h w")
        ret = self.model.infer_beam_batch_tensor(
            t, [width], beams_k=self.beams_k, max_seq_length=255
        )
        return idxs_to_text(self.dictionary, ret[0][0].tolist())


def strips_from_region(img_rgb: np.ndarray, region: dict) -> List[np.ndarray]:
    """One 48px strip per polygon (textline). Merged regions have multiple polys."""
    from manga_translator.utils import Quadrilateral

    polys = region.get("polygons") or []
    direction = "v" if region.get("vertical") else "h"
    out: List[np.ndarray] = []
    for poly in polys:
        pts = np.array(poly, dtype=np.int32)
        q = Quadrilateral(pts, "", 1.0)
        out.append(q.get_transformed_region(img_rgb, direction, H))
    return out


def strip_from_region(img_rgb: np.ndarray, region: dict) -> Optional[np.ndarray]:
    """Deprecated for quality: only first polygon. Prefer strips_from_region."""
    strips = strips_from_region(img_rgb, region)
    return strips[0] if strips else None


def smoke_stages(
    runtime: Ocr48BeamRuntime,
    image: Path,
    stages: Path,
    out: Path,
) -> dict:
    stages_j = json.loads(stages.read_text(encoding="utf-8"))
    img = cv2.cvtColor(cv2.imread(str(image)), cv2.COLOR_BGR2RGB)
    rows = []
    for i, region in enumerate(stages_j.get("regions") or []):
        strips = strips_from_region(img, region)
        if not strips:
            continue
        line_texts_ort: List[str] = []
        line_texts_pt: List[str] = []
        probs: List[float] = []
        enc_ms = 0.0
        beam_ms = 0.0
        for strip in strips:
            text_ort, prob, timing = runtime.ocr_strip(strip)
            text_pt = runtime.ocr_strip_pt_full(strip)
            line_texts_ort.append(text_ort)
            line_texts_pt.append(text_pt)
            probs.append(float(prob))
            enc_ms += float(timing["enc_ms"])
            beam_ms += float(timing["beam_ms"])
        text_ort = "".join(line_texts_ort)
        text_pt = "".join(line_texts_pt)
        mit = region.get("sourceText") or ""
        rows.append(
            {
                "i": i,
                "n_lines": len(strips),
                "mit": mit,
                "ort_beam": text_ort,
                "pt_beam": text_pt,
                "line_ort": line_texts_ort,
                "ort_eq_pt": text_ort == text_pt,
                "ort_eq_mit": text_ort == mit,
                "ort_prefix_mit": bool(text_ort and mit.startswith(text_ort)),
                "prob": round(float(min(probs) if probs else 0.0), 4),
                "enc_ms": round(enc_ms, 2),
                "beam_ms": round(beam_ms, 2),
                "width": int(strips[0].shape[1]),
            }
        )
        print(
            f"r{i}: lines={len(strips)} ort_eq_pt={text_ort == text_pt} "
            f"ort_eq_mit={text_ort == mit} "
            f"ort={text_ort!r} mit={mit!r} "
            f"enc={enc_ms:.0f}ms beam={beam_ms:.0f}ms"
        )
    summary = {
        "image": str(image),
        "stages": str(stages),
        "beams_k": runtime.beams_k,
        "encoder": "onnxruntime",
        "decoder": "pytorch_beam",
        "rows": rows,
        "ort_eq_pt_rate": (
            sum(1 for r in rows if r["ort_eq_pt"]) / len(rows) if rows else 0.0
        ),
        "ort_eq_mit_rate": (
            sum(1 for r in rows if r["ort_eq_mit"]) / len(rows) if rows else 0.0
        ),
        "ort_prefix_mit_rate": (
            sum(1 for r in rows if r["ort_prefix_mit"]) / len(rows) if rows else 0.0
        ),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"wrote {out} ort_eq_pt={summary['ort_eq_pt_rate']} "
        f"prefix_mit={summary['ort_prefix_mit_rate']}"
    )
    return summary


def smoke_three_pages(runtime: Ocr48BeamRuntime, out_dir: Path) -> dict:
    base = Path("../manga-translate-native/result/batch_hana_timing")
    stages_dir = Path(
        "result/bench_mit_stages_ab/simple_sort_20260808_205647/baseline"
    )
    pages = []
    for name in ("005_005", "007_007", "033_033"):
        summary = smoke_stages(
            runtime,
            base / name / "page_work.jpg",
            stages_dir / f"{name}.stages.json",
            out_dir / f"{name}.json",
        )
        pages.append(
            {
                "page": name,
                "ort_eq_pt_rate": summary["ort_eq_pt_rate"],
                "ort_eq_mit_rate": summary["ort_eq_mit_rate"],
                "ort_prefix_mit_rate": summary["ort_prefix_mit_rate"],
                "n": len(summary["rows"]),
            }
        )
    all_sum = {
        "pages": pages,
        "ort_eq_pt_all": all(p["ort_eq_pt_rate"] == 1.0 for p in pages),
        "ort_eq_mit_all": all(p["ort_eq_mit_rate"] == 1.0 for p in pages),
        "mean_prefix_mit": sum(p["ort_prefix_mit_rate"] for p in pages) / len(pages),
        "mean_eq_mit": sum(p["ort_eq_mit_rate"] for p in pages) / len(pages),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(all_sum, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("ALL", all_sum)
    return all_sum


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ckpt", type=Path, default=Path("models/ocr/ocr_ar_48px.ckpt"))
    ap.add_argument(
        "--alphabet", type=Path, default=Path("models/ocr/alphabet-all-v7.txt")
    )
    ap.add_argument(
        "--encoder-onnx",
        type=Path,
        default=Path("result/ocr_coreml/ocr48_encoder_w512.onnx"),
    )
    ap.add_argument("--w-max", type=int, default=512)
    ap.add_argument("--beams-k", type=int, default=5)
    ap.add_argument("--smoke-stages", action="store_true")
    ap.add_argument("--smoke-3pages", action="store_true")
    ap.add_argument("--image", type=Path, default=None)
    ap.add_argument("--stages", type=Path, default=None)
    ap.add_argument(
        "--out-dir", type=Path, default=Path("result/ocr_beam_runtime")
    )
    args = ap.parse_args()

    if not args.encoder_onnx.is_file():
        raise SystemExit(
            f"missing encoder onnx: {args.encoder_onnx} "
            "(run export_ocr48_coreml / onnx export first)"
        )

    print(f"Loading runtime encoder={args.encoder_onnx} beams_k={args.beams_k}")
    rt = Ocr48BeamRuntime(
        args.ckpt, args.alphabet, args.encoder_onnx, args.w_max, args.beams_k
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.smoke_3pages:
        smoke_three_pages(rt, args.out_dir)
        return 0
    if args.smoke_stages:
        if not args.image or not args.stages:
            raise SystemExit("--smoke-stages needs --image and --stages")
        smoke_stages(rt, args.image, args.stages, args.out_dir / "one.json")
        return 0
    raise SystemExit("pass --smoke-3pages or --smoke-stages")


if __name__ == "__main__":
    raise SystemExit(main())
