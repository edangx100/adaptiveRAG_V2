"""
TechMart Adaptive RAG System Configuration

This module contains all configuration constants for the adaptive RAG system.
"""

import os

# Retry Logic Configuration
RETRY_LIMIT = 2  # Maximum number of query rewrite attempts

# Retrieval Configuration
TOP_K = 5  # Number of documents to retrieve per collection

# ChromaDB Configuration
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "chroma_db/")  # ChromaDB persistent storage location

# Available Collections
COLLECTIONS = [
    "catalog",
    "faq",
    "troubleshooting"
]

# Anthropic Model Configuration
# Task-specific models for each component
ROUTING_MODEL = "claude-haiku-4-5-20251001"      # Model for query routing decisions
GRADING_MODEL = "claude-haiku-4-5-20251001"      # Model for document relevance grading
REWRITE_MODEL = "claude-haiku-4-5-20251001"      # Model for query rewriting
GENERATION_MODEL = "claude-haiku-4-5-20251001"    # Model for answer generation

# Available models: "claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929", "claude-opus-4-5-20251101"

# API Configuration (loaded from .env)
# Required environment variables:
# - JINA_API_KEY: Jina Embeddings v3 API key
# - EXA_API_KEY: Exa AI search API key
# - ANTHROPIC_API_KEY: Claude API key
