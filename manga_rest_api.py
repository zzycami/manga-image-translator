#!/usr/bin/env python3
"""
Manga Translator REST API 包装器
提供标准的 HTTP multipart/form-data 接口，便于 Kotlin/Java 调用
"""

import io
import tempfile
import traceback
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

from manga_translator import MangaTranslator
from manga_translator.config import (
    Config, TranslatorConfig, DetectorConfig, InpainterConfig,
    Translator, Detector, Inpainter, RenderConfig, OcrConfig
)

# 创建 FastAPI 应用
app = FastAPI(
    title="Manga Translator REST API",
    description="简单易用的漫画翻译 API，支持标准 HTTP 请求",
    version="1.0.0"
)

# 全局翻译器实例（模型常驻内存）
translator: Optional[MangaTranslator] = None


@app.on_event("startup")
async def startup_event():
    """应用启动时加载模型"""
    global translator
    print("🚀 正在加载 Manga Translator 模型...")
    print("⏳ 首次启动可能需要下载模型，请耐心等待...")

    # 初始化时提供所有必需的参数
    translator = MangaTranslator({
        'use_gpu': True,
        'verbose': True,
        'kernel_size': 3,  # 必需参数
        'input': [],       # 必需参数（文件列表）
        'save_text': False,
        'load_text': False
    })

    print("✅ 模型加载完成！服务已就绪。")


@app.get("/")
async def root():
    """根路径 - 显示 API 信息"""
    return {
        "name": "Manga Translator REST API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "model_loaded": translator is not None
    }


@app.post("/translate")
async def translate_image(
    file: UploadFile = File(..., description="要翻译的漫画图片"),
    target_lang: str = Form("CHS", description="目标语言: CHS, CHT, ENG, JPN, KOR, etc."),
    translator_name: str = Form("none", description="翻译器: none, google, deepl, gpt3.5, etc."),
    detector: str = Form("default", description="检测器: default, ctd, craft"),
    inpainter: str = Form("lama_large", description="擦除模型: lama_large, lama_mpe, aot"),
    direction: str = Form("auto", description="文字方向: auto, horizontal, vertical"),
    size: Optional[int] = Form(None, description="处理尺寸 (可选，如 1536)")
):
    """
    翻译漫画图片

    参数:
    - file: 图片文件 (JPG, PNG)
    - target_lang: 目标语言 (CHS=简体中文, CHT=繁体中文, ENG=英语)
    - translator_name: 翻译引擎 (none=不翻译只擦除)
    - detector: 文字检测器
    - inpainter: 文字擦除模型
    - direction: 文字方向
    - size: 处理尺寸 (可选)

    返回: 翻译后的图片
    """
    if translator is None:
        raise HTTPException(status_code=503, detail="模型尚未加载，请稍候...")

    try:
        print(f"\n{'='*60}")
        print(f"📥 收到翻译请求")
        print(f"文件名: {file.filename}")
        print(f"目标语言: {target_lang}")
        print(f"翻译器: {translator_name}")
        print(f"检测器: {detector}")
        print(f"擦除模型: {inpainter}")
        print(f"{'='*60}\n")

        # 读取上传的图片
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))

        print(f"📊 图片信息: {image.size[0]}x{image.size[1]}, {image.mode}")
        print(f"⏳ 开始处理...")

        # 构建 Config 对象
        config = Config()

        # 配置翻译器
        config.translator = TranslatorConfig(
            translator=Translator[translator_name],
            target_lang=target_lang.upper()
        )

        # 配置检测器
        config.detector = DetectorConfig(
            detector=Detector[detector],
            detection_size=size if size else 2048
        )

        # 配置擦除模型
        config.inpainter = InpainterConfig(
            inpainter=Inpainter[inpainter],
            inpainting_size=size if size else 2048
        )

        # 配置 OCR（关键！）
        config.ocr = OcrConfig()

        # 配置渲染
        config.render = RenderConfig()

        # 执行翻译
        result = await translator.translate(image, config)

        # 保存结果到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            # 从 Context 对象获取 result 图片
            if hasattr(result, 'result'):
                result_image = result.result
            else:
                result_image = result

            # 如果图片有 alpha 通道，转换为 RGB
            if result_image.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                rgb_image = Image.new('RGB', result_image.size, (255, 255, 255))
                # 如果有 alpha 通道，使用它进行合成
                if result_image.mode == 'RGBA':
                    rgb_image.paste(result_image, mask=result_image.split()[3])
                else:
                    rgb_image.paste(result_image)
                result_image = rgb_image

            result_image.save(tmp.name, 'JPEG', quality=95)
            tmp_path = tmp.name

        print(f"✅ 处理完成！")
        print(f"💾 结果保存到: {tmp_path}\n")

        # 返回图片文件
        return FileResponse(
            tmp_path,
            media_type="image/jpeg",
            filename=f"translated_{file.filename}",
            headers={
                "X-Original-Filename": file.filename,
                "X-Target-Lang": target_lang
            }
        )

    except Exception as e:
        error_msg = f"翻译失败: {str(e)}"
        print(f"\n❌ {error_msg}")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail={
                "error": error_msg,
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )


