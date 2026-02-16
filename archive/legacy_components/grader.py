"""
Document Grading Component

This module provides functions to grade document relevance using Claude API.
Implements binary relevance scoring (yes/no) with reasoning using structured outputs.

References:
https://platform.claude.com/docs/en/build-with-claude/structured-outputs
https://claude.com/blog/structured-outputs-on-the-claude-developer-platform
"""

import os
import json
from typing import Dict, Any
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration and prompts
from config import GRADING_MODEL
from prompts import grading_prompt


def grade_document(query: str, document: str) -> Dict[str, Any]:
    """
    Grade the relevance of a document to a query using Claude API with structured outputs.

    This function evaluates whether a document contains information that helps
    answer the query, returning a binary yes/no decision with reasoning.

    Args:
        query: The user's query string
        document: The document text to evaluate

    Returns:
        Dictionary containing:
            - relevant: Boolean (True for "yes", False for "no")
            - reasoning: String explaining the grading decision
            - raw_response: The full JSON response from Claude

    Example:
        >>> result = grade_document(
        ...     "What gaming laptops do you have?",
        ...     "TechBook Pro 15 | Gaming laptop with RTX 4060..."
        ... )
        >>> print(f"Relevant: {result['relevant']}")
        >>> print(f"Reasoning: {result['reasoning']}")
    """
    # Initialize Anthropic client
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Format the grading prompt with query and document
    formatted_prompt = grading_prompt.format(
        query=query,
        document=document
    )

    # Define JSON schema for structured output
    GRADING_SCHEMA = {
        "type": "object",
        "properties": {
            "relevant": {
                "type": "boolean",
                "description": "True if the document is relevant to the query, False otherwise"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation for the grading decision"
            }
        },
        "required": ["relevant", "reasoning"],
        "additionalProperties": False
    }

    try:
        # Call Claude API for grading with structured outputs
        message = client.beta.messages.create(
            model=GRADING_MODEL,
            max_tokens=500,
            temperature=0,  # Use temperature 0 for consistent grading
            betas=["structured-outputs-2025-11-13"],
            output_format={
                "type": "json_schema",
                "schema": GRADING_SCHEMA
            },
            messages=[
                {"role": "user", "content": formatted_prompt}
            ]
        )

        # Extract and parse JSON response
        response_text = message.content[0].text.strip()
        grading_result = json.loads(response_text)

        return {
            "relevant": grading_result["relevant"],
            "reasoning": grading_result["reasoning"],
            "raw_response": response_text
        }

    except Exception as e:
        print(f"Error grading document: {e}")
        return {
            "relevant": False,
            "reasoning": f"Error during grading: {str(e)}",
            "raw_response": ""
        }


def grade_documents(query: str, documents: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Grade multiple documents for relevance to a query.

    This function takes a list of documents (as returned by chromadb_tool)
    and grades each one, adding grading results to the document metadata.

    Args:
        query: The user's query string
        documents: List of document dictionaries from chromadb_tool.query_chromadb()
                   Each should have 'document' key with text content

    Returns:
        List of documents with added grading information:
            - grading_result: Dictionary with relevant, reasoning, raw_response

    Example:
        >>> from tools.chromadb_tool import query_chromadb
        >>> docs = query_chromadb("gaming laptops", top_k=3)
        >>> graded_docs = grade_documents("gaming laptops", docs)
        >>> relevant_docs = [d for d in graded_docs if d['grading_result']['relevant']]
    """
    graded_documents = []

    for doc in documents:
        # Extract document text
        doc_text = doc.get('document', '')

        # Grade the document
        grading_result = grade_document(query, doc_text)

        # Add grading result to document
        doc_with_grading = doc.copy()
        doc_with_grading['grading_result'] = grading_result

        graded_documents.append(doc_with_grading)

    return graded_documents


def filter_relevant_documents(graded_documents: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Filter documents to only include those graded as relevant.

    Args:
        graded_documents: List of documents with grading_result from grade_documents()

    Returns:
        List containing only relevant documents

    Example:
        >>> graded_docs = grade_documents("gaming laptops", all_docs)
        >>> relevant_only = filter_relevant_documents(graded_docs)
        >>> print(f"Found {len(relevant_only)} relevant documents")
    """
    return [
        doc for doc in graded_documents
        if doc.get('grading_result', {}).get('relevant', False)
    ]
