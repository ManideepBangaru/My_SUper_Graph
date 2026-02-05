"""
S3Operations - Handles file upload/download operations to AWS S3.

Uses AWS SSO profile-based authentication and stores files in a structured
folder hierarchy: {prefix}/{user_id}/{thread_id}/{filename}
"""

import asyncio
import os
from typing import BinaryIO, Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


# Allowed file extensions and their content types
ALLOWED_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Image types for extracted PDF images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


class S3Operations:
    """
    Handles S3 file operations with SSO profile authentication.
    
    Usage:
        s3_ops = S3Operations()
        
        # Upload a single file
        await s3_ops.upload_file(file_data, "document.pdf", "user_123", "thread_456")
        
        # Upload multiple files
        await s3_ops.upload_files(files, "user_123", "thread_456")
        
        # List files for a thread
        files = await s3_ops.list_files("user_123", "thread_456")
        
        # Download a file
        file_data = await s3_ops.download_file("document.pdf", "user_123", "thread_456")
    """
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        prefix: Optional[str] = None,
        profile_name: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME")
        self.prefix = prefix or os.getenv("S3_PREFIX", "")
        self.profile_name = profile_name or os.getenv("AWS_PROFILE")
        
        if not self.bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable is required")
        
        # Create boto3 session with SSO profile
        self._session = boto3.Session(profile_name=self.profile_name)
        self._s3_client = self._session.client("s3")
    
    def _build_s3_key(self, user_id: str, thread_id: str, filename: str) -> str:
        """Build the full S3 key for a file."""
        if self.prefix:
            return f"{self.prefix}/{user_id}/{thread_id}/{filename}"
        return f"{user_id}/{thread_id}/{filename}"
    
    def _get_content_type(self, filename: str) -> str:
        """Get the content type based on file extension."""
        ext = os.path.splitext(filename)[1].lower()
        return ALLOWED_FILE_TYPES.get(ext, "application/octet-stream")
    
    def _validate_file_type(self, filename: str) -> bool:
        """Validate that the file type is allowed."""
        ext = os.path.splitext(filename)[1].lower()
        return ext in ALLOWED_FILE_TYPES
    
    async def upload_file(
        self,
        file_data: bytes | BinaryIO,
        filename: str,
        user_id: str,
        thread_id: str,
    ) -> dict:
        """
        Upload a single file to S3.
        
        Args:
            file_data: File content as bytes or file-like object
            filename: Name of the file
            user_id: User identifier
            thread_id: Thread identifier
            
        Returns:
            Dict with upload details (key, bucket, size)
            
        Raises:
            ValueError: If file type is not allowed
            ClientError: If S3 upload fails
        """
        if not self._validate_file_type(filename):
            allowed = ", ".join(ALLOWED_FILE_TYPES.keys())
            raise ValueError(f"File type not allowed. Allowed types: {allowed}")
        
        s3_key = self._build_s3_key(user_id, thread_id, filename)
        content_type = self._get_content_type(filename)
        
        # Convert bytes to file-like object if needed
        if isinstance(file_data, bytes):
            from io import BytesIO
            file_obj = BytesIO(file_data)
            file_size = len(file_data)
        else:
            file_obj = file_data
            # Get file size
            file_obj.seek(0, 2)  # Seek to end
            file_size = file_obj.tell()
            file_obj.seek(0)  # Seek back to start
        
        # Run S3 upload in thread pool to not block async event loop
        def _upload():
            self._s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={"ContentType": content_type}
            )
        
        await asyncio.to_thread(_upload)
        
        return {
            "key": s3_key,
            "bucket": self.bucket_name,
            "filename": filename,
            "size": file_size,
            "content_type": content_type,
        }
    
    async def upload_files(
        self,
        files: list[tuple[bytes | BinaryIO, str]],
        user_id: str,
        thread_id: str,
    ) -> list[dict]:
        """
        Upload multiple files to S3 in parallel.
        
        Args:
            files: List of tuples (file_data, filename)
            user_id: User identifier
            thread_id: Thread identifier
            
        Returns:
            List of upload result dicts
        """
        tasks = [
            self.upload_file(file_data, filename, user_id, thread_id)
            for file_data, filename in files
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results, converting exceptions to error dicts
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "filename": files[i][1],
                    "error": str(result),
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def download_file(
        self,
        filename: str,
        user_id: str,
        thread_id: str,
    ) -> bytes:
        """
        Download a file from S3.
        
        Args:
            filename: Name of the file
            user_id: User identifier
            thread_id: Thread identifier
            
        Returns:
            File content as bytes
            
        Raises:
            ClientError: If file doesn't exist or download fails
        """
        from io import BytesIO
        
        s3_key = self._build_s3_key(user_id, thread_id, filename)
        buffer = BytesIO()
        
        def _download():
            self._s3_client.download_fileobj(self.bucket_name, s3_key, buffer)
        
        await asyncio.to_thread(_download)
        buffer.seek(0)
        return buffer.read()
    
    async def download_by_key(self, s3_key: str) -> bytes:
        """
        Download a file directly by its S3 key.
        
        This is useful when you have the full S3 key (e.g., from image_keys in document_chunks)
        rather than constructing it from user/thread/filename.
        
        Args:
            s3_key: Full S3 key of the file
            
        Returns:
            File content as bytes
            
        Raises:
            ClientError: If file doesn't exist or download fails
        """
        from io import BytesIO
        
        buffer = BytesIO()
        
        def _download():
            self._s3_client.download_fileobj(self.bucket_name, s3_key, buffer)
        
        await asyncio.to_thread(_download)
        buffer.seek(0)
        return buffer.read()
    
    async def get_presigned_url(
        self,
        filename: str,
        user_id: str,
        thread_id: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for downloading a file.
        
        Args:
            filename: Name of the file
            user_id: User identifier
            thread_id: Thread identifier
            expiration: URL expiration time in seconds (default: 1 hour)
            
        Returns:
            Presigned URL string
        """
        s3_key = self._build_s3_key(user_id, thread_id, filename)
        
        def _generate_url():
            return self._s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
        
        return await asyncio.to_thread(_generate_url)
    
    async def list_files(
        self,
        user_id: str,
        thread_id: str,
    ) -> list[dict]:
        """
        List all files for a specific user/thread.
        
        Args:
            user_id: User identifier
            thread_id: Thread identifier
            
        Returns:
            List of file info dicts (key, filename, size, last_modified)
        """
        prefix = self._build_s3_key(user_id, thread_id, "")
        
        def _list_objects():
            response = self._s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
            )
            return response.get("Contents", [])
        
        objects = await asyncio.to_thread(_list_objects)
        
        files = []
        for obj in objects:
            # Extract filename from the full key
            filename = obj["Key"].split("/")[-1]
            if filename:  # Skip empty filenames (folder markers)
                files.append({
                    "key": obj["Key"],
                    "filename": filename,
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                })
        
        return files
    
    async def delete_file(
        self,
        filename: str,
        user_id: str,
        thread_id: str,
    ) -> dict:
        """
        Delete a file from S3.
        
        Args:
            filename: Name of the file
            user_id: User identifier
            thread_id: Thread identifier
            
        Returns:
            Dict with deletion status
            
        Raises:
            ClientError: If deletion fails
        """
        s3_key = self._build_s3_key(user_id, thread_id, filename)
        
        def _delete():
            self._s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
        
        await asyncio.to_thread(_delete)
        
        return {
            "deleted": True,
            "key": s3_key,
            "filename": filename,
        }
    
    async def file_exists(
        self,
        filename: str,
        user_id: str,
        thread_id: str,
    ) -> bool:
        """
        Check if a file exists in S3.
        
        Args:
            filename: Name of the file
            user_id: User identifier
            thread_id: Thread identifier
            
        Returns:
            True if file exists, False otherwise
        """
        s3_key = self._build_s3_key(user_id, thread_id, filename)
        
        def _head_object():
            try:
                self._s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                return True
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                # S3 returns "404" or "NoSuchKey" for missing objects
                if error_code in ("404", "NoSuchKey"):
                    return False
                raise
            except Exception:
                # If we can't check, assume it doesn't exist
                return False
        
        return await asyncio.to_thread(_head_object)
