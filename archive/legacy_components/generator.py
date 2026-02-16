"""
Answer Generation Component

This module provides functions to generate answers using Claude API.
Synthesizes answers from retrieved documents with fallback for no-context cases.
"""

import os
from typing import Dict, Any, List, Optional
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration and prompts
from config import GENERATION_MODEL
from prompts import subquery_answer_generation_prompt


def generate_answer(query: str, documents: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Generate an answer to a query using retrieved documents as context.

    This function synthesizes an answer from relevant documents. If no documents
    are provided, it generates a fallback response acknowledging the limitation.

    Args:
        query: The user's query string
        documents: Optional list of relevant document dictionaries from chromadb_tool.
                   Each should have 'document' key with text content and optional metadata.
                   If None or empty, will generate fallback response.

    Returns:
        Dictionary containing:
            - answer: The generated answer string
            - num_documents_used: Number of documents used for generation
            - has_context: Boolean indicating if documents were available
            - model_used: The model name used for generation

    Example:
        >>> from tools.chromadb_tool import query_chromadb
        >>> from components.grader import grade_documents, filter_relevant_documents
        >>>
        >>> # With relevant documents
        >>> docs = query_chromadb("gaming laptops", top_k=5)
        >>> graded = grade_documents("gaming laptops", docs)
        >>> relevant = filter_relevant_documents(graded)
        >>> result = generate_answer("gaming laptops", relevant)
        >>> print(result['answer'])
        >>>
        >>> # Without documents (fallback)
        >>> result = generate_answer("obscure query with no results", [])
        >>> print(result['answer'])
    """
    # Initialize Anthropic client
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Check if documents are provided and not empty
    has_context = documents is not None and len(documents) > 0

    # Build context from documents
    if has_context:
        # Extract document text and metadata
        context_parts = []
        for i, doc in enumerate(documents, 1):
            doc_text = doc.get('document', '')
            metadata = doc.get('metadata', {})
            source = metadata.get('source', 'Unknown')

            # Format each document with source information
            context_parts.append(f"[Document {i} from {source}]\n{doc_text}")

        context = "\n\n".join(context_parts)
    else:
        # No documents available - use empty context
        context = "No relevant documents were found in the knowledge base."

    # Format the generation prompt
    formatted_prompt = subquery_answer_generation_prompt.format(
        query=query,
        context=context
    )

    try:
        # Call Claude API for answer generation
        message = client.messages.create(
            model=GENERATION_MODEL,
            max_tokens=2000,
            temperature=0.3,  # Slightly creative but focused
            messages=[
                {"role": "user", "content": formatted_prompt}
            ]
        )

        # Extract the answer
        answer = message.content[0].text.strip()

        return {
            "answer": answer,
            "num_documents_used": len(documents) if documents else 0,
            "has_context": has_context,
            "model_used": GENERATION_MODEL
        }

    except Exception as e:
        print(f"Error generating answer: {e}")
        return {
            "answer": f"I apologize, but I encountered an error while generating an answer: {str(e)}",
            "num_documents_used": 0,
            "has_context": False,
            "model_used": GENERATION_MODEL
        }


def generate_answer_with_metadata(
    query: str,
    documents: Optional[List[Dict[str, Any]]] = None,
    include_sources: bool = True
) -> Dict[str, Any]:
    """
    Generate an answer with additional metadata about the generation process.

    This is an extended version of generate_answer that includes source citations
    and more detailed metadata about the documents used.

    Args:
        query: The user's query string
        documents: Optional list of relevant documents
        include_sources: Whether to include source information in the response

    Returns:
        Dictionary containing:
            - answer: The generated answer
            - num_documents_used: Number of documents used
            - has_context: Boolean indicating if documents were available
            - model_used: Model name used
            - sources: List of source identifiers (if include_sources=True)
            - collections_used: List of collection names used

    Example:
        >>> result = generate_answer_with_metadata("gaming laptops", relevant_docs)
        >>> print(f"Answer: {result['answer']}")
        >>> print(f"Sources: {', '.join(result['sources'])}")
        >>> print(f"Collections: {', '.join(result['collections_used'])}")
    """
    # Generate base answer
    result = generate_answer(query, documents)

    # Add additional metadata
    if documents and len(documents) > 0:
        # Extract unique sources
        sources = list(set(
            doc.get('metadata', {}).get('source', 'Unknown')
            for doc in documents
        ))

        # Extract unique collections
        collections = list(set(
            doc.get('metadata', {}).get('collection', 'Unknown')
            for doc in documents
        ))

        result['sources'] = sources if include_sources else []
        result['collections_used'] = collections
    else:
        result['sources'] = []
        result['collections_used'] = []

    return result
