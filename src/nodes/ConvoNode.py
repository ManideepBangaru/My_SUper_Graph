import os
from dotenv import load_dotenv
import asyncio

# Support both LangGraph Studio (relative imports) and FastAPI server (src-prefixed imports)
try:
    from state.state import MainGraphState
    from schemas.ConvoAgentSchema import ConvoAgentSchema
    from utils.message_logger import MessageLogger
    from utils.image_utils import fetch_images_for_chunks
    from utils.s3_operations import S3Operations
except ImportError:
    from src.state.state import MainGraphState
    from src.schemas.ConvoAgentSchema import ConvoAgentSchema
    from src.utils.message_logger import MessageLogger
    from src.utils.image_utils import fetch_images_for_chunks
    from src.utils.s3_operations import S3Operations

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, HumanMessage
from langchain.chat_models import init_chat_model
from langgraph.config import get_stream_writer

load_dotenv()

# Initialize the LLM - one with structured output, one for multimodal
Convo_Agent_LLM = init_chat_model(model=os.getenv("GOOGLE_MODEL"))
Convo_Agent_LLM_w_Structured_Output = Convo_Agent_LLM.with_structured_output(ConvoAgentSchema)
# Multimodal LLM without structured output (structured output may not work with images)
Convo_Agent_LLM_Multimodal = init_chat_model(model=os.getenv("GOOGLE_MODEL"))

# Initialize the message logger for human-readable message storage
message_logger = MessageLogger()

# Maximum images to include in context
MAX_IMAGES_IN_CONTEXT = 10

BASE_SYSTEM_PROMPT = """
You are a helpful assistant. Respond to the user's message politely and helpfully 
using gaming terms wherever appropriate.
You are a helpful gaming assistant. Always format your responses using proper markdown:

- Use ## headings for main sections
- Use numbered lists (1., 2., 3.) for sequential information
- Use bullet points (-) for features or items
- Add blank lines between sections for readability
- Use **bold** for emphasis on key terms
- Keep paragraphs concise and well-structured

Respond using gaming terminology where appropriate and ensure all responses are well-formatted and easy to read.
"""

DOCUMENT_CONTEXT_PROMPT = """

---
DOCUMENT CONTEXT:
The following content has been extracted from documents uploaded by the user. Use this information to answer their questions accurately. Reference specific pages when relevant.

{document_context}
---
"""

MULTIMODAL_SYSTEM_PROMPT = """You are a helpful assistant. Respond to the user's message politely and helpfully using gaming terms wherever appropriate.

You have access to document content and images from PDF files uploaded by the user. When the user asks about images (e.g., "describe the image on page 1"), refer to the images provided in the context. Each image is labeled with its page number."""


def _build_document_context(document_chunks: list[dict] | None) -> str:
    """
    Build a formatted document context string from chunks.
    
    Groups chunks by filename and page for better readability.
    """
    if not document_chunks:
        return ""
    
    # Group chunks by filename and page
    context_parts = []
    current_file = None
    
    for chunk in document_chunks:
        filename = chunk.get("filename", "Unknown")
        page_num = chunk.get("page_num", 0)
        content = chunk.get("content", "")
        image_keys = chunk.get("image_keys", [])
        
        # Add file header if switching files
        if filename != current_file:
            context_parts.append(f"\n[FILE: {filename}]")
            current_file = filename
        
        # Add page and content
        page_header = f"[Page {page_num + 1}]"
        if image_keys:
            page_header += f" (contains {len(image_keys)} image(s))"
        
        context_parts.append(f"{page_header}\n{content}")
    
    return "\n\n".join(context_parts)


def _has_images(document_chunks: list[dict] | None) -> bool:
    """Check if any chunks have images."""
    if not document_chunks:
        return False
    return any(chunk.get("image_keys") for chunk in document_chunks)


async def _build_multimodal_context(
    document_chunks: list[dict],
    s3_ops: S3Operations,
    writer,
    cached_images: dict | None = None,
) -> tuple[list[dict], dict]:
    """
    Build multimodal context with text and images organized by page.
    
    Args:
        document_chunks: List of document chunks with text and image_keys
        s3_ops: S3Operations instance for fetching images
        writer: Stream writer for progress updates
        cached_images: Optional dict of already-fetched images (keyed by page_key)
    
    Returns:
        Tuple of (content_parts for LLM, page_images dict for caching)
    """
    # Use cached images if available, otherwise fetch from S3
    if cached_images:
        writer({"Progress": "Using cached images ..."})
        page_images = cached_images
    else:
        writer({"Progress": "Fetching images ..."})
        page_images = await fetch_images_for_chunks(
            document_chunks, 
            s3_ops, 
            max_total_images=MAX_IMAGES_IN_CONTEXT
        )
        writer({"Progress": "Images fetched and will be cached ..."})
    
    # Keep a copy for caching (since we delete keys during iteration)
    images_to_cache = {k: v for k, v in page_images.items()}
    
    content_parts = []
    current_file = None
    
    writer({"Progress": "Building multimodal context ..."})
    # Group chunks by file and page for organization
    for chunk in document_chunks:
        filename = chunk.get("filename", "Unknown")
        page_num = chunk.get("page_num", 0)
        text_content = chunk.get("content", "")
        
        # Add file header if switching files
        if filename != current_file:
            content_parts.append({
                "type": "text",
                "text": f"\n--- Document: {filename} ---\n"
            })
            current_file = filename
        
        # Add page header and text
        content_parts.append({
            "type": "text",
            "text": f"[Page {page_num + 1}]\n{text_content}"
        })
        # Add images for this page (only for first chunk of each page)
        page_key = f"{filename}:{page_num}"
        if page_key in page_images:
            images = page_images[page_key]
            for i, img in enumerate(images):
                # Add image label
                content_parts.append({
                    "type": "text",
                    "text": f"[Image {i + 1} of {len(images)} on Page {page_num + 1}]"
                })
                # Add the image
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img["base64_url"]}
                })
            # Remove from dict so we don't add again for other chunks of same page
            del page_images[page_key]
    writer({"Progress": "Multimodal context built ..."})
    await asyncio.sleep(1)
    return content_parts, images_to_cache


