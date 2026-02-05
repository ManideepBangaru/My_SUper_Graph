# Lumos Graph 🎮✨

A multi-agent architecture powered by **LangGraph** for intelligent gaming analytics. This system routes user queries to specialized agents using LLM-driven decision making, featuring a modern ChatGPT-style web interface.

---

## Overview

Lumos Graph is designed to enhance conversational AI capabilities for gaming analytics by implementing an intelligent routing system. Instead of hardcoded rules or regex patterns, queries are classified and routed using LLM-based structured outputs, enabling natural and context-aware interactions.

### Key Features

- **🧠 LLM-Powered Routing** — Intelligent query classification using structured outputs (no hardcoded patterns)
- **💬 ChatGPT-Style Interface** — Modern web UI with real-time streaming responses
- **🔄 Stateful Conversations** — Persistent conversation history with PostgreSQL-backed checkpointing
- **📡 Real-Time Streaming** — Server-Sent Events (SSE) for token-by-token response streaming
- **📝 Human-Readable Logs** — Queryable message history stored in PostgreSQL
- **⏪ Time Travel** — Replay and inspect conversation states via LangGraph checkpointing
- **🎯 Domain Gating** — Only gaming-related queries are processed; others receive a friendly rejection
- **📱 Responsive Design** — Mobile-friendly interface with collapsible sidebar

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│  ┌──────────────┐  ┌────────────────────────────────────────────┐  │
│  │   Sidebar    │  │              Chat Window                    │  │
│  │  - Threads   │  │  ┌────────────────────────────────────┐    │  │
│  │  - New Chat  │  │  │     Messages (Markdown)            │    │  │
│  │              │  │  │     - Streaming responses          │    │  │
│  │              │  │  └────────────────────────────────────┘    │  │
│  │              │  │  ┌────────────────────────────────────┐    │  │
│  │              │  │  │         Input Area                 │    │  │
│  └──────────────┘  │  └────────────────────────────────────┘    │  │
└────────────────────┴────────────────────────────────────────────────┘
                                    │
                                    │ SSE Stream
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Backend (FastAPI)                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   /api/chat      │  │  /api/threads    │  │   /api/health    │  │
│  │   (SSE Stream)   │  │  (CRUD)          │  │                  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────────┘  │
└───────────┼─────────────────────┼───────────────────────────────────┘
            │                     │
            ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LangGraph Engine                             │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐ │
│  │  Domain Identifier Agent    │───▶│      Convo Agent            │ │
│  │  (Gaming Classification)    │    │  (Gaming Responses)         │ │
│  └─────────────────────────────┘    └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                          ┌─────────────────┐
                          │   PostgreSQL    │
                          │  - Checkpoints  │
                          │  - Messages     │
                          │  - Threads      │
                          └─────────────────┘
```

### Current Agents

| Agent | Purpose |
|-------|---------|
| **DomainIdentifierAgent** | Classifies if query is gaming-related using structured LLM output |
| **ConvoAgent** | Responds to gaming queries conversationally with gaming terminology |

### Planned Data Sources

| Source | Type | Purpose |
|--------|------|---------|
| **Qdrant** | Vector DB | Semantic search over gaming metadata |
| **DuckDB** | OLAP | Fast analytical queries on game statistics |
| **Neo4j** | Graph DB | Relationship queries (players, teams, games) |
| **MCP Tools** | External | Extended capabilities via FastMCP servers |

---

## Tech Stack

### Backend
- **LangGraph** — Agent orchestration and state management
- **LangChain** — LLM abstractions and tool integrations
- **FastAPI** — High-performance REST API with SSE streaming
- **PostgreSQL** — Checkpoint storage, message history, and thread management
- **Pydantic** — Structured outputs and state validation
- **Python 3.11+** — Modern async/await patterns

### Frontend
- **Next.js 16** — React framework with App Router
- **Tailwind CSS** — Utility-first styling
- **React Markdown** — Rich markdown rendering with syntax highlighting
- **Lucide React** — Beautiful icon library
- **TypeScript** — Type-safe development

---

## Project Structure

```
Lumos_Graph/
├── src/
│   ├── api/                          # FastAPI Backend
│   │   ├── main.py                   # FastAPI app with CORS and routes
│   │   ├── database.py               # PostgreSQL utilities
│   │   └── routes/
│   │       ├── chat.py               # SSE streaming chat endpoint
│   │       └── threads.py            # Thread CRUD operations
│   ├── graphs/
│   │   └── graph.py                  # Main graph definition with routing
│   ├── nodes/
│   │   ├── ConvoNode.py              # Conversational response agent
│   │   └── DomainIdentifierNode.py   # Gaming query classifier
│   ├── schemas/
│   │   ├── ConvoAgentSchema.py       # Pydantic schema for convo output
│   │   └── DomainIdentiferAgentSchema.py  # Classification schema
│   ├── state/
│   │   └── state.py                  # MainGraphState with reducers
│   ├── utils/
│   │   ├── message_logger.py         # Human-readable PostgreSQL logging
│   │   └── read_yaml.py              # YAML configuration utilities
│   └── test.py                       # Standalone test runner
├── frontend/                         # Next.js Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx            # Root layout with fonts
│   │   │   ├── page.tsx              # Main chat page
│   │   │   └── globals.css           # Global styles and Tailwind
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx        # Main chat area with messages
│   │   │   ├── MessageBubble.tsx     # Message display with markdown
│   │   │   ├── InputArea.tsx         # Auto-resizing input with send
│   │   │   └── Sidebar.tsx           # Thread history sidebar
│   │   ├── hooks/
│   │   │   └── useChat.ts            # SSE streaming hook
│   │   └── lib/
│   │       └── api.ts                # API client functions
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── scripts/
│   ├── dev.sh                        # Run both servers concurrently
│   └── setup_db.sh                   # PostgreSQL setup script
├── prompts/
│   └── test_agent_config.yaml        # Agent system prompts
├── langgraph.json                    # LangGraph deployment config
├── pyproject.toml                    # Python dependencies
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL (running locally or remotely)
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Installation

