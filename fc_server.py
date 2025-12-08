#!/usr/bin/env python3
"""
阿里云函数计算HTTP服务器
使用FastAPI作为HTTP框架，兼容FC的HTTP触发器
支持流式响应，兼容Kotlin后端的调用方式
"""
import os
import sys
import logging
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import base64
import io
import requests
from PIL import Image
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from manga_translator import MangaTranslator, Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Manga Translator FC", version="1.0.0")

# 结果目录（FC环境使用/tmp目录）
RESULT_ROOT = Path("/tmp/result")
RESULT_ROOT.mkdir(parents=True, exist_ok=True)

# 添加result文件夹静态文件服务（如果存在）
if RESULT_ROOT.exists():
    try:
        app.mount("/result", StaticFiles(directory=str(RESULT_ROOT)), name="result")
    except Exception as e:
        logger.warning(f"Failed to mount static files: {e}")


class TranslateRequest(BaseModel):
    """翻译请求模型"""
    image_url: Optional[str] = None
    image_base64: Optional[str] = None
    config: Dict[str, Any] = {}
    env: Optional[Dict[str, str]] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return {"status": "ok"}


@app.get("/api", tags=["api"])
async def api_info():
    """API信息（JSON格式）"""
    return {
        "service": "Manga Translator",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "translate": "/translate",
            "translate_stream": "/translate/with-form/image/stream",
            "status": "/status",
            "queue_size": "/queue-size",
            "results_list": "/results/list",
            "results_clear": "/results/clear",
            "results_delete": "/results/{folder_name}"
        }
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    """Web UI界面"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Manga Translator FC - 管理界面</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        .section { margin: 20px 0; padding: 15px; background: #f9f9f9; border-radius: 4px; }
        .endpoint { margin: 10px 0; padding: 10px; background: white; border-left: 3px solid #007bff; }
        .endpoint code { color: #007bff; }
        button { padding: 8px 16px; margin: 5px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        button.danger { background: #dc3545; }
        button.danger:hover { background: #c82333; }
        .results-list { margin: 10px 0; }
        .result-item { padding: 10px; margin: 5px 0; background: white; border: 1px solid #ddd; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
        .status { padding: 5px 10px; border-radius: 4px; font-size: 12px; }
        .status.ok { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 Manga Translator FC - 管理界面</h1>
        
        <div class="section">
            <h2>📊 服务状态</h2>
            <div id="status" class="status ok">运行中</div>
            <p>服务地址: <code>https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run</code></p>
        </div>
        
        <div class="section">
            <h2>📋 API端点</h2>
            <div class="endpoint">
                <strong>GET</strong> <code>/health</code> - 健康检查
            </div>
            <div class="endpoint">
                <strong>POST</strong> <code>/translate</code> - 翻译接口（JSON）
            </div>
            <div class="endpoint">
                <strong>POST</strong> <code>/translate/with-form/image/stream</code> - 流式翻译接口（Form）
            </div>
            <div class="endpoint">
                <strong>GET</strong> <code>/results/list</code> - 查看结果列表
            </div>
            <div class="endpoint">
                <strong>DELETE</strong> <code>/results/{folder_name}</code> - 删除指定结果
            </div>
            <div class="endpoint">
                <strong>DELETE</strong> <code>/results/clear</code> - 清空所有结果
            </div>
        </div>
        
        <div class="section">
            <h2>🗂️ 缓存管理</h2>
            <button onclick="loadResults()">刷新列表</button>
            <button onclick="clearAll()" class="danger">清空所有缓存</button>
            <div id="results" class="results-list"></div>
        </div>
    </div>
    
    <script>
        async function loadResults() {
            try {
                const response = await fetch('/results/list');
                const data = await response.json();
                const resultsDiv = document.getElementById('results');
                if (data.directories && data.directories.length > 0) {
                    resultsDiv.innerHTML = '<h3>结果列表:</h3>' + 
                        data.directories.map(dir => `
                            <div class="result-item">
                                <span>${dir}</span>
                                <button onclick="deleteResult('${dir}')" class="danger">删除</button>
                            </div>
                        `).join('');
                } else {
                    resultsDiv.innerHTML = '<p>暂无结果文件</p>';
                }
            } catch (error) {
                document.getElementById('results').innerHTML = '<p class="status error">加载失败: ' + error.message + '</p>';
            }
        }
        
        async function deleteResult(folderName) {
            if (!confirm('确定要删除 ' + folderName + ' 吗？')) return;
            try {
                const response = await fetch(`/results/${folderName}`, { method: 'DELETE' });
                const data = await response.json();
                alert(data.message || '删除成功');
                loadResults();
            } catch (error) {
                alert('删除失败: ' + error.message);
            }
        }
        
        async function clearAll() {
            if (!confirm('确定要清空所有缓存吗？此操作不可恢复！')) return;
            try {
                const response = await fetch('/results/clear', { method: 'DELETE' });
                const data = await response.json();
                alert(data.message || '清空成功');
                loadResults();
            } catch (error) {
                alert('清空失败: ' + error.message);
            }
        }
        
        // 页面加载时自动加载结果列表
        loadResults();
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.post("/translate")
async def translate(request: TranslateRequest):
    """翻译图片"""
    try:
        # 设置环境变量
        if request.env:
            for key, value in request.env.items():
                os.environ[key] = value
                logger.info(f"Set environment variable: {key}")
        
        # 获取图片数据
        image_data = None
        if request.image_url:
            logger.info(f"Downloading image from: {request.image_url}")
            response = requests.get(request.image_url, timeout=30)
            response.raise_for_status()
            image_data = response.content
        elif request.image_base64:
            logger.info("Decoding base64 image")
            image_data = base64.b64decode(request.image_base64)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either image_url or image_base64 must be provided"
            )
        
        # 加载图片
        try:
            image = Image.open(io.BytesIO(image_data))
            logger.info(f"Image loaded: {image.size}, mode: {image.mode}")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to load image: {str(e)}"
            )
        
        # 创建配置
        try:
            config = Config(**request.config)
            logger.info(f"Config created: translator={config.translator.translator}")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid config: {str(e)}"
            )
        
        # 执行翻译
        logger.info("Starting translation...")
        # MangaTranslator.__init__ 期望接收字典，而不是Config对象
        translator_params = {
            'use_gpu': True,  # FC环境使用GPU
            'verbose': False,
            'kernel_size': config.kernel_size if hasattr(config, 'kernel_size') else 3,
            'input': [],  # 必需参数
            'save_text': False,
            'load_text': False,
        }
        translator = MangaTranslator(translator_params)
        
        # 运行异步翻译（translate方法接收Config对象，返回Context对象）
        result_ctx = await translator.translate(image, config)
        result_image = result_ctx.result
        logger.info("Translation completed")
        
        # 转换为base64
        img_byte_arr = io.BytesIO()
        result_image.save(img_byte_arr, format='PNG')
        result_bytes = img_byte_arr.getvalue()
        result_base64 = base64.b64encode(result_bytes).decode('utf-8')
        
        return {
            "success": True,
            "result_image_base64": result_base64,
            "result_size": len(result_bytes),
            "original_size": len(image_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )


async def stream_translation(image: Image.Image, config: Config, translator_params: dict = None):
    """
    流式翻译生成器（异步生成器）
    使用进度hook实现流式进度报告，类似队列系统
    流式响应格式: 1byte status + 4byte size + n byte data
    Status 码说明:
      - 0: 结果数据（图片）
      - 1: 进度报告
      - 2: 错误信息
      - 3: 队列位置（FC环境不使用队列，始终为0）
    """
    # 创建进度队列用于流式传输
    progress_queue = asyncio.Queue()
    result_image_bytes = None
    error_message = None
    
    try:
        # 发送进度：开始翻译
        progress_msg = "Starting translation...".encode('utf-8')
        yield b'\x01' + len(progress_msg).to_bytes(4, 'big') + progress_msg
        
        # 创建翻译器
        # 使用Kotlin发送的translator_params，如果没有则使用默认值
        if translator_params is None:
            translator_params = {
                'use_gpu': True,  # FC环境使用GPU
                'verbose': False,
                'kernel_size': config.kernel_size if hasattr(config, 'kernel_size') else 3,
                'input': [],  # 必需参数
                'save_text': False,
                'load_text': False,
            }
        translator = MangaTranslator(translator_params)
        
        # 添加进度hook，将进度信息发送到队列
        async def progress_hook(state: str, finished: bool):
            """进度回调函数，将进度信息发送到队列"""
            try:
                state_data = state.encode('utf-8')
                progress_data = b'\x01' + len(state_data).to_bytes(4, 'big') + state_data
                await progress_queue.put(progress_data)
            except Exception as e:
                logger.error(f"Error in progress hook: {e}")
        
        translator.add_progress_hook(progress_hook)
        
        # 创建翻译任务（在后台运行）
        async def translate_task():
            nonlocal result_image_bytes, error_message
            try:
                # translate方法接收Config对象，返回Context对象
                result_ctx = await translator.translate(image, config)
                result_image = result_ctx.result
                
                # 转换为PNG字节
                img_byte_arr = io.BytesIO()
                result_image.save(img_byte_arr, format='PNG')
                result_image_bytes = img_byte_arr.getvalue()
                
                # 发送完成信号
                await progress_queue.put(None)  # None表示翻译完成
            except Exception as e:
                logger.error(f"Translation task error: {e}", exc_info=True)
                error_message = str(e)
                await progress_queue.put(None)  # 发送完成信号（即使出错）
        
        # 启动翻译任务
        translate_coro = asyncio.create_task(translate_task())
        
        # 流式发送进度和结果
        while True:
            try:
                # 等待进度更新或结果
                item = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                
                if item is None:
                    # 翻译完成，检查结果
                    if error_message:
                        error_msg = error_message.encode('utf-8')
                        yield b'\x02' + len(error_msg).to_bytes(4, 'big') + error_msg
                    elif result_image_bytes:
                        # 发送结果图片
                        yield b'\x00' + len(result_image_bytes).to_bytes(4, 'big') + result_image_bytes
                    break
                else:
                    # 发送进度信息
                    yield item
                    
            except asyncio.TimeoutError:
                # 检查翻译任务是否完成
                if translate_coro.done():
                    # 任务完成，处理剩余数据
                    if error_message:
                        error_msg = error_message.encode('utf-8')
                        yield b'\x02' + len(error_msg).to_bytes(4, 'big') + error_msg
                    elif result_image_bytes:
                        yield b'\x00' + len(result_image_bytes).to_bytes(4, 'big') + result_image_bytes
                    break
                # 继续等待
                continue
        
    except Exception as e:
        logger.error(f"Streaming translation error: {str(e)}", exc_info=True)
        error_msg = str(e).encode('utf-8')
        yield b'\x02' + len(error_msg).to_bytes(4, 'big') + error_msg


@app.post("/translate/with-form/image/stream", response_class=StreamingResponse, 
          tags=["api", "form"], 
          response_description="A stream over elements with structure(1byte status, 4 byte size, n byte data) status code are 0,1,2,3,4 0 is result data, 1 is progress report, 2 is error, 3 is waiting queue position, 4 is waiting for translator instance")
async def stream_image_form(req: Request, image: UploadFile = File(...), config: str = Form("{}")):
    """
    流式翻译端点（兼容Kotlin后端）
    使用multipart/form-data格式，包含image文件和config JSON字符串
    返回流式响应，格式：1byte status + 4byte size + n byte data
    """
    try:
        # 读取图片数据
        img_bytes = await image.read()
        logger.info(f"Received image: {image.filename}, size: {len(img_bytes)} bytes")
        
        # 加载图片
        try:
            pil_image = Image.open(io.BytesIO(img_bytes))
            logger.info(f"Image loaded: {pil_image.size}, mode: {pil_image.mode}")
        except Exception as e:
            error_msg = f"Failed to load image: {str(e)}".encode('utf-8')
            async def error_stream():
                yield b'\x02' + len(error_msg).to_bytes(4, 'big') + error_msg
            return StreamingResponse(error_stream(), media_type="application/octet-stream")
        
        # 解析配置
        try:
            import json
            params_dict = json.loads(config) if config else {}
            
            # 从params_dict中提取config部分（用于translate方法）
            config_dict = params_dict.pop('config', params_dict)  # 如果没有config字段，使用整个字典
            
            # 从config_dict中提取env（如果存在），然后从config_dict中移除
            env_vars = config_dict.pop('env', None)
            
            # 创建Config对象（用于translate方法）
            translation_config = Config(**config_dict)
            logger.info(f"Config created: translator={translation_config.translator.translator}")
            
            # 设置环境变量（如果配置中有）
            if env_vars and isinstance(env_vars, dict):
                for key, value in env_vars.items():
                    os.environ[key] = str(value)
                    logger.info(f"Set environment variable: {key}")
        except Exception as e:
            error_msg = f"Invalid config: {str(e)}".encode('utf-8')
            async def error_stream():
                yield b'\x02' + len(error_msg).to_bytes(4, 'big') + error_msg
            return StreamingResponse(error_stream(), media_type="application/octet-stream")
        
        # 创建流式响应（直接使用异步生成器）
        # 传递translator_params给stream_translation函数
        return StreamingResponse(
            stream_translation(pil_image, translation_config, params_dict),
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        logger.error(f"Stream endpoint error: {str(e)}", exc_info=True)
        error_msg = f"Translation failed: {str(e)}".encode('utf-8')
        async def error_stream():
            yield b'\x02' + len(error_msg).to_bytes(4, 'big') + error_msg
        return StreamingResponse(error_stream(), media_type="application/octet-stream")


@app.get("/results/list", tags=["api"])
async def list_results():
    """列出所有结果目录"""
    try:
        if not RESULT_ROOT.exists():
            return {"directories": []}
        
        directories = []
        for item_path in RESULT_ROOT.iterdir():
            if item_path.is_dir():
                # 检查是否有final.png文件
                final_png_path = item_path / "final.png"
                if final_png_path.exists():
                    directories.append(item_path.name)
        
        return {"directories": directories}
    except Exception as e:
        logger.error(f"Error listing results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing results: {str(e)}")


@app.delete("/results/clear", tags=["api"])
async def clear_results():
    """清空所有结果目录"""
    try:
        if not RESULT_ROOT.exists():
            return {"message": "No results directory found"}
        
        deleted_count = 0
        for item_path in RESULT_ROOT.iterdir():
            if item_path.is_dir():
                final_png_path = item_path / "final.png"
                if final_png_path.exists():
                    shutil.rmtree(item_path)
                    deleted_count += 1
        
        logger.info(f"Cleared {deleted_count} result directories")
        return {"message": f"Deleted {deleted_count} result directories"}
    except Exception as e:
        logger.error(f"Error clearing results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error clearing results: {str(e)}")


@app.delete("/results/{folder_name}", tags=["api"])
async def delete_result(folder_name: str):
    """删除指定的结果目录"""
    try:
        # 安全检查：防止路径遍历攻击
        if ".." in folder_name or "/" in folder_name or "\\" in folder_name:
            raise HTTPException(status_code=400, detail="Invalid folder name")
        
        folder_path = RESULT_ROOT / folder_name
        
        if not folder_path.exists():
            raise HTTPException(status_code=404, detail="Result directory not found")
        
        # 检查是否有final.png文件
        final_png_path = folder_path / "final.png"
        if not final_png_path.exists():
            raise HTTPException(status_code=404, detail="Result file not found")
        
        shutil.rmtree(folder_path)
        logger.info(f"Deleted result directory: {folder_name}")
        return {"message": f"Deleted result directory: {folder_name}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting result: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting result: {str(e)}")


@app.get("/queue-size", tags=["api"])
async def queue_size():
    """获取队列大小（FC环境始终返回0，因为不使用队列）"""
    return 0


@app.get("/status", tags=["api"])
async def status():
    """获取服务状态"""
    try:
        result_count = 0
        if RESULT_ROOT.exists():
            for item_path in RESULT_ROOT.iterdir():
                if item_path.is_dir() and (item_path / "final.png").exists():
                    result_count += 1
        
        return {
            "status": "running",
            "version": "1.0.0",
            "result_count": result_count,
            "result_directory": str(RESULT_ROOT)
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


# FC HTTP触发器入口
def handler(environ, start_response):
    """
    WSGI入口（兼容FC的HTTP触发器）
    """
    from mangum import Mangum
    asgi_handler = Mangum(app)
    return asgi_handler(environ, start_response)


# 如果直接运行，启动开发服务器
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 9000))
    uvicorn.run(app, host="0.0.0.0", port=port)


