#!/bin/bash

# Development script to run both backend and frontend servers
# Usage: ./scripts/dev.sh

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Lumos Graph Development Servers${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down servers...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found. Make sure to create one with POSTGRES_URI and GOOGLE_MODEL${NC}"
fi

# Start backend server
echo -e "${GREEN}Starting Backend (FastAPI) on http://localhost:8000${NC}"
cd "$PROJECT_ROOT"
uvicorn src.api.main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start frontend server
echo -e "${GREEN}Starting Frontend (Next.js) on http://localhost:3000${NC}"
cd "$PROJECT_ROOT/frontend"

# Check if node_modules exists, if not install dependencies
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    npm install
fi

npm run dev &
FRONTEND_PID=$!

echo ""
echo -e "${BLUE}✨ Development servers are running!${NC}"
echo -e "   Backend API: ${GREEN}http://localhost:8000${NC}"
echo -e "   Frontend:    ${GREEN}http://localhost:3000${NC}"
echo -e "   API Docs:    ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
