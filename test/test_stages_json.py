"""Unit tests for TranslationStages JSON (no GPU)."""
import numpy as np

from manga_translator.stages_json import to_translation_stages, SCHEMA_VERSION
from manga_translator.utils import Context, TextBlock


def test_to_translation_stages_basic():
    ctx = Context()
    ctx.img_rgb = np.zeros((200, 100, 3), dtype=np.uint8)
    # one quadrilateral textline → TextBlock
    lines = [[[10, 20], [50, 20], [50, 40], [10, 40]]]
    blk = TextBlock(
        lines=lines,
        texts=["こんにちは"],
        translation="你好",
        fg_color=(0, 0, 0),
        bg_color=(255, 255, 255),
        angle=0,
        source_lang="ja",
        target_lang="zh",
        direction="h",
    )
    ctx.text_regions = [blk]

    stages = to_translation_stages(ctx, include_inpainted=False)
    assert stages.schemaVersion == SCHEMA_VERSION
    assert stages.imageWidth == 100
    assert stages.imageHeight == 200
    assert len(stages.regions) == 1
    r = stages.regions[0]
    assert r.id == "r0"
    assert r.sourceText == "こんにちは"
    assert r.translatedText == "你好"
    assert r.boundingBox.x == 10
    assert r.boundingBox.y == 20
    assert r.boundingBox.w == 40
    assert r.boundingBox.h == 20
    assert r.fgColor.startswith("#")
    assert r.fontSize > 0
    dumped = stages.model_dump()
    assert dumped["pipelineMode"] == "json_stages"
    assert dumped.get("inpaintedJpegBase64") in (None, "")

    ctx.img_inpainted = np.ones((200, 100, 3), dtype=np.uint8) * 200
    stages2 = to_translation_stages(ctx, include_inpainted=True)
    assert stages2.skipRegionFill is True
    assert stages2.inpaintedJpegBase64
    assert len(stages2.inpaintedJpegBase64) > 100



if __name__ == "__main__":
    test_to_translation_stages_basic()
    print("PASS")
