# SuperFlow Graph

A multi-agent architecture powered by **LangGraph** for healthcare-focused patient condition and medication history analysis. This system routes clinician queries to specialized agents using LLM-driven decision making, featuring a modern ChatGPT-style web interface with document upload and visual comprehension capabilities.

---

## Overview

SuperFlow Graph is designed to enhance conversational AI capabilities for healthcare analysis by implementing an intelligent routing system. Instead of hardcoded rules or regex patterns, queries are classified and routed using LLM-based structured outputs, enabling natural and context-aware interactions. The system supports **multimodal conversations** with PDF and image documents, extracting both text and visuals for comprehensive clinical understanding.

### Key Features

- **LLM-Powered Routing** — Intelligent query classification using structured outputs (no hardcoded patterns)
- **ChatGPT-Style Interface** — Modern web UI with real-time streaming responses
- **Stateful Conversations** — Persistent conversation history with Supabase-backed checkpointing
- **Real-Time Streaming** — Server-Sent Events (SSE) for token-by-token response streaming
- **Human-Readable Logs** — Queryable message history stored in Supabase PostgreSQL
- **Time Travel** — Replay and inspect conversation states via LangGraph checkpointing
- **Domain Gating** — Only healthcare and medication-related queries are processed; others receive a friendly rejection
- **Responsive Design** — Mobile-friendly interface with collapsible sidebar
- **Document Processing** — PDF and image upload with automatic text extraction and chunking
- **Multimodal Understanding** — Images are passed to vision-capable LLMs (Gemini)
- **Supabase Storage** — File persistence for documents and image assets
- **Image Caching** — Extracted images cached in conversation state to avoid re-fetching

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
│  │  (Healthcare Classification)│    │  (Multimodal Responses)     │ │
│  └─────────────────────────────┘    │  - Text + Image Context     │ │
│                                     │  - Document Understanding   │ │
│                                     └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Supabase Postgres│    │ Supabase Storage│     │  Document       │
│  - Checkpoints  │     │  - PDF files    │     │  Processing     │
│  - Messages     │     │  - Images       │     │  - Text chunks  │
│  - Threads      │     │  - Attachments  │     │  - Image extract│
│  - Doc Chunks   │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Current Agents

| Agent | Purpose |
|-------|---------|
| **DomainIdentifierAgent** | Classifies if query is healthcare-related using structured LLM output |
| **ConvoAgent** | Responds to clinician queries with multimodal context (text + images from documents) |

### Document Processing Pipeline

| Stage | Description |
|-------|-------------|
| **Upload** | PDF/image files uploaded to Supabase Storage via `/api/files/upload` |
| **Processing** | Background task extracts text (chunked) and images |
| **Storage** | Text chunks stored in Supabase PostgreSQL, images in Supabase Storage |
| **Context** | Chunks loaded into conversation state for LLM context |
| **Multimodal** | Images converted to base64 and passed to vision LLM |

### Planned Data Sources

| Source | Type | Purpose |
|--------|------|---------|
| **Qdrant** | Vector DB | Semantic search over clinical and medication metadata |
| **DuckDB** | OLAP | Fast analytical queries on patient summaries |
| **Neo4j** | Graph DB | Relationship queries (patients, conditions, medications) |
| **MCP Tools** | External | Extended capabilities via FastMCP servers |

---

## Tech Stack

