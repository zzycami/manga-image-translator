import asyncio
import builtins
import hashlib
import io
import re
from base64 import b64decode
from typing import Optional, Tuple, Union

import requests
from PIL import Image
from fastapi import Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

from manga_translator import Config
from server.myqueue import task_queue, wait_in_queue, QueueElement, BatchQueueElement
from server.streaming import notify, stream

class TranslateRequest(BaseModel):
    """This request can be a multipart or a json request"""
    image: bytes|str
    """can be a url, base64 encoded image or a multipart image"""
    config: Config = Config()
    """in case it is a multipart this needs to be a string(json.stringify)"""

class BatchTranslateRequest(BaseModel):
    """Batch translation request"""
    images: list[bytes|str]
    """List of images, can be URLs, base64 encoded strings, or binary data"""
    config: Config = Config()
    """Translation configuration"""
    batch_size: int = 4
    """Batch size, default is 4"""

async def resolve_raw_image_bytes(image: Union[str, bytes]) -> bytes:
    """Raw file bytes used for MD5 correlation (same bytes Hub/client hash)."""
    try:
        if isinstance(image, builtins.bytes):
            if len(image) == 0:
                raise ValueError("Image data is empty")
            return image
        if re.match(r'^data:image/.+;base64,', image):
            value = image.split(',', 1)[1]
            image_data = b64decode(value)
            if len(image_data) == 0:
                raise ValueError("Decoded image data is empty")
            return image_data
        response = requests.get(image)
        if len(response.content) == 0:
            raise ValueError("Downloaded image data is empty")
        return response.content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to load image bytes: {str(e)}")


def bind_source_image_md5(
    config: Config,
    image_bytes: bytes,
    declared_md5: Optional[str] = None,
) -> Tuple[Config, str]:
    """Compute MD5 of raw upload bytes; reject if client-declared md5 mismatches.

    Fills config.source_image_md5 with the server-computed value for stages echo.
    """
    if not image_bytes:
        raise HTTPException(status_code=422, detail="Image file is empty")
    src_md5 = hashlib.md5(image_bytes).hexdigest()
    declared = (declared_md5 or config.source_image_md5 or "").strip().lower()
    if declared and declared != src_md5:
        raise HTTPException(
            status_code=422,
            detail=f"SOURCE_IMAGE_MD5_MISMATCH: declared={declared}, received={src_md5}",
        )
    config.source_image_md5 = src_md5
    return config, src_md5


async def to_pil_image(image: Union[str, bytes]) -> Image.Image:
    try:
        if isinstance(image, builtins.bytes):
            if len(image) == 0:
                raise ValueError("Image data is empty")
            image_obj = Image.open(io.BytesIO(image))
            return image_obj
        else:
            if re.match(r'^data:image/.+;base64,', image):
                value = image.split(',', 1)[1]
                image_data = b64decode(value)
                if len(image_data) == 0:
                    raise ValueError("Decoded image data is empty")
                image_obj = Image.open(io.BytesIO(image_data))
                return image_obj
            else:
                response = requests.get(image)
                if len(response.content) == 0:
                    raise ValueError("Downloaded image data is empty")
                image_obj = Image.open(io.BytesIO(response.content))
                return image_obj
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to load image: {str(e)}")


async def get_ctx(req: Request, config: Config, image: str|bytes):
    image = await to_pil_image(image)

    task = QueueElement(req, image, config, 0)
    task_queue.add_task(task)

    return await wait_in_queue(task, None)

async def while_streaming(req: Request, transform, config: Config, image: bytes | str, meta: dict | None = None):
    image = await to_pil_image(image)

    task = QueueElement(req, image, config, 0)
    task_queue.add_task(task)

    messages = asyncio.Queue()

    def notify_internal(code: int, data: bytes) -> None:
        notify(code, data, transform, messages)

    # Optional metadata frame (status=5). Backward-compatible:
    # - Existing clients that only handle 0..4 will ignore it.
    # - New clients can validate correlation (e.g., source image md5 / request id).
    if meta:
        import json
        meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
        messages.put_nowait((5).to_bytes(1, "big") + len(meta_bytes).to_bytes(4, "big") + meta_bytes)
    streaming_response = StreamingResponse(stream(messages), media_type="application/octet-stream")
    asyncio.create_task(wait_in_queue(task, notify_internal))
    return streaming_response

async def get_batch_ctx(req: Request, config: Config, images: list[str|bytes], batch_size: int = 4):
    """Process batch translation request"""
    # Convert images to PIL Image objects
    pil_images = []
    for img in images:
        pil_img = await to_pil_image(img)
        pil_images.append(pil_img)
    
    # Create batch task
    batch_task = BatchQueueElement(req, pil_images, config, batch_size)
    task_queue.add_task(batch_task)
    
    return await wait_in_queue(batch_task, None)
