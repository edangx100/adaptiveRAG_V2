"""
ChromaDB Retrieval Tool

This module provides functions to query ChromaDB collections for document retrieval.
Implements parallel retrieval across multiple collections.
"""

import os
import httpx
from typing import List, Dict, Any
from functools import lru_cache
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents

# Load environment variables
load_dotenv()

# Import configuration
from config import CHROMA_DB_PATH, COLLECTIONS, TOP_K

# Global variables for singleton instances
_client = None
_embedding_function = None


class JinaEmbeddingFunction(EmbeddingFunction):
    """
    Custom embedding function for ChromaDB using Jina Embeddings v3.

    This class implements ChromaDB's EmbeddingFunction interface to generate
    embeddings using the Jina AI API for query embeddings.
    """

    def __init__(self, api_key: str = None, model: str = "jina-embeddings-v3"):
        """
        Initialize the Jina embedding function.

        Args:
            api_key: Jina API key (defaults to JINA_API_KEY from environment)
            model: Jina model to use (default: jina-embeddings-v3)
        """
        self.api_key = api_key or os.getenv("JINA_API_KEY")
        self.model = model
        self.base_url = "https://api.jina.ai/v1/embeddings"
        self.embedding_dimension = 1024

        if not self.api_key:
            raise ValueError(
                "JINA_API_KEY not found. Please set it in your .env file."
            )

    def __call__(self, input: Documents) -> List[List[float]]:
        """
        Generate embeddings for a list of documents.

        Args:
            input: List of text documents to embed

        Returns:
            List of embedding vectors
        """
        return self._generate_embeddings_sync(input)

    def _generate_embeddings_sync(self, texts: List[str]) -> List[List[float]]:
        """
        Synchronously generate embeddings using Jina API.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "input": texts,
            "task": "retrieval.query"  # For query embeddings
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                embeddings = [item["embedding"] for item in result["data"]]

                return embeddings

        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            raise


@lru_cache(maxsize=1)
def get_chromadb_client():
    """
    Get or create singleton ChromaDB client.

    This function ensures only one ChromaDB client is created and reused
    across all requests, significantly improving performance by avoiding
    repeated initialization overhead.

    Returns:
        ChromaDB client instance (singleton)
    """
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=CHROMA_DB_PATH,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False
            )
        )
    return _client


@lru_cache(maxsize=1)
def get_embedding_function():
    """
    Get or create singleton Jina embedding function.

    This function ensures only one Jina embedding function is created and reused
    across all requests, avoiding repeated API connection establishment and
    authentication overhead.

    Returns:
        JinaEmbeddingFunction instance (singleton)
    """
    global _embedding_function
    if _embedding_function is None:
        _embedding_function = JinaEmbeddingFunction()
    return _embedding_function


def initialize_chromadb_client():
    """
    Initialize ChromaDB client with persistent storage.

    DEPRECATED: Use get_chromadb_client() instead.
    This function is kept for backwards compatibility.

    Returns:
        ChromaDB client instance
    """
    return get_chromadb_client()


def query_chromadb(query_text: str, top_k: int = TOP_K) -> List[Dict[str, Any]]:
    """
    Query ChromaDB collections in parallel and return relevant documents.

    This function implements parallel retrieval across all three collections
    (catalog, faq, troubleshooting) and returns top-k documents from each.

    Args:
        query_text: The query string to search for
        top_k: Number of documents to retrieve per collection (default: from config)

    Returns:
        List of dictionaries containing:
            - document: The document text
            - metadata: Document metadata (source, collection, row_index, etc.)
            - distance: Similarity distance (lower is more similar)
            - collection: Name of the collection this document came from

    Example:
        >>> results = query_chromadb("laptop for professionals", top_k=5)
        >>> print(f"Retrieved {len(results)} documents")
        >>> for result in results:
        ...     print(f"Collection: {result['collection']}")
        ...     print(f"Document: {result['document'][:100]}...")
        ...     print(f"Metadata: {result['metadata']}")
    """
    # Get singleton ChromaDB client
    client = get_chromadb_client()

    # Get singleton Jina embedding function
    jina_embedding_function = get_embedding_function()

    # Store all results
    all_results = []

    # Query each collection in parallel (simulated with sequential calls)
    for collection_name in COLLECTIONS:
        try:
            # Get collection with embedding function
            collection = client.get_collection(
                name=collection_name,
                embedding_function=jina_embedding_function
            )

            # Query the collection
            results = collection.query(
                query_texts=[query_text],
                n_results=top_k
            )

            # Process results from this collection
            for doc, metadata, distance in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                all_results.append({
                    'document': doc,
                    'metadata': metadata,
                    'distance': distance,
                    'collection': collection_name,
                    'similarity_score': 1 - distance  # Convert distance to similarity
                })

        except Exception as e:
            print(f"Error querying collection '{collection_name}': {e}")
            # Continue with other collections even if one fails

    return all_results


def query_specific_collections(
    query_text: str,
    collection_names: List[str],
    top_k: int = TOP_K
) -> List[Dict[str, Any]]:
    """
    Query specific ChromaDB collections and return relevant documents.

    This function allows querying a subset of collections instead of all.

    Args:
        query_text: The query string to search for
        collection_names: List of collection names to query
        top_k: Number of documents to retrieve per collection

    Returns:
        List of dictionaries with document, metadata, distance, and collection info
    """
    # Get singleton ChromaDB client
    client = get_chromadb_client()

    # Get singleton Jina embedding function
    jina_embedding_function = get_embedding_function()

    # Store all results
    all_results = []

    # Query each specified collection
    for collection_name in collection_names:
        if collection_name not in COLLECTIONS:
            print(f"Warning: Collection '{collection_name}' not found. Skipping.")
            continue

        try:
            # Get collection with embedding function
            collection = client.get_collection(
                name=collection_name,
                embedding_function=jina_embedding_function
            )

            # Query the collection
            results = collection.query(
                query_texts=[query_text],
                n_results=top_k
            )

            # Process results from this collection
            for doc, metadata, distance in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                all_results.append({
                    'document': doc,
                    'metadata': metadata,
                    'distance': distance,
                    'collection': collection_name,
                    'similarity_score': 1 - distance
                })

        except Exception as e:
            print(f"Error querying collection '{collection_name}': {e}")

    return all_results
