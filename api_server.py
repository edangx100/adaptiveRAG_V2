"""
FastAPI server for TechMart Adaptive RAG
Connects the Next.js frontend to the Python orchestrator backend
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from typing import Optional, List, Dict, Any
import sys
import os

# Add parent directory to path to import orchestrator
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from orchestrator import run_adaptive_rag

app = FastAPI(
    title="TechMart Adaptive RAG API",
    description="API for adaptive retrieval-augmented generation system",
    version="1.0.0"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        os.getenv("FRONTEND_URL", "")  # Production Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize ChromaDB on application startup"""
    import subprocess
    import time

    print("=" * 60)
    print("Initializing ChromaDB on startup...")
    print("=" * 60)

    try:
        # Check if ChromaDB exists
        chroma_path = os.getenv("CHROMA_DB_PATH", "chroma_db/")
        if not os.path.exists(chroma_path) or not os.listdir(chroma_path):
            print(f"ChromaDB not found at {chroma_path}. Building from CSV files...")

            # Run setup_vectordb.py
            result = subprocess.run(
                ["python", "setup_vectordb.py"],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                print("✓ ChromaDB initialized successfully!")
                print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            else:
                print(f"✗ ChromaDB initialization failed: {result.stderr}")
        else:
            print(f"✓ ChromaDB already exists at {chroma_path}")

    except Exception as e:
        print(f"Error during ChromaDB initialization: {e}")
        print("Application will continue, but queries may fail.")

    print("=" * 60)


class QueryRequest(BaseModel):
    """Request model for query endpoint"""
    query: str
    retry_limit: Optional[int] = 2


class QueryResponse(BaseModel):
    """Response model for query endpoint"""
    answer: str
    sources: List[str]
    metadata: Dict[str, Any]
    collections_used: List[str]
    route: str
    num_retries: int
    relevant_docs_count: int
    processing_time: float
    formatted_citations: List[str]
    retry_history: Optional[List[Dict[str, Any]]] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "TechMart Adaptive RAG API",
        "version": "1.0.0"
    }


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Process a customer query through the adaptive RAG pipeline

    Args:
        request: QueryRequest containing the query and optional retry_limit

    Returns:
        QueryResponse with answer, sources, metadata, and citations
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Run the adaptive RAG orchestrator
        result = await run_adaptive_rag(
            query=request.query,
            retry_limit=request.retry_limit
        )

        # Transform orchestrator response to match API contract
        response = {
            "answer": result["answer"],
            "sources": result["metadata"].get("sources", []),
            "metadata": result["metadata"],
            "collections_used": result["metadata"].get("collections_used", []),
            "route": result["routing_decision"]["route"],
            "num_retries": result["num_retries"],
            "relevant_docs_count": result["num_graded_relevant"],
            "processing_time": result["execution_time"],
            "formatted_citations": result["metadata"].get("formatted_citations", []),
            "retry_history": result.get("retry_history", [])
        }

        return response

    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"Error processing query: {str(e)}")
        print("Full traceback:")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )


@app.get("/api/health")
async def health():
    """Detailed health check with component status"""
    try:
        # Test that we can import required components
        from agents.query_agent import QueryAgent
        from agents.retrieval_agent import RetrievalAgent
        from agents.grader_agent import GraderAgent
        from agents.generator_agent import GeneratorAgent

        return {
            "status": "healthy",
            "components": {
                "orchestrator": "ok",
                "query_agent": "ok",
                "retrieval_agent": "ok",
                "grader_agent": "ok",
                "generator_agent": "ok"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting TechMart Adaptive RAG API server...")
    print("API will be available at: http://localhost:8000")
    print("API docs available at: http://localhost:8000/docs")
    print("Next.js frontend should run on: http://localhost:3000")
    print("\n⚡ Make sure your .env file has all required API keys!")

    port = int(os.getenv("PORT", 8000))  # Railway assigns PORT dynamically
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # No reload in production
        log_level="info"
    )
