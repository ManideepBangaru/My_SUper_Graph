try:
    from state.state import MainGraphState
    from schemas.GateAgentSchema import GateAgentSchema
    from utils.message_logger import MessageLogger
    from utils.read_yaml import read_yaml
except ImportError:
    from src.state.state import MainGraphState
    from src.schemas.GateAgentSchema import GateAgentSchema
    from src.utils.message_logger import MessageLogger
    from src.utils.read_yaml import read_yaml

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage
from langchain.chat_models import init_chat_model
from langgraph.config import get_stream_writer

# Load config from YAML
_config = read_yaml("prompts/gate_node.yaml")
_model_cfg = _config["model"]

SYSTEM_PROMPT = _config["system_prompt"]
REJECTION_MESSAGE = _config["rejection_message"]

_llm = init_chat_model(
    model=_model_cfg["name"],
    temperature=_model_cfg.get("temperature", 0.0),
)
_llm_structured = _llm.with_structured_output(GateAgentSchema)

message_logger = MessageLogger()


async def GateAgent(state: MainGraphState, config: RunnableConfig):
    """
    Classifies user queries into 'games', 'movies', or 'none'.
    Rejects out-of-domain queries with a friendly message.
    All configuration is loaded from prompts/gate_node.yaml.
    """
    writer = get_stream_writer()
    writer({"Progress": "Domain check initiated ..."})

    user_id = config["configurable"]["user_id"]
    thread_id = config["configurable"]["thread_id"]

    response = await _llm_structured.ainvoke(
        [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    )

    domain = response.domain
    writer({"Progress": f"Domain detected: {domain}"})

    if domain == "none":
        await message_logger.log_message(
            thread_id=thread_id,
            user_id=user_id,
            role="ai",
            content=REJECTION_MESSAGE,
        )
        return {
            "domain": "none",
            "messages": [AIMessage(content=REJECTION_MESSAGE)],
            "conversation_history": [REJECTION_MESSAGE],
        }

    writer({"Progress": f"Routing to {domain} agent 🚀"})
    return {"domain": domain}
