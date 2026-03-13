# Super Graph 🎮✨

A multi-agent architecture powered by **LangGraph** for intelligent gaming analytics with multimodal document understanding. This system routes user queries to specialized agents using LLM-driven decision making, featuring a modern ChatGPT-style web interface with document upload and visual comprehension capabilities.

---

## Overview

Super Graph is designed to enhance conversational AI capabilities for gaming analytics by implementing an intelligent routing system. Instead of hardcoded rules or regex patterns, queries are classified and routed using LLM-based structured outputs, enabling natural and context-aware interactions. The system now supports **multimodal conversations** with PDF and PowerPoint documents, extracting both text and images for comprehensive document understanding.

### Key Features

- **🧠 LLM-Powered Routing** — Intelligent query classification using structured outputs (no hardcoded patterns)
- **💬 ChatGPT-Style Interface** — Modern web UI with real-time streaming responses
- **🔄 Stateful Conversations** — Persistent conversation history with PostgreSQL-backed checkpointing
- **📡 Real-Time Streaming** — Server-Sent Events (SSE) for token-by-token response streaming
- **📝 Human-Readable Logs** — Queryable message history stored in PostgreSQL
- **⏪ Time Travel** — Replay and inspect conversation states via LangGraph checkpointing
- **🎯 Domain Gating** — Only gaming-related queries are processed; others receive a friendly rejection
- **📱 Responsive Design** — Mobile-friendly interface with collapsible sidebar
- **📄 Document Processing** — PDF and PPTX file upload with automatic text extraction and chunking
- **🖼️ Multimodal Understanding** — Images extracted from documents are passed to vision-capable LLMs (Gemini)
- **☁️ S3 File Storage** — AWS S3 integration with SSO authentication for file persistence
- **🔄 Image Caching** — Extracted images cached in conversation state to avoid re-fetching

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│  ┌──────────────┐  ┌────────────────────────────────────────────┐  │
│  │   Sidebar    │  │              Chat Window                    │  │
│  │  - Threads   │  │  ┌────────────────────────────────────┐    │  │
│  │  - New Chat  │  │  │     Messages (Markdown)            │    │  │
│  │  - Timeline  │  │  │     - Streaming responses          │    │  │
│  │              │  │  │     - File attachments             │    │  │
│  │              │  │  └────────────────────────────────────┘    │  │
│  │              │  │  ┌────────────────────────────────────┐    │  │
│  │              │  │  │   Input Area + File Upload         │    │  │
│  └──────────────┘  │  └────────────────────────────────────┘    │  │
└────────────────────┴────────────────────────────────────────────────┘
                                    │
                                    │ SSE Stream
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Backend (FastAPI)                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   /api/chat      │  │  /api/threads    │  │   /api/files     │  │
│  │   /api/chat/fork │  │  (CRUD)          │  │   (Upload/DL)    │  │
│  │   (SSE Stream)   │  │                  │  │                  │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
└───────────┼─────────────────────┼─────────────────────┼─────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LangGraph Engine                             │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐ │
│  │  Domain Identifier Agent    │───▶│      Convo Agent            │ │
│  │  (Gaming Classification)    │    │  (Multimodal Responses)     │ │
│  └─────────────────────────────┘    │  - Text + Image Context     │ │
│                                     │  - Document Understanding   │ │
│                                     └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   PostgreSQL    │     │     AWS S3      │     │  Document       │
│  - Checkpoints  │     │  - PDF/PPTX     │     │  Processing     │
│  - Messages     │     │  - Images       │     │  - Text chunks  │
│  - Threads      │     │  - Attachments  │     │  - Image extract│
│  - Doc Chunks   │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Current Agents

| Agent | Purpose |
|-------|---------|
| **DomainIdentifierAgent** | Classifies if query is gaming-related using structured LLM output |
| **ConvoAgent** | Responds to queries with multimodal context (text + images from documents) |

### Document Processing Pipeline