### Backend
- **LangGraph 1.0.9** — Agent orchestration and state management
- **LangChain 1.2.10** — LLM abstractions and tool integrations
- **FastAPI** — High-performance REST API with SSE streaming
- **Supabase** — PostgreSQL + Storage for checkpoints, messages, threads, chunks, and files
- **PyMuPDF** — PDF text and image extraction
- **Pillow** — Image processing for direct image uploads
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
SuperFlow_Graph/
├── src/
│   ├── api/                          # FastAPI Backend
│   │   ├── main.py                   # FastAPI app with CORS and routes
│   │   ├── database.py               # Supabase PostgreSQL utilities (threads, messages, doc_chunks)
│   │   └── routes/
│   │       ├── chat.py               # SSE streaming chat + fork endpoint
│   │       ├── files.py              # File upload/download to Supabase Storage
│   │       └── threads.py            # Thread CRUD operations
│   ├── graphs/
│   │   └── graph.py                  # Main graph definition with routing
│   ├── nodes/
│   │   ├── ConvoNode.py              # Multimodal clinical conversational agent
│   │   └── DomainIdentifierNode.py   # Healthcare query classifier
│   ├── schemas/
│   │   ├── ConvoAgentSchema.py       # Pydantic schema for convo output
│   │   └── DomainIdentiferAgentSchema.py  # Classification schema
│   ├── state/
│   │   └── state.py                  # MainGraphState with document_context and cached_images
│   ├── utils/
│   │   ├── message_logger.py         # Human-readable PostgreSQL logging
│   │   ├── pdf_processor.py          # PDF text/image extraction + chunking
│   │   ├── image_processor.py        # Direct image validation and preprocessing
│   │   ├── supabase_operations.py    # Supabase file upload/download operations
│   │   ├── image_utils.py            # Supabase image fetching + base64 conversion
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
│   └── setup_db.sh                   # Supabase SQL bootstrap helper
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
- Supabase project (PostgreSQL + Storage enabled)
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Installation

1. **Clone the repository**
   ```bash
   cd SuperFlow_Graph
   ```

2. **Install backend dependencies**
   ```bash
   uv sync
   ```

3. **Install frontend dependencies**
   ```bash
   cd frontend && npm install && cd ..
   ```

4. **Set up Supabase database schema**
   ```bash
   ./scripts/setup_db.sh
   ```

5. **Configure environment variables**
   
   Create a `.env` file in the project root:
   ```env
   # LLM Configuration
   GOOGLE_API_KEY=your-google-api-key
   GOOGLE_MODEL=google_genai:gemini-flash-lite-latest
   
   # Supabase Project Configuration
   SUPABASE_URL=https://your-project-ref.supabase.co
   SUPABASE_KEY=your-anon-key
   SUPABASE_SERVICE_KEY=your-service-role-key
   
   # Supabase Storage Configuration
   SUPABASE_STORAGE_BUCKET=superflow-documents
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
  "message": "Summarize this patient's medication history for hypertension",
  "thread_id": "uuid-string",
  "user_id": "doctor_123",
  "attachments": [
    {"filename": "patient_summary.pdf", "size": 12345, "storage_key": "..."}
  ]
}
```

**Fork Request Body:**
```json
{
  "message": "Now compare with the latest lab trends",
  "thread_id": "uuid-string",
  "user_id": "doctor_123",
  "checkpoint_id": "checkpoint-uuid",
  "attachments": []
}
```

