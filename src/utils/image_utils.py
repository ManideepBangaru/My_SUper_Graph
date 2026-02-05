"""
Image utilities for multimodal LLM support.

Provides functions to fetch images from S3 and convert them to base64
format suitable for sending to vision-capable LLMs like Gemini.
"""

import asyncio
import base64
import os
from typing import Optional

# Support both LangGraph Studio and FastAPI server imports
try:
    from utils.s3_operations import S3Operations
except ImportError:
    from src.utils.s3_operations import S3Operations


# Mapping of file extensions to MIME types
MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "webp": "image/webp",
}

# Default maximum number of images to include (to avoid token overflow)
DEFAULT_MAX_IMAGES = 10


def get_mime_type(s3_key: str) -> str:
    """
    Get the MIME type based on the file extension in the S3 key.
    
    Args:
        s3_key: S3 key containing the filename with extension
        
    Returns:
        MIME type string, defaults to "image/png" if unknown
    """
    ext = s3_key.rsplit(".", 1)[-1].lower() if "." in s3_key else ""
    return MIME_TYPES.get(ext, "image/png")


async def fetch_single_image_as_base64(
    s3_key: str,
    s3_ops: S3Operations,
) -> Optional[dict]:
    """
    Fetch a single image from S3 and convert to base64.
    
    Args:
        s3_key: S3 key of the image
        s3_ops: S3Operations instance
        
    Returns:
        Dict with key, base64 data URL, and mime_type, or None if failed
    """
    try:
        image_bytes = await s3_ops.download_by_key(s3_key)
        mime_type = get_mime_type(s3_key)
        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        
        return {
            "key": s3_key,
            "base64_url": f"data:{mime_type};base64,{base64_data}",
            "mime_type": mime_type,
        }
    except Exception as e:
        print(f"[Image Utils] Failed to fetch image {s3_key}: {e}")
        return None


async def fetch_images_as_base64(
    image_keys: list[str],
    s3_ops: S3Operations,
    max_images: int = DEFAULT_MAX_IMAGES,
) -> list[dict]:
    """
    Fetch multiple images from S3 and convert to base64.
    
    Downloads images in parallel for better performance.
    
    Args:
        image_keys: List of S3 keys for images to fetch
        s3_ops: S3Operations instance
        max_images: Maximum number of images to fetch (to limit tokens)
        
    Returns:
        List of dicts, each containing:
        - key: S3 key
        - base64_url: Data URL with base64 content (e.g., "data:image/png;base64,...")
        - mime_type: MIME type of the image
    """
    if not image_keys:
        return []
    
    # Limit number of images
    keys_to_fetch = image_keys[:max_images]
    
    if len(image_keys) > max_images:
        print(f"[Image Utils] Limiting images from {len(image_keys)} to {max_images}")
    
    # Fetch all images in parallel
    tasks = [
        fetch_single_image_as_base64(key, s3_ops)
        for key in keys_to_fetch
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Filter out None results (failed fetches)
    successful_results = [r for r in results if r is not None]
    
    print(f"[Image Utils] Fetched {len(successful_results)}/{len(keys_to_fetch)} images")
    
    return successful_results


async def fetch_images_for_chunks(
    document_chunks: list[dict],
    s3_ops: S3Operations,
    max_total_images: int = DEFAULT_MAX_IMAGES,
) -> dict[str, list[dict]]:
    """
    Fetch images for all document chunks, organized by page.
    
    Args:
        document_chunks: List of chunk dicts with image_keys
        s3_ops: S3Operations instance
        max_total_images: Maximum total images across all pages
        
    Returns:
        Dict mapping "filename:page_num" to list of base64 image dicts
    """
    # Collect all unique image keys with their page info
    page_images: dict[str, list[str]] = {}
    all_keys: list[str] = []
    
    for chunk in document_chunks:
        filename = chunk.get("filename", "unknown")
        page_num = chunk.get("page_num", 0)
        image_keys = chunk.get("image_keys", [])
        
        if image_keys:
            page_key = f"{filename}:{page_num}"
            if page_key not in page_images:
                page_images[page_key] = []
            
            for key in image_keys:
                if key not in all_keys:  # Avoid duplicates
                    all_keys.append(key)
                    page_images[page_key].append(key)
    
    if not all_keys:
        return {}
    
    # Limit total images
    if len(all_keys) > max_total_images:
        print(f"[Image Utils] Limiting total images from {len(all_keys)} to {max_total_images}")
        all_keys = all_keys[:max_total_images]
    
    # Fetch all images
    fetched = await fetch_images_as_base64(all_keys, s3_ops, max_images=max_total_images)
    
    # Create lookup by key
    fetched_by_key = {img["key"]: img for img in fetched}
    
    # Organize results by page
    result: dict[str, list[dict]] = {}
    for page_key, keys in page_images.items():
        page_results = []
        for key in keys:
            if key in fetched_by_key:
                page_results.append(fetched_by_key[key])
        if page_results:
            result[page_key] = page_results
    
    return result
