"""
File upload/download routes for S3 operations.
Supports PDF and PPTX file uploads with user/thread organization.
Includes background processing for text extraction and chunking.
"""

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from src.api.database import delete_document_chunks, get_processing_status
from src.utils.pdf_processor import process_uploaded_file
from src.utils.pptx_processor import process_uploaded_pptx_file
from src.utils.s3_operations import S3Operations, ALLOWED_FILE_TYPES

# PPTX content type for detection
PPTX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

router = APIRouter(prefix="/api/files", tags=["files"])


class FileUploadResponse(BaseModel):
    """Response model for file upload."""
    key: str
    bucket: str
    filename: str
    size: int
    content_type: str


class FileListItem(BaseModel):
    """Model for a single file in list response."""
    key: str
    filename: str
    size: int
    last_modified: str


class FileDeleteResponse(BaseModel):
    """Response model for file deletion."""
    deleted: bool
    key: str
    filename: str


class UploadResult(BaseModel):
    """Result for a single file upload (success or error)."""
    filename: str
    key: str | None = None
    bucket: str | None = None
    size: int | None = None
    content_type: str | None = None
    error: str | None = None


class MultiUploadResponse(BaseModel):
    """Response model for multiple file uploads."""
    uploaded: list[UploadResult]
    success_count: int
    error_count: int
    processing_triggered: int = 0  # Number of files queued for background processing


class FileProcessingStatus(BaseModel):
    """Response model for file processing status."""
    filename: str
    processed: bool
    chunk_count: int
    first_processed_at: str | None = None
    last_processed_at: str | None = None


def _get_s3_ops() -> S3Operations:
    """Get S3Operations instance. Raises HTTPException if not configured."""
    try:
        return S3Operations()
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"S3 not configured: {str(e)}"
        )


@router.post("/upload", response_model=MultiUploadResponse)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    user_id: str = Form(...),
    thread_id: str = Form(...),
):
    """
    Upload one or more files (PDF or PPTX) to S3.
    
    Files are stored at: {prefix}/{user_id}/{thread_id}/{filename}
    PDF and PPTX files are automatically queued for background processing to extract
    text and images for use as conversation context.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    # Validate file types
    allowed_extensions = list(ALLOWED_FILE_TYPES.keys())
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has invalid type. Allowed: {', '.join(allowed_extensions)}"
            )
    
    s3_ops = _get_s3_ops()
    
    # Read file contents and prepare for upload
    files_to_upload = []
    for file in files:
        content = await file.read()
        files_to_upload.append((content, file.filename))
    
    # Upload all files
    results = await s3_ops.upload_files(files_to_upload, user_id, thread_id)
    
    # Format response
    upload_results = []
    success_count = 0
    error_count = 0
    processing_triggered = 0
    
    for result in results:
        if "error" in result:
            error_count += 1
            upload_results.append(UploadResult(
                filename=result["filename"],
                error=result["error"],
            ))
        else:
            success_count += 1
            upload_results.append(UploadResult(
                filename=result["filename"],
                key=result["key"],
                bucket=result["bucket"],
                size=result["size"],
                content_type=result["content_type"],
            ))
            
            # Trigger background processing for PDF files
            if result.get("content_type") == "application/pdf":
                background_tasks.add_task(
                    process_uploaded_file,
                    result["key"],
                    user_id,
                    thread_id,
                    result["filename"],
                )
                processing_triggered += 1
            
            # Trigger background processing for PPTX files
            elif result.get("content_type") == PPTX_CONTENT_TYPE:
                background_tasks.add_task(
                    process_uploaded_pptx_file,
                    result["key"],
                    user_id,
                    thread_id,
                    result["filename"],
                )
                processing_triggered += 1
    
    return MultiUploadResponse(
        uploaded=upload_results,
        success_count=success_count,
        error_count=error_count,
        processing_triggered=processing_triggered,
    )


@router.get("/{user_id}/{thread_id}", response_model=list[FileListItem])
async def list_files(user_id: str, thread_id: str):
    """
    List all files for a specific user and thread.
    """
    s3_ops = _get_s3_ops()
    
    try:
        files = await s3_ops.list_files(user_id, thread_id)
        return [FileListItem(**f) for f in files]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.get("/{user_id}/{thread_id}/{filename}")
async def download_file(user_id: str, thread_id: str, filename: str):
    """
    Download a specific file.
    
    Returns the file content with appropriate content type.
    """
    s3_ops = _get_s3_ops()
    
    # Check if file exists
    exists = await s3_ops.file_exists(filename, user_id, thread_id)
    if not exists:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        content = await s3_ops.download_file(filename, user_id, thread_id)
        content_type = s3_ops._get_content_type(filename)
        
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@router.get("/{user_id}/{thread_id}/{filename}/url")
async def get_presigned_url(
    user_id: str,
    thread_id: str,
    filename: str,
    expiration: int = 3600,
):
    """
    Get a presigned URL for direct file download.
    
    Args:
        expiration: URL expiration time in seconds (default: 1 hour, max: 7 days)
    """
    # Limit expiration to 7 days
    max_expiration = 7 * 24 * 60 * 60
    expiration = min(expiration, max_expiration)
    
    s3_ops = _get_s3_ops()
    
    # Check if file exists
    exists = await s3_ops.file_exists(filename, user_id, thread_id)
    if not exists:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        url = await s3_ops.get_presigned_url(filename, user_id, thread_id, expiration)
        return {"url": url, "expires_in": expiration}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate URL: {str(e)}")


@router.get("/{user_id}/{thread_id}/{filename}/status", response_model=FileProcessingStatus)
async def get_file_status(user_id: str, thread_id: str, filename: str):
    """
    Check if a file has been processed and is ready for queries.
    
    Use this endpoint to poll for processing completion after upload.
    """
    try:
        status = await get_processing_status(thread_id, filename)
        return FileProcessingStatus(
            filename=filename,
            processed=status["processed"],
            chunk_count=status["chunk_count"],
            first_processed_at=status["first_processed_at"],
            last_processed_at=status["last_processed_at"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.delete("/{user_id}/{thread_id}/{filename}", response_model=FileDeleteResponse)
async def delete_file(user_id: str, thread_id: str, filename: str):
    """
    Delete a specific file from S3 and its processed chunks from the database.
    
    Note: S3 delete is idempotent - it succeeds even if the file doesn't exist.
    """
    from botocore.exceptions import ClientError
    
    s3_ops = _get_s3_ops()
    
    try:
        # Delete from S3
        result = await s3_ops.delete_file(filename, user_id, thread_id)
        
        # Also delete processed chunks from database
        await delete_document_chunks(thread_id, filename)
        
        return FileDeleteResponse(**result)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "AccessDenied":
            raise HTTPException(
                status_code=403, 
                detail="Permission denied: Your AWS role doesn't have s3:DeleteObject permission"
            )
        import traceback
        print(f"Delete error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
    except Exception as e:
        import traceback
        print(f"Delete error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
