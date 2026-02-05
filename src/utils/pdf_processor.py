"""
PDF Processor - Extracts text and images from PDF files.

Processes PDFs into chunks suitable for LLM context, with images uploaded to S3.
"""

import asyncio
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Support both LangGraph Studio and FastAPI server imports
try:
    from utils.s3_operations import S3Operations
except ImportError:
    from src.utils.s3_operations import S3Operations


@dataclass
class DocumentChunk:
    """Represents a single chunk of document content."""
    page_num: int
    chunk_index: int
    content: str
    image_keys: list[str]
    
    def to_dict(self) -> dict:
        return {
            "page_num": self.page_num,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "image_keys": self.image_keys,
        }


@dataclass
class PageData:
    """Represents extracted data from a single page."""
    page_num: int
    text: str
    images: list[tuple[bytes, str]]  # (image_bytes, extension)


class PDFProcessor:
    """
    Processes PDF files by extracting text and images.
    
    Text is chunked using RecursiveCharacterTextSplitter for optimal LLM context.
    Images are uploaded to S3 and referenced by key.
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        s3_ops: Optional[S3Operations] = None,
    ):
        """
        Initialize the PDF processor.
        
        Args:
            chunk_size: Maximum size of each text chunk
            chunk_overlap: Overlap between chunks for context continuity
            s3_ops: S3Operations instance for image uploads
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.s3_ops = s3_ops
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    
    def _extract_pages(self, pdf_bytes: bytes) -> list[PageData]:
        """
        Extract text and images from each page of a PDF.
        
        Args:
            pdf_bytes: Raw PDF file content
            
        Returns:
            List of PageData objects, one per page
        """
        pages_data = []
        
        # Open PDF from bytes
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        try:
            for page_num, page in enumerate(doc):
                # Extract text from page
                text = page.get_text("text")
                
                # Extract images
                images = []
                for img in page.get_images():
                    xref = img[0]
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        extension = base_image["ext"]
                        images.append((image_bytes, extension))
                    except Exception:
                        # Skip images that can't be extracted
                        continue
                
                pages_data.append(PageData(
                    page_num=page_num,
                    text=text,
                    images=images,
                ))
        finally:
            doc.close()
        
        return pages_data
    
    async def _upload_images(
        self,
        images: list[tuple[bytes, str]],
        page_num: int,
        user_id: str,
        thread_id: str,
        filename: str,
    ) -> list[str]:
        """
        Upload extracted images to S3.
        
        Args:
            images: List of (image_bytes, extension) tuples
            page_num: Page number for naming
            user_id: User identifier
            thread_id: Thread identifier
            filename: Original PDF filename for organizing images
            
        Returns:
            List of S3 keys for uploaded images
        """
        if not self.s3_ops or not images:
            return []
        
        image_keys = []
        base_name = filename.rsplit(".", 1)[0]
        
        for img_idx, (image_bytes, ext) in enumerate(images):
            image_filename = f"{base_name}_page{page_num}_img{img_idx}.{ext}"
            
            try:
                result = await self.s3_ops.upload_file(
                    file_data=image_bytes,
                    filename=image_filename,
                    user_id=user_id,
                    thread_id=thread_id,
                )
                image_keys.append(result["key"])
                print(f"Uploaded image: {result['key']}")
            except Exception as e:
                # Log error but continue with other images
                print(f"Failed to upload image {image_filename}: {e}")
                continue
        
        return image_keys
    
    def _chunk_text(self, text: str) -> list[str]:
        """
        Split text into chunks for LLM context.
        
        Args:
            text: Full page text
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []
        
        chunks = self.text_splitter.split_text(text)
        return chunks
    
    async def process_pdf(
        self,
        pdf_bytes: bytes,
        user_id: str,
        thread_id: str,
        filename: str,
    ) -> list[DocumentChunk]:
        """
        Process a PDF file, extracting text chunks and uploading images.
        
        Args:
            pdf_bytes: Raw PDF file content
            user_id: User identifier for S3 organization
            thread_id: Thread identifier for S3 organization
            filename: Original filename of the PDF
            
        Returns:
            List of DocumentChunk objects ready for database storage
        """
        # Extract pages in a thread to avoid blocking
        pages_data = await asyncio.to_thread(self._extract_pages, pdf_bytes)
        
        all_chunks = []
        
        for page_data in pages_data:
            # Upload images for this page
            print(f"[PDF Processor] Page {page_data.page_num}: {len(page_data.images)} images to upload")
            image_keys = await self._upload_images(
                images=page_data.images,
                page_num=page_data.page_num,
                user_id=user_id,
                thread_id=thread_id,
                filename=filename,
            )
            print(f"[PDF Processor] Page {page_data.page_num}: uploaded image_keys = {image_keys}")
            
            # Chunk the text
            text_chunks = self._chunk_text(page_data.text)
            
            if text_chunks:
                # Create DocumentChunk for each text chunk
                for chunk_idx, chunk_text in enumerate(text_chunks):
                    # Only attach image keys to the first chunk of each page
                    chunk_image_keys = image_keys if chunk_idx == 0 else []
                    
                    all_chunks.append(DocumentChunk(
                        page_num=page_data.page_num,
                        chunk_index=chunk_idx,
                        content=chunk_text,
                        image_keys=chunk_image_keys,
                    ))
            elif image_keys:
                # Page has images but no text - create a placeholder chunk
                all_chunks.append(DocumentChunk(
                    page_num=page_data.page_num,
                    chunk_index=0,
                    content=f"[Page {page_data.page_num + 1}: Contains {len(image_keys)} image(s)]",
                    image_keys=image_keys,
                ))
        
        return all_chunks


async def process_uploaded_file(
    s3_key: str,
    user_id: str,
    thread_id: str,
    filename: str,
) -> int:
    """
    Background task to process an uploaded PDF file.
    
    Downloads from S3, processes, and stores chunks in the database.
    
    Args:
        s3_key: S3 key of the uploaded file
        user_id: User identifier
        thread_id: Thread identifier
        filename: Original filename
        
    Returns:
        Number of chunks created
    """
    print(f"[PDF Processor] Starting processing for {filename}")
    
    # Import here to avoid circular imports
    try:
        from api.database import save_document_chunks
    except ImportError:
        from src.api.database import save_document_chunks
    
    try:
        s3_ops = S3Operations()
        
        # Download the PDF from S3
        print(f"[PDF Processor] Downloading {filename} from S3...")
        pdf_bytes = await s3_ops.download_file(filename, user_id, thread_id)
        print(f"[PDF Processor] Downloaded {len(pdf_bytes)} bytes")
        
        # Process the PDF
        processor = PDFProcessor(s3_ops=s3_ops)
        chunks = await processor.process_pdf(
            pdf_bytes=pdf_bytes,
            user_id=user_id,
            thread_id=thread_id,
            filename=filename,
        )
        print(f"[PDF Processor] Extracted {len(chunks)} chunks")
        
        # Save to database
        chunk_dicts = [chunk.to_dict() for chunk in chunks]
        saved_count = await save_document_chunks(
            thread_id=thread_id,
            user_id=user_id,
            filename=filename,
            chunks=chunk_dicts,
        )
        
        print(f"[PDF Processor] Saved {saved_count} chunks to database for {filename}")
        return saved_count
    except Exception as e:
        print(f"[PDF Processor] Error processing {filename}: {e}")
        import traceback
        traceback.print_exc()
        raise
