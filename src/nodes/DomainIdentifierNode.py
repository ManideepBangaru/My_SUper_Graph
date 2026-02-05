import os
from dotenv import load_dotenv

# Support both LangGraph Studio (relative imports) and FastAPI server (src-prefixed imports)
try:
    from state.state import MainGraphState
    from schemas.DomainIdentiferAgentSchema import DomainIdentiferAgentSchema
    from utils.message_logger import MessageLogger
except ImportError:
    from src.state.state import MainGraphState
    from src.schemas.DomainIdentiferAgentSchema import DomainIdentiferAgentSchema
    from src.utils.message_logger import MessageLogger

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage
from langchain.chat_models import init_chat_model
from langgraph.config import get_stream_writer

load_dotenv()

# Initialize the LLM with structured output for domain classification
Domain_Identifier_Gate = init_chat_model(model=os.getenv("GOOGLE_MODEL"))
Domain_Identifier_Gate_structured_output = Domain_Identifier_Gate.with_structured_output(DomainIdentiferAgentSchema)

# Initialize the message logger for human-readable message storage
message_logger = MessageLogger()

BASE_SYSTEM_PROMPT = "You are a helpful assistant. Classify whether the user's query is related to Gaming."

DOCUMENT_CONTEXT_PROMPT = """

The user has uploaded the following documents. Consider the document content when determining if the query is gaming-related. If the user is asking about content from these documents and the documents are gaming-related, classify the query as gaming-related.

DOCUMENT CONTEXT:
{document_context}
"""

# Rejection message for non-gaming queries
REJECTION_MESSAGE = "I'm sorry, but I can only help with gaming-related queries. Please ask me about video games, gaming strategies, game lore, or anything related to gaming!"


def _build_document_context_summary(document_chunks: list[dict] | None) -> str:
    """
    Build a summarized document context for domain classification.
    
    Uses a condensed format to keep token usage low while providing enough context.
    """
    if not document_chunks:
        return ""
    
    # Group by filename and take first chunk from each page for summary
    seen_pages = set()
    context_parts = []
    current_file = None
    
    for chunk in document_chunks:
        filename = chunk.get("filename", "Unknown")
        page_num = chunk.get("page_num", 0)
        content = chunk.get("content", "")
        
        # Only take first chunk per page to keep it concise
        page_key = f"{filename}:{page_num}"
        if page_key in seen_pages:
            continue
        seen_pages.add(page_key)
        
        # Add file header if switching files
        if filename != current_file:
            context_parts.append(f"\n[FILE: {filename}]")
            current_file = filename
        
        # Truncate content for summary (first 300 chars)
        truncated = content[:300] + "..." if len(content) > 300 else content
        context_parts.append(f"[Page {page_num + 1}] {truncated}")
    
    return "\n".join(context_parts)


async def DomainIdentifierAgent(state: MainGraphState, config: RunnableConfig):
    """
    Classifies user queries to determine if they are gaming-related.
    Logs both user messages and AI responses to a human-readable table.
    Returns rejection message for non-gaming queries.
    Considers document context when available for classification.
    """
    writer = get_stream_writer()
    writer({"Progress": "Domain Check initiated ..."})

    user_id = config["configurable"]["user_id"]
    thread_id = config["configurable"]["thread_id"]
    
    # Get the last message (user input)
    last_message = state["messages"][-1]
    
    # # Log the user message to human-readable table
    # await message_logger.log_message(
    #     thread_id=thread_id,
    #     user_id=user_id,
    #     role=last_message.type,
    #     content=last_message.content,
    #     message_id=getattr(last_message, 'id', None)
    # )

    # Build system prompt with document context if available
    system_prompt = BASE_SYSTEM_PROMPT
    document_context = state.get("document_context")
    
    if document_context:
        formatted_context = _build_document_context_summary(document_context)
        if formatted_context:
            system_prompt += DOCUMENT_CONTEXT_PROMPT.format(
                document_context=formatted_context
            )

    # Classify the query
    response = await Domain_Identifier_Gate_structured_output.ainvoke(
        [{"role": "system", "content": system_prompt}] + state["messages"]
    )
    
    is_gaming_query = response.Gaming
    
    writer({"Progress": "Domain Check completed ..."})
    
    # If not a gaming query, return rejection message
    if not is_gaming_query:
        # Log the rejection message
        await message_logger.log_message(
            thread_id=thread_id,
            user_id=user_id,
            role="ai",
            content=REJECTION_MESSAGE
        )
        
        # Create AIMessage for rejection
        rejection_ai_message = AIMessage(content=REJECTION_MESSAGE)
        
        return {
            "Approval": False,
            "messages": [rejection_ai_message],
            "conversation_history": [REJECTION_MESSAGE]
        }
    
    # Log that it's a gaming query (no response message needed, ConvoAgent will handle it)
    # ai_response_content = f"Gaming query: {is_gaming_query}"
    # await message_logger.log_message(
    #     thread_id=thread_id,
    #     user_id=user_id,
    #     role="ai",
    #     content=ai_response_content
    # )
    writer({"Progress": "Approved Query 🚀"})
    return {"Approval": True}
