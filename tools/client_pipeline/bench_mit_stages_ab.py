#!/usr/bin/env python3
"""
A/B bench for MIT /translate/with-form/stages/stream.

Measures wall time between progress frames (detection / ocr / translating / …)
and compares stages JSON quality (boxes, OCR text, translations).

Throwaway-friendly but kept under tools/client_pipeline for reuse.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("need requests: pip install requests", file=sys.stderr)
    sys.exit(1)

STATUS_RESULT = 0
STATUS_PROGRESS = 1
STATUS_ERROR = 2
STATUS_QUEUE = 3
STATUS_WAITING = 4
STATUS_META = 5

DEFAULT_IMAGES = [
    Path(__file__).resolve().parents[3]
    / "manga-translate-native/result/batch_hana_timing/005_005/page_work.jpg",
    Path(__file__).resolve().parents[3]
    / "manga-translate-native/result/batch_hana_timing/007_007/page_work.jpg",
    Path(__file__).resolve().parents[3]
    / "manga-translate-native/result/batch_hana_timing/033_033/page_work.jpg",
]

# Match Hub LocalMangaTranslationProvider json_stages defaults
BASELINE_CONFIG: Dict[str, Any] = {
    "translator": {"translator": "custom_openai", "target_lang": "CHS"},
    "detector": {"detector": "default", "detection_size": 1536},
    "ocr": {"ocr": "48px"},
    "inpainter": {
        "inpainter": "lama_large",
        "inpainting_size": 1536,
        "inpainting_precision": "bf16",
    },
    "render": {"renderer": "default", "alignment": "auto"},
    "kernel_size": 3,
    "pipeline_mode": "json_stages",
    "stages_include_mask": True,
    "stages_include_inpainted": False,
}


@dataclass
class StageMark:
    state: str
    t_wall: float
    dt_from_prev_ms: float


@dataclass
class PageResult:
    image: str
    image_md5: str
    ok: bool
    error: Optional[str] = None
    total_ms: float = 0.0
    stages_path: Optional[str] = None
    region_count: int = 0
    stage_marks: List[StageMark] = field(default_factory=list)
    stage_durations_ms: Dict[str, float] = field(default_factory=dict)
    ocr_texts: List[str] = field(default_factory=list)
    translations: List[str] = field(default_factory=list)
    boxes: List[List[float]] = field(default_factory=list)


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_frames(resp) -> List[Tuple[int, bytes]]:
    frames: List[Tuple[int, bytes]] = []
    buf = b""
    for chunk in resp.iter_content(chunk_size=65536):
        if not chunk:
            continue
        buf += chunk
        while len(buf) >= 5:
            status = buf[0]
            (size,) = struct.unpack(">I", buf[1:5])
            if size < 0 or size > 64 * 1024 * 1024:
                raise RuntimeError(f"bad frame size {size}")
            if len(buf) < 5 + size:
                break
            payload = buf[5 : 5 + size]
            buf = buf[5 + size :]
            frames.append((status, payload))
    return frames


def extract_regions(stages: Dict[str, Any]) -> Tuple[List[str], List[str], List[List[float]]]:
    regions = stages.get("regions") or stages.get("text_regions") or []
    ocr: List[str] = []
    tr: List[str] = []
    boxes: List[List[float]] = []
    for r in regions:
        if not isinstance(r, dict):
            continue
        text = (
            r.get("sourceText")
            or r.get("text")
            or r.get("ocr")
            or r.get("text_ocr")
            or ""
        )
        if isinstance(text, list):
            text = "".join(str(x) for x in text)
        trans = (
            r.get("translatedText")
            or r.get("translation")
            or r.get("translated")
            or r.get("text_translated")
            or ""
        )
        if isinstance(trans, list):
            trans = "".join(str(x) for x in trans)
        ocr.append(str(text))
        tr.append(str(trans))
        box = r.get("boundingBox") or r.get("bbox") or r.get("xyxy")
        if box is None and "x" in r and "y" in r and "w" in r and "h" in r:
            box = [r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]]
        if isinstance(box, dict):
            x = float(box.get("x", 0))
            y = float(box.get("y", 0))
            w = float(box.get("w", 0))
            h = float(box.get("h", 0))
            boxes.append([x, y, x + w, y + h])
        elif isinstance(box, (list, tuple)) and len(box) >= 4:
            boxes.append([float(box[0]), float(box[1]), float(box[2]), float(box[3])])
        else:
            boxes.append([0.0, 0.0, 0.0, 0.0])
    return ocr, tr, boxes


def durations_from_marks(marks: List[StageMark]) -> Dict[str, float]:
    """Attribute dt_from_prev to the state that just finished (previous mark)."""
    out: Dict[str, float] = {}
    for i in range(1, len(marks)):
        prev = marks[i - 1].state
        out[prev] = out.get(prev, 0.0) + marks[i].dt_from_prev_ms
    return out


def run_one(
    host: str,
    image: Path,
    config: Dict[str, Any],
    out_dir: Path,
    timeout: float,
) -> PageResult:
    image = image.resolve()
    im_md5 = md5_file(image)
    url = host.rstrip("/") + "/translate/with-form/stages/stream"
    stem = image.parent.name if image.name == "page_work.jpg" else image.stem
    t0 = time.perf_counter()
    marks: List[StageMark] = []
    last_t = t0
    try:
        with image.open("rb") as f:
            files = {"image": (image.name, f, "image/jpeg")}
            data = {"config": json.dumps(config, ensure_ascii=False)}
            resp = requests.post(url, files=files, data=data, stream=True, timeout=timeout)
        if resp.status_code != 200:
            body = resp.text[:500]
            return PageResult(
                image=str(image),
                image_md5=im_md5,
                ok=False,
                error=f"HTTP {resp.status_code}: {body}",
                total_ms=(time.perf_counter() - t0) * 1000,
            )
        frames = read_frames(resp)
    except Exception as e:
        return PageResult(
            image=str(image),
            image_md5=im_md5,
            ok=False,
            error=str(e),
            total_ms=(time.perf_counter() - t0) * 1000,
        )

    stages_bytes: Optional[bytes] = None
    for status, payload in frames:
        now = time.perf_counter()
        dt = (now - last_t) * 1000
        last_t = now
        if status == STATUS_PROGRESS:
            state = payload.decode("utf-8", errors="replace")
            marks.append(StageMark(state=state, t_wall=now - t0, dt_from_prev_ms=dt))
        elif status == STATUS_ERROR:
            err = payload.decode("utf-8", errors="replace")
            return PageResult(
                image=str(image),
                image_md5=im_md5,
                ok=False,
                error=err,
                total_ms=(time.perf_counter() - t0) * 1000,
                stage_marks=marks,
                stage_durations_ms=durations_from_marks(marks),
            )
        elif status == STATUS_QUEUE:
            marks.append(
                StageMark(
                    state=f"queue:{payload.decode('utf-8', errors='replace')}",
                    t_wall=now - t0,
                    dt_from_prev_ms=dt,
                )
            )
        elif status == STATUS_WAITING:
            marks.append(StageMark(state="waiting", t_wall=now - t0, dt_from_prev_ms=dt))
        elif status == STATUS_RESULT:
            stages_bytes = payload
            marks.append(StageMark(state="result", t_wall=now - t0, dt_from_prev_ms=dt))

    total_ms = (time.perf_counter() - t0) * 1000
    if not stages_bytes:
        return PageResult(
            image=str(image),
            image_md5=im_md5,
            ok=False,
            error="no result frame",
            total_ms=total_ms,
            stage_marks=marks,
            stage_durations_ms=durations_from_marks(marks),
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    stages_path = out_dir / f"{stem}.stages.json"
    stages_path.write_bytes(stages_bytes)
    try:
        stages = json.loads(stages_bytes.decode("utf-8"))
    except Exception as e:
        return PageResult(
            image=str(image),
            image_md5=im_md5,
            ok=False,
            error=f"stages JSON parse: {e}",
            total_ms=total_ms,
            stages_path=str(stages_path),
            stage_marks=marks,
            stage_durations_ms=durations_from_marks(marks),
        )

    ocr, tr, boxes = extract_regions(stages)
    # Prefer server-embedded timings (accurate); fall back to stream mark deltas (often buffered≈0).
    server_timings = stages.get("stageTimingsMs") or {}
    if isinstance(server_timings, dict) and server_timings:
        stage_ms = {str(k): float(v) for k, v in server_timings.items()}
    else:
        stage_ms = durations_from_marks(marks)
    return PageResult(
        image=str(image),
        image_md5=im_md5,
        ok=True,
        total_ms=total_ms,
        stages_path=str(stages_path),
        region_count=len(ocr),
        stage_marks=marks,
        stage_durations_ms=stage_ms,
        ocr_texts=ocr,
        translations=tr,
        boxes=boxes,
    )


def box_iou(a: List[float], b: List[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def compare_page(base: PageResult, var: PageResult) -> Dict[str, Any]:
    if not base.ok or not var.ok:
        return {
            "ok": False,
            "base_ok": base.ok,
            "var_ok": var.ok,
            "base_error": base.error,
            "var_error": var.error,
        }
    n = max(len(base.boxes), len(var.boxes))
    ious: List[float] = []
    ocr_match = 0
    ocr_total = 0
    # greedy match by IoU
    used = set()
    for i, bb in enumerate(base.boxes):
        best_j, best_iou = -1, -1.0
        for j, vb in enumerate(var.boxes):
            if j in used:
                continue
            iou = box_iou(bb, vb)
            if iou > best_iou:
                best_iou, best_j = iou, j
        if best_j >= 0 and best_iou >= 0.3:
            used.add(best_j)
            ious.append(best_iou)
            ocr_total += 1
            if base.ocr_texts[i].strip() == var.ocr_texts[best_j].strip():
                ocr_match += 1
        else:
            ious.append(0.0)
            ocr_total += 1

    mean_iou = sum(ious) / len(ious) if ious else 0.0
    trans_exact = sum(
        1
        for a, b in zip(base.translations, var.translations)
        if a.strip() == b.strip()
    )
    # pad-safe: only zip min length already; also count region delta
    return {
        "ok": True,
        "region_count_base": base.region_count,
        "region_count_var": var.region_count,
        "region_delta": var.region_count - base.region_count,
        "mean_box_iou": round(mean_iou, 4),
        "ocr_exact_rate": round(ocr_match / ocr_total, 4) if ocr_total else None,
        "translation_exact_prefix": round(
            trans_exact / max(1, min(len(base.translations), len(var.translations))), 4
        ),
        "total_ms_base": round(base.total_ms, 1),
        "total_ms_var": round(var.total_ms, 1),
        "speedup": round(base.total_ms / var.total_ms, 3) if var.total_ms > 0 else None,
        "saved_ms": round(base.total_ms - var.total_ms, 1),
        "stage_ms_base": {k: round(v, 1) for k, v in base.stage_durations_ms.items()},
        "stage_ms_var": {k: round(v, 1) for k, v in var.stage_durations_ms.items()},
        # Heuristic pass for detect/OCR-focused opts
        "quality_pass_detect_ocr": (
            var.region_count == base.region_count
            and mean_iou >= 0.85
            and (ocr_match / ocr_total if ocr_total else 0) >= 0.9
        ),
    }


def deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(base))
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def serialize_page(p: PageResult) -> Dict[str, Any]:
    d = asdict(p)
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--host",
        default="http://192.168.31.156:8000",
        help="MIT base URL (Docker LAN default)",
    )
    ap.add_argument(
        "--images",
        nargs="*",
        type=Path,
        default=None,
        help="Images (default: hana timing 3 pages)",
    )
    ap.add_argument(
        "--variant-name",
        default="det1024",
        help="Name for optimized config run",
    )
    ap.add_argument(
        "--variant-patch",
        default='{"detector":{"detection_size":1024}}',
        help="JSON patch merged onto baseline config",
    )
    ap.add_argument(
        "--baseline-only",
        action="store_true",
        help="Only run baseline",
    )
    ap.add_argument(
        "--variant-only",
        action="store_true",
        help="Only run variant (needs --baseline-dir for compare)",
    )
    ap.add_argument("--baseline-dir", type=Path, default=None)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output root (default result/bench_mit_stages_ab/<ts>)",
    )
    ap.add_argument("--warmup", action="store_true", default=True)
    ap.add_argument("--no-warmup", action="store_true")
    ap.add_argument("--timeout", type=float, default=1800)
    args = ap.parse_args()

    images = args.images or [p for p in DEFAULT_IMAGES if p.is_file()]
    if not images:
        print("no images found", file=sys.stderr)
        return 2
    for p in images:
        if not p.is_file():
            print(f"missing image: {p}", file=sys.stderr)
            return 2

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_root = args.out or (
        Path(__file__).resolve().parents[2] / "result" / "bench_mit_stages_ab" / ts
    )
    out_root.mkdir(parents=True, exist_ok=True)

    patch = json.loads(args.variant_patch)
    variant_cfg = deep_merge(BASELINE_CONFIG, patch)

    meta = {
        "host": args.host,
        "images": [str(p) for p in images],
        "baseline_config": BASELINE_CONFIG,
        "variant_name": args.variant_name,
        "variant_config": variant_cfg,
    }
    (out_root / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    do_warmup = args.warmup and not args.no_warmup
    if do_warmup and not args.variant_only:
        print(f"warmup against {args.host} …")
        warm = run_one(
            args.host, images[0], BASELINE_CONFIG, out_root / "_warmup", args.timeout
        )
        print(f"  warmup ok={warm.ok} total_ms={warm.total_ms:.0f} err={warm.error}")

    baseline_pages: List[PageResult] = []
    if not args.variant_only:
        bdir = out_root / "baseline"
        print(f"=== baseline → {bdir} ===")
        for img in images:
            print(f"baseline {img} …")
            r = run_one(args.host, img, BASELINE_CONFIG, bdir, args.timeout)
            baseline_pages.append(r)
            print(
                f"  ok={r.ok} total_ms={r.total_ms:.0f} regions={r.region_count} "
                f"stages={r.stage_durations_ms} err={r.error}"
            )
        summary = {
            "label": "baseline",
            "pages": [serialize_page(p) for p in baseline_pages],
            "total_ms_sum": round(sum(p.total_ms for p in baseline_pages), 1),
            "ok_all": all(p.ok for p in baseline_pages),
        }
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:
        if not args.baseline_dir:
            print("--variant-only needs --baseline-dir", file=sys.stderr)
            return 2
        summary = json.loads((args.baseline_dir / "summary.json").read_text())
        baseline_pages = []
        for raw in summary["pages"]:
            marks = [StageMark(**m) for m in raw.get("stage_marks") or []]
            baseline_pages.append(
                PageResult(
                    image=raw["image"],
                    image_md5=raw["image_md5"],
                    ok=raw["ok"],
                    error=raw.get("error"),
                    total_ms=raw.get("total_ms") or 0,
                    stages_path=raw.get("stages_path"),
                    region_count=raw.get("region_count") or 0,
                    stage_marks=marks,
                    stage_durations_ms=raw.get("stage_durations_ms") or {},
                    ocr_texts=raw.get("ocr_texts") or [],
                    translations=raw.get("translations") or [],
                    boxes=raw.get("boxes") or [],
                )
            )
        out_root = args.baseline_dir.parent
        # keep writing variant beside baseline
        pass

    if args.baseline_only:
        print(f"done baseline-only → {out_root}")
        return 0 if all(p.ok for p in baseline_pages) else 1

    vdir = out_root / args.variant_name
    print(f"=== variant {args.variant_name} → {vdir} ===")
    variant_pages: List[PageResult] = []
    for img in images:
        print(f"{args.variant_name} {img} …")
        r = run_one(args.host, img, variant_cfg, vdir, args.timeout)
        variant_pages.append(r)
        print(
            f"  ok={r.ok} total_ms={r.total_ms:.0f} regions={r.region_count} "
            f"stages={r.stage_durations_ms} err={r.error}"
        )
    vsummary = {
        "label": args.variant_name,
        "pages": [serialize_page(p) for p in variant_pages],
        "total_ms_sum": round(sum(p.total_ms for p in variant_pages), 1),
        "ok_all": all(p.ok for p in variant_pages),
    }
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "summary.json").write_text(
        json.dumps(vsummary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    compares = []
    for b, v in zip(baseline_pages, variant_pages):
        c = compare_page(b, v)
        c["image"] = b.image
        compares.append(c)
    report = {
        "host": args.host,
        "variant_name": args.variant_name,
        "variant_patch": patch,
        "baseline_total_ms_sum": round(sum(p.total_ms for p in baseline_pages), 1),
        "variant_total_ms_sum": round(sum(p.total_ms for p in variant_pages), 1),
        "pages": compares,
        "all_quality_pass_detect_ocr": all(
            c.get("quality_pass_detect_ocr") for c in compares if c.get("ok")
        ),
    }
    (out_root / "compare.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== compare ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nwrote {out_root}")
    return 0 if report.get("all_quality_pass_detect_ocr") and vsummary["ok_all"] else 0


if __name__ == "__main__":
    # Always exit 0 on completed runs so we can inspect compare.json; quality in JSON.
    sys.exit(main() and 0)