async def ConvoAgent(state: MainGraphState, config: RunnableConfig):
    """
    Responds to user queries in a conversational manner.
    Logs both user messages and AI responses to a human-readable table.
    Adds AI response to both messages (for checkpointing) and conversation_history.
    Incorporates document context and images when available.
    Caches images in state to avoid re-fetching from S3 on follow-up messages.
    """
    writer = get_stream_writer()
    writer({"Progress": "ConvoAgent initiated ..."})
    
    user_id = config["configurable"]["user_id"]
    thread_id = config["configurable"]["thread_id"]
    
    # Get the last message (user input)
    last_message = state["messages"][-1]
    
    # Note: User message is logged in chat.py with attachments
    # We only log the AI response here to avoid duplicates

    document_context = state.get("document_context")
    cached_images = state.get("cached_images")  # Get cached images from state
    writer({"Progress": "Document read completed ..."})
    has_images = _has_images(document_context)
    writer({"Progress": "Visually understanding the document ..."})
    
    # Track images to cache (will be populated if we fetch from S3)
    images_to_cache = cached_images  # Default to existing cache
    
    if has_images and document_context:
        # Use multimodal approach with images
        print("[ConvoNode] Using multimodal mode with images")
        if cached_images:
            print("[ConvoNode] Using cached images")
        
        try:
            s3_ops = S3Operations()
            
            # Build multimodal content with images (uses cache if available)
            multimodal_content, images_to_cache = await _build_multimodal_context(
                document_context, s3_ops, writer, cached_images
            )
            writer({"Progress": "Multimodal context built ..."})
            # Create the context message with system prompt and document content
            context_content = [
                {"type": "text", "text": MULTIMODAL_SYSTEM_PROMPT},
                {"type": "text", "text": "\n\n--- DOCUMENT CONTENT AND IMAGES ---\n"},
            ] + multimodal_content
            
            # Build messages for multimodal LLM
            # Use HumanMessage with multimodal content for the context
            messages = [
                HumanMessage(content=context_content),
                AIMessage(content="I've reviewed the document content and images. How can I help you with this material?"),
            ]
            
            # Add conversation history (text only for previous messages)
            for msg in state["messages"]:
                if hasattr(msg, 'content'):
                    messages.append(msg)
            
            # Use multimodal LLM (without structured output)
            response = await Convo_Agent_LLM_Multimodal.ainvoke(messages)
            ai_response_content = response.content
            
        except Exception as e:
            print(f"[ConvoNode] Multimodal failed, falling back to text-only: {e}")
            # Fallback to text-only mode
            has_images = False
    
    if not has_images:
        # Use text-only approach with structured output
        writer({"Progress": "Using text-only approach ..."})
        system_prompt = BASE_SYSTEM_PROMPT

        if document_context:
            writer({"Progress": "Building document context ..."})
            formatted_context = _build_document_context(document_context)
            writer({"Progress": "Document context built ..."})
            if formatted_context:
                system_prompt += DOCUMENT_CONTEXT_PROMPT.format(
                    document_context=formatted_context
                )

        # Generate the response with structured output
        writer({"Progress": "Generating response ..."})
        response = await Convo_Agent_LLM_w_Structured_Output.ainvoke(
            [{"role": "system", "content": system_prompt}] + state["messages"]
        )
        writer({"Progress": "Response generated ..."})
        ai_response_content = response.Convo
    
    # Log the AI response to human-readable table
    await message_logger.log_message(
        thread_id=thread_id,
        user_id=user_id,
        role="ai",
        content=ai_response_content
    )
    
    # Create AIMessage to add to messages state for checkpointing
    ai_message = AIMessage(content=ai_response_content)
    
    # Return state update including cached images for persistence
    result = {
        "messages": [ai_message],  # Added to messages via add_messages reducer
        "conversation_history": [ai_response_content],  # Must be a list for reducer
    }
    
    # Only include cached_images if we have images to cache
    if images_to_cache:
        result["cached_images"] = images_to_cache
    
    return result