**SSE Events:**
```
data: {"type": "progress", "content": {"Progress": "Document read completed ..."}}
data: {"type": "progress", "content": {"Progress": "Visually understanding the document ..."}}
data: {"type": "token", "content": "Patient"}
data: {"type": "token", "content": " history"}
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
| `POST` | `/api/files/upload` | Upload PDF/image files to Supabase Storage |
| `GET` | `/api/files/{user_id}/{thread_id}` | List files for a thread |
| `GET` | `/api/files/{user_id}/{thread_id}/{filename}` | Download a file |
| `GET` | `/api/files/{user_id}/{thread_id}/{filename}/url` | Get signed download URL |
| `GET` | `/api/files/{user_id}/{thread_id}/{filename}/status` | Check processing status |
| `DELETE` | `/api/files/{user_id}/{thread_id}/{filename}` | Delete file and chunks |

**Upload Request (multipart/form-data):**
```
files: [file1.pdf, xray_image.png]
user_id: "doctor_123"
thread_id: "uuid-string"
```

**Upload Response:**
```json
{
  "uploaded": [
    {"filename": "patient_summary.pdf", "key": "doctor_123/thread_id/patient_summary.pdf", "size": 12345}
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
    Healthcare: bool = Field(
        ...,
        description="Is the user's question related to healthcare, patient conditions, medication history, or medical analysis?"
    )
```

The LLM evaluates each query and returns a structured classification. Non-healthcare queries receive a friendly rejection message.

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
    document_context: Optional[List[dict]]  # Processed PDF/image chunks for context
    cached_images: Optional[dict]  # Cached base64 images keyed by "filename:page_num"
    Approval: Optional[bool]  # Healthcare classification result
```

### Document Context Flow

When a user uploads a PDF or image file:

1. **Upload**: File is stored in Supabase Storage under `{user_id}/{thread_id}/{filename}`
2. **Background Processing**: Extracts text (chunked with overlap) and images
3. **Storage**: Text chunks → Supabase PostgreSQL `document_chunks` table; Images → Supabase Storage
4. **Chat Request**: Chunks are loaded into `document_context` state
5. **Multimodal**: If chunks contain images, they're fetched from Supabase Storage and converted to base64
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
await graph.ainvoke({"messages": [{"role": "user", "content": "What changed in the medication timeline?"}]}, config)
```

### Multimodal Document Understanding

The ConvoAgent supports multimodal conversations when documents contain images:

```python
# When document_context contains chunks with image_keys:
if has_images and document_context:
    # Fetch images from Supabase Storage (or use cached)
    multimodal_content, images_to_cache = await _build_multimodal_context(
        document_context, supabase_ops, writer, cached_images
    )
    
    # Build message with interleaved text and images
    context_content = [
        {"type": "text", "text": MULTIMODAL_SYSTEM_PROMPT},
        {"type": "text", "text": "--- DOCUMENT CONTENT AND IMAGES ---"},
    ] + multimodal_content
    
    # Use vision-capable LLM (Gemini)
    response = await Convo_Agent_LLM_Multimodal.ainvoke(messages)
```

This enables doctors to ask questions about medical visuals, like "Describe this chest X-ray pattern" or "What trend is visible in this lab chart image?"

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

- [x] Domain classification gate (healthcare vs non-healthcare)
- [x] Conversational agent with clinical context
- [x] Supabase PostgreSQL message logging
- [x] Stateful conversation continuity
- [x] ChatGPT-style web interface (Next.js)
- [x] FastAPI backend with SSE streaming
- [x] Conversation history sidebar
- [x] Markdown rendering in responses
- [x] PDF document upload and processing
- [x] Direct medical image upload and processing
- [x] Supabase Storage integration
- [x] Multimodal conversations (text + images from documents)
- [x] Image extraction and base64 conversion for LLM
- [x] Image caching in conversation state
- [x] Time travel / fork from checkpoint
- [x] Progress streaming events during processing
- [x] Document chunks stored in Supabase PostgreSQL
- [x] File management API (upload, download, delete, status)

### In Progress

- [ ] Timeline panel UI for checkpoint navigation
- [ ] File attachment display in messages

### Planned

- [ ] Integrate Qdrant for semantic clinical search
- [ ] Add DuckDB for OLAP analytics queries
- [ ] Connect Neo4j for patient/condition/medication relationship graphs
- [ ] Implement MCP skill servers with FastMCP
- [ ] Build specialized healthcare analysis agents
- [ ] Dark/Light mode toggle
- [ ] User authentication
- [ ] Vector search over document content
- [ ] Patient history visualization workflows
- [ ] Medication interaction analysis
- [ ] Clinical decision support integration
- [ ] HIPAA compliance hardening checklist
- [ ] FHIR and HL7 interoperability connectors

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>SuperFlow Graph</strong> — Advancing Clinical Insights with Multimodal AI Agents
</p>
