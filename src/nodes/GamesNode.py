try:
    from state.state import MainGraphState
    from schemas.ConvoAgentSchema import ConvoAgentSchema
    from utils.message_logger import MessageLogger
    from utils.read_yaml import read_yaml
except ImportError:
    from src.state.state import MainGraphState
    from src.schemas.ConvoAgentSchema import ConvoAgentSchema
    from src.utils.message_logger import MessageLogger
    from src.utils.read_yaml import read_yaml

import asyncio
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage
from langchain.chat_models import init_chat_model
from langgraph.config import get_stream_writer

# Load config from YAML
_config = read_yaml("prompts/games_node.yaml")
_model_cfg = _config["model"]

SYSTEM_PROMPT = _config["system_prompt"]

_llm = init_chat_model(
    model=_model_cfg["name"],
    temperature=_model_cfg.get("temperature", 0.7),
)
_llm_structured = _llm.with_structured_output(ConvoAgentSchema)

message_logger = MessageLogger()


async def GamesAgent(state: MainGraphState, config: RunnableConfig):
    """
    Responds to gaming-related queries.
    All configuration is loaded from prompts/games_node.yaml.
    """
    writer = get_stream_writer()
    writer({"Progress": "Games Agent at Work ..."})
    await asyncio.sleep(2)

    user_id = config["configurable"]["user_id"]
    thread_id = config["configurable"]["thread_id"]

    writer({"Progress": "Generating response ..."})
    response = await _llm_structured.ainvoke(
        [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    )
    ai_response_content = response.Convo

    await message_logger.log_message(
        thread_id=thread_id,
        user_id=user_id,
        role="ai",
        content=ai_response_content,
    )

    return {
        "messages": [AIMessage(content=ai_response_content)],
        "conversation_history": [ai_response_content],
    }