| Stage | Description |
|-------|-------------|
| **Upload** | PDF/PPTX files uploaded to S3 via `/api/files/upload` |
| **Processing** | Background task extracts text (chunked) and images |
| **Storage** | Text chunks stored in PostgreSQL, images in S3 |
| **Context** | Chunks loaded into conversation state for LLM context |
| **Multimodal** | Images converted to base64 and passed to vision LLM |

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
- **PostgreSQL** — Checkpoint storage, message history, thread management, and document chunks
- **AWS S3** — File storage with SSO authentication (boto3)
- **PyMuPDF** — PDF text and image extraction
- **python-pptx** — PowerPoint text and image extraction
- **Pydantic** — Structured outputs and state validation
- **Python 3.11+** — Modern async/await patterns
- **Google Gemini** — Vision-capable LLM for multimodal understanding

### Frontend
- **Next.js 16** — React framework with App Router
- **Tailwind CSS** — Utility-first styling
- **React Markdown** — Rich markdown rendering with syntax highlighting
- **Lucide React** — Beautiful icon library
- **TypeScript** — Type-safe development

---

## Project Structure

```
Super_Graph/
├── src/
│   ├── api/                          # FastAPI Backend
│   │   ├── main.py                   # FastAPI app with CORS and routes
│   │   ├── database.py               # PostgreSQL utilities (threads, messages, doc_chunks)
│   │   └── routes/
│   │       ├── chat.py               # SSE streaming chat + fork endpoint
│   │       ├── files.py              # File upload/download to S3
│   │       └── threads.py            # Thread CRUD operations
│   ├── graphs/
│   │   └── graph.py                  # Main graph definition with routing
│   ├── nodes/
│   │   ├── ConvoNode.py              # Multimodal conversational agent
│   │   └── DomainIdentifierNode.py   # Gaming query classifier
│   ├── schemas/
│   │   ├── ConvoAgentSchema.py       # Pydantic schema for convo output
│   │   └── DomainIdentiferAgentSchema.py  # Classification schema
│   ├── state/
│   │   └── state.py                  # MainGraphState with document_context & cached_images
│   ├── utils/
│   │   ├── message_logger.py         # Human-readable PostgreSQL logging
│   │   ├── pdf_processor.py          # PDF text/image extraction + chunking
│   │   ├── pptx_processor.py         # PPTX text/image extraction + chunking
│   │   ├── s3_operations.py          # AWS S3 file upload/download with SSO
│   │   ├── image_utils.py            # S3 image fetching + base64 conversion
│   │   └── read_yaml.py              # YAML configuration utilities
│   └── main.py                       # Standalone test runner
├── frontend/                         # Next.js Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx            # Root layout with fonts
│   │   │   ├── page.tsx              # Main chat page
│   │   │   └── globals.css           # Global styles and Tailwind
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx        # Main chat area with messages
│   │   │   ├── MessageBubble.tsx     # Message display with markdown
│   │   │   ├── InputArea.tsx         # Auto-resizing input with file upload
│   │   │   ├── Sidebar.tsx           # Thread history sidebar
│   │   │   └── TimelinePanel.tsx     # Time travel / checkpoint navigation
│   │   ├── hooks/
│   │   │   └── useChat.ts            # SSE streaming hook with progress events
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
   cd Super_Graph
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
   # LLM Configuration
   GOOGLE_API_KEY=your-google-api-key
   GOOGLE_MODEL=google_genai:gemini-flash-lite-latest
   
   # PostgreSQL Database
   POSTGRES_URI=postgresql://user:password@localhost:5432/super_graph_db
   
   # AWS S3 Configuration (for file storage)
   AWS_PROFILE=your-sso-profile          # AWS SSO profile name
   S3_BUCKET_NAME=your-bucket-name       # S3 bucket for file storage
   S3_PREFIX=Super-graph                 # Optional prefix for S3 keys
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
| `POST` | `/api/chat/fork` | Fork from a checkpoint (time travel) and continue |

**Chat Request Body:**
```json
{
  "message": "Tell me about Elden Ring",
  "thread_id": "uuid-string",
  "user_id": "user_123",
  "attachments": [
    {"filename": "guide.pdf", "size": 12345, "s3_key": "..."}
  ]
}
```

**Fork Request Body:**
```json
{
  "message": "Actually, tell me about Dark Souls instead",
  "thread_id": "uuid-string",
  "user_id": "user_123",
  "checkpoint_id": "checkpoint-uuid",
  "attachments": []
}
```

**SSE Events:**
```
data: {"type": "progress", "content": {"Progress": "Document read completed ..."}}
data: {"type": "progress", "content": {"Progress": "Visually understanding the document ..."}}
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

