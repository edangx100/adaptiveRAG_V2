#!/bin/bash

# TechMart Adaptive RAG - Frontend Startup Script
# This script starts both the backend API server and the Next.js frontend

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   TechMart Adaptive RAG - Frontend Startup    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "orchestrator.py" ]; then
    echo -e "${RED}❌ Error: orchestrator.py not found${NC}"
    echo -e "${YELLOW}Please run this script from the project root directory${NC}"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Warning: Virtual environment not activated${NC}"
    echo -e "${YELLOW}Attempting to activate .venv...${NC}"
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}❌ Error: Virtual environment not found at .venv/${NC}"
        echo -e "${YELLOW}Please run: uv venv && source .venv/bin/activate${NC}"
        exit 1
    fi
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo -e "${YELLOW}Please create .env with required API keys${NC}"
    exit 1
fi

# Check if ChromaDB is indexed
if [ ! -d "chroma_db" ]; then
    echo -e "${YELLOW}⚠️  Warning: ChromaDB not found${NC}"
    echo -e "${YELLOW}Running setup_vectordb.py...${NC}"
    python setup_vectordb.py
    echo -e "${GREEN}✓ ChromaDB indexed${NC}"
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠️  Frontend dependencies not installed${NC}"
    echo -e "${YELLOW}Installing npm packages...${NC}"
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
fi

echo ""
echo -e "${GREEN}✓ All prerequisites checked${NC}"
echo ""
echo -e "${BLUE}Starting servers...${NC}"
echo ""

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $API_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✓ Servers stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start API server in background
echo -e "${BLUE}🚀 Starting FastAPI backend server...${NC}"
python api_server.py &
API_PID=$!

# Wait a bit for API to start
sleep 3

# Check if API server is running
if ! kill -0 $API_PID 2>/dev/null; then
    echo -e "${RED}❌ Error: API server failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}✓ API server running (PID: $API_PID)${NC}"
echo -e "${GREEN}  http://localhost:8000${NC}"
echo ""

# Start frontend in background
echo -e "${BLUE}🎨 Starting Next.js frontend server...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait a bit for frontend to start
sleep 5

# Check if frontend server is running
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Error: Frontend server failed to start${NC}"
    kill $API_PID 2>/dev/null || true
    exit 1
fi

echo -e "${GREEN}✓ Frontend server running (PID: $FRONTEND_PID)${NC}"
echo -e "${GREEN}  http://localhost:3000${NC}"
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         🎉 All systems operational! 🎉         ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}📍 Frontend:${NC} http://localhost:3000"
echo -e "${GREEN}📍 API:${NC}      http://localhost:8000"
echo -e "${GREEN}📚 API Docs:${NC} http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo ""

# Wait for user interrupt
wait
