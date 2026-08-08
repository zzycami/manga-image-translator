import base64
import struct
from typing import Dict, List, Union

import cv2
import numpy as np
from pydantic import BaseModel, Field

from manga_translator import Context
from manga_translator.utils import TextBlock


def _encode_background_png_b64(array: np.ndarray) -> str:
    _retval, buffer = cv2.imencode('.png', array)
    return "data:image/png;base64," + base64.b64encode(buffer).decode("utf-8")


class TextColor(BaseModel):
    fg: tuple[int, int, int]
    bg: tuple[int, int, int]

class Translation(BaseModel):
    minX: int
    minY: int
    maxX: int
    maxY: int
    is_bulleted_list: bool
    angle: float | int
    prob: float
    text_color: TextColor
    text: dict[str, str]
    # Store as base64 data-URL for OpenAPI/Pydantic v2 (avoid np.ndarray schema errors).
    background: str = Field(
        ...,
        description="Background image encoded as a base64 string",
        examples=["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA..."]
    )

    @staticmethod
    def encode_background(array: np.ndarray) -> str:
        return _encode_background_png_b64(array)

    def to_bytes(self):
        coords_bytes = struct.pack('4i', self.minX, self.minY, self.maxX, self.maxY)
        is_bulleted_list_byte = struct.pack('?', self.is_bulleted_list)
        angle_bytes = struct.pack('f', float(self.angle) if isinstance(self.angle, int) else self.angle)
        prob_bytes = struct.pack('f', self.prob)
        fg = struct.pack('3B', self.text_color.fg[0], self.text_color.fg[1], self.text_color.fg[2])
        bg = struct.pack('3B', self.text_color.bg[0], self.text_color.bg[1], self.text_color.bg[2])
        text_bytes = struct.pack('i', len(self.text.items()))
        for key, value in self.text.items():
            text_bytes += struct.pack('I', len(key.encode('utf-8'))) + key.encode('utf-8')
            text_bytes += struct.pack('I', len(value.encode('utf-8'))) + value.encode('utf-8')
        raw = self._background_raw_bytes()
        background_bytes = struct.pack('I', len(raw)) + raw
        return coords_bytes +is_bulleted_list_byte+ angle_bytes+prob_bytes+fg + bg + text_bytes + background_bytes

    def _background_raw_bytes(self) -> bytes:
        bg: Union[str, np.ndarray] = self.background  # type: ignore[assignment]
        if isinstance(bg, np.ndarray):
            return bg.tobytes()
        if isinstance(bg, str) and bg.startswith('data:image') and ',' in bg:
            return base64.b64decode(bg.split(',', 1)[1])
        if isinstance(bg, str):
            return bg.encode('utf-8')
        return bytes(bg)

class TranslationResponse(BaseModel):
    translations: List[Translation]
    debug_folder: str = None  # 添加debug_folder字段

    def to_bytes(self):
        items= [v.to_bytes() for v in self.translations]
        return struct.pack('i', len(items)) + b''.join(items)

def to_translation(ctx: Context) -> TranslationResponse:
    text_regions:list[TextBlock] = ctx.text_regions
    inpaint = ctx.img_inpainted
    translations:Dict[str, List[str]] = ctx.translations
    results = []
    for i, blk in enumerate(text_regions):
        minX, minY, maxX, maxY = blk.xyxy
        text_region = text_regions[i]
        if 'translations' in ctx:
            trans = {key: value[i] for key, value in translations.items()}
        else:
            trans = {}
        trans[text_region.source_lang] = text_regions[i].text
        text_region.adjust_bg_color = False
        color1, color2 = text_region.get_font_colors()
        results.append(Translation(text=trans,
                    minX=int(minX),minY=int(minY),maxX=int(maxX),maxY=int(maxY),
                    background=Translation.encode_background(inpaint[minY:maxY, minX:maxX]),
                    is_bulleted_list=text_region.is_bulleted_list,
                    text_color=TextColor(fg=color1.tolist(), bg=color2.tolist()),
                    prob=text_region.prob,
                    angle=text_region.angle
        ))
        #todo: background angle

    # 获取debug_folder信息
    debug_folder = getattr(ctx, 'debug_folder', None)

    return TranslationResponse(translations=results, debug_folder=debug_folder)