### File Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/files/upload` | Upload PDF/PPTX files to S3 |
| `GET` | `/api/files/{user_id}/{thread_id}` | List files for a thread |
| `GET` | `/api/files/{user_id}/{thread_id}/{filename}` | Download a file |
| `GET` | `/api/files/{user_id}/{thread_id}/{filename}/url` | Get presigned download URL |
| `GET` | `/api/files/{user_id}/{thread_id}/{filename}/status` | Check processing status |
| `DELETE` | `/api/files/{user_id}/{thread_id}/{filename}` | Delete file and chunks |

**Upload Request (multipart/form-data):**
```
files: [file1.pdf, file2.pptx]
user_id: "user_123"
thread_id: "uuid-string"
```

**Upload Response:**
```json
{
  "uploaded": [
    {"filename": "guide.pdf", "key": "prefix/user_123/thread_id/guide.pdf", "size": 12345}
  ],
  "success_count": 1,
  "error_count": 0,
  "processing_triggered": 1
}
```

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
    document_context: Optional[List[dict]]  # Processed PDF/PPTX chunks for context
    cached_images: Optional[dict]  # Cached base64 images keyed by "filename:page_num"
    Approval: Optional[bool]  # Gaming classification result
```

### Document Context Flow

When a user uploads a PDF or PPTX file:

1. **Upload**: File is stored in S3 under `{prefix}/{user_id}/{thread_id}/{filename}`
2. **Background Processing**: Extracts text (chunked with overlap) and images
3. **Storage**: Text chunks → PostgreSQL `document_chunks` table; Images → S3
4. **Chat Request**: Chunks are loaded into `document_context` state
5. **Multimodal**: If chunks contain images, they're fetched from S3 and converted to base64
6. **Caching**: Images are stored in `cached_images` state to avoid re-fetching

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

### Multimodal Document Understanding

The ConvoAgent supports multimodal conversations when documents contain images:

```python
# When document_context contains chunks with image_keys:
if has_images and document_context:
    # Fetch images from S3 (or use cached)
    multimodal_content, images_to_cache = await _build_multimodal_context(
        document_context, s3_ops, writer, cached_images
    )
    
    # Build message with interleaved text and images
    context_content = [
        {"type": "text", "text": MULTIMODAL_SYSTEM_PROMPT},
        {"type": "text", "text": "--- DOCUMENT CONTENT AND IMAGES ---"},
    ] + multimodal_content
    
    # Use vision-capable LLM (Gemini)
    response = await Convo_Agent_LLM_Multimodal.ainvoke(messages)
```

This enables users to ask questions about images in PDFs, like "Describe the diagram on page 3" or "What does the chart on slide 5 show?"

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

### Completed

- [x] Domain classification gate (gaming vs non-gaming)
- [x] Conversational agent with gaming context
- [x] PostgreSQL message logging
- [x] Stateful conversation continuity
- [x] ChatGPT-style web interface (Next.js)
- [x] FastAPI backend with SSE streaming
- [x] Conversation history sidebar
- [x] Markdown rendering in responses
- [x] PDF document upload and processing
- [x] PPTX (PowerPoint) document upload and processing
- [x] AWS S3 file storage integration
- [x] Multimodal conversations (text + images from documents)
- [x] Image extraction and base64 conversion for LLM
- [x] Image caching in conversation state
- [x] Time travel / fork from checkpoint
- [x] Progress streaming events during processing
- [x] Document chunks stored in PostgreSQL
- [x] File management API (upload, download, delete, status)

### In Progress

- [ ] Timeline panel UI for checkpoint navigation
- [ ] File attachment display in messages

### Planned

- [ ] Integrate Qdrant for semantic game search
- [ ] Add DuckDB for OLAP analytics queries
- [ ] Connect Neo4j for player/team relationship graphs
- [ ] Implement MCP skill servers with FastMCP
- [ ] Build specialized gaming analytics agents
- [ ] Dark/Light mode toggle
- [ ] User authentication
- [ ] Vector search over document content

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Super Graph</strong> — Illuminating Gaming Insights with Multimodal AI Agents 💡
</p>