@app.post("/detect")
async def detect_text(
    file: UploadFile = File(..., description="要检测的漫画图片"),
    detector: str = Form("default", description="检测器: default, ctd, craft")
):
    """
    仅检测图片中的文字区域，返回 JSON

    返回格式:
    {
        "text_regions": [
            {
                "bbox": [x1, y1, x2, y2],
                "text": "检测到的文字",
                "confidence": 0.95
            }
        ]
    }
    """
    if translator is None:
        raise HTTPException(status_code=503, detail="模型尚未加载")

    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))

        # 调用检测功能
        # 注意：这里需要根据实际的 API 调整
        result = await translator.detect(image=image, detector=detector)

        return JSONResponse({
            "status": "success",
            "image_size": list(image.size),
            "text_regions": result
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect_and_ocr")
async def detect_and_ocr(
    file: UploadFile = File(..., description="要识别的漫画图片"),
    detector: str = Form("default", description="检测器: default, ctd, craft")
):
    """
    检测文字区域并进行OCR识别

    返回格式:
    {
        "text_regions": [
            {
                "bbox": [x1, y1, x2, y2],
                "text": "识别到的文字",
                "direction": "horizontal"
            }
        ]
    }
    """
    if translator is None:
        raise HTTPException(status_code=503, detail="模型尚未加载")

    try:
        print(f"\n{'='*60}")
        print(f"📥 收到OCR识别请求")
        print(f"文件名: {file.filename}")
        print(f"检测器: {detector}")
        print(f"{'='*60}\n")

        # 读取图片
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))

        print(f"📊 图片信息: {image.size[0]}x{image.size[1]}, {image.mode}")
        print(f"⏳ 开始检测和识别...")

        # 构建 Config 对象（只做检测和OCR，不翻译）
        config = Config()

        # 配置检测器
        config.detector = DetectorConfig(
            detector=Detector[detector],
            detection_size=2048
        )

        # 配置 OCR（关键！）
        config.ocr = OcrConfig()

        # 配置翻译器为none（不翻译）
        config.translator = TranslatorConfig(
            translator=Translator.none,
            target_lang="CHS"
        )

        # 执行翻译流程（实际上会做检测和OCR）
        result = await translator.translate(image, config)

        # 提取文字区域信息
        text_regions = []
        if hasattr(result, 'text_regions') and result.text_regions:
            for region in result.text_regions:
                text_regions.append({
                    "bbox": region.bbox if hasattr(region, 'bbox') else None,
                    "text": region.text if hasattr(region, 'text') else "",
                    "direction": region.direction if hasattr(region, 'direction') else "horizontal",
                    "confidence": region.confidence if hasattr(region, 'confidence') else 0.0
                })

        print(f"✅ 检测完成！")
        print(f"📝 识别到 {len(text_regions)} 个文字区域")
        for i, region in enumerate(text_regions):
            print(f"   区域 {i+1}: {region['text'][:50]}...")

        return JSONResponse({
            "status": "success",
            "image_size": list(image.size),
            "text_regions": text_regions,
            "total_regions": len(text_regions)
        })

    except Exception as e:
        error_msg = f"OCR识别失败: {str(e)}"
        print(f"\n❌ {error_msg}")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail={
                "error": error_msg,
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )


@app.get("/models")
async def list_models():
    """列出可用的模型"""
    return {
        "translators": [
            "none",      # 不翻译
            "google",    # Google Translate
            "deepl",     # DeepL
            "gpt3.5",    # GPT-3.5
            "gpt4",      # GPT-4
        ],
        "detectors": [
            "default",   # 默认检测器
            "ctd",       # Comic Text Detector
            "craft",     # CRAFT
        ],
        "inpainters": [
            "lama_large",  # LaMa Large (推荐)
            "lama_mpe",    # LaMa MPE
            "aot",         # AOT
        ],
        "languages": {
            "CHS": "简体中文",
            "CHT": "繁体中文",
            "ENG": "英语",
            "JPN": "日语",
            "KOR": "韩语",
            "RUS": "俄语",
            "FRA": "法语",
            "DEU": "德语",
        }
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manga Translator REST API Server")
    parser.add_argument("--host", default="127.0.0.1", help="服务器地址")
    parser.add_argument("--port", type=int, default=5004, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="开启热重载（开发模式）")

    args = parser.parse_args()

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        🎨 Manga Translator REST API Server 🎨                ║
║                                                               ║
║  服务地址: http://{args.host}:{args.port}                      ║
║  API 文档: http://{args.host}:{args.port}/docs                ║
║  健康检查: http://{args.host}:{args.port}/health              ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "manga_rest_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )
