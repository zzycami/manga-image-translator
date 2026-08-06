"""
TranslationStages JSON for client-side rendering (manga-translate-native SCHEMA 0.1.0).
"""
from __future__ import annotations

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


class TranslationStages(BaseModel):
    schemaVersion: str = SCHEMA_VERSION
    imageWidth: int
    imageHeight: int
    sourceLang: Optional[str] = None
    targetLang: Optional[str] = None
    regions: List[StageRegion] = Field(default_factory=list)
    maskPngBase64: Optional[str] = None
    pipelineMode: str = "json_stages"


def to_translation_stages(ctx: Context, include_mask: bool = False) -> TranslationStages:
    """Build compact stages JSON (no per-region background crops)."""
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
            # Prefer configured target language list if present
            for _lang, arr in ctx.translations.items():
                if i < len(arr) and arr[i]:
                    translated = arr[i]
                    break
        if source_lang is None and getattr(blk, "source_lang", None):
            source_lang = blk.source_lang
        if target_lang is None and getattr(blk, "target_lang", None):
            target_lang = blk.target_lang
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
            )
        )

    mask_b64 = None
    if include_mask and getattr(ctx, "mask", None) is not None:
        import base64
        import cv2

        ok, buf = cv2.imencode(".png", ctx.mask)
        if ok:
            mask_b64 = base64.b64encode(buf.tobytes()).decode("ascii")

    return TranslationStages(
        imageWidth=w,
        imageHeight=h,
        sourceLang=source_lang,
        targetLang=target_lang,
        regions=regions,
        maskPngBase64=mask_b64,
        pipelineMode="json_stages",
    )


def stages_dict(ctx: Context, include_mask: bool = False) -> Dict[str, Any]:
    return to_translation_stages(ctx, include_mask=include_mask).model_dump()
