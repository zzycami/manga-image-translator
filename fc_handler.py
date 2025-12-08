#!/usr/bin/env python3
"""
阿里云函数计算入口函数
处理HTTP触发器请求
"""
import json
import base64
import io
import os
import logging
from typing import Dict, Any
from PIL import Image
import requests

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入翻译模块
from manga_translator import MangaTranslator, Config

def handler(environ, start_response):
    """
    FC HTTP触发器入口函数
    environ: WSGI环境变量
    start_response: WSGI响应函数
    """
    try:
        # 解析请求
        request_method = environ.get('REQUEST_METHOD', 'GET')
        path_info = environ.get('PATH_INFO', '/')
        
        # 读取请求体
        content_length = int(environ.get('CONTENT_LENGTH', 0))
        request_body = environ['wsgi.input'].read(content_length) if content_length > 0 else b''
        
        # 处理不同路径
        if path_info == '/health':
            return handle_health(start_response)
        elif path_info == '/translate' and request_method == 'POST':
            return handle_translate(request_body, start_response)
        else:
            return handle_404(start_response)
            
    except Exception as e:
        logger.error(f"Handler error: {str(e)}", exc_info=True)
        return handle_error(str(e), start_response)


def handle_health(start_response):
    """健康检查"""
    response_body = json.dumps({"status": "ok"}).encode('utf-8')
    status = '200 OK'
    headers = [('Content-Type', 'application/json')]
    start_response(status, headers)
    return [response_body]


def handle_404(start_response):
    """404处理"""
    response_body = json.dumps({"error": "Not Found"}).encode('utf-8')
    status = '404 Not Found'
    headers = [('Content-Type', 'application/json')]
    start_response(status, headers)
    return [response_body]


def handle_error(error_msg: str, start_response):
    """错误处理"""
    response_body = json.dumps({"error": error_msg}).encode('utf-8')
    status = '500 Internal Server Error'
    headers = [('Content-Type', 'application/json')]
    start_response(status, headers)
    return [response_body]


async def translate_image_async(image_data: bytes, config_dict: Dict[str, Any]) -> bytes:
    """异步翻译图片"""
    import asyncio
    
    # 加载图片
    image = Image.open(io.BytesIO(image_data))
    
    # 创建配置
    config = Config(**config_dict)
    
    # 创建翻译器
    translator = MangaTranslator(config)
    
    # 执行翻译
    result = await translator.translate(image)
    
    # 转换为字节
    img_byte_arr = io.BytesIO()
    result.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()


def handle_translate(request_body: bytes, start_response):
    """处理翻译请求"""
    try:
        # 解析JSON请求
        request_data = json.loads(request_body.decode('utf-8'))
        
        # 获取图片数据
        image_data = None
        if 'image_url' in request_data:
            # 从URL下载图片
            image_url = request_data['image_url']
            response = requests.get(image_url, timeout=30)
            image_data = response.content
        elif 'image_base64' in request_data:
            # Base64编码的图片
            image_data = base64.b64decode(request_data['image_base64'])
        else:
            raise ValueError("Missing image_url or image_base64")
        
        # 获取配置
        config_dict = request_data.get('config', {})
        
        # 设置环境变量（API密钥等）
        if 'env' in request_data:
            for key, value in request_data['env'].items():
                os.environ[key] = value
        
        # 执行翻译（同步方式）
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_image = loop.run_until_complete(
                translate_image_async(image_data, config_dict)
            )
        finally:
            loop.close()
        
        # 返回结果
        result_base64 = base64.b64encode(result_image).decode('utf-8')
        response_body = json.dumps({
            "success": True,
            "result_image_base64": result_base64,
            "result_size": len(result_image)
        }).encode('utf-8')
        
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        return [response_body]
        
    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        return handle_error(f"Translation failed: {str(e)}", start_response)


# 为了兼容FC的HTTP触发器，也可以使用这个简化版本
def handler_http(event, context):
    """
    FC HTTP触发器入口（简化版）
    event: 事件对象
    context: 上下文对象
    """
    try:
        # 解析请求
        path = event.get('path', '/')
        method = event.get('httpMethod', 'GET')
        body = event.get('body', '{}')
        headers = event.get('headers', {})
        
        # 处理健康检查
        if path == '/health':
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({"status": "ok"})
            }
        
        # 处理翻译请求
        if path == '/translate' and method == 'POST':
            request_data = json.loads(body)
            
            # 获取图片
            image_data = None
            if 'image_url' in request_data:
                image_url = request_data['image_url']
                response = requests.get(image_url, timeout=30)
                image_data = response.content
            elif 'image_base64' in request_data:
                image_data = base64.b64decode(request_data['image_base64'])
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({"error": "Missing image_url or image_base64"})
                }
            
            # 获取配置
            config_dict = request_data.get('config', {})
            
            # 设置环境变量
            if 'env' in request_data:
                for key, value in request_data['env'].items():
                    os.environ[key] = value
            
            # 执行翻译
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_image = loop.run_until_complete(
                    translate_image_async(image_data, config_dict)
                )
            finally:
                loop.close()
            
            # 返回结果
            result_base64 = base64.b64encode(result_image).decode('utf-8')
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    "success": True,
                    "result_image_base64": result_base64,
                    "result_size": len(result_image)
                })
            }
        
        return {
            'statusCode': 404,
            'body': json.dumps({"error": "Not Found"})
        }
        
    except Exception as e:
        logger.error(f"Handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({"error": str(e)})
        }