1. **Clone the repository**
   ```bash
   cd Lumos_Graph
   ```

2. **Install backend dependencies**
   ```bash
   uv sync
   ```

3. **Install frontend dependencies**
   ```bash
   cd frontend && npm install && cd ..
   ```

4. **Set up PostgreSQL database**
   ```bash
   ./scripts/setup_db.sh
   ```

5. **Configure environment variables**
   
   Create a `.env` file in the project root:
   ```env
   GOOGLE_MODEL=your-google-model-name
   POSTGRES_URI=postgresql://user:password@localhost:5432/lumos_graph_db
   ```

### Running the Application

**Quick Start (Both Servers):**
```bash
./scripts/dev.sh
```

This starts:
- **Backend API**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

**Run Servers Separately:**

```bash
# Backend (from project root)
uvicorn src.api.main:app --reload --port 8000

# Frontend (from frontend/)
cd frontend && npm run dev
```

**With LangGraph Studio (Development):**
```bash
uv run langgraph dev
```
This starts the LangGraph Studio UI at `http://127.0.0.1:2024` with hot-reloading.

---

## API Reference

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send message and receive SSE stream |

**Request Body:**
```json
{
  "message": "Tell me about Elden Ring",
  "thread_id": "uuid-string",
  "user_id": "user_123"
}
```

**SSE Events:**
```
data: {"type": "token", "content": "Elden"}
data: {"type": "token", "content": " Ring"}
data: {"type": "token", "content": " is"}
...
data: {"type": "done"}
```

### Thread Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/threads?user_id=xxx` | List all threads for a user |
| `POST` | `/api/threads` | Create a new thread |
| `GET` | `/api/threads/{id}/messages` | Get messages for a thread |
| `PATCH` | `/api/threads/{id}` | Update thread title |
| `DELETE` | `/api/threads/{id}` | Delete thread and messages |

---

## How It Works

### Domain Classification

The system uses Pydantic models for structured LLM outputs:

```python
class DomainIdentiferAgentSchema(BaseModel):
    Gaming: bool = Field(..., description="Is the user's question related to Gaming?")
```

The LLM evaluates each query and returns a structured classification. Non-gaming queries receive a friendly rejection message.

### State Management

Conversation state is managed through a typed schema with custom reducers:

```python
from langgraph.graph import add_messages

def add_to_conversation(existing: List[str], new: List[str]) -> List[str]:
    """Reducer to accumulate conversation history strings."""
    return (existing or []) + (new or [])

class MainGraphState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]  # LangChain messages
    conversation_history: Annotated[List[str], add_to_conversation]  # String history
    Approval: Optional[bool]  # Gaming classification result
```

### Real-Time Streaming

The frontend uses Server-Sent Events (SSE) for real-time token streaming:

```typescript
// Frontend: useChat hook streams tokens
for await (const event of streamChat(message, threadId, userId)) {
  if (event.type === "token") {
    setMessages(prev => /* append token to last message */);
  }
}
```

```python
# Backend: FastAPI streams from LangGraph
async for event in graph.astream_events(input_state, config, version="v2"):
    if event.get("event") == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
```

### Conversation Continuity

When using the same `thread_id`, the full conversation is automatically restored:

```python
config = {"configurable": {"thread_id": "1", "user_id": "1"}}

# First message
await graph.ainvoke({"messages": [{"role": "user", "content": "Hi!"}]}, config)

# Continuing the same thread - previous messages are restored automatically
await graph.ainvoke({"messages": [{"role": "user", "content": "What about Elden Ring?"}]}, config)
```

---

## Development

### Running Tests

```bash
uv run python src/test.py
```

### Adding New Agents

1. **Define the schema** in `src/schemas/`
   ```python
   class NewAgentSchema(BaseModel):
       response: str = Field(..., description="Agent response")
   ```

2. **Create the node** in `src/nodes/`
   ```python
   async def NewAgent(state: MainGraphState, config: RunnableConfig):
       # Process state and return updates
       return {"messages": [AIMessage(content="...")]}
   ```

3. **Register in the graph** in `src/graphs/graph.py`
   ```python
   builder.add_node("NewAgent", NewAgent)
   builder.add_edge("ConvoAgent", "NewAgent")  # or conditional edges
   ```

---

## Roadmap

- [x] Domain classification gate (gaming vs non-gaming)
- [x] Conversational agent with gaming context
- [x] PostgreSQL message logging
- [x] Stateful conversation continuity
- [x] ChatGPT-style web interface (Next.js)
- [x] FastAPI backend with SSE streaming
- [x] Conversation history sidebar
- [x] Markdown rendering in responses
- [ ] Integrate Qdrant for semantic game search
- [ ] Add DuckDB for OLAP analytics queries
- [ ] Connect Neo4j for player/team relationship graphs
- [ ] Implement MCP skill servers with FastMCP
- [ ] Build specialized gaming analytics agents
- [ ] Dark/Light mode toggle
- [ ] User authentication

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Lumos Graph</strong> — Illuminating Gaming Insights with Intelligent Agents 💡
</p>
