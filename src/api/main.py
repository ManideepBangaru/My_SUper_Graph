"""
FastAPI application for Lumos Graph chat interface.
Provides REST API and SSE streaming for the LangGraph backend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.database import setup_tables
from src.api.routes import chat, files, threads


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup: ensure database tables exist
    await setup_tables()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Lumos Graph API",
    description="Chat API for Lumos Graph with streaming support",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(threads.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "lumos-graph-api"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Lumos Graph API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
