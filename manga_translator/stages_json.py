"""
TranslationStages JSON for client-side rendering (manga-translate-native SCHEMA 0.1.0).
"""
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .utils import Context
from .utils import TextBlock


SCHEMA_VERSION = "0.1.0"


def _rgb_to_hex(rgb) -> str:
    vals = [int(max(0, min(255, round(float(c))))) for c in list(rgb)[:3]]
    while len(vals) < 3:
        vals.append(0)
    return f"#{vals[0]:02X}{vals[1]:02X}{vals[2]:02X}"


def _polygons_from_block(blk: TextBlock) -> List[List[List[int]]]:
    out: List[List[List[int]]] = []
    try:
        lines = blk.lines.reshape(-1, 4, 2)
        for poly in lines:
            out.append([[int(p[0]), int(p[1])] for p in poly])
    except Exception:
        x1, y1, x2, y2 = [int(v) for v in blk.xyxy]
        out.append([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
    return out


def _encode_jpeg_b64(rgb, quality: int = 85) -> Optional[str]:
    """RGB uint8 HxWx3 → base64 JPEG."""
    import cv2
    import numpy as np

    if rgb is None:
        return None
    arr = np.asarray(rgb)
    if arr.ndim != 3 or arr.shape[2] < 3:
        return None
    bgr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _encode_png_b64(gray_or_rgb) -> Optional[str]:
    import cv2
    import numpy as np

    if gray_or_rgb is None:
        return None
    arr = np.asarray(gray_or_rgb)
    ok, buf = cv2.imencode(".png", arr)
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


class BoundingBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class StageRegion(BaseModel):
    id: str
    boundingBox: BoundingBox
    polygons: List[List[List[int]]] = Field(default_factory=list)
    angleDeg: float = 0
    sourceText: str = ""
    translatedText: str = ""
    fgColor: str = "#000000"
    bgColor: str = "#FFFFFF"
    vertical: bool = False
    # Mirror TextBlock fields used by manga_translator.rendering.text_render
    fontSize: int = 0
    alignment: str = "center"


class TranslationStages(BaseModel):
    schemaVersion: str = SCHEMA_VERSION
    imageWidth: int
    imageHeight: int
    sourceLang: Optional[str] = None
    targetLang: Optional[str] = None
    regions: List[StageRegion] = Field(default_factory=list)
    maskPngBase64: Optional[str] = None
    # Erased page from server inpaint — client draws text on this (no white boxes).
    inpaintedJpegBase64: Optional[str] = None
    skipRegionFill: bool = False
    pipelineMode: str = "json_stages"
    # MD5 hex of raw upload bytes — Hub/client correlate response to page (additive; old clients ignore).
    sourceImageMd5: Optional[str] = None
    # Server-side wall ms per progress state (detection/ocr/translating/…). Additive; old clients ignore.
    stageTimingsMs: Optional[Dict[str, float]] = None


def to_translation_stages(
    ctx: Context,
    include_mask: bool = True,
    include_inpainted: bool = False,
    inpainted_jpeg_quality: int = 85,
    source_image_md5: Optional[str] = None,
) -> TranslationStages:
    """Build stages JSON for client render.

    Default: refined maskPngBase64 (small) + no inpainted JPEG. Client keeps the
    original page and erases via lama/geometry. Pass include_inpainted=True for
    legacy opt-in erased base.
    """
    text_regions: List[TextBlock] = list(getattr(ctx, "text_regions", None) or [])
    h, w = 0, 0
    if getattr(ctx, "img_rgb", None) is not None:
        h, w = int(ctx.img_rgb.shape[0]), int(ctx.img_rgb.shape[1])
    elif getattr(ctx, "input", None) is not None:
        w, h = ctx.input.size

    source_lang = None
    target_lang = None
    regions: List[StageRegion] = []
    for i, blk in enumerate(text_regions):
        x1, y1, x2, y2 = [int(v) for v in blk.xyxy]
        fg, bg = blk.get_font_colors()
        src = getattr(blk, "text", "") or ""
        translated = getattr(blk, "translation", "") or ""
        if not translated and getattr(ctx, "translations", None):
            for _lang, arr in ctx.translations.items():
                if i < len(arr) and arr[i]:
                    translated = arr[i]
                    break
        if source_lang is None and getattr(blk, "source_lang", None):
            source_lang = blk.source_lang
        if target_lang is None and getattr(blk, "target_lang", None):
            target_lang = blk.target_lang
        font_size = int(getattr(blk, "font_size", 0) or 0)
        if font_size <= 0:
            bw, bh = max(0, x2 - x1), max(0, y2 - y1)
            font_size = max(1, min(bw, bh) if bool(getattr(blk, "vertical", False)) else max(1, bh // 2))
        # Long translation vs short source: start a bit smaller so client fit has headroom
        n_src = max(1, len(src.strip()))
        n_tr = max(1, len(translated.strip()))
        if n_tr > n_src * 1.3 and font_size > 8:
            font_size = max(8, int(font_size * (n_src / n_tr) ** 0.5))
        alignment = getattr(blk, "alignment", None) or "center"
        if alignment not in ("left", "center", "right"):
            alignment = "center"
        regions.append(
            StageRegion(
                id=f"r{i}",
                boundingBox=BoundingBox(x=x1, y=y1, w=max(0, x2 - x1), h=max(0, y2 - y1)),
                polygons=_polygons_from_block(blk),
                angleDeg=float(getattr(blk, "angle", 0) or 0),
                sourceText=src,
                translatedText=translated,
                fgColor=_rgb_to_hex(fg),
                bgColor=_rgb_to_hex(bg),
                vertical=bool(getattr(blk, "vertical", False)),
                fontSize=int(font_size),
                alignment=alignment,
            )
        )

    mask_b64 = None
    if include_mask and getattr(ctx, "mask", None) is not None:
        mask_b64 = _encode_png_b64(ctx.mask)

    inpainted_b64 = None
    skip_fill = False
    if include_inpainted and getattr(ctx, "img_inpainted", None) is not None:
        inpainted_b64 = _encode_jpeg_b64(ctx.img_inpainted, quality=inpainted_jpeg_quality)
        skip_fill = inpainted_b64 is not None

    md5 = source_image_md5 or getattr(ctx, "source_image_md5", None)
    if isinstance(md5, str):
        md5 = md5.strip().lower() or None

    timings = getattr(ctx, "stage_timings_ms", None)
    if isinstance(timings, dict):
        timings = {str(k): float(v) for k, v in timings.items()}
    else:
        timings = None

    return TranslationStages(
        imageWidth=w,
        imageHeight=h,
        sourceLang=source_lang,
        targetLang=target_lang,
        regions=regions,
        maskPngBase64=mask_b64,
        inpaintedJpegBase64=inpainted_b64,
        skipRegionFill=skip_fill,
        pipelineMode="json_stages",
        sourceImageMd5=md5,
        stageTimingsMs=timings,
    )


def stages_dict(
    ctx: Context,
    include_mask: bool = True,
    include_inpainted: bool = False,
    source_image_md5: Optional[str] = None,
) -> Dict[str, Any]:
    return to_translation_stages(
        ctx,
        include_mask=include_mask,
        include_inpainted=include_inpainted,
        source_image_md5=source_image_md5,
    ).model_dump()